"""Bilan du mois et tableau de bord (lot 2 ergonomie, T544, décision L30 ; défauts 1, 31, 36, 37 du retest).

Même mois d'essai que tests/test_rapport_bilan_mois.py (novembre 2026, calculé à la main ; horloge au 20/11/2026) :
Hugo Martin 45 €/h (3 h sur des OT clôturés), Karim Benali sans taux (2,5 h), FLX-HP 38,50 €, JT-12 sans prix.
    taux moyen    réglage du responsable (Paramètres, parametres.csv « taux_horaire_moyen ») : avec 40 €/h, Karim
                  compte 2,5 × 40 = 100 € ; le taux propre de Hugo passe avant (45) ; coût 135 + 100 + 38,50 = 273,50 € ;
                  même coût à la fiche de l'OT (Ordres.cout) qu'aux indicateurs ; heures-homme toujours dites (5,5 h).

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_bilan_l30.py" -v
"""
import unittest

import test_rapport_bilan_mois as base
from commun import attendre_pret, preregler_profil, url_fichier

blancs = base.blancs


class CasL30(base.CasBilan):

    PROFIL = ("responsable", "Responsable")
    DEPLIER = True                  # familles du tableau de bord dépliées sur ce poste (repliées d'office, L30)

    def ouvrir(self, tables=None):
        self.contexte.clock.set_fixed_time(self.HORLOGE)
        preregler_profil(self.contexte, *self.PROFIL)
        if self.DEPLIER:
            self.contexte.add_init_script(base.DEPLIER_FAMILLES_JS)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Test' });
          await Donnees.chargerTout();
        }""", tables or base.TABLES)

    def sans_taux_ni_prix(self):
        self.page.evaluate("""async () => {
            await Donnees.modifier('techniciens', (l) => { l.forEach((t) => { t.taux_horaire = ''; }); });
            await Donnees.modifier('articles', (l) => { l.forEach((a) => { a.prix_unitaire = ''; }); }); }""")

    def instrument_cout(self):
        self.page.evaluate("() => { location.hash = '#/indicateurs?periode=mois'; }")
        cout = self.page.locator('#contenu [data-indicateur="cout"]')
        cout.wait_for()
        return blancs(cout.inner_text())

    def regler_taux(self, valeur):
        self.page.evaluate("""async (valeur) => { await Donnees.modifier('parametres', (lignes) => {
            const ligne = lignes.find((l) => l.cle === 'taux_horaire_moyen');
            if (ligne) ligne.valeur = valeur; else lignes.push({ cle: 'taux_horaire_moyen', valeur }); }); }""", valeur)

    def cout_global(self):
        return self.page.evaluate("""() => { const g = Indicateurs.global(Indicateurs.periodeDuMois('2026-11'), {}, '2026-11-20');
            return { valeur: g.cout.valeur, heures: g.cout.heures }; }""")


class TestTauxMoyen(CasL30):

    def test_sans_taux_moyen_rien_ne_change(self):
        self.assertEqual(self.page.evaluate("() => Ordres.tauxHoraire(Donnees.trouver('techniciens', 'TEC-0002'))"), None)
        self.assertEqual(self.cout_global(), {"valeur": 173.5, "heures": 5.5})

    def test_taux_moyen_pour_le_technicien_sans_taux_propre(self):
        self.regler_taux("40")
        self.assertEqual(self.cout_global(), {"valeur": 273.5, "heures": 5.5})
        m = self.page.evaluate("""() => { const m = Indicateurs.manquesCout(Indicateurs.periodeDuMois('2026-11'));
            return [m.techniciens.length, m.articles.length]; }""")
        self.assertEqual(m, [0, 1])                                   # plus d'heures sans taux ; la pièce sans prix reste
        couts = self.page.evaluate("""() => Donnees.lignes('ordres_travail').map((ot) =>
            [ot.id, Indicateurs.interne.coutDeLOt(ot, Indicateurs.interne.contexte()), Ordres.cout(ot).total])""")
        for ot_id, indicateur, fiche in couts:
            self.assertEqual(indicateur, fiche, ot_id)
        self.assertEqual(dict((c[0], c[2]) for c in couts)["OT-2026-0002"], 80)          # 2 h × 40 (Karim)
        self.assertEqual(dict((c[0], c[2]) for c in couts)["OT-2026-0004"], 45)          # 1 h × 45 (Hugo : son taux)

    def test_un_taux_illisible_ou_negatif_n_est_pas_un_taux(self):
        for valeur in ("abc", "-5", ""):
            self.regler_taux(valeur)
            self.assertIsNone(self.page.evaluate("() => Ordres.tauxHoraire(Donnees.trouver('techniciens', 'TEC-0002'))"), valeur)

    def test_heures_homme_au_bilan_et_au_tableau_de_bord(self):
        r = self.donnees()
        self.assertEqual(blancs(self.tuile(r, "cout")["heuresHomme"]), "5,5 h de main-d'œuvre")
        page = blancs(self.page.evaluate("() => Rapport.html('2026-11', { apercu: true })"))
        self.assertIn('<div class="heures-homme">5,5 h de main-d\'œuvre</div>', page)
        self.assertIn("5,5 h de main-d'œuvre", blancs(r["courriel"]["corps"]))
        self.page.evaluate("() => { location.hash = '#/indicateurs?periode=mois'; }")
        cout = self.page.locator('#contenu [data-indicateur="cout"]')
        cout.wait_for()
        self.assertIn("5,5 h de main-d'œuvre", blancs(cout.inner_text()))

    def test_reglage_dans_parametres(self):
        self.page.evaluate("() => { location.hash = '#/parametres'; }")
        champ = self.page.locator('#form-parametres [name="taux_horaire_moyen"]')
        champ.wait_for()
        self.assertEqual(champ.input_value(), "")
        self.page.click("#form-parametres button[type=submit]")                    # vide : permis, rien de supposé
        self.page.wait_for_function("() => Donnees.lignes('parametres').some((l) => l.cle === 'tolerance_preventif_pct')")
        self.assertEqual(self.page.evaluate("() => (Donnees.trouver('parametres', 'taux_horaire_moyen') || {}).valeur"), "")
        champ.fill("38,5")
        self.page.click("#form-parametres button[type=submit]")
        self.page.wait_for_function("() => Donnees.parametre('taux_horaire_moyen', '') === '38.5'")
        champ.fill("-3")
        self.page.click("#form-parametres button[type=submit]")
        self.page.locator('#form-parametres [name="taux_horaire_moyen"][aria-invalid="true"]').wait_for()
        self.assertEqual(self.page.evaluate("() => Donnees.parametre('taux_horaire_moyen', '')"), "38.5")


class TestNonChiffreAuTableauDeBord(CasL30):
    """Défaut 36 : « 0,00 € » au tableau de bord contre « non chiffré » au rapport du même mois."""

    def test_aucun_taux_ni_prix_non_chiffre_comme_le_bilan(self):
        self.sans_taux_ni_prix()
        cout = self.instrument_cout()
        self.assertNotIn("0,00 €", cout)
        self.assertIn("non chiffré", cout)
        self.assertIn("5,5 h sans taux horaire (Paramètres ou Équipe), 2 pièces sans prix (Magasin)", cout)
        self.assertIn("5,5 h de main-d'œuvre", cout)
        self.assertEqual(self.page.get_attribute('#contenu [data-indicateur="cout"]', "data-valeur"), "")
        self.assertEqual(self.tuile(self.donnees(), "cout")["texteValeur"], "non chiffré")      # le bilan dit pareil
        # Tableau par équipement : PI-01 et CP-01 (heures sans taux) ne disent plus 0,00 €.
        lignes = self.page.locator("#contenu .indicateurs-equipements tbody tr")
        textes = [blancs(texte) for texte in lignes.all_inner_texts()]
        for repere in ("PI-01", "CP-01"):
            ligne = [texte for texte in textes if repere in texte]
            self.assertEqual(len(ligne), 1, textes)
            self.assertIn("non chiffré", ligne[0], repere)
            self.assertNotIn("0,00 €", ligne[0], repere)

    def test_cout_partiel_garde_son_montant(self):
        cout = self.instrument_cout()
        self.assertIn("173,50 €", cout)
        self.assertIn("Partiel : 2,5 h sans taux horaire (Paramètres ou Équipe), 1 pièce sans prix (Magasin)", cout)

    def test_complet_avec_le_taux_moyen(self):
        self.regler_taux("40")
        self.page.evaluate("""async () => { await Donnees.modifier('articles', (l) => { l.forEach((a) => { a.prix_unitaire = a.prix_unitaire || '2'; }); }); }""")
        cout = self.instrument_cout()
        self.assertIn("277,50 €", cout)                                # 135 + 100 + 38,50 + 2 × 2
        self.assertNotIn("Partiel", cout)
        self.assertNotIn("non chiffré", cout)


class TestNonChiffreDirection(TestNonChiffreAuTableauDeBord):
    """La direction voit les coûts (T520) : elle a aussi la réserve (avant : « 0,00 € » sans réserve)."""

    PROFIL = ("direction", "")


class TestDeuxLignesDuBilan(CasL30):
    """Défaut 1 : le patron cherche les retards et le délai de prise en charge ; mêmes calculs qu'au tableau de bord."""

    def test_ot_en_retard_et_delai_de_prise_en_charge(self):
        # OT-1 P1 (créé 08:00, démarré 08:15 : 0,25 h), OT-3 P1 (07:30 → 08:00 : 0,5 h), OT-2 P2 (04/11 09:00 → 05/11
        # 08:00 : 23 h) ; un OT ouvert prévu le 15/11 : en retard au 20/11.
        self.page.evaluate("""async () => { await Donnees.modifier('ordres_travail', (lignes) => {
            const p = { 'OT-2026-0001': 'P1', 'OT-2026-0002': 'P2', 'OT-2026-0003': 'P1', 'OT-2026-0004': 'P3' };
            lignes.forEach((ot) => { ot.priorite = p[ot.id]; ot.date_prevue = ''; });
            lignes.push({ id: 'OT-2026-0005', equipement_id: 'EQ-0002', type: 'correctif différé', statut: 'Planifié',
              titre: 'Graissage', date_creation: '2026-11-12 10:00', date_prevue: '2026-11-15', priorite: 'P3', arret_production: '0' }); }); }""")
        r = self.donnees()
        phrases = [blancs(p) for p in r["phrases"]]
        self.assertIn("1 OT en retard au 20/11/2026", phrases)
        self.assertIn("délai de prise en charge (médiane) : P1 0,4 h (2 OT), P2 23 h (1 OT), P3 0 h (1 OT)", phrases)
        g = self.page.evaluate("""() => { const g = Indicateurs.global(Indicateurs.periodeDuMois('2026-11'), {}, '2026-11-20');
            return [g.otEnRetard.valeur, g.delais.P1.mediane, g.delais.P2.mediane]; }""")
        self.assertEqual(g, [1, 0.375, 23])                               # le tableau de bord, même calcul
        page = blancs(self.page.evaluate("() => Rapport.html('2026-11', { apercu: true })"))
        self.assertIn("1 OT en retard au 20/11/2026", page)
        self.assertIn("délai de prise en charge (médiane) : P1 0,4 h (2 OT)", page)
        self.assertIn("1 OT en retard au 20/11/2026", blancs(r["courriel"]["corps"]))


class TestTousLesMoisEtEnregistrer(CasL30):
    """Défaut 31 : « Voir le bilan » ne proposait que le mois en cours et le premier mois ; « Figer » faisait hésiter."""

    HORLOGE = "2027-01-04T09:00:00"

    def test_tous_les_mois_qui_ont_des_donnees(self):
        self.page.evaluate("""async () => { await Donnees.modifier('ordres_travail', (lignes) => {
            lignes.push({ id: 'OT-2026-0009', equipement_id: 'EQ-0002', type: 'amélioration', statut: 'Créé', titre: 'Carter',
              date_creation: '2026-12-05 10:00', arret_production: '0' }); }); }""")
        self.page.evaluate("() => { location.hash = '#/indicateurs?onglet=rapports'; }")
        self.page.locator("#rapports-apercu-mois").wait_for()
        self.assertEqual(self.page.locator("#rapports-apercu-mois option").all_inner_texts(),
                         ["janvier 2027 (en cours)", "décembre 2026", "novembre 2026 (premier mois d'utilisation)"])
        self.page.select_option("#rapports-apercu-mois", "2026-12")
        with self.page.expect_popup() as attente:
            self.page.click(".rapports-apercu-formulaire button[type=submit]")
        fenetre = attente.value
        fenetre.wait_for_load_state()
        self.assertIn("décembre 2026", blancs(fenetre.frame_locator("iframe").locator("body").inner_text()))
        self.assertEqual(self.page.evaluate("() => Rapport.rapportsFiges()"), [])

    def test_enregistrer_ce_bilan_avec_sa_phrase(self):
        self.page.evaluate("() => { location.hash = '#/indicateurs?onglet=rapports'; }")
        carte = self.page.locator(".rapports-figer")
        carte.wait_for()
        texte = blancs(carte.inner_text())
        self.assertIn("Enregistrer le bilan d'un mois", texte)
        self.assertIn("Les chiffres de ce mois ne changeront plus, même si un OT est corrigé ensuite.", texte)
        self.assertEqual(blancs(carte.locator("button[type=submit]").inner_text()), "Enregistrer ce bilan")
        self.assertNotIn("Figer", texte)
        carte.locator("button[type=submit]").click()
        self.page.wait_for_function("() => Rapport.rapportsFiges().length === 1")
        bandeau = self.page.locator("#rapports-message")
        bandeau.wait_for()
        self.assertIn("Bilan de décembre 2026 enregistré", blancs(bandeau.inner_text()))
        self.assertIn("Bilans enregistrés", blancs(self.page.inner_text(".rapports-liste")))


class TestTeteDuTableauDeBord(CasL30):
    """Défaut 37 : tableau de bord de 10 à 13 écrans ; en tête les quatre chiffres du bilan, le reste replié par famille."""

    DEPLIER = False
    FAMILLES = ["fiabilite", "preventif", "retards", "couts", "heures", "equipements"]

    def tete(self):
        tete = self.page.locator("#contenu .indicateurs-tete")
        tete.wait_for()
        return {cle: blancs(tete.locator('[data-tete="%s"]' % cle).inner_text()) for cle in
                ("disponibilite", "heures-cout", "pannes", "preventif")}

    def test_quatre_chiffres_en_tete_le_reste_replie(self):
        self.page.evaluate("() => { location.hash = '#/indicateurs?periode=mois'; }")
        tete = self.tete()
        self.assertIn("à compléter", tete["disponibilite"])                       # D35 : rien de supposé
        self.assertIn("5,5 h", tete["heures-cout"])
        self.assertIn("coût : 173,50 € · Partiel : 2,5 h sans taux horaire", tete["heures-cout"])
        self.assertIn("1,5 h d'arrêt", tete["pannes"])
        self.assertTrue(tete["pannes"].split("\n")[1].strip() == "1" or "\n1\n" in tete["pannes"], tete["pannes"])
        self.assertIn("18,2 %", tete["preventif"])
        familles = self.page.eval_on_selector_all("#contenu details.indicateurs-famille", "ds => ds.map((d) => [d.dataset.famille, d.open])")
        self.assertEqual(familles, [[f, False] for f in self.FAMILLES])
        self.assertFalse(self.page.is_visible('#contenu [data-indicateur="mtbf"]'))
        self.assertFalse(self.page.is_visible("#contenu .indicateurs-delais"))

    def test_non_chiffre_en_tete(self):
        self.sans_taux_ni_prix()
        self.page.evaluate("() => { location.hash = '#/indicateurs?periode=mois'; }")
        self.assertIn("coût non chiffré (5,5 h sans taux horaire", self.tete()["heures-cout"])

    def test_famille_ouverte_gardee_sur_ce_poste(self):
        self.page.evaluate("() => { location.hash = '#/indicateurs?periode=mois'; }")
        self.tete()
        self.page.click('#contenu details[data-famille="retards"] > summary')
        self.page.locator("#contenu .indicateurs-delais").wait_for()
        self.assertEqual(self.page.evaluate("() => JSON.parse(localStorage.getItem('prevo.indicateurs.familles'))"), ["retards"])
        self.page.evaluate("() => { location.hash = '#/indicateurs?periode=3-mois'; }")    # autre période : réaffiché
        self.page.wait_for_function("() => document.querySelector('#contenu .indicateurs-resultats').dataset.periode === '3-mois'")
        ouvertes = self.page.eval_on_selector_all("#contenu details.indicateurs-famille[open]", "ds => ds.map((d) => d.dataset.famille)")
        self.assertEqual(ouvertes, ["retards"])
        self.page.click('#contenu details[data-famille="retards"] > summary')
        self.page.wait_for_function("() => JSON.parse(localStorage.getItem('prevo.indicateurs.familles')).length === 0")


class TestDirectionArriveSurLesQuatreChiffres(CasL30):

    PROFIL = ("direction", "")
    DEPLIER = False

    def test_accueil_de_la_direction(self):
        self.page.evaluate("() => { location.hash = '#/parc'; }")                     # accueil réaffiché sur le mois d'essai
        self.page.wait_for_function("() => !document.querySelector('#contenu .accueil-direction-tete')")
        self.page.evaluate("() => { location.hash = '#/accueil'; }")
        tete = self.page.locator("#contenu .accueil-direction-tete")
        tete.wait_for()
        texte = blancs(tete.inner_text())
        self.assertIn("Ce mois-ci : ", texte)
        for attendu in ("Disponibilité", "à compléter", "Heures et coût", "5,5 h", "Pannes", "1,5 h d'arrêt", "Part du préventif", "18,2 %"):
            self.assertIn(attendu, texte)
        self.assertTrue(self.page.is_visible('#contenu a[href="#/indicateurs"]'))      # le tableau de bord reste à un clic


if __name__ == "__main__":
    unittest.main()
