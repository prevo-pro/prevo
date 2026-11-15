"""Fenêtre « Ajouter une habilitation » de la fiche technicien, cases des habilitations électriques (lot 2, L19 ; T565).

Défaut du rejeu : UI.fenetreAction lit une case cochée comme '1' ; la fenêtre attendait le symbole (« BR ») et ne
voyait donc jamais de case cochée : aucune ligne écrite, et « Ajouter » exigeait l'intitulé. Ici, la vraie fenêtre est
ouverte depuis la fiche d'un technicien de la démo (index.html en file://) :
    cases seules       BR, B2V et BC cochées, intitulé vide : trois lignes (mêmes dates), puis le contrôle
                       d'habilitation d'un OT qui exige BR ne signale plus rien pour ce technicien ;
    case et intitulé   BR cochée et « CACES R489 » saisi : les deux lignes.

Lancer depuis la racine du projet (au travers du verrou des navigateurs) :
    py -X utf8 -m unittest discover -s tests -p "test_habilitations_l19_fenetre.py" -v
"""
import unittest

from commun import RACINE, CasNavigateur, attendre_pret, preregler_profil

OBTENTION = "2026-01-05"
CONTROLE = "2026-06-01"

# Un nouveau technicien de test (aucune habilitation), créé dans la démo.
CREER_JS = """async () => {
  const id = await Equipe.creerTechnicien({ nom: 'Fenetre', prenom: 'Essai' });
  return typeof id === 'string' ? id : id.id;
}"""

LIGNES_JS = """(technicien) => Donnees.lignes('habilitations').filter((h) => h.technicien_id === technicien)
  .map((h) => [h.intitule, h.date_obtention, h.date_echeance])"""

# Contrôle d'un OT de dépannage qui exige BR (colonne habilitation_requise), sans équipement.
CONTROLE_JS = """([technicien, date]) => {
  const ot = { id: 'OT-TEST', statut: 'Préparé', type: 'correctif différé', priorite: 'P2', equipement_id: '',
               technicien_id: technicien, date_prevue: date, habilitation_requise: 'BR' };
  const controle = Ordres.controleHabilitation(ot, technicien, date);
  return { bloque: controle.bloque, manquantes: controle.manquantes.map((m) => m.intitule) };
}"""


class TestFenetreAjout(CasNavigateur):

    def setUp(self):
        super().setUp()
        preregler_profil(self.contexte, "responsable")
        self.page.goto((RACINE / "index.html").resolve().as_uri())
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.technicien = self.page.evaluate(CREER_JS)

    def ouvrir(self):
        self.page.evaluate("(id) => { location.hash = '#/equipe/' + id; }", self.technicien)
        self.page.click("#equipe-ajouter-habilitation")
        self.page.wait_for_selector("dialog[open] input[name=symbole_BR]")
        self.page.fill("dialog[open] input[name=date_obtention]", OBTENTION)

    def ajouter(self):
        self.page.click("dialog[open] button:has-text('Ajouter')")
        self.page.wait_for_selector("dialog[open]", state="detached")

    def lignes(self):
        return self.page.evaluate(LIGNES_JS, self.technicien)

    def test_cases_seules_sans_intitule_trois_lignes_et_br_plus_signalee(self):
        avant = self.page.evaluate(CONTROLE_JS, [self.technicien, CONTROLE])
        self.assertEqual((avant["bloque"], avant["manquantes"]), (True, ["BR"]))
        self.ouvrir()
        for symbole in ("BR", "B2V", "BC"):
            self.page.check("dialog[open] input[name=symbole_%s]" % symbole)
        self.assertEqual(self.page.input_value("dialog[open] input[name=intitule]"), "")
        self.ajouter()
        lignes = self.lignes()
        self.assertEqual(sorted(l[0] for l in lignes), ["B2V", "BC", "BR"])
        self.assertEqual({(l[1], l[2]) for l in lignes}, {(lignes[0][1], lignes[0][2])})
        self.assertEqual(lignes[0][1], OBTENTION)
        apres = self.page.evaluate(CONTROLE_JS, [self.technicien, CONTROLE])
        self.assertEqual((apres["bloque"], apres["manquantes"]), (False, []))

    def test_une_case_et_un_intitule_libre_deux_lignes(self):
        self.ouvrir()
        self.page.check("dialog[open] input[name=symbole_BR]")
        self.page.fill("dialog[open] input[name=intitule]", "CACES R489")
        self.ajouter()
        self.assertEqual(sorted(l[0] for l in self.lignes()), ["BR", "CACES R489"])


if __name__ == "__main__":
    unittest.main()
