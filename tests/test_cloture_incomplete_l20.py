"""Tests de L20, clôtures incomplètes (lot 2 ergonomie, T554 ; js/modules/ordres-cloture.js).

Démo (file://) :
    - réglage du responsable « Autoriser les clôtures incomplètes » (clé clotures_incompletes, défaut non) dans
      Paramètres ;
    - réglage actif, le technicien clôture malgré des champs vides : le bouton dit « Clôturer incomplet — il manque N
      éléments », la fenêtre le redit, l'OT passe « Clôturé techniquement » avec ses manques ; une date de fin
      incohérente bloque toujours ; réglage inactif : rien ne change (refus) ;
    - le responsable retrouve ces OT sur son accueil (carte « Clôtures à compléter », calculée : aucune colonne), sur la
      fiche (ce qui manque, « Compléter la clôture ») ; il complète sans rouvrir l'OT ; la validation administrative
      exige RG4 entière ; le responsable lui-même ne clôture jamais incomplet.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_cloture_incomplete_l20.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, figer_a_midi, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_statut_en_cours"]
FENETRE = "dialog.dialogue[open]"
BOUTON = FENETRE + " .fenetre-actions .btn-primaire"

# OT sans rien de la clôture sauf la date de fin (ni temps, ni codes, ni compte rendu, ni case).
VIDER_JS = """async (otId) => {
  await Ordres.interne.modifierOt(otId, { date_fin: '', symptome_code: '', cause_code: '', remede_code: '',
    cause_precision: '', remede_precision: '', compte_rendu: '', remise_service: '0', arret_production: '0', duree_arret_h: '' }, 'essai');
  await Donnees.modifier('ot_temps', (lignes) => {
    for (let i = lignes.length - 1; i >= 0; i -= 1) if (lignes[i].ot_id === otId) lignes.splice(i, 1);
  }, { action: 'essai' });
  return Donnees.trouver('ordres_travail', otId).technicien_id;
}"""

REGLER_JS = """(valeur) => Donnees.modifier('parametres', (lignes) => {
  const l = lignes.find((x) => x.cle === 'clotures_incompletes');
  if (l) l.valeur = valeur; else lignes.push({ cle: 'clotures_incompletes', valeur }); }, { action: 'essai' })"""

# L'OT laissé « Clôturé techniquement » sans compte rendu, sans codes ni case (comme après une clôture incomplète).
CLOS_INCOMPLET_JS = """async (otId) => Donnees.modifier('ordres_travail', (lignes) => {
  const l = lignes.find((x) => x.id === otId);
  Object.assign(l, { statut: 'Clôturé techniquement', date_cloture_tech: Donnees.maintenant(), date_fin: Donnees.maintenant(),
    cause_code: '', remede_code: '', compte_rendu: '', remise_service: '0' });
}, { action: 'essai' })"""


class CasIncomplete(CasNavigateur):

    def ouvrir(self, contexte, profil, technicien_id=""):
        preregler_profil(contexte, profil, "Essai", technicien_id)
        page = contexte.new_page() if contexte is not self.contexte else self.page
        if page is not self.page:
            self.surveiller(page)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        return page

    def page_technicien(self, regle):
        technicien = self.ouvrir(self.contexte, "responsable").evaluate(VIDER_JS, OT)
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        page = self.ouvrir(contexte, "technicien", technicien)
        page.evaluate(VIDER_JS, OT)
        page.evaluate(REGLER_JS, regle)
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-actions")
        page.click(".ot-actions [data-cible='Clôturé techniquement']")
        page.wait_for_selector(FENETRE + " [name='compte_rendu']", state="visible")
        return page

    def page_responsable(self):
        page = self.ouvrir(self.contexte, "responsable")
        page.evaluate(VIDER_JS, OT)
        page.evaluate(CLOS_INCOMPLET_JS, OT)
        page.evaluate(REGLER_JS, "1")
        return page


class TestTechnicien(CasIncomplete):

    def test_reglage_actif_cloture_incomplete(self):
        page = self.page_technicien("1")
        self.assertEqual(page.inner_text(BOUTON).strip(), "Clôturer incomplet — il manque 5 éléments")
        self.assertIn("le responsable complétera", page.inner_text(FENETRE + " .ot-cloture-manques"))
        page.fill(FENETRE + " [name='heures']", "")
        page.click(BOUTON)
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'", arg=OT)
        manques = page.evaluate("(id) => Ordres.verifierCloture(Donnees.trouver('ordres_travail', id))", OT)
        self.assertEqual(len(manques), 5, manques)
        page.wait_for_selector("#ot-message .alerte")
        self.assertIn("Votre part est terminée.", page.inner_text("#ot-message"))
        # Sur la fiche du technicien : ce qui manque, sans le bouton du responsable.
        self.assertIn("Clôture incomplète.", page.inner_text(".ot-bandeau-etat"))
        self.assertEqual(page.locator("#ot-completer").count(), 0)

    def test_reglage_inactif_refus(self):
        page = self.page_technicien("0")
        self.assertTrue(page.inner_text(BOUTON).strip().startswith("Clôturer techniquement — il manque"))
        page.click(BOUTON)
        page.wait_for_selector(FENETRE + " .champ[data-champ='compte_rendu'].en-erreur")
        self.assertEqual(page.evaluate("(id) => Donnees.trouver('ordres_travail', id).statut", OT), "En cours")

    def test_date_incoherente_bloque_toujours(self):
        page = self.page_technicien("1")
        regles = page.evaluate("""() => [
          Ordres.manquesQuiBloquent([{ champ: 'heures', texte: 'a' }, { champ: 'date_fin', texte: 'b', incoherent: true }]).length,
          Ordres.manquesQuiBloquent([{ champ: 'heures', texte: 'a' }]).length,
          Ordres.manquesCloture({ id: 'X', type: 'correctif immédiat', date_debut: '2026-01-02 10:00', date_fin: '2026-01-01 10:00' },
            { temps: [] }).filter((m) => m.incoherent).map((m) => m.champ)]""")
        self.assertEqual(regles, [1, 0, ["date_fin"]])


class TestResponsable(CasIncomplete):

    def test_reglage_dans_parametres(self):
        page = self.ouvrir(self.contexte, "responsable")
        self.assertEqual(page.evaluate("Ordres.cloturesIncompletesAutorisees()"), False)
        page.evaluate("location.hash = '#/parametres'")
        page.wait_for_selector("[name='clotures_incompletes']")
        self.assertIn("Autoriser les clôtures incomplètes", page.inner_text("body"))

    def test_accueil_fiche_completer_valider(self):
        figer_a_midi(self.contexte)         # clôture de l'OT « en cours » de la démo
        page = self.page_responsable()
        # Le responsable ne clôture jamais incomplet, même réglage actif.
        self.assertEqual(page.evaluate("Ordres.manquesQuiBloquent([{ champ: 'heures', texte: 'a' }]).length"), 1)
        page.evaluate("location.hash = '#/ot'")
        page.wait_for_selector(".ot-liste, .liste-ot, table, .liste-cartes")
        page.evaluate("location.hash = '#/accueil'")
        page.wait_for_selector("#accueil-clotures-incompletes")
        carte = page.inner_text("#accueil-clotures-incompletes")
        self.assertIn("Clôtures à compléter", carte)
        self.assertIn(OT, carte)
        self.assertIn("Retirer l'autorisation", carte)
        # La validation administrative exige RG4 entière.
        verification = page.evaluate("(id) => Ordres.verifierPassage(Donnees.trouver('ordres_travail', id), 'Clôturé administrativement').ok", OT)
        self.assertFalse(verification)
        page.click("#accueil-clotures-incompletes a[href='#/ot/%s']" % OT)
        page.wait_for_selector("#ot-completer")
        self.assertIn("Clôture incomplète.", page.inner_text(".ot-bandeau-etat"))
        page.click("#ot-completer")
        page.wait_for_selector(FENETRE + " [name='compte_rendu']", state="visible")
        self.assertTrue(page.inner_text(BOUTON).strip().startswith("Compléter la clôture — il manque"))
        cause = page.locator(FENETRE + " [name='cause_code'] option").nth(2).get_attribute("value")
        remede = page.locator(FENETRE + " [name='remede_code'] option").nth(2).get_attribute("value")
        page.select_option(FENETRE + " [name='cause_code']", cause)
        page.select_option(FENETRE + " [name='remede_code']", remede)
        page.fill(FENETRE + " [name='compte_rendu']", "Courroie usée remplacée, tension réglée.")
        page.check(FENETRE + " [name='remise_service']")
        if page.locator(FENETRE + " select[name='technicien_id']").count():
            page.select_option(FENETRE + " select[name='technicien_id']", index=1)
        page.fill(FENETRE + " [name='heures']", "1h")
        self.assertEqual(page.inner_text(BOUTON).strip(), "Compléter la clôture")
        page.click(BOUTON)
        page.wait_for_function("(id) => Ordres.verifierCloture(Donnees.trouver('ordres_travail', id)).length === 0", arg=OT)
        ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT)
        self.assertEqual((ot["statut"], ot["cause_code"], ot["remise_service"]), ("Clôturé techniquement", cause, "1"))
        self.assertEqual(page.evaluate("(id) => Donnees.lignes('ot_temps').filter((l) => l.ot_id === id).map((l) => l.heures)", OT), ["1"])
        self.assertTrue(page.evaluate("(id) => Ordres.verifierPassage(Donnees.trouver('ordres_travail', id), 'Clôturé administrativement').ok", OT))
        self.assertEqual(page.evaluate("Ordres.otsClotureIncomplete().length"), page.evaluate(
            "Donnees.lignes('ordres_travail').filter((o) => o.statut === 'Clôturé techniquement' && Ordres.verifierCloture(o).length).length"))
        self.assertNotIn(OT, page.evaluate("Ordres.otsClotureIncomplete().map((o) => o.id)"))


if __name__ == "__main__":
    unittest.main()
