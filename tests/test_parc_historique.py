"""Historique de la machine sur sa fiche (lot 2 ergonomie, décision L28 ; js/modules/parc-fiche.js).

Ce qui est vérifié, sur PO-02 (EQ-0005) de la démo (file://, rien n'est écrit) :
    - chaque ligne d'OT dit le technicien (prénom et nom), le temps passé (somme de ot_temps) et, pour une panne,
      la cause et le remède en clair (libellés de codes_defaillance) ; aucun montant (le temps n'est pas un coût) ;
    - filtre « Pannes / Préventif / Tout » : « Tout » choisi d'abord, chaque bouton garde les seuls OT de son genre ;
    - téléphone 375 px : bouton « Historique » en haut de la fiche (48 px), qui fait venir l'historique à l'écran ;
      les cartes disent le technicien et le temps passé ; aucun défilement horizontal ;
    - demandeur : ni technicien ni temps passé (D126 : il ne lit ni l'un ni l'autre en mode serveur).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_parc_historique.py" -v
"""
import csv
import io
import re
import unittest

from commun import CasNavigateur, DOSSIER_DEMO, attendre_pret, duree_fr, url_fichier

EQUIPEMENT = "EQ-0005"                       # PO-02, pompe de la démo : pannes de garniture et préventif
CORRECTIFS = ("correctif immédiat", "correctif différé")
PREVENTIFS = ("préventif systématique", "préventif conditionnel", "réglementaire")
ESPACES = re.compile(r"[\s  ]+")


def lire(nom):
    texte = (DOSSIER_DEMO / nom).read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


def simple(texte):
    return ESPACES.sub(" ", texte).strip()


def heures_fr(valeur):
    """2.75 → « 2 h 45 » (UI.heures, L21 : à la minute)."""
    return duree_fr(valeur)


class TestHistoriqueMachine(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ordres = [o for o in lire("ordres_travail.csv") if o["equipement_id"] == EQUIPEMENT]
        cls.temps = {}
        for ligne in lire("ot_temps.csv"):
            cls.temps[ligne["ot_id"]] = cls.temps.get(ligne["ot_id"], 0) + float(ligne["heures"])
        cls.techniciens = {t["id"]: (t["prenom"] + " " + t["nom"]).strip() for t in lire("techniciens.csv")}
        cls.codes = {(c["famille"], c["code"]): c["libelle"] for c in lire("codes_defaillance.csv")}

    def ouvrir(self, profil="responsable"):
        page = self.page
        page.goto(url_fichier("index.html"))
        page.wait_for_function("document.documentElement.dataset.etat === 'demarrage'")
        page.click("#btn-demo")
        page.wait_for_function("document.documentElement.dataset.etat === 'profil'")
        if profil == "demandeur":
            page.click("#profil-demandeur")
            page.fill("#profil-nom", "Opérateur test")
            page.click("#profil-panneau-demandeur button[type=submit]")
        else:
            page.click("#profil-responsable")
        attendre_pret(page)
        page.evaluate("(r) => { location.hash = r; }", "#/equipement/" + EQUIPEMENT)
        page.wait_for_selector("#parc-historique .parc-filtre-historique")

    def liens_ot(self):
        return sorted(set(self.page.eval_on_selector_all("#parc-historique a[href^='#/ot/OT-']",
                                                         "liens => liens.map(a => a.getAttribute('href').slice(5))")))

    def test_ligne_technicien_temps_cause_remede_et_filtre(self):
        self.ouvrir()
        page = self.page
        entetes = simple(page.locator("#parc-historique table").first.locator("thead").inner_text())
        for attendu in ("Technicien", "Temps passé"):
            self.assertIn(attendu, entetes)
        panne = next(o for o in self.ordres if o["type"] in CORRECTIFS and o["cause_code"] and o["remede_code"])
        ligne = simple(page.locator("#parc-historique table tr", has_text=panne["id"]).first.inner_text())
        self.assertIn(self.techniciens[panne["technicien_id"]], ligne)
        self.assertIn(heures_fr(self.temps[panne["id"]]), ligne)
        self.assertIn("Cause : " + self.codes[("cause", panne["cause_code"])], ligne)
        self.assertIn("Remède : " + self.codes[("remède", panne["remede_code"])], ligne)
        preventif = next(o for o in self.ordres if o["type"] in PREVENTIFS)
        ligne = simple(page.locator("#parc-historique table tr", has_text=preventif["id"]).first.inner_text())
        self.assertNotIn("Cause :", ligne)
        self.assertIn(self.techniciens[preventif["technicien_id"]], ligne)
        # Aucun montant dans l'historique (le temps passé n'est pas un coût)
        self.assertNotIn("€", page.inner_text("#parc-historique"))
        # Filtre : « Tout » choisi d'abord ; libellés avec le nombre d'OT ; chaque bouton garde son genre
        pannes = sorted(o["id"] for o in self.ordres if o["type"] in CORRECTIFS)
        preventifs = sorted(o["id"] for o in self.ordres if o["type"] in PREVENTIFS)
        boutons = [simple(t) for t in page.locator(".parc-filtre-historique").all_inner_texts()]
        self.assertEqual(boutons, ["Pannes (%d)" % len(pannes), "Préventif (%d)" % len(preventifs),
                                   "Tout (%d)" % len(self.ordres)])
        self.assertEqual(page.get_attribute(".parc-filtre-historique[data-filtre=tout]", "aria-pressed"), "true")
        self.assertEqual(self.liens_ot(), sorted(o["id"] for o in self.ordres))
        page.click(".parc-filtre-historique[data-filtre=pannes]")
        self.assertEqual(self.liens_ot(), pannes)
        self.assertEqual(page.get_attribute(".parc-filtre-historique[data-filtre=pannes]", "aria-pressed"), "true")
        self.assertEqual(page.get_attribute(".parc-filtre-historique[data-filtre=tout]", "aria-pressed"), "false")
        page.click(".parc-filtre-historique[data-filtre=preventif]")
        self.assertEqual(self.liens_ot(), preventifs)
        page.click(".parc-filtre-historique[data-filtre=tout]")
        self.assertEqual(self.liens_ot(), sorted(o["id"] for o in self.ordres))
        # Sur PC, pas de bouton « Historique » (la fiche tient sur l'écran)
        self.assertEqual(page.locator("#parc-aller-historique").count(), 0)

    def test_telephone_bouton_historique_en_haut_et_cartes(self):
        page = self.page
        page.set_viewport_size({"width": 375, "height": 800})
        self.ouvrir()
        bouton = page.locator("#parc-aller-historique")
        self.assertTrue(bouton.is_visible())
        boite = bouton.bounding_box()
        self.assertLess(boite["y"], 400)                         # en haut de la fiche, sans défiler
        self.assertGreaterEqual(boite["height"], 47.5)            # zone tactile (gants)
        self.assertIn("Historique", bouton.inner_text())
        self.assertGreater(page.evaluate("document.getElementById('parc-historique').getBoundingClientRect().top"), 800)
        bouton.click()
        page.wait_for_function("Math.abs(document.getElementById('parc-historique').getBoundingClientRect().top) < 200")
        self.assertEqual(page.evaluate("document.activeElement && document.activeElement.id"), "parc-historique")
        # Cartes : technicien et temps passé
        panne = next(o for o in self.ordres if o["type"] in CORRECTIFS and o["cause_code"])
        carte = simple(page.locator("#parc-historique .liste-cartes li", has_text=panne["id"]).first.inner_text())
        self.assertIn(self.techniciens[panne["technicien_id"]], carte)
        self.assertIn("Temps passé : " + heures_fr(self.temps[panne["id"]]), carte)
        self.assertIn("Cause : " + self.codes[("cause", panne["cause_code"])], carte)
        page.click(".parc-filtre-historique[data-filtre=pannes]")
        self.assertEqual(self.liens_ot(), sorted(o["id"] for o in self.ordres if o["type"] in CORRECTIFS))
        largeurs = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.assertLessEqual(largeurs[0], largeurs[1])

    def test_demandeur_ni_technicien_ni_temps(self):
        self.ouvrir("demandeur")
        texte = simple(self.page.inner_text("#parc-historique"))
        self.assertNotIn("Temps passé", texte)
        self.assertNotIn("Technicien", texte)
        for nom in self.techniciens.values():
            self.assertNotIn(nom, texte)


if __name__ == "__main__":
    unittest.main()
