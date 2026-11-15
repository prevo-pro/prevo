"""Tests de L22 (lot 2 ergonomie, défaut n° 18) : ce que Prévo dit après une clôture (js/modules/ordres-cloture.js).

Démo (file://) :
    - en équipe, le technicien qui clôture techniquement lit « Votre part est terminée. Le responsable validera. »
      (toast et message au-dessus des onglets, qui reste) ; le responsable qui clôture techniquement ne le lit pas ;
    - en Solo, « Clore » ouvre une seule fenêtre sans « deux temps » ni « verrouiller » (bouton « Clore ») et dit
      « … est clos. » (toast) ; hors Solo, la fenêtre « Clore » du responsable reste « Clore et verrouiller ».

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_cloture_l22.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_statut_en_cours"]          # correctif « En cours », venu d'une demande
PART_TERMINEE = "Votre part est terminée. Le responsable validera."

# Un toast disparaît au bout de 4 s : chaque toast affiché est noté (même principe que tests/test_ordres_lot2.py).
NOTER_TOASTS_JS = """() => {
  window.__toasts = [];
  let dernier = '';
  new MutationObserver(() => {
    const zone = document.getElementById('toast');
    const texte = zone && zone.classList.contains('visible') ? zone.textContent.trim() : '';
    if (texte && texte !== dernier) window.__toasts.push(texte);
    dernier = texte;
  }).observe(document, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class'] });
}"""

# OT rendu complet pour la clôture technique, par les écritures habituelles (comme test_solo_cloture.py).
PREPARER_JS = """async (otId) => {
  const ot = Donnees.trouver('ordres_travail', otId);
  const code = (famille) => Donnees.lignes('codes_defaillance').find((c) => c.famille === famille && c.code).code;
  const deux = (n) => String(n).padStart(2, '0');
  const d = new Date(Date.now() - 3600000);
  const fin = d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate()) + ' ' + deux(d.getHours()) + ':' + deux(d.getMinutes());
  const debut = new Date(Date.now() - 5 * 3600000);
  const dateDebut = debut.getFullYear() + '-' + deux(debut.getMonth() + 1) + '-' + deux(debut.getDate()) + ' ' + deux(debut.getHours()) + ':' + deux(debut.getMinutes());
  await Ordres.interne.modifierOt(otId, { date_debut: dateDebut, date_fin: fin, symptome_code: code('symptôme'),
    cause_code: code('cause'), remede_code: code('remède'), compte_rendu: 'Roulement grippé remplacé, essai concluant.',
    remise_service: '1' }, 'compte rendu');
  await Ordres.interne.modifierLieeAOt(otId, 'ot_temps', (lignes, outils) => {
    lignes.push({ id: outils.nouvelId(lignes), ot_id: otId, technicien_id: ot.technicien_id, date: fin.slice(0, 10), heures: '1' });
  }, { action: 'temps passé sur ' + otId });
  return ot.technicien_id;
}"""


class CasCloture(CasNavigateur):

    def ouvrir_demo(self, profil, technicien_id=""):
        preregler_profil(self.contexte, profil, "Essai", technicien_id)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page

    def aller_fiche(self, page):
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-actions")

    def clore_techniquement(self, page):
        page.click(".ot-actions [data-cible='Clôturé techniquement']")
        # L20 : la fenêtre de clôture unique (tout est déjà rempli ; mot pour l'opérateur facultatif, A4) : on la valide.
        page.wait_for_selector("dialog [name='compte_rendu']", state="visible")
        page.click("dialog .fenetre-actions .btn-primaire")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'", arg=OT)
        page.wait_for_selector("#ot-message .alerte")
        return page.text_content("#ot-message")


class TestEquipe(CasCloture):

    def test_technicien_votre_part_est_terminee(self):
        technicien = self.ouvrir_demo("responsable").evaluate("(id) => Donnees.trouver('ordres_travail', id).technicien_id", OT)
        self.assertTrue(technicien)
        # Nouvelle démo, profil du technicien de l'OT : il le complète et le clôture techniquement par le bouton.
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        try:
            preregler_profil(contexte, "technicien", "Essai", technicien)
            page = contexte.new_page()
            self.surveiller(page)
            page.goto(url_fichier("index.html"))
            page.click("#btn-demo")
            attendre_pret(page)
            self.assertTrue(page.evaluate("Ordres.interne.estTechnicien()"))
            page.evaluate(PREPARER_JS, OT)
            self.aller_fiche(page)
            self.assertIn(PART_TERMINEE, self.clore_techniquement(page))
        finally:
            contexte.close()

    def test_message_selon_le_profil(self):
        page = self.ouvrir_demo("responsable")
        self.assertNotIn(PART_TERMINEE, page.evaluate("() => Ordres.messageApresTransition({ id: 'OT-X' }, 'Clôturé techniquement')"))
        self.assertEqual(page.evaluate("() => Ordres.messageApresTransition({ id: 'OT-X' }, 'En cours')"), "OT-X : En cours.")
        # T554 : « Clore » (une fois) dit le libellé de P10.
        self.assertEqual(page.evaluate("() => Ordres.messageApresTransition({ id: 'OT-X' }, 'Clôturé administrativement', true)"), "OT-X : clôturé.")

    def test_technicien_en_equipe(self):
        page = self.ouvrir_demo("technicien", "TEC-0001")
        self.assertTrue(page.evaluate("Ordres.interne.estTechnicien()"))
        self.assertEqual(page.evaluate("() => Ordres.messageApresTransition({ id: 'OT-X' }, 'Clôturé techniquement')"),
                         "OT-X : Terminé, à valider. " + PART_TERMINEE)
        # Aucune phrase de plus pour une autre transition.
        self.assertEqual(page.evaluate("() => Ordres.messageApresTransition({ id: 'OT-X' }, 'En attente')"), "OT-X : En attente.")

    def test_responsable_clore_hors_solo_reste_clore_et_verrouiller(self):
        page = self.ouvrir_demo("responsable")
        page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
          const l = lignes.find((x) => x.cle === 'cloture_une_etape');
          if (l) l.valeur = '1'; else lignes.push({ cle: 'cloture_une_etape', valeur: '1' }); }, { action: 'essai' })""")
        self.aller_fiche(page)
        page.click("#ot-clore")
        page.wait_for_selector("dialog [name='compte_rendu']", state="visible")
        # L20 : le bouton dit ce qui manque (OT de la démo incomplet) ; rempli, il redevient « Clore et verrouiller ».
        self.assertTrue(page.text_content("dialog .fenetre-actions .btn-primaire").strip().startswith("Clore et verrouiller — il manque"))


class TestSolo(CasCloture):

    def test_solo_une_seule_cloture(self):
        page = self.ouvrir_demo("responsable")
        technicien = page.evaluate(PREPARER_JS, OT)
        page.evaluate("""(t) => Donnees.modifier('parametres', (lignes) => {
          const poser = (cle, valeur) => { const l = lignes.find((x) => x.cle === cle);
            if (l) l.valeur = valeur; else lignes.push({ cle, valeur }); };
          poser('mode_solo', '1'); poser('solo_technicien_id', t); poser('cloture_une_etape', '1'); }, { action: 'essai' })""", technicien)
        self.assertTrue(page.evaluate("App.modeSolo()"))
        self.aller_fiche(page)
        page.evaluate(NOTER_TOASTS_JS)
        page.click("#ot-clore")
        page.wait_for_selector("dialog [name='compte_rendu']", state="visible")
        self.assertEqual(page.text_content("dialog .fenetre-actions .btn-primaire").strip(), "Clore")         # tout est rempli d'avance
        fenetre = page.text_content("dialog")
        self.assertNotIn("verrouill", fenetre)
        self.assertNotIn("administrative", fenetre)
        page.check("dialog [name='remise_service']")
        self.assertEqual(page.text_content("dialog .fenetre-actions .btn-primaire").strip(), "Clore")
        page.click("dialog .fenetre-actions .btn-primaire")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé administrativement'", arg=OT)
        message = page.wait_for_function("() => window.__toasts.find((t) => / est clos\./.test(t)) || null").json_value()
        self.assertEqual(message, OT + " est clos.")


if __name__ == "__main__":
    unittest.main()
