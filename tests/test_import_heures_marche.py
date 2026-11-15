"""Heures de marche des machines à l'import (lot 2 ergonomie, T544, décision L30 ; défaut 1 du retest : la disponibilité
du bilan reste « à compléter » parce que les heures par jour des machines n'ont jamais été demandées).

Démo (file://), import de tests/fixtures/import/equipements.xlsx (5 machines créées, 1 mise à jour, sans colonne
d'heures) jusqu'à l'étape 5 « Importer » :
    question     « Combien d'heures par jour tournent vos machines ? », vide (aucune valeur proposée), avec le nombre
                 de machines importées qui n'en ont pas ;
    réponse      16 : donnée aux machines créées ou mises à jour qui n'en ont pas, jamais aux autres ni à la place d'une
                 valeur ; saisie fausse : dite sous le champ, rien n'est écrit ;
    passée       champ laissé vide : rien n'est supposé (heures vides) ; la question part une fois l'import fait.

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_import_heures_marche.py" -v
"""
import unittest

import test_import_ecrans as base

HEURES_JS = "() => Object.fromEntries(Donnees.lignes('equipements').map((e) => [e.id, e.heures_fonct_jour || '']))"
CHAMP = '#contenu [name="import_heures_jour"]'


class TestHeuresDeMarche(base.CasImport):

    def jusqu_a_importer(self):
        self.ouvrir_demo()
        self.jusqu_a_l_apercu("equipements", fichier="equipements.xlsx")
        self.continuer(5)
        return self.page.evaluate(HEURES_JS)

    def importees(self, avant):
        """Machines créées, et machines existantes que l'aperçu met à jour."""
        apercu = self.page.evaluate("() => { const e = Import.assistant.etat().apercu.ecritures.equipements;"
                                    " return [e.creer.map((l) => l.id), e.modifier.map((m) => m.id)]; }")
        return apercu[0], apercu[1]

    def test_question_sans_valeur_proposee(self):
        avant = self.jusqu_a_importer()
        creees, modifiees = self.importees(avant)
        attendu = len(creees) + len([i for i in modifiees if not avant[i]])
        self.assertGreater(attendu, 0)
        bloc = self.page.locator("#contenu .import-heures-marche")
        self.assertIn("Combien d'heures par jour tournent vos machines ?", bloc.inner_text())
        self.assertIn("%d machines importées n'ont pas d'heures de marche par jour" % attendu, bloc.inner_text())
        self.assertEqual(self.page.input_value(CHAMP), "")

    def test_reponse_donnee_aux_seules_machines_importees_sans_heures(self):
        avant = self.jusqu_a_importer()
        creees, modifiees = self.importees(avant)
        self.page.fill(CHAMP, "25")
        self.page.click("#import-importer")
        self.page.wait_for_selector('#contenu .import-heures-marche [aria-invalid="true"]')
        self.assertEqual(self.page.evaluate(HEURES_JS), avant, "saisie fausse : rien n'est écrit")
        self.page.fill(CHAMP, "16")
        self.importer()
        apres = self.page.evaluate(HEURES_JS)
        for identifiant in creees:
            self.assertEqual(apres[identifiant], "16", identifiant)
        for identifiant, heures in avant.items():
            attendu = "16" if identifiant in modifiees and not heures else heures
            self.assertEqual(apres[identifiant], attendu, identifiant)
        self.assertEqual(self.page.locator("#contenu .import-heures-marche").count(), 0)

    def test_valeur_de_l_assistant_proposee_d_office(self):
        """T559 (P04.1) : heures_marche_proposees (posé par l'assistant sans machine) remplit la question, avec sa phrase ;
        elle s'applique telle quelle à l'import, ou se change."""
        self.ouvrir_demo()
        self.page.evaluate("() => Donnees.modifier('parametres', (lignes) => { lignes.push({ cle: 'heures_marche_proposees', valeur: '7.5' }); })")
        self.jusqu_a_l_apercu("equipements", fichier="equipements.xlsx")
        self.continuer(5)
        avant = self.page.evaluate(HEURES_JS)
        creees, _ = self.importees(avant)
        self.assertEqual(self.page.input_value(CHAMP).replace(",", "."), "7.5")
        self.assertIn("Proposé d'après votre réponse à l'installation", self.page.locator("#contenu .import-heures-marche").inner_text())
        self.importer()
        apres = self.page.evaluate(HEURES_JS)
        for identifiant in creees:
            self.assertEqual(apres[identifiant], "7.5", identifiant)

    def test_question_passee_rien_n_est_suppose(self):
        avant = self.jusqu_a_importer()
        creees, _ = self.importees(avant)
        self.importer()
        apres = self.page.evaluate(HEURES_JS)
        self.assertEqual([apres[i] for i in creees], [""] * len(creees))
        self.assertEqual({i: h for i, h in apres.items() if i in avant}, avant)


if __name__ == "__main__":
    unittest.main()
