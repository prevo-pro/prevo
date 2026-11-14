"""« Je prends » une demande (lot 2 ergonomie, L17, T537 ; ARCHITECTURE.md §14.2, « Qui accepte une demande »).

Familles :
    reglage    : Paramètres, section « Demandes d'intervention », « Qui peut accepter une demande » (deux libellés,
                 valeurs stockées « techniciens » / « responsable ») ; Demandes.techniciensAcceptent : vrai sans la
                 ligne (base existante sans réglage), faux pour « responsable » seulement ;
    parcours   : mode serveur avec comptes ; le technicien (julien.moreau, TEC-0001) voit la demande « Nouvelle » dans
                 « À prendre » (nombre dans le titre), « Je prends » : la demande est acceptée, l'OT créé à son nom
                 (ligne de prise datée de la création), la fiche de l'OT s'ouvre ; le responsable voit sur son accueil
                 « Demandes prises par les techniciens » ; réglage « responsable » : plus de demande dans « À prendre »,
                 ni de « Je prends » sur la fiche de la demande, et Demandes.prendre est refusé.
Le serveur (droits, les deux réglages) : tests/test_acceptation_demandes.py.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_prendre_demande.py" -v
"""
import csv
import io
import re
import time
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret

MOI = "TEC-0001"


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


class CasPrendre(CasNavigateur):

    def ouvrir(self, serveur, role, route="#/accueil"):
        serveur.poser_session(self.contexte, role)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def changer_de_role(self, serveur, role, route="#/accueil"):
        """Contexte neuf (le profil posé avant chargement ne se retire pas d'un contexte), session de ce rôle."""
        self.contexte.close()
        self.contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.contexte.set_default_timeout(self.DELAI_PAR_DEFAUT_MS)
        self.page = self.contexte.new_page()
        self.surveiller(self.page)
        self.ouvrir(serveur, role, route)

    def regler(self, valeur):
        """Le réglage écrit comme Paramètres l'écrit (profil responsable)."""
        self.page.evaluate("""v => Donnees.modifier('parametres', (lignes) => {
            const ligne = lignes.find((l) => l.cle === 'acceptation_demandes');
            if (ligne) ligne.valeur = v; else lignes.push({ cle: 'acceptation_demandes', valeur: v }); })""", valeur)

    def attendre(self, condition, delai_s=10):
        fin = time.time() + delai_s
        while not condition() and time.time() < fin:
            time.sleep(0.2)
        return condition()


class TestReglage(CasPrendre):

    def test_parametres_deux_libelles_et_accesseur(self):
        with ServeurPrevo(comptes=True) as serveur:
            self.ouvrir(serveur, "responsable", "#/parametres")
            self.page.wait_for_selector("#form-parametres select[name=acceptation_demandes]")
            options = self.page.eval_on_selector_all("#form-parametres select[name=acceptation_demandes] option",
                                                     "os => os.map((o) => [o.value, o.textContent.trim()])")
            self.assertEqual(options, [["techniciens", "Le responsable et les techniciens"],
                                       ["responsable", "Le responsable seulement"]])
            self.assertEqual(self.page.input_value("#form-parametres select[name=acceptation_demandes]"), "techniciens")
            self.assertTrue(self.page.evaluate("Demandes.techniciensAcceptent()"))      # ligne absente : par défaut
            self.page.select_option("#form-parametres select[name=acceptation_demandes]", "responsable")
            self.page.click("#form-parametres button[type=submit]")
            self.assertTrue(self.attendre(lambda: any(l["cle"] == "acceptation_demandes" and l["valeur"] == "responsable"
                                                      for l in lire_csv(serveur.dossier, "parametres.csv"))))
            self.assertFalse(self.page.evaluate("Demandes.techniciensAcceptent()"))


class TestParcours(CasPrendre):

    def test_le_technicien_prend_la_demande_le_responsable_le_voit(self):
        with ServeurPrevo(comptes=True) as serveur:
            demande = next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["statut"] == "Nouvelle")
            nouvelles = sum(1 for d in lire_csv(serveur.dossier, "demandes.csv") if d["statut"] == "Nouvelle")
            self.ouvrir(serveur, "technicien")
            carte = "#contenu .accueil-a-prendre"
            self.page.wait_for_selector(carte + " button[data-action=prendre-demande][data-di='%s']" % demande["id"])
            titre = self.page.inner_text(carte + " h2")
            nombre = int(re.match(r"^À prendre \((\d+)\)$", titre).group(1))
            self.assertGreaterEqual(nombre, nouvelles)
            self.assertEqual(self.page.locator(carte + " .accueil-demande-a-prendre a[href='#/di/%s']" % demande["id"]).count(), 1)

            self.page.click(carte + " button[data-action=prendre-demande][data-di='%s']" % demande["id"])
            self.page.wait_for_function("() => /^#\\/ot\\/OT-/.test(location.hash)")
            ligne = None
            for _ in range(50):
                ligne = next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["id"] == demande["id"])
                if ligne["statut"] == "Acceptée":
                    break
                time.sleep(0.2)
            self.assertEqual(ligne["statut"], "Acceptée")
            ot = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ligne["ot_id"])
            self.assertEqual((ot["di_id"], ot["technicien_id"]), (demande["id"], MOI))
            self.assertEqual(ot["prises_en_charge"], ot["date_creation"][:16] + "|" + MOI + "|")
            self.assertIn(ligne["ot_id"], self.page.url)
            journal = [j for j in lire_csv(serveur.dossier, "journal.csv") if demande["id"] in j["action"]]
            self.assertTrue(any("par le technicien " + MOI in j["action"] and j["profil"].startswith("Technicien")
                                for j in journal), journal)

            # Le responsable : la ligne discrète de son accueil
            self.changer_de_role(serveur, "responsable")
            self.page.wait_for_selector("#contenu .accueil-prises-techniciens")
            texte = self.page.inner_text("#contenu .accueil-prises-techniciens")
            self.assertIn("Julien a pris " + demande["id"], texte)
            self.assertEqual(self.page.get_attribute("#contenu .accueil-prises-techniciens a", "href"), "#/ot/" + ligne["ot_id"])

    def test_reglage_responsable_seul_rien_a_prendre(self):
        with ServeurPrevo(comptes=True) as serveur:
            demande = next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["statut"] == "Nouvelle")
            self.ouvrir(serveur, "responsable", "#/parametres")
            self.regler("responsable")
            self.changer_de_role(serveur, "technicien")
            self.page.wait_for_selector("#contenu .accueil-a-prendre")
            self.assertEqual(self.page.locator("#contenu .accueil-a-prendre [data-action=prendre-demande]").count(), 0)
            self.page.evaluate("id => { location.hash = '#/di/' + id; }", demande["id"])
            self.page.wait_for_selector(".di-suivi")
            self.assertEqual(self.page.locator(".di-prise, .di-panneau-decision").count(), 0)
            erreur = self.page.evaluate("id => Demandes.prendre(id, 'TEC-0001').then(() => '', (e) => e.message)", demande["id"])
            self.assertIn("réservé l'acceptation", erreur)
            self.assertEqual(next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["id"] == demande["id"])["statut"],
                             "Nouvelle")

    def test_fiche_de_la_demande_je_prends(self):
        with ServeurPrevo(comptes=True) as serveur:
            demande = next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["statut"] == "Nouvelle")
            self.ouvrir(serveur, "technicien", "#/di/" + demande["id"])
            self.page.wait_for_selector(".di-prise [data-action=prendre-demande]")
            self.page.click(".di-prise [data-action=prendre-demande]")
            self.page.wait_for_function("() => /^#\\/ot\\/OT-/.test(location.hash)")
            self.page.wait_for_selector(".ot-fiche .ot-numero")


if __name__ == "__main__":
    unittest.main()
