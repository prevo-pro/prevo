"""Tests des habilitations simplifiées (lot 2 ergonomie, T556 ; L19, Q1, P06) : liste fixe des habilitations
électriques, habilitation déduite du risque électrique de la machine (format 6) et du type d'OT (dépannage ou travail
planifié), réglage du responsable « signalée seulement » (défaut) ou « bloquante », équipe sans habilitation saisie
(jamais de blocage), autres autorisations jamais bloquantes, saisie d'un bloc (« B2V BR BC »).

Règles pures seulement (Ordres, Equipe) ; rien n'est écrit.

Lancer depuis la racine du projet (test à navigateur : au travers du verrou du chantier) :
    py -X utf8 -m unittest discover -s tests -p "test_habilitations_l19.py" -v
"""
import csv as module_csv
import io
import unittest

from commun import CasNavigateur, charger_scripts

SCRIPTS = [
    "js/lib/papaparse.min.js",
    "js/schema.js",
    "js/donnees.js",
    "js/stockage-demo.js",
    "js/interface.js",
    "js/modules/ordres-regles.js",
    "js/modules/equipe-regles.js",
]
DATE = "2026-11-20"


def csv(entete, lignes):
    sortie = io.StringIO()
    ecrivain = module_csv.writer(sortie, delimiter=";", lineterminator="\r\n")
    ecrivain.writerow(entete.split(";"))
    for ligne in lignes:
        ecrivain.writerow(ligne.split(";"))
    return sortie.getvalue()


EQUIPEMENTS = csv("id;repere;designation;statut;actif;habilitation_requise;risque_electrique", [
    "EQ-0001;CP-01;Compresseur;en service;1;;basse tension",
    "EQ-0002;TR-01;Transformateur;en service;1;;haute tension",
    "EQ-0003;PO-01;Poste de livraison;en service;1;;local haute tension",
    "EQ-0004;CH-01;Chariot élévateur;en service;1;CACES R489;",
    "EQ-0005;AE-01;Armoire;en service;1;BR;basse tension",
    "EQ-0006;TG-01;TGBT;en service;1;B2V BC;",
    "EQ-0007;PR-01;Presse;en service;1;;",
])
TECHNICIENS = csv("id;nom;prenom;actif", [
    "TEC-0001;Moreau;Julien;1",       # BR seule
    "TEC-0002;Benali;Karim;1",        # B1V (variante de B1, Q1)
    "TEC-0003;Petit;Sophie;1",        # H0V, H2
    "TEC-0004;Garnier;Thomas;1",      # rien
])
HABILITATIONS = csv("id;technicien_id;intitule;date_obtention;date_echeance", [
    "HAB-0001;TEC-0001;BR;2025-03-10;2028-03-10",
    "HAB-0002;TEC-0002;B1V;2025-03-10;2028-03-10",
    "HAB-0003;TEC-0003;H0V;2025-03-10;2028-03-10",
    "HAB-0004;TEC-0003;h2;2025-03-10;2028-03-10",
])
ORDRES = csv("id;statut;type;priorite;equipement_id;technicien_id;date_prevue;habilitation_requise", [
    "OT-2026-0001;Préparé;correctif immédiat;P1;EQ-0001;;2026-11-20;",       # dépannage BT : BR
    "OT-2026-0002;Préparé;préventif systématique;P3;EQ-0001;;2026-11-20;",   # planifié BT : B1, B2 ou BC
    "OT-2026-0003;Préparé;amélioration;P3;EQ-0002;;2026-11-20;",             # HT : H1, H2 ou HC
    "OT-2026-0004;Préparé;correctif différé;P2;EQ-0003;;2026-11-20;",        # local HT : H0
    "OT-2026-0005;Préparé;correctif différé;P2;EQ-0004;;2026-11-20;",        # CACES : jamais bloquante
    "OT-2026-0006;Préparé;préventif systématique;P3;EQ-0005;;2026-11-20;",   # BR explicite + B1/B2/BC déduite
    "OT-2026-0007;Préparé;correctif différé;P2;EQ-0006;;2026-11-20;",        # « B2V BC » d'un bloc
    "OT-2026-0008;Préparé;correctif différé;P2;EQ-0007;;2026-11-20;",        # machine non concernée
])


def tables(bloquante=True, habilitations=HABILITATIONS):
    parametres = csv("cle;valeur", ["habilitation_absente;bloquante"] if bloquante else [])
    return {"equipements": EQUIPEMENTS, "techniciens": TECHNICIENS, "habilitations": habilitations,
            "ordres_travail": ORDRES, "parametres": parametres, "journal": csv("id;date_heure;poste;profil;table;id_ligne;action", [])}


class CasL19(CasNavigateur):

    def charger(self, donnees):
        charger_scripts(self.page, SCRIPTS)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", donnees)

    def js(self, script, argument=None):
        return self.page.evaluate(script, argument)

    def exigees(self, ot):
        return [(e["intitule"], e["origines"], e["travail"]) for e in self.js("(ot) => Ordres.habilitationsExigees(ot)", ot)]

    def refus(self, ot, technicien):
        return self.js("""([ot, technicien, date]) => {
          const ligne = Object.assign({}, Donnees.trouver('ordres_travail', ot), { technicien_id: technicien });
          const refus = Ordres.interne.refusHabilitation(ligne, technicien, date);
          return refus ? refus.manquantes.map((m) => m.intitule) : null;
        }""", [ot, technicien, DATE])

    def bloque(self, ot, technicien):
        return self.js("([ot, technicien, date]) => Ordres.controleHabilitation(ot, technicien, date).bloque", [ot, technicien, DATE])


class TestListeFixe(CasL19):

    def setUp(self):
        super().setUp()
        self.charger(tables())

    def test_liste_et_symboles(self):
        self.assertEqual(self.js("() => Equipe.HABILITATIONS_ELECTRIQUES"),
                         ["BR", "B1", "B1V", "B2", "B2V", "BC", "H0", "H1", "H2", "HC"])
        self.assertEqual(self.js("() => ['b r', 'B2V', 'h0v', 'CACES R489', ''].map(Equipe.symboleElectrique)"),
                         ["BR", "B2V", "H0V", "", ""])

    def test_bloc_saisi_d_une_traite(self):
        self.assertEqual(self.js("() => Equipe.symbolesDuBloc('B2V BR BC')"), ["B2V", "BR", "BC"])
        self.assertEqual(self.js("() => Equipe.symbolesDuBloc('BR, b2v / BR')"), ["BR", "B2V"])
        self.assertIsNone(self.js("() => Equipe.symbolesDuBloc('CACES R489')"))
        self.assertIsNone(self.js("() => Equipe.symbolesDuBloc('BR soudure')"))

    def test_variantes_q1(self):
        self.assertEqual(self.js("() => Equipe.symbolesPermis('B1V')"), ["B1V", "B1"])
        self.assertEqual(self.js("() => Equipe.symbolesPermis('B2V')"), ["B2V", "B2"])
        self.assertEqual(self.js("() => Equipe.symbolesPermis('BR')"), ["BR"])


class TestDeduction(CasL19):

    def setUp(self):
        super().setUp()
        self.charger(tables())

    def test_habilitation_attendue_selon_le_travail(self):
        self.assertEqual(self.exigees("OT-2026-0001"), [("BR", ["risque"], "depannage_bt")])
        self.assertEqual(self.exigees("OT-2026-0002"), [("B1 / B2 / BC", ["risque"], "planifie_bt")])
        self.assertEqual(self.exigees("OT-2026-0003"), [("H1 / H2 / HC", ["risque"], "travaux_ht")])
        self.assertEqual(self.exigees("OT-2026-0004"), [("H0", ["risque"], "local_ht")])
        self.assertEqual(self.exigees("OT-2026-0008"), [])

    def test_colonne_existante_gardee_et_combinee(self):
        # habilitation_requise de l'équipement garde son sens (exigée en plus), la déduite s'ajoute.
        self.assertEqual(self.exigees("OT-2026-0006"), [("BR", ["equipement"], ""), ("B1 / B2 / BC", ["risque"], "planifie_bt")])
        self.assertEqual(self.exigees("OT-2026-0007"), [("B2V", ["equipement"], ""), ("BC", ["equipement"], "")])

    def test_une_des_habilitations_suffit_et_variantes(self):
        self.assertFalse(self.bloque("OT-2026-0001", "TEC-0001"))     # BR
        self.assertTrue(self.bloque("OT-2026-0002", "TEC-0001"))      # BR ne vaut pas pour du planifié
        self.assertFalse(self.bloque("OT-2026-0002", "TEC-0002"))     # B1V vaut B1 (Q1)
        self.assertFalse(self.bloque("OT-2026-0003", "TEC-0003"))     # h2
        self.assertFalse(self.bloque("OT-2026-0004", "TEC-0003"))     # H0V vaut H0
        self.assertTrue(self.bloque("OT-2026-0004", "TEC-0001"))

    def test_techniciens_habilites(self):
        noms = self.js("""() => Equipe.techniciensHabilites(Ordres.habilitationsExigees('OT-2026-0002')[0], '2026-11-20')
                            .map((t) => t.id)""")
        self.assertEqual(noms, ["TEC-0002"])


class TestReglage(CasL19):

    def test_bloquante_refuse_les_seules_habilitations_electriques(self):
        self.charger(tables(bloquante=True))
        self.assertEqual(self.refus("OT-2026-0001", "TEC-0004"), ["BR"])
        self.assertIsNone(self.refus("OT-2026-0001", "TEC-0001"))
        self.assertEqual(self.refus("OT-2026-0006", "TEC-0001"), ["B1 / B2 / BC"])
        # Autre autorisation (CACES) : signalée (contrôle), jamais refusée.
        self.assertTrue(self.bloque("OT-2026-0005", "TEC-0004"))
        self.assertIsNone(self.refus("OT-2026-0005", "TEC-0004"))

    def test_signalee_seulement_par_defaut(self):
        self.charger(tables(bloquante=False))
        self.assertFalse(self.js("() => Equipe.absenceBloquanteReglee()"))
        self.assertTrue(self.bloque("OT-2026-0001", "TEC-0004"))
        self.assertIsNone(self.refus("OT-2026-0001", "TEC-0004"))
        passage = self.js("""() => Ordres.verifierPassage(Object.assign({}, Donnees.trouver('ordres_travail', 'OT-2026-0001'),
                              { technicien_id: 'TEC-0004' }), 'Planifié')""")
        self.assertIsNone(passage["habilitation"])

    def test_equipe_sans_habilitation_saisie_jamais_bloquee(self):
        self.charger(tables(bloquante=True, habilitations=csv("id;technicien_id;intitule;date_obtention;date_echeance", [])))
        self.assertTrue(self.js("() => Equipe.aucuneHabilitationSaisie()"))
        self.assertFalse(self.js("() => Equipe.absenceBloquante()"))
        self.assertIsNone(self.refus("OT-2026-0001", "TEC-0004"))
        self.assertFalse(self.js("() => Equipe.habilitationSaisiePour('TEC-0001')"))


if __name__ == "__main__":
    unittest.main()
