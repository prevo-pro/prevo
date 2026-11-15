"""Tests de T566 (lot 2 ergonomie, décision de Nicolas du 15/11) : les OT « à valider » (statut stocké « Clôturé
techniquement », dit « Terminé, à valider ») visibles du responsable.

Démo (file://) :
    - liste des OT : état « À valider » (#/ot?etat=a-valider) pour le responsable, entre « En retard » et
      « Clôturés » ; il ne garde que les OT « Clôturé techniquement » ; « Ouverts » reste sans eux (estOuvert inchangé) ;
    - le technicien n'a pas ce choix ; son adresse ?etat=a-valider est ignorée (il garde « Ouverts ») ;
    - accueil du responsable : un OT clôturé techniquement de plus fait monter le bouton « OT à valider : N » et la
      phrase ; le compteur suit Accueil.calculerCompteurs().otAValider.
(La phrase, ses accords et « Rien d'urgent » : tests/test_bento.py, famille « phrase ».)

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ot_a_valider.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_statut_en_cours"]          # correctif « En cours », venu d'une demande
A_VALIDER_JS = "() => Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé techniquement').map((o) => o.id).sort()"
LIGNES_JS = "() => [...document.querySelectorAll('.ot-liste-tableau tbody tr')].map((tr) => tr.textContent)"


class CasAValider(CasNavigateur):

    def ouvrir_demo(self, profil, technicien_id=""):
        preregler_profil(self.contexte, profil, "Essai", technicien_id)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page

    def aller(self, page, adresse):
        page.evaluate("(a) => { location.hash = a; }", adresse)
        page.wait_for_selector("#ot-filtre-etat")

    def etats(self, page):
        return page.eval_on_selector_all("#ot-filtre-etat option", "l => l.map((o) => o.value)")


class TestListe(CasAValider):

    def test_responsable_etat_a_valider_par_l_adresse(self):
        page = self.ouvrir_demo("responsable")
        attendus = page.evaluate(A_VALIDER_JS)
        self.assertEqual(len(attendus), 13)
        self.aller(page, "#/ot?etat=a-valider")
        self.assertEqual(self.etats(page), ["ouverts", "retard", "a-valider", "clotures", "annules", "tous"])
        self.assertEqual(page.input_value("#ot-filtre-etat"), "a-valider")
        self.assertEqual(page.eval_on_selector("#ot-filtre-etat option[value='a-valider']", "o => o.textContent"), "À valider")
        lignes = page.evaluate(LIGNES_JS)
        self.assertEqual(len(lignes), 13)
        self.assertTrue(all("Terminé, à valider" in ligne for ligne in lignes))
        self.assertTrue(page.text_content("#ot-compteur").startswith("13 "))
        # Règle pure : seuls les « Clôturé techniquement » ; « Ouverts » ne les montre toujours pas (estOuvert inchangé).
        ids = page.evaluate("() => Ordres.filtrer(Donnees.lignes('ordres_travail'), { etat: 'a-valider' }).map((o) => o.id).sort()")
        self.assertEqual(ids, attendus)
        ouverts = page.evaluate("() => Ordres.filtrer(Donnees.lignes('ordres_travail'), { etat: 'ouverts' }).map((o) => o.statut)")
        self.assertNotIn("Clôturé techniquement", ouverts)
        self.assertFalse(page.evaluate("() => Ordres.estOuvert({ statut: 'Clôturé techniquement' })"))
        # Le choix à la main fait de même
        page.select_option("#ot-filtre-etat", "ouverts")
        self.assertFalse(any("Terminé, à valider" in ligne for ligne in page.evaluate(LIGNES_JS)))
        page.select_option("#ot-filtre-etat", "a-valider")
        self.assertEqual(len(page.evaluate(LIGNES_JS)), 13)

    def test_technicien_sans_l_etat_a_valider(self):
        page = self.ouvrir_demo("technicien", "TEC-0001")
        self.aller(page, "#/ot?etat=a-valider")
        self.assertEqual(self.etats(page), ["ouverts", "retard", "clotures", "annules", "tous"])
        self.assertEqual(page.input_value("#ot-filtre-etat"), "ouverts")


class TestAccueil(CasAValider):

    def test_compteur_suit_une_cloture_technique(self):
        page = self.ouvrir_demo("responsable")
        page.wait_for_selector("#bento")
        self.assertEqual(page.text_content("#bento-a-valider").strip(), "OT à valider : 13")
        self.assertEqual(page.get_attribute("#bento-a-valider", "href"), "#/ot?etat=a-valider")
        page.evaluate("""async (id) => { await Donnees.modifier('ordres_travail', (l) => {
            const ot = l.find((o) => o.id === id); ot.statut = 'Clôturé techniquement'; }); await App.reafficher(); }""", OT)
        page.wait_for_function("() => (document.getElementById('bento-a-valider') || {}).textContent === 'OT à valider : 14'")
        self.assertIn("14 OT à valider", page.text_content("#bento-phrase"))
        self.assertEqual(page.evaluate("() => Accueil.calculerCompteurs().otAValider.length"), 14)
        page.click("#bento-a-valider")
        page.wait_for_function("() => document.getElementById('ot-filtre-etat') && document.getElementById('ot-filtre-etat').value === 'a-valider'")
        self.assertTrue(any(OT in ligne for ligne in page.evaluate(LIGNES_JS)))


if __name__ == "__main__":
    unittest.main()
