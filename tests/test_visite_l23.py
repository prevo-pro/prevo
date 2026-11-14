"""Tests de L23 (lot 2 ergonomie, défauts n° 9 et 30) : clôture d'une visite préventive (js/modules/ordres-cloture.js),
sans l'écran de clôture unique (L20, seconde livraison).

Démo (file://), profil Responsable, OT préventif ouvert du jeu de démo (gamme périodique, déclencheur date) :
    - liste de contrôle toute cochée, sans anomalie : le compte rendu est montré rempli d'office (« Visite faite, rien à
      signaler. », modifiable) et le temps passé proposé d'après le temps prévu ; « Clôturer techniquement » avec la
      seule case de remise en service (et la date de fin) clôt l'OT : compte rendu écrit, temps ajouté, « Prochaine
      visite : le … » dit (toast et message) ;
    - la case de remise en service reste exigée ;
    - anomalie constatée : rien n'est écrit d'office (compte rendu à écrire) ; après la clôture, l'OT de réparation est
      proposé (« Créer l'OT de réparation », nouvel OT pré-rempli sur le même équipement) ;
    - fenêtre « Clore » (clôture en une étape) : compte rendu et temps proposés de la même façon.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_visite_l23.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_preventif_ouvert"]
RIEN_A_SIGNALER = "Visite faite, rien à signaler."

# Visite prête à clore : En cours, liste de contrôle toute cochée (une ligne au moins), sans anomalie, compte rendu
# vide, aucun temps, date de fin passée, gamme périodique (date) avec un temps prévu de 1,5 h. Rend la gamme.
PREPARER_JS = """async ([otId, anomalie]) => {
  let ot = Donnees.trouver('ordres_travail', otId);
  const deux = (n) => String(n).padStart(2, '0');
  const quand = (h) => { const d = new Date(Date.now() - h * 3600000);
    return d.getFullYear() + '-' + deux(d.getMonth() + 1) + '-' + deux(d.getDate()) + ' ' + deux(d.getHours()) + ':' + deux(d.getMinutes()); };
  await Donnees.modifier('gammes', (lignes) => { const g = lignes.find((l) => l.id === ot.gamme_id);
    g.declencheur = 'date'; g.periodicite_jours = '30'; g.temps_prevu_h = '1.5'; g.actif = '1'; }, { action: 'essai' });
  await Donnees.modifier('ordres_travail', (lignes) => { const l = lignes.find((x) => x.id === otId);
    l.statut = 'En cours'; l.date_debut = quand(3); l.date_fin = ''; l.compte_rendu = ''; l.remise_service = '0';
    l.temps_prevu_h = '1.5'; l.anomalie_constatee = anomalie ? '1' : '0'; }, { action: 'essai' });
  await Donnees.modifier('ot_temps', (lignes) => { for (let i = lignes.length - 1; i >= 0; i -= 1) if (lignes[i].ot_id === otId) lignes.splice(i, 1); },
    { action: 'essai' });
  await Donnees.modifier('ot_operations', (lignes, outils) => {
    if (!lignes.some((l) => l.ot_id === otId)) lignes.push({ id: outils.nouvelId(lignes), ot_id: otId, ordre: '1', operation: 'Contrôle', valeur_attendue: '', fait: '0', valeur_mesuree: '' });
    lignes.filter((l) => l.ot_id === otId).forEach((l) => { l.fait = '1'; });
  }, { action: 'essai' });
  await Ordres.interne.modifierOt(otId, { date_fin: quand(1) }, 'essai');
  return { gamme: ot.gamme_id, temps: Donnees.lignes('ot_temps').filter((l) => l.ot_id === otId).length };
}"""


class CasVisite(CasNavigateur):

    def ouvrir(self, anomalie=False, une_etape=False):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        etat = page.evaluate(PREPARER_JS, [OT, anomalie])
        self.assertTrue(etat["gamme"])
        self.temps_avant = etat["temps"]
        if une_etape:
            page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
              const l = lignes.find((x) => x.cle === 'cloture_une_etape');
              if (l) l.valeur = '1'; else lignes.push({ cle: 'cloture_une_etape', valeur: '1' }); }, { action: 'essai' })""")
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-actions")
        return page

    def onglet(self, page, nom, selecteur):
        """Fiche réaffichée (données écrites par le test), puis l'onglet `nom` ouvert."""
        page.evaluate("App.reafficher()")
        page.wait_for_selector(".onglet[data-onglet='%s']" % nom)
        page.click(".onglet[data-onglet='%s']" % nom)
        page.wait_for_selector(selecteur)

    def ot(self, page):
        return page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT)

    def temps(self, page):
        return page.evaluate("(id) => Donnees.lignes('ot_temps').filter((l) => l.ot_id === id).map((l) => l.heures)", OT)


class TestRegles(CasVisite):

    def test_regles(self):
        page = self.ouvrir()
        ot = self.ot(page)
        self.assertTrue(page.evaluate("(ot) => Ordres.visiteSansAnomalie(ot)", ot))
        self.assertEqual(page.evaluate("(ot) => Ordres.interne.compteRenduDOffice(ot)", ot), RIEN_A_SIGNALER)
        self.assertEqual(page.evaluate("(ot) => Ordres.interne.tempsPropose(ot)", ot), "1.5")
        # Une opération non cochée, ou une anomalie : rien d'office.
        self.assertFalse(page.evaluate("(ot) => Ordres.visiteSansAnomalie(Object.assign({}, ot, { anomalie_constatee: '1' }))", ot))
        self.assertEqual(page.evaluate("(ot) => Ordres.interne.compteRenduDOffice(Object.assign({}, ot, { compte_rendu: 'Déjà écrit.' }))", ot), "")


class TestClotureEquipe(CasVisite):

    def test_tout_coche_case_seule_cloture_avec_prochaine_visite(self):
        page = self.ouvrir()
        # Onglet Exécution : le temps est proposé d'après le temps prévu ; onglet Compte rendu : rempli d'office.
        self.onglet(page, "execution", "#ot-temps-heures")
        self.assertEqual(page.input_value("#ot-temps-heures").replace("\u00a0", " "), "1 h 30")
        self.onglet(page, "compte-rendu", "#form-compte-rendu [name='compte_rendu']")
        self.assertEqual(page.input_value("#form-compte-rendu [name='compte_rendu']"), RIEN_A_SIGNALER)
        # La case de remise en service reste exigée : sans elle, refus (le temps proposé et le compte rendu d'office,
        # eux, sont pris au clic, comme une saisie de la fiche).
        page.click("#form-compte-rendu [data-cible='Clôturé techniquement']")
        page.wait_for_selector("#ot-message .alerte")
        self.assertIn("remis en service", page.inner_text("#ot-message"))
        self.assertEqual(self.ot(page)["statut"], "En cours")
        self.assertEqual(self.temps(page), ["1.5"])
        # Case cochée, puis « Clôturer techniquement » : l'OT est clos, rien de doublé.
        page.check("#form-compte-rendu [name='remise_service']")
        page.click("#form-compte-rendu [data-cible='Clôturé techniquement']")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'", arg=OT)
        ot = self.ot(page)
        self.assertEqual(ot["compte_rendu"], RIEN_A_SIGNALER)
        self.assertEqual(self.temps(page), ["1.5"])
        page.wait_for_selector("#ot-message .alerte")
        message = page.inner_text("#ot-message")
        gamme = page.evaluate("(id) => Donnees.trouver('gammes', Donnees.trouver('ordres_travail', id).gamme_id).prochaine_echeance", OT)
        jour = gamme[8:10] + "/" + gamme[5:7] + "/" + gamme[0:4]
        self.assertIn("Prochaine visite : le %s." % jour, message)

    def test_anomalie_compte_rendu_a_ecrire_et_reparation_proposee(self):
        page = self.ouvrir(anomalie=True)
        self.onglet(page, "compte-rendu", "#form-compte-rendu [name='compte_rendu']")
        self.assertEqual(page.input_value("#form-compte-rendu [name='compte_rendu']"), "")
        page.evaluate("""(id) => Ordres.interne.modifierOt(id, { remise_service: '1',
          compte_rendu: 'Courroie fissurée, à changer au prochain arrêt.' }, 'essai')""", OT)
        page.evaluate("""(id) => Ordres.interne.modifierLieeAOt(id, 'ot_temps', (lignes, outils) => {
          lignes.push({ id: outils.nouvelId(lignes), ot_id: id, technicien_id: 'TEC-0001', date: '2026-01-01', heures: '1' }); },
          { action: 'essai' })""", OT)
        self.onglet(page, "compte-rendu", "#form-compte-rendu [data-cible='Clôturé techniquement']")
        page.click("#form-compte-rendu [data-cible='Clôturé techniquement']")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'", arg=OT)
        page.wait_for_selector("#ot-reparation")
        self.assertIn("Créer l'OT de réparation", page.inner_text("#ot-reparation"))
        adresse = page.get_attribute("#ot-reparation", "href")
        equipement = self.ot(page)["equipement_id"]
        self.assertTrue(adresse.startswith("#/ot/nouveau?equipement=" + equipement), adresse)
        page.click("#ot-reparation")
        page.wait_for_selector("#form-nouvel-ot [name='titre']")
        self.assertIn(OT, page.input_value("#form-nouvel-ot [name='titre']"))


class TestClore(CasVisite):

    def test_fenetre_clore_propose_compte_rendu_et_temps(self):
        page = self.ouvrir(une_etape=True)
        page.click("#ot-clore")
        page.wait_for_selector("dialog [name='compte_rendu']", state="visible")
        self.assertEqual(page.input_value("dialog [name='compte_rendu']"), RIEN_A_SIGNALER)
        self.assertEqual(page.input_value("dialog [name='heures']").replace("\u00a0", " "), "1 h 30")
        page.check("dialog [name='remise_service']")
        page.click("dialog .fenetre-actions .btn-primaire")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé administrativement'", arg=OT)
        self.assertEqual(self.ot(page)["compte_rendu"], RIEN_A_SIGNALER)
        self.assertIn("1.5", self.temps(page))


if __name__ == "__main__":
    unittest.main()
