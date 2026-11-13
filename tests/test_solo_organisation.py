"""Paramètres › « Organisation : seul ou en équipe » (lot 1 ergonomie, B, T521 ; js/modules/parametres-solo.js ;
ARCHITECTURE.md §22.11).

    - « Passer en équipe » : mode_solo = 0, rien d'autre ne change (OT, technicien « moi »), les écrans d'équipe
      reviennent, une fenêtre dit quoi faire ensuite ;
    - « Revenir en Solo » refusé avec deux techniciens actifs (message qui les nomme, lien Équipe) ; accepté quand il
      n'en reste qu'un : les OT ouverts sans technicien ou au nom d'un technicien inactif passent à son nom après
      confirmation ;
    - mode comptes : refus quand un autre compte technicien ou responsable est actif, à l'écran et au serveur (PUT de
      parametres.csv qui passe mode_solo à 1 : 400, rien d'écrit) ; droits de parametres inchangés.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_solo_organisation.py" -v
"""
import csv
import io
import json
import re
import ssl
import unittest
import urllib.request
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

LIGNE_PRISE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}\|(TEC-\d{4})\|")


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def parametre(dossier, cle):
    valeur = next((l["valeur"] for l in lire_csv(dossier, "parametres.csv") if l["cle"] == cle), "")
    return valeur[1:] if valeur.startswith("'") else valeur          # apostrophe de protection (« '1 »)


class CasOrganisation(CasNavigateur):

    def ouvrir(self, serveur, route):
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)

    def poser_solo(self, moi="TEC-0001"):
        self.page.evaluate("""moi => Donnees.modifier('parametres', (lignes) => {
            const poser = (cle, valeur) => { const l = lignes.find((x) => x.cle === cle);
              if (l) l.valeur = valeur; else lignes.push({ cle, valeur }); };
            poser('mode_solo', '1'); poser('solo_technicien_id', moi); poser('cloture_une_etape', '1');
        })""", moi)

    def garder_un_seul_technicien(self, moi):
        self.page.evaluate("""moi => Donnees.modifier('techniciens', (lignes) => {
            lignes.forEach((t) => { if (t.id !== moi) t.actif = '0'; }); })""", moi)

    def aller(self, route, selecteur):
        self.page.evaluate("r => { location.hash = r; }", route)
        self.page.wait_for_selector(selecteur)


class TestSansComptes(CasOrganisation):

    def test_passer_en_equipe_puis_revenir_en_solo(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", nom="Julien")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/parametres")
            self.poser_solo()
            page.reload()
            attendre_pret(page)
            self.aller("#/parametres", "#carte-solo")
            page.evaluate("Solo.convertirDemandes()")       # celles de l'ouverture faites (file de l'onglet)
            carte = page.inner_text("#carte-solo")
            self.assertIn("Organisation : seul ou en équipe", carte)
            self.assertIn("Seul (mode Solo)", carte)
            self.assertEqual(page.get_attribute("#solo-ma-fiche", "href"), "#/equipe/TEC-0001")
            self.assertEqual(page.get_attribute("#solo-acces", "href"), "#/equipe/acces")
            ordres_avant = {o["id"]: o["technicien_id"] for o in lire_csv(serveur.dossier, "ordres_travail.csv")}
            techniciens_avant = (serveur.dossier / "techniciens.csv").read_bytes()

            # Passer en équipe : mode_solo = 0, rien d'autre ; la fenêtre « ensuite » et ses liens
            page.click("#btn-passer-equipe")
            page.wait_for_selector("#solo-ensuite")
            self.assertEqual(page.locator('#solo-ensuite a[href="#/equipe/nouveau"]').count(), 1)
            self.assertEqual(page.locator('#solo-ensuite a[href="#/equipe/acces"]').count(), 1)
            self.assertEqual(parametre(serveur.dossier, "mode_solo"), "0")
            self.assertEqual(parametre(serveur.dossier, "solo_technicien_id"), "TEC-0001")
            self.assertEqual({o["id"]: o["technicien_id"] for o in lire_csv(serveur.dossier, "ordres_travail.csv")},
                             ordres_avant)
            self.assertEqual((serveur.dossier / "techniciens.csv").read_bytes(), techniciens_avant)
            page.click('#solo-ensuite a[href="#/equipe/nouveau"]')
            page.wait_for_function("location.hash === '#/equipe/nouveau'")
            self.assertEqual(page.locator("dialog[open]").count(), 0)
            menu = page.evaluate("[...document.querySelectorAll('#menu > a')].map(a => a.dataset.ecran)")
            self.assertIn("equipe", menu)
            self.assertIn("planning", menu)

            # Revenir en Solo : refusé tant que plusieurs techniciens sont actifs (ils sont nommés), rien d'écrit
            self.aller("#/parametres", "#btn-passer-solo")
            page.click("#btn-passer-solo")
            page.wait_for_selector("#solo-refus:not([hidden])")
            refus = page.inner_text("#solo-refus")
            self.assertIn("Retour en Solo impossible", refus)
            actifs = [t for t in lire_csv(serveur.dossier, "techniciens.csv") if t["actif"] != "0"]
            self.assertGreater(len(actifs), 1)
            self.assertIn(actifs[0]["prenom"], refus)
            self.assertEqual(page.locator('#solo-refus a[href="#/equipe"]').count(), 1)
            self.assertEqual(parametre(serveur.dossier, "mode_solo"), "0")

            # Un seul technicien actif : les OT ouverts des techniciens partis (ou sans technicien) passent à lui
            self.garder_un_seul_technicien("TEC-0002")
            ouverts_autres = [o["id"] for o in lire_csv(serveur.dossier, "ordres_travail.csv")
                              if o["statut"] not in ("Clôturé techniquement", "Clôturé administrativement", "Annulé")
                              and o["technicien_id"] != "TEC-0002"]
            self.assertTrue(ouverts_autres)
            self.aller("#/parametres", "#btn-passer-solo")
            page.click("#btn-passer-solo")
            page.wait_for_selector("#solo-confirmation")
            self.assertIn(ouverts_autres[0], page.inner_text("#solo-confirmation"))
            page.click("dialog[open] .btn-primaire")
            page.wait_for_function("App.modeSolo()")
            self.assertEqual(parametre(serveur.dossier, "mode_solo"), "1")
            self.assertEqual(parametre(serveur.dossier, "solo_technicien_id"), "TEC-0002")
            ordres = {o["id"]: o for o in lire_csv(serveur.dossier, "ordres_travail.csv")}
            for ot_id in ouverts_autres:
                with self.subTest(ot=ot_id):
                    self.assertEqual(ordres[ot_id]["technicien_id"], "TEC-0002")
                    self.assertEqual(LIGNE_PRISE.findall(ordres[ot_id]["prises_en_charge"])[-1], "TEC-0002")
            # Les OT clôturés gardent leur technicien
            for ot_id, technicien in ordres_avant.items():
                if ordres[ot_id]["statut"] in ("Clôturé techniquement", "Clôturé administrativement", "Annulé"):
                    self.assertEqual(ordres[ot_id]["technicien_id"], technicien, ot_id)


class TestAvecComptes(CasOrganisation):

    def test_autre_compte_actif_refus_ecran_et_serveur(self):
        page = self.page
        with ServeurPrevo(comptes=True) as serveur:
            serveur.poser_session(self.contexte, "responsable")
            self.ouvrir(serveur, "#/parametres")
            self.garder_un_seul_technicien("TEC-0001")
            # Écran : le compte technicien julien.moreau (actif) empêche le retour en Solo
            self.aller("#/parametres", "#btn-passer-solo")
            page.click("#btn-passer-solo")
            page.wait_for_selector("#solo-refus:not([hidden])")
            refus = page.inner_text("#solo-refus")
            self.assertIn("Julien Moreau", refus)
            self.assertEqual(page.locator('#solo-refus a[href="#/equipe/acces"]').count(), 1)
            self.assertNotEqual(parametre(serveur.dossier, "mode_solo"), "1")
            # Serveur : la même écriture faite directement est refusée (400), rien d'écrit
            self.autoriser_erreur("400 (Bad Request)")
            message = page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
                const l = lignes.find((x) => x.cle === 'mode_solo');
                if (l) l.valeur = '1'; else lignes.push({ cle: 'mode_solo', valeur: '1' }); })
                .then(() => 'écrit', (e) => String(e && e.message))""")
            self.assertIn("julien.moreau", message)
            self.assertNotEqual(parametre(serveur.dossier, "mode_solo"), "1")
            # Toute autre écriture de parametres par le responsable reste permise (droit inchangé)
            page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
                const l = lignes.find((x) => x.cle === 'entreprise_nom');
                if (l) l.valeur = 'Atelier T521'; else lignes.push({ cle: 'entreprise_nom', valeur: 'Atelier T521' }); })""")
            self.assertEqual(parametre(serveur.dossier, "entreprise_nom"), "Atelier T521")

    def test_droits_de_parametres_inchanges(self):
        with ServeurPrevo(comptes=True) as serveur:
            cookie = serveur.session("technicien")
            requete = urllib.request.Request(serveur.url + "/api/csv/parametres", data=b"cle;valeur\r\nmode_solo;1\r\n",
                                             method="PUT", headers={"X-Prevo": "1", "Cookie": cookie,
                                                                    "X-Version-Attendue": "*",
                                                                    "Content-Type": "text/csv; charset=utf-8"})
            try:
                urllib.request.urlopen(requete, timeout=10)
                statut = 200
            except urllib.error.HTTPError as erreur:
                statut = erreur.code
            self.assertEqual(statut, 403)


if __name__ == "__main__":
    unittest.main()
