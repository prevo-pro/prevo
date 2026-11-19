"""Tests de L20, dépannage provisoire (lot 2 ergonomie, T554 ; js/modules/ordres-cloture.js, ordres-ecritures.js).

Démo (file://) :
    - sur une panne (« correctif immédiat ») seulement, la fenêtre de clôture a la case « Dépannage provisoire, remise
      en état à prévoir » et un mot (colonne remise_en_etat, format 6) ; case décochée : rien à prévoir ;
    - à la validation par le responsable, « Créer l'OT de remise en état » crée en un geste une « Réparation
      programmée » (correctif différé), même machine, titre et travail à faire repris du mot, liée à la panne
      (ot_lie_id) ; une seule (un second appel rend la même).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_cloture_provisoire_l20.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, figer_a_midi, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_statut_en_cours"]
FENETRE = "dialog.dialogue[open]"
BOUTON = FENETRE + " .fenetre-actions .btn-primaire"
MOT = "Changer le roulement côté moteur"

PANNE_JS = """async ([otId, type]) => {
  await Ordres.interne.modifierOt(otId, { type, date_fin: '', cause_code: '', remede_code: '', compte_rendu: '',
    remise_service: '0', remise_en_etat: '' }, 'essai');
  return Donnees.trouver('ordres_travail', otId).technicien_id;
}"""

VALIDE_JS = """async ([otId, mot]) => Donnees.modifier('ordres_travail', (lignes) => {
  const l = lignes.find((x) => x.id === otId);
  Object.assign(l, { type: 'correctif immédiat', statut: 'Clôturé techniquement', date_cloture_tech: Donnees.maintenant(),
    date_fin: Donnees.maintenant(), compte_rendu: 'Roulement graissé, bruit réduit, à changer.', remise_service: '1', cause_code: 'C01', remede_code: 'R01',
    remise_en_etat: mot });
}, { action: 'essai' })"""


class CasProvisoire(CasNavigateur):

    def ouvrir(self, contexte, profil, technicien_id=""):
        preregler_profil(contexte, profil, "Essai", technicien_id)
        page = self.page if contexte is self.contexte else contexte.new_page()
        if page is not self.page:
            self.surveiller(page)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        return page

    def fenetre_technicien(self, type_ot):
        technicien = self.ouvrir(self.contexte, "responsable").evaluate(PANNE_JS, [OT, type_ot])
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        page = self.ouvrir(contexte, "technicien", technicien)
        page.evaluate(PANNE_JS, [OT, type_ot])
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-actions")
        page.click(".ot-actions [data-cible='Clôturé techniquement']")
        page.wait_for_selector(FENETRE + " [name='compte_rendu']", state="visible")
        return page


class TestFenetre(CasProvisoire):

    def test_panne_case_et_mot_ecrits(self):
        page = self.fenetre_technicien("correctif immédiat")
        self.assertIn("Dépannage provisoire, remise en état à prévoir", page.inner_text(FENETRE))
        self.assertFalse(page.is_visible(FENETRE + " [name='remise_en_etat']"))
        page.check(FENETRE + " [name='depannage_provisoire']")
        page.fill(FENETRE + " [name='remise_en_etat']", MOT)
        page.select_option(FENETRE + " [name='cause_code']", index=2)
        page.select_option(FENETRE + " [name='remede_code']", index=2)
        page.fill(FENETRE + " [name='compte_rendu']", "Roulement graissé, bruit réduit, à changer.")
        page.check(FENETRE + " [name='remise_service']")
        if not page.input_value(FENETRE + " [name='heures']"):
            page.fill(FENETRE + " [name='heures']", "1h")
        page.click(BOUTON)
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'", arg=OT)
        self.assertEqual(page.evaluate("(id) => Donnees.trouver('ordres_travail', id).remise_en_etat", OT), MOT)
        page.wait_for_selector(".ot-bandeau-etat .alerte")
        self.assertIn(MOT, page.inner_text(".ot-bandeau-etat"))
        self.assertEqual(page.locator("#ot-remise-en-etat").count(), 0)      # le technicien ne valide pas

    def test_hors_panne_pas_de_case(self):
        page = self.fenetre_technicien("correctif différé")
        self.assertEqual(page.locator(FENETRE + " [name='depannage_provisoire']").count(), 0)


class TestValidation(CasProvisoire):

    def test_valider_puis_creer_en_un_geste(self):
        figer_a_midi(self.contexte)         # clôture de l'OT « en cours » de la démo
        page = self.ouvrir(self.contexte, "responsable")
        page.evaluate(VALIDE_JS, [OT, MOT])
        self.assertEqual(page.evaluate("(id) => Ordres.verifierCloture(Donnees.trouver('ordres_travail', id))", OT), [])
        panne = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT)
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-actions [data-cible='Clôturé administrativement']")
        self.assertIn("À la validation", page.inner_text(".ot-bandeau-etat"))
        page.click(".ot-actions [data-cible='Clôturé administrativement']")
        page.click("dialog .fenetre-actions .btn-primaire")
        page.wait_for_selector("#ot-remise-en-etat")
        page.click("#ot-remise-en-etat")
        page.wait_for_function("(id) => /^#\\/ot\\/OT-/.test(location.hash) && location.hash !== '#/ot/' + id", arg=OT)
        nouveau = page.evaluate("(id) => Donnees.lignes('ordres_travail').find((o) => o.ot_lie_id === id)", OT)
        self.assertEqual((nouveau["type"], nouveau["equipement_id"], nouveau["titre"], nouveau["travail_a_faire"], nouveau["statut"]),
                         ("correctif différé", panne["equipement_id"], MOT, MOT, "Créé"))
        self.assertEqual(page.evaluate("(id) => Ordres.creerRemiseEnEtat(id)", OT), nouveau["id"])
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-bandeau-etat a[href='#/ot/%s']" % nouveau["id"])
        self.assertEqual(page.locator("#ot-remise-en-etat").count(), 0)


if __name__ == "__main__":
    unittest.main()
