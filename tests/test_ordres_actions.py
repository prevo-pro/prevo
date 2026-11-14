"""Tests de la carte Actions de la fiche d'un OT (lot 2 ergonomie, L18 ; js/modules/ordres-prise.js, rangerActions) :
un seul bouton mis en avant, celui de la prochaine étape utile pour la personne connectée ; « Marquer préparé » et
« Annuler » sous « Plus d'options » ; Préparé et Planifié marqués « facultatif » sur la frise.

Familles :
    principal : le bouton mis en avant selon l'état de l'OT et le profil (responsable, technicien), le reste en second.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ordres_actions.py" -v
"""
import unittest

from commun import ServeurPrevo
from test_ordres_prise import CasPrise, KARIM, JULIEN

PRINCIPAL = ".ot-actions > .actions > .ot-bouton-principal"


class CasActions(CasPrise):

    def principal(self):
        """(data-cible ou data-sorte ou id) du bouton mis en avant, None s'il n'y en a pas."""
        return self.page.evaluate("""s => { const b = document.querySelector(s);
            return b ? (b.dataset.cible || b.dataset.sorte || b.id) : null; }""", PRINCIPAL)

    def nombre_bleus(self):
        return self.page.locator(".ot-actions .btn-primaire").count()

    def aller_fiche(self, ot_id):
        """La fiche réaffichée même si elle l'est déjà (détour par la liste)."""
        self.page.evaluate("() => { location.hash = '#/ot'; }")
        self.page.wait_for_selector(".ot-liste-tete")
        super().aller_fiche(ot_id)

    def passer(self, ot_id, depuis, cible, complement=None):
        self.page.evaluate("([id, a, b, c]) => Ordres.changerStatut(id, a, b, c || {})", [ot_id, depuis, cible, complement])


class TestPrincipal(CasActions):

    def test_principal_plus_options_et_frise(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            affecte = self.creer_ot({"equipement_id": "EQ-0005", "titre": "L18 affecté", "technicien_id": JULIEN})
            libre = self.creer_ot({"equipement_id": "EQ-0005", "titre": "L18 libre"})

            # Responsable, OT affecté et Créé : « Démarrer » seul en bleu ; Marquer préparé et Annuler repliés
            self.aller_fiche(affecte)
            self.assertEqual(self.principal(), "En cours")
            self.assertEqual(self.nombre_bleus(), 1)
            self.assertEqual(self.page.locator(".ot-actions > .actions > button").first.get_attribute("data-cible"), "En cours")
            for cible in ("Préparé", "Annulé"):
                self.assertEqual(self.page.locator(".ot-plus-options button[data-cible='%s']" % cible).count(), 1, cible)
                self.assertEqual(self.page.locator(".ot-actions > .actions button[data-cible='%s']" % cible).count(), 0, cible)
            self.assertTrue(self.page.is_hidden(".ot-plus-options button[data-cible='Annulé']"))     # replié
            self.assertIn("Plus d'options", self.page.inner_text(".ot-plus-options summary"))
            self.assertTrue(self.page.is_visible(".ot-actions > .actions button[data-cible='En attente']"))
            # Frise : Préparé et Planifié marqués « facultatif » ; les autres non
            facultatives = self.page.eval_on_selector_all(".ot-etapes li[data-facultatif]", "l => l.map(e => e.innerText)")
            self.assertEqual(len(facultatives), 2, facultatives)
            self.assertTrue(all("facultatif" in t for t in facultatives), facultatives)
            self.assertEqual(self.page.locator(".ot-etapes .etape-facultatif").count(), 2)

            # Responsable, OT sans technicien : aucun passage obligé à mettre en avant (rien en bleu)
            self.aller_fiche(libre)
            self.assertIsNone(self.principal())
            self.assertEqual(self.nombre_bleus(), 0)

            # Technicien, OT sans technicien : « Je prends cet OT »
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.aller_fiche(libre)
            self.assertEqual(self.principal(), "prendre")
            self.assertEqual(self.nombre_bleus(), 1)

            # En cours : la clôture technique ; clôturé techniquement : la clôture administrative, « Rouvrir » en second
            self.changer_profil(serveur, "#/accueil", "responsable")
            self.passer(affecte, "Créé", "En cours")
            self.aller_fiche(affecte)
            self.assertEqual(self.principal(), "Clôturé techniquement")
            self.assertEqual(self.nombre_bleus(), 1)
            self.page.evaluate("""id => Donnees.modifier('ordres_travail', (lignes) => { const l = lignes.find((o) => o.id === id);
                Object.assign(l, { date_fin: Donnees.maintenant().slice(0, 16), compte_rendu: 'Courroie changée et retendue.',
                  remise_service: '1', cause_precision: 'usure', remede_precision: 'remplacement' }); })""", affecte)
            self.page.evaluate("""id => Donnees.modifier('ot_temps', (lignes, outils) => { lignes.push({ id: outils.nouvelId(lignes),
                ot_id: id, technicien_id: 'TEC-0001', date: Donnees.aujourdhui(), heures: '1' }); })""", affecte)
            self.assertEqual(self.page.evaluate("id => Ordres.verifierCloture(Donnees.trouver('ordres_travail', id))", affecte), [])
            self.passer(affecte, "En cours", "Clôturé techniquement")
            self.aller_fiche(affecte)
            self.assertEqual(self.principal(), "Clôturé administrativement")
            self.assertEqual(self.nombre_bleus(), 1)
            self.assertIn("btn-secondaire", self.page.get_attribute(".ot-actions button[data-cible='En cours']", "class"))


if __name__ == "__main__":
    unittest.main()
