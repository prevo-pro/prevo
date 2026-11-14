"""Tests de L21 (lot 2 ergonomie, défaut n° 29) : temps passé et durée d'arrêt saisis « comme à l'atelier ».

    - UI.lireDuree comprend « 1h15 », « 1 h 15 », « 1:15 », « 75 min », « 1,25 » et « 1.25 » (→ 1,25 h) ;
      une saisie non comprise → null ;
    - UI.heures montre « 1 h 15 », « 2 h », « 45 min » (un seul formateur, dans la langue de l'écran) ;
    - un champ durée (UI.champ type « duree », ou champ décimal du schéma marqué duree) : lu en heures décimales,
      valeur gardée et non retouchée rendue telle quelle, message clair si la saisie n'est pas comprise ;
    - fenêtre « Clore » (démo, file://) : « 1h15 » de temps passé et « 1:30 » d'arrêt → ot_temps.heures = 1.25 et
      duree_arret_h = 1.5 (CSV inchangés : heures décimales) ; « deux heures » refusé, rien d'écrit.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_duree_l21.py" -v
"""
import re
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, scenarios_demo, url_fichier

GUIDE = "tests/fixtures/guide-style.html"
OT = scenarios_demo()["ot_statut_en_cours"]          # correctif « En cours »
ESPACES = re.compile("[  ]")


def simple(texte):
    return ESPACES.sub(" ", texte)


class TestLectureEtAffichage(CasNavigateur):

    def setUp(self):
        super().setUp()
        self.page.goto(url_fichier(GUIDE))
        self.page.wait_for_function("() => typeof UI !== 'undefined' && typeof I18n !== 'undefined'")

    def test_saisies_comprises(self):
        for saisie in ("1h15", "1 h 15", "1H15", "1 h 15 min", "1:15", "75 min", "75min", "1,25", "1.25"):
            with self.subTest(saisie=saisie):
                self.assertAlmostEqual(self.page.evaluate("(t) => UI.lireDuree(t)", saisie), 1.25)
        for saisie, attendu in (("2 h", 2), ("45 min", 0.75), ("0:45", 0.75), ("1h05", 65 / 60), ("90m", 1.5)):
            with self.subTest(saisie=saisie):
                self.assertAlmostEqual(self.page.evaluate("(t) => UI.lireDuree(t)", saisie), attendu)

    def test_saisies_non_comprises(self):
        for saisie in ("", "deux heures", "1h75", "1,5 h 15", "-1", "1:5:0"):
            with self.subTest(saisie=saisie):
                self.assertIsNone(self.page.evaluate("(t) => UI.lireDuree(t)", saisie))

    def test_affichage_heures_minutes(self):
        for valeur, attendu in (("1.25", "1 h 15"), ("2", "2 h"), ("0.75", "45 min"), ("0", "0 h"), ("1.3333", "1 h 20"),
                                ("1500.5", "1 500 h 30"), ("", "–"), ("abc", "–")):
            with self.subTest(valeur=valeur):
                self.assertEqual(simple(self.page.evaluate("(v) => UI.heures(v)", valeur)), attendu)
        self.assertEqual(self.page.evaluate("() => UI.dureeEnTexte(UI.lireDuree('1h20'))"), "1.33")

    def test_champ_duree_lu_en_heures_decimales(self):
        resultat = self.page.evaluate("""() => {
          const form = document.createElement('form');
          form.appendChild(UI.champ({ nom: 'a', type: 'duree' }, ''));
          form.appendChild(UI.champ({ nom: 'b', type: 'decimal', duree: true }, '1.3333'));
          form.appendChild(UI.champ({ nom: 'c', type: 'duree' }, ''));
          document.body.appendChild(form);
          const affichee = form.elements.b.value;
          form.elements.a.value = '1h15';
          form.elements.c.value = 'deux heures';
          const valeurs = UI.lireFormulaire(form);
          const erreurs = UI.verifierFormulaire(form);
          form.remove();
          return { affichee, valeurs, erreurs };
        }""")
        self.assertEqual(simple(resultat["affichee"]), "1 h 20")
        self.assertEqual(resultat["valeurs"]["a"], "1.25")
        self.assertEqual(resultat["valeurs"]["b"], "1.3333")          # montrée « 1 h 20 », non retouchée : gardée
        self.assertEqual([e["nom"] for e in resultat["erreurs"]], ["c"])
        self.assertIn("1h15", resultat["erreurs"][0]["message"])
        self.assertIn("75 min", resultat["erreurs"][0]["message"])


class TestClore(CasNavigateur):

    def ouvrir(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        page.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
          const ligne = lignes.find((l) => l.cle === 'cloture_une_etape');
          if (ligne) ligne.valeur = '1'; else lignes.push({ cle: 'cloture_une_etape', valeur: '1' });
        }, { action: 'essai' })""")
        page.wait_for_function("() => Ordres.clotureUneEtape()")
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector("#ot-clore")
        return page

    def remplir(self, page, heures, arret):
        page.click("#ot-clore")
        page.wait_for_selector("dialog [name='compte_rendu']", state="visible")
        page.check("dialog [name='arret_production']")
        page.fill("dialog [name='duree_arret_h']", arret)
        page.fill("dialog [name='heures']", heures)
        technicien = page.evaluate("(id) => Donnees.trouver('ordres_travail', id).technicien_id || "
                                   "Donnees.lignes('techniciens').find((t) => t.actif !== '0').id", OT)
        page.select_option("dialog [name='technicien_id']", technicien)
        page.evaluate("""() => {
          for (const nom of ['symptome_code', 'cause_code', 'remede_code']) {
            const liste = document.querySelector("dialog [name='" + nom + "']");
            if (liste) { const option = Array.from(liste.options).find((o) => o.value); if (option) liste.value = option.value; }
          }
        }""")
        page.fill("dialog [name='compte_rendu']", "Roulement grippé remplacé, essai à vide concluant.")
        page.check("dialog [name='remise_service']")
        page.click("dialog .fenetre-actions .btn-primaire")

    def test_clore_avec_1h15_et_1_30(self):
        page = self.ouvrir()
        self.remplir(page, "1h15", "1:30")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé administrativement'", arg=OT)
        ot = page.evaluate("(id) => Donnees.trouver('ordres_travail', id)", OT)
        self.assertEqual(ot["duree_arret_h"], "1.5")
        temps = page.evaluate("(id) => Donnees.lignes('ot_temps').filter((l) => l.ot_id === id).map((l) => l.heures)", OT)
        self.assertIn("1.25", temps)

    def test_duree_non_comprise_rien_d_ecrit(self):
        page = self.ouvrir()
        avant = page.evaluate("(id) => JSON.stringify(Donnees.trouver('ordres_travail', id))", OT)
        self.remplir(page, "deux heures", "1,5")
        page.wait_for_selector("dialog .champ[data-champ='heures'] .erreur-champ:not([hidden])")
        self.assertIn("Durée non comprise", page.text_content("dialog .champ[data-champ='heures'] .erreur-champ"))
        self.assertEqual(page.evaluate("(id) => JSON.stringify(Donnees.trouver('ordres_travail', id))", OT), avant)


if __name__ == "__main__":
    unittest.main()
