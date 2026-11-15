"""Tests de L20 (lot 2 ergonomie, T553) : la fenêtre de clôture unique (js/modules/ordres-cloture.js).

Démo (file://) :
    - « Clôturer techniquement » (technicien en équipe) ouvre UNE fenêtre : date de fin à « maintenant », une étoile sur
      chaque champ exigé, la liste de ce qui manque EN HAUT (tenue à jour pendant la saisie), le bouton qui dit ce qui
      manque ; « Autre (préciser) » en tête des codes, le libellé en clair à côté du sigle ; pour une panne, « La
      machine était-elle arrêtée ? » ; un clic avec des manques n'écrit rien et dit les manques sous les champs ;
      rempli, l'OT est clôturé techniquement (temps, arrêt, codes, compte rendu écrits ; « Votre part est terminée ») ;
    - temps passé proposé d'après l'heure de début (arrondi au quart d'heure) quand rien n'est saisi ;
    - Ordres.manquesCloture et Ordres.verifierCloture disent la même chose (RG4, une seule règle) ;
    - « Clore » (responsable, réglage cloture_une_etape) ouvre la même fenêtre (liste des manques, étoiles).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_cloture_l20.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_statut_en_cours"]          # correctif « En cours », venu d'une demande
PART_TERMINEE = "Votre part est terminée. Le responsable validera."
FENETRE = "dialog.dialogue[open]"
BOUTON = FENETRE + " .fenetre-actions .btn-primaire"

# OT sans rien de la clôture (ni fin, ni temps, ni codes, ni compte rendu, ni case), commencé il y a 1 h 10.
VIDER_JS = """async (otId) => {
  const deux = (n) => String(n).padStart(2, '0');
  const d = new Date(Date.now() - 70 * 60000);
  const debut = d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate()) + ' ' + deux(d.getHours()) + ':' + deux(d.getMinutes());
  await Ordres.interne.modifierOt(otId, { date_debut: debut, date_fin: '', symptome_code: '', cause_code: '', remede_code: '',
    cause_precision: '', remede_precision: '', compte_rendu: '', remise_service: '0', arret_production: '0', duree_arret_h: '' }, 'essai');
  await Donnees.modifier('ot_temps', (lignes) => {
    for (let i = lignes.length - 1; i >= 0; i -= 1) if (lignes[i].ot_id === otId) lignes.splice(i, 1);
  }, { action: 'essai' });
  return Donnees.trouver('ordres_travail', otId).technicien_id;
}"""


class CasFenetre(CasNavigateur):

    def ouvrir_demo(self, profil, technicien_id=""):
        preregler_profil(self.contexte, profil, "Essai", technicien_id)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page

    def page_technicien(self):
        technicien = self.ouvrir_demo("responsable").evaluate(VIDER_JS, OT)
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        preregler_profil(contexte, "technicien", "Essai", technicien)
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        page.evaluate(VIDER_JS, OT)
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-actions")
        return page

    def manques(self, page):
        return [t.strip() for t in page.locator(FENETRE + " .ot-cloture-manques li").all_inner_texts()]


class TestFenetreTechnicien(CasFenetre):

    def test_une_fenetre_tout_marque_d_avance(self):
        page = self.page_technicien()
        page.click(".ot-actions [data-cible='Clôturé techniquement']")
        page.wait_for_selector(FENETRE + " [name='compte_rendu']", state="visible")
        fenetre = page.locator(FENETRE)
        # Date de fin à « maintenant » ; temps proposé d'après l'heure de début (1 h 10 → 1 h 15).
        maintenant = page.evaluate("Donnees.maintenant().replace(' ', 'T')")
        self.assertEqual(page.input_value(FENETRE + " [name='date_fin']"), maintenant)
        self.assertEqual(page.input_value(FENETRE + " [name='heures']").replace(" ", " "), "1 h 15")
        # Étoiles : fin, temps, cause, remède, compte rendu, case de sécurité.
        etoilees = page.evaluate("""(f) => Array.from(document.querySelectorAll(f + ' .requis'))
          .map((e) => (e.closest('.champ') ? e.closest('.champ').dataset.champ : '?'))""", FENETRE)
        self.assertEqual(sorted(etoilees), sorted(["date_fin", "heures", "cause_code", "remede_code", "compte_rendu", "remise_service"]))
        # « Autre (préciser) » en tête, le libellé en clair à côté du sigle.
        options = page.locator(FENETRE + " [name='cause_code'] option").all_inner_texts()
        self.assertEqual(options[1], "Autre (préciser)")
        self.assertRegex(options[2], r"^\S+ — \S")
        # Panne : la question de l'arrêt, en clair.
        self.assertIn("La machine était-elle arrêtée ?", fenetre.inner_text())
        self.assertFalse(page.is_visible(FENETRE + " [name='duree_arret_h']"))
        # Ce qui manque, en haut, et le bouton qui le dit.
        self.assertEqual(len(self.manques(page)), 4, self.manques(page))      # cause, remède, compte rendu, case
        self.assertEqual(page.inner_text(BOUTON).strip(), "Clôturer techniquement — il manque 4 éléments")
        self.assertLess(page.locator(FENETRE + " .ot-cloture-manques").bounding_box()["y"],
                        page.locator(FENETRE + " [name='date_fin']").bounding_box()["y"])
        # Un clic avec des manques : rien n'est écrit, les manques sont dits sous les champs.
        page.click(BOUTON)
        page.wait_for_selector(FENETRE + " .champ[data-champ='compte_rendu'].en-erreur")
        self.assertEqual(page.evaluate("(id) => Donnees.trouver('ordres_travail', id).statut", OT), "En cours")
        # La liste suit la saisie.
        cause = page.locator(FENETRE + " [name='cause_code'] option").nth(2).get_attribute("value")
        remede = page.locator(FENETRE + " [name='remede_code'] option").nth(2).get_attribute("value")
        page.select_option(FENETRE + " [name='cause_code']", cause)
        page.select_option(FENETRE + " [name='remede_code']", remede)
        page.fill(FENETRE + " [name='compte_rendu']", "Courroie usée remplacée, tension réglée.")
        self.assertEqual(len(self.manques(page)), 1)
        self.assertEqual(page.inner_text(BOUTON).strip(), "Clôturer techniquement — il manque 1 élément")
        page.check(FENETRE + " [name='remise_service']")
        self.assertIn("Tout ce qui est demandé est rempli.", page.inner_text(FENETRE + " .ot-cloture-manques"))
        self.assertEqual(page.inner_text(BOUTON).strip(), "Clôturer techniquement")
        # La machine était arrêtée 45 min.
        page.check(FENETRE + " [name='arret_production'][value='1']")
        page.fill(FENETRE + " [name='duree_arret_h']", "45 min")
        page.click(BOUTON)
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'", arg=OT)
        ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT)
        self.assertEqual((ot["cause_code"], ot["remede_code"], ot["remise_service"], ot["arret_production"], ot["duree_arret_h"]),
                         (cause, remede, "1", "1", "0.75"))
        self.assertEqual(page.evaluate("(id) => Donnees.lignes('ot_temps').filter((l) => l.ot_id === id).map((l) => l.heures)", OT), ["1.25"])
        page.wait_for_selector("#ot-message .alerte")
        self.assertIn(PART_TERMINEE, page.inner_text("#ot-message"))

    def test_manques_meme_regle_que_rg4(self):
        page = self.ouvrir_demo("responsable")
        page.evaluate(VIDER_JS, OT)
        resultat = page.evaluate("""(id) => { const ot = Donnees.trouver('ordres_travail', id);
          return [Ordres.verifierCloture(ot), Ordres.manquesCloture(ot)]; }""", OT)
        textes, details = resultat
        self.assertEqual(textes, [m["texte"] for m in details])
        self.assertEqual([m["champ"] for m in details],
                         ["date_fin", "heures", "cause_code", "remede_code", "compte_rendu", "remise_service"])


class TestFenetreClore(CasFenetre):

    def test_clore_meme_fenetre(self):
        page = self.ouvrir_demo("responsable")
        page.evaluate(VIDER_JS, OT)
        page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
          const l = lignes.find((x) => x.cle === 'cloture_une_etape');
          if (l) l.valeur = '1'; else lignes.push({ cle: 'cloture_une_etape', valeur: '1' }); }, { action: 'essai' })""")
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector("#ot-clore")
        page.click("#ot-clore")
        page.wait_for_selector(FENETRE + " [name='compte_rendu']", state="visible")
        self.assertEqual(len(self.manques(page)), 4)
        self.assertTrue(page.inner_text(BOUTON).strip().startswith("Clore et verrouiller — il manque"))
        self.assertGreaterEqual(page.locator(FENETRE + " .requis").count(), 6)


if __name__ == "__main__":
    unittest.main()
