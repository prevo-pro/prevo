"""Tests de la carte Actions de la fiche d'un OT (lot 2 ergonomie, L18 ; js/modules/ordres-prise.js, rangerActions) :
un seul bouton mis en avant, celui de la prochaine étape utile pour la personne connectée ; « Marquer préparé » et
« Annuler » sous « Plus d'options » ; Préparé et Planifié marqués « facultatif » sur la frise.

Familles :
    principal : le bouton mis en avant selon l'état de l'OT et le profil (responsable, technicien), le reste en second ;
    suite     : OT en attente à mon nom (« Reprendre le travail », clôture sans reprise) ; OT en attente d'un collègue
                (« Prendre la suite » : à mon nom et en cours en un geste, trace de prise, RG8 comme l'affectation) ;
    telephone : barre fixe du bouton mis en avant (390 px) : visible sans défiler, agit comme l'original, ne cache pas
                le dernier élément de la fiche, cachée pendant une saisie, pas de débordement en largeur ; absente sur PC.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ordres_actions.py" -v
"""
import unittest

from commun import ServeurPrevo, demo_rg8_bloquante
from test_ordres_prise import CasPrise, KARIM, JULIEN, THOMAS, LIGNE_PRISE, ot_sur_disque

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

    def completer_cloture(self, ot_id, technicien_id=JULIEN):
        """Saisies de la clôture technique (RG4) faites, temps passé compris."""
        self.page.evaluate("""id => Donnees.modifier('ordres_travail', (lignes) => { const l = lignes.find((o) => o.id === id);
            Object.assign(l, { date_fin: Donnees.maintenant().slice(0, 16), compte_rendu: 'Courroie changée et retendue.',
              remise_service: '1', cause_precision: 'usure', remede_precision: 'remplacement' }); })""", ot_id)
        self.page.evaluate("""([id, tec]) => Donnees.modifier('ot_temps', (lignes, outils) => { lignes.push({ id: outils.nouvelId(lignes),
            ot_id: id, technicien_id: tec, date: Donnees.aujourdhui(), heures: '1' }); })""", [ot_id, technicien_id])
        self.assertEqual(self.page.evaluate("id => Ordres.verifierCloture(Donnees.trouver('ordres_travail', id))", ot_id), [])


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
            self.completer_cloture(affecte)
            self.passer(affecte, "En cours", "Clôturé techniquement")
            self.aller_fiche(affecte)
            self.assertEqual(self.principal(), "Clôturé administrativement")
            self.assertEqual(self.nombre_bleus(), 1)
            self.assertIn("btn-secondaire", self.page.get_attribute(".ot-actions button[data-cible='En cours']", "class"))



class TestSuite(CasActions):

    def test_en_attente_a_mon_nom_reprendre_le_travail_et_clore_sans_reprise(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            # en attente sans avoir démarré (la friction du retest : « Reprendre (Préparé) » caché, ni Démarrer ni Clore)
            jamais = self.creer_ot({"equipement_id": "EQ-0005", "titre": "L18 attente", "technicien_id": KARIM}, statut="En attente")
            demarre = self.creer_ot({"equipement_id": "EQ-0005", "titre": "L18 attente démarré", "technicien_id": KARIM})
            self.passer(demarre, "Créé", "En cours")
            self.passer(demarre, "En cours", "En attente", {"motif_attente": "pièce"})
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.aller_fiche(jamais)
            self.assertEqual(self.principal(), "En cours")
            self.assertEqual(self.page.inner_text(PRINCIPAL).strip(), "Reprendre le travail")
            self.assertEqual(self.nombre_bleus(), 1)
            self.assertTrue(self.page.is_visible(".ot-actions > .actions button[data-cible='Clôturé techniquement']"))
            self.assertEqual(self.page.locator(".ot-actions > .actions button[data-cible='Préparé']").count(), 0)   # plus de « Reprendre (Préparé) »
            self.assertEqual(self.page.locator(".ot-actions button[data-action=prendre-ot]").count(), 0)
            # « Reprendre le travail » : En cours d'un geste (date de début posée)
            self.page.click(PRINCIPAL)
            ligne = self.attendre_disque(serveur, jamais, lambda o: o["statut"] == "En cours")
            self.assertEqual(ligne["statut"], "En cours")
            self.assertTrue(ligne["date_debut"])
            # Clôture technique directe depuis En attente (sans reprise), avec les contrôles RG4 habituels
            self.aller_fiche(demarre)
            self.assertEqual(self.page.inner_text(PRINCIPAL).strip(), "Reprendre le travail")
            self.completer_cloture(demarre, KARIM)
            self.aller_fiche(demarre)
            self.page.click(".ot-actions > .actions button[data-cible='Clôturé techniquement']")
            try:                                     # mot pour l'opérateur (A4, facultatif) : fenêtre validée telle quelle
                self.page.wait_for_selector("dialog.dialogue[open]", timeout=3000)
                self.page.click("dialog.dialogue[open] .fenetre-actions .btn-primaire")
            except Exception:
                pass
            ligne = self.attendre_disque(serveur, demarre, lambda o: o["statut"] == "Clôturé techniquement")
            self.assertEqual(ligne["statut"], "Clôturé techniquement")
            self.assertEqual(ligne["technicien_id"], KARIM)

    def test_prendre_la_suite_d_un_collegue(self):
        with ServeurPrevo(demo_rg8_bloquante()) as serveur:          # L19 (T556) : RG8 réglée « bloquante »
            self.ouvrir(serveur, "#/ot")
            panne = self.creer_ot({"equipement_id": "EQ-0005", "titre": "L18 panne de Julien", "technicien_id": JULIEN})
            self.passer(panne, "Créé", "En cours")
            self.passer(panne, "En cours", "En attente", {"motif_attente": "pièce"})
            exige = self.creer_ot({"equipement_id": "EQ-0012", "titre": "L18 armoire", "technicien_id": JULIEN,
                                   "date_prevue": "2026-10-21"}, statut="En attente")
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.aller_fiche(panne)
            self.assertEqual(self.principal(), "suite")
            self.assertEqual(self.page.inner_text(PRINCIPAL).strip(), "Prendre la suite")
            self.assertEqual(self.nombre_bleus(), 1)
            # un seul « Reprendre » à l'écran : celui qui remettrait en cours au nom de Julien est replié
            self.assertEqual(self.page.locator(".ot-actions > .actions button[data-cible='En cours']").count(), 0)
            self.assertEqual(self.page.locator(".ot-plus-options button[data-cible='En cours']").count(), 1)
            self.assertTrue(self.page.is_visible(".ot-actions > .actions button[data-cible='Clôturé techniquement']"))
            self.page.click(PRINCIPAL)
            self.page.wait_for_selector("dialog.dialogue[open]")
            self.assertIn("Cet OT est au nom de Julien", self.page.inner_text("dialog.dialogue[open]"))
            self.page.click("dialog.dialogue[open] .fenetre-actions .btn-primaire")
            ligne = self.attendre_disque(serveur, panne, lambda o: o["statut"] == "En cours" and o["technicien_id"] == KARIM)
            self.assertEqual((ligne["statut"], ligne["technicien_id"]), ("En cours", KARIM))
            self.assertEqual(LIGNE_PRISE.match(ligne["prises_en_charge"].split("\n")[-1]).groups(), (KARIM, JULIEN))
            self.page.wait_for_selector(".onglet[data-onglet='execution'][aria-selected='true']")
            self.page.wait_for_selector(".ot-actions > .actions > .ot-bouton-principal[data-cible='Clôturé techniquement']")
            # En cours au nom d'un collègue : « Prendre la suite » aussi (le statut reste En cours)
            self.changer_profil(serveur, "#/accueil", "technicien", JULIEN, "Julien Moreau")
            self.aller_fiche(panne)
            self.assertEqual(self.principal(), "suite")
            # RG8 : Thomas (sans BR valide) est refusé comme à l'affectation ; rien n'est écrit, pas même le statut.
            # L19 (T556) : ceux qui ont l'habilitation sont nommés à la place de « Prendre la suite »
            self.changer_profil(serveur, "#/accueil", "technicien", THOMAS, "Thomas Garnier")
            self.autoriser_erreur("BR")
            self.aller_fiche(exige)
            avant = ot_sur_disque(serveur.dossier, exige)
            self.page.wait_for_selector(".ot-actions .ot-habilites")
            self.assertIn("BR", self.page.inner_text(".ot-actions .ot-habilites"))
            self.assertEqual(self.page.locator(".ot-actions button[data-action=prendre-ot]").count(), 0)
            refus = self.page.evaluate("""([ot, tec, avant]) => Ordres.prendre(ot, tec, avant).then(() => 'écrit', (e) => e.message)""",
                                       [exige, THOMAS, JULIEN])
            self.assertIn("BR", refus)
            self.assertEqual(ot_sur_disque(serveur.dossier, exige), avant)



class TestTelephone(CasActions):

    BARRE = ".ot-barre-principale button"

    def test_barre_fixe_sur_telephone(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            affecte = self.creer_ot({"equipement_id": "EQ-0005", "titre": "L18 téléphone", "technicien_id": KARIM})
            # PC (responsable : l'onglet Préparation se saisit) : pas de barre visible
            self.page.set_viewport_size({"width": 1440, "height": 900})
            self.aller_fiche(affecte)
            self.assertTrue(self.page.is_hidden(".ot-barre-principale"))
            # Téléphone : « Démarrer » visible sans défiler, dans l'écran
            self.page.set_viewport_size({"width": 390, "height": 844})
            self.aller_fiche(affecte)
            self.page.evaluate("() => window.scrollTo(0, 0)")
            self.assertTrue(self.page.is_visible(self.BARRE))
            self.assertEqual(self.page.inner_text(self.BARRE).strip(), self.page.inner_text(PRINCIPAL).strip())
            boite = self.page.locator(self.BARRE).bounding_box()
            self.assertGreaterEqual(boite["y"], 0)
            self.assertLessEqual(boite["y"] + boite["height"], 844)
            self.assertLessEqual(self.page.evaluate("() => document.documentElement.scrollWidth"), 390)   # pas de débordement
            # le bas de la fiche défilé jusqu'au bout : son dernier élément passe au-dessus de la barre
            self.page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
            bas_fiche = self.page.evaluate("""() => { const f = document.querySelector('.ot-fiche .ot-onglets');
                return f.getBoundingClientRect().bottom; }""")
            haut_barre = self.page.evaluate("() => document.querySelector('.ot-barre-principale').getBoundingClientRect().top")
            self.assertLessEqual(bas_fiche, haut_barre + 1)
            # saisie : la barre se cache (clavier ouvert), puis revient
            self.page.click(".onglet[data-onglet='preparation']")
            champ = "#form-preparation textarea"
            self.page.wait_for_selector(champ)
            self.page.focus(champ)
            self.assertTrue(self.page.is_hidden(".ot-barre-principale"))
            self.page.evaluate("() => document.activeElement.blur()")
            self.assertTrue(self.page.is_visible(self.BARRE))
            # la barre agit comme l'original : « Démarrer »
            self.page.click(self.BARRE)
            ligne = self.attendre_disque(serveur, affecte, lambda o: o["statut"] == "En cours")
            self.assertEqual(ligne["statut"], "En cours")


if __name__ == "__main__":
    unittest.main()
