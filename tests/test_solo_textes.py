"""Textes du mode Solo (lot 2 ergonomie, T546, décision L33 ; défauts n° 20 et 33 du retest).

Une personne seule est à la fois responsable et technicien, sans menu Équipe :
    - consignation sans procédure (fiche d'un OT, fiche de la machine) : « Aucune procédure de consignation pour cette
      machine : ajoutez-la sur sa fiche », avec le lien vers la fiche à modifier ; en équipe, le texte « voyez votre
      responsable » ne change pas ;
    - relecture des textes affichés en Solo (T546) : plus de « votre responsable » ni d'« Équipe › » dans les textes Solo
      (bon de travail, codes de clôture, anomalie, signalement, rapport) ;
    - l'assistant et la fiche d'accès renvoient à Paramètres › Accès (lien vers #/equipe/acces), pas à Équipe › Accès ;

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_solo_textes.py" -v
"""
import re
import unittest
from pathlib import Path

from commun import ServeurPrevo, preregler_profil
from test_solo_flux import CasSolo

RACINE = Path(__file__).resolve().parent.parent
LANGUES = ("fr", "en", "tr", "it", "pt-PT")
CLES = ("ordres.consignation.aucune_procedure_solo", "parc.carte_consignation.aucune_procedure_solo",
        "installation.direction.explication_solo", "installation.direction.non_cree_solo",
        "installation.direction.noter_solo", "installation.mot_de_passe.responsables_solo",
        "ordres.bon_de_travail.aucune_procedure_solo", "ordres.codes.aucun_code_cause_solo", "ordres.codes.aucun_code_remede_solo",
        "ordres.anomalie.anomalie_traiter_solo", "demandes.confirmation.danger_solo", "demandes.nouvelle.danger_solo",
        "demandes.nouvelle.cinq_questions_solo", "rapport.ou.taux_horaire_solo")


class TestTextesSolo(unittest.TestCase):

    def test_cles_dans_les_cinq_langues_sans_renvoi_a_equipe(self):
        for langue in LANGUES:
            texte = (RACINE / "js" / "i18n" / (langue + ".js")).read_text(encoding="utf-8")
            for cle in CLES:
                with self.subTest(langue=langue, cle=cle):
                    ligne = next((l for l in texte.splitlines() if l.startswith("  '" + cle + "':")), None)
                    self.assertIsNotNone(ligne, "clé absente")
                    self.assertNotRegex(ligne, r"(Équipe|Team|Ekip|Squadra|Equipa) ›")
                    self.assertNotRegex(ligne, r"(?i)votre responsable|le responsable|your manager|the manager|manager before")
            for cle in ("ordres.consignation.aucune_procedure_solo", "parc.carte_consignation.aucune_procedure_solo",
                        "installation.mot_de_passe.responsables_solo"):
                self.assertIn("{lien}", next(l for l in texte.splitlines() if l.startswith("  '" + cle + "':")))


class TestAffichageSolo(CasSolo):

    def sans_procedure(self, page, equipement="EQ-0005"):
        page.evaluate("""id => Donnees.modifier('equipements', (lignes) => {
            lignes.find((l) => l.id === id).consignation = ''; })""", equipement)

    def test_consignation_sans_procedure_en_solo_et_en_equipe(self):
        page = self.page
        page.add_init_script("window.print = function () {};")
        preregler_profil(self.contexte, "responsable", nom="Thomas")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            self.sans_procedure(page)
            ot_id = page.evaluate("""() => Ordres.creer({ origine: 'manuel', equipement_id: 'EQ-0005', titre: 'Essai T546',
                type: 'correctif différé', priorite: 'P3', technicien_id: 'TEC-0004', date_prevue: '2026-10-21' })""")
            # Équipe : le texte d'avant, rien de changé
            self.poser_mode(page, False)
            page.evaluate("id => { location.hash = '#/ot/' + id; }", ot_id)
            page.wait_for_selector(".ot-consignation")
            self.assertIn("voyez votre responsable", page.inner_text(".ot-consignation"))
            # Solo : le texte de la personne seule, avec le lien vers la fiche à modifier
            self.poser_mode(page, True)
            page.evaluate("id => { location.hash = '#/ot/' + id; }", ot_id)
            page.wait_for_selector(".ot-consignation")
            bloc = page.inner_text(".ot-consignation")
            self.assertIn("Aucune procédure de consignation pour cette machine", bloc)
            self.assertNotIn("responsable", bloc.split("Cocher")[0].lower())
            self.assertEqual(page.locator('.ot-consignation a[href="#/equipement/EQ-0005/modifier"]').count(), 1)
            # Fiche de la machine
            page.evaluate("() => { location.hash = '#/equipement/EQ-0005'; }")
            page.wait_for_selector(".parc-consignation")
            self.assertEqual(page.locator('.parc-consignation a[href="#/equipement/EQ-0005/modifier"]').count(), 1)
            self.assertNotIn("demandez-la au responsable", page.inner_text(".parc-consignation"))
            # Bon de travail imprimé : la même consigne, sans « voir le responsable »
            page.evaluate("id => { location.hash = '#/ot/' + id; }", ot_id)
            page.wait_for_selector("#ot-imprimer")
            page.click("#ot-imprimer")
            page.emulate_media(media="print")
            bon = page.inner_text("#impression")
            self.assertIn("ajoutez-la sur la fiche de la machine", bon)
            self.assertNotIn("voir le responsable", bon)

    def test_signalement_en_solo_et_en_equipe(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", nom="Thomas")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/di/nouvelle")
            self.poser_mode(page, False)
            page.wait_for_selector(".di-nouvelle")
            self.assertIn("Le responsable maintenance reçoit votre demande", page.inner_text(".di-nouvelle h1 + p"))
            self.poser_mode(page, True)
            page.wait_for_selector(".di-nouvelle")
            self.assertIn("L'OT s'ouvre aussitôt à votre nom", page.inner_text(".di-nouvelle h1 + p"))


if __name__ == "__main__":
    unittest.main()
