"""Journal des modifications fermé au technicien et à la Direction (lot 2 ergonomie, T556, R2 ; règle de Nicolas : les
journaux ne sont lisibles que par le responsable).

    serveur     GET /api/csv/journal : 403 au technicien et à la Direction, le fichier entier au responsable (inchangé) ;
                GET /api/journal/extraits : refusé au demandeur ; au technicien et à la Direction, les seules lignes
                utiles (dérogation RG8 accordée, poste vidé ; historique d'un contrôle et de ses réserves, lignes
                entières ; création et changements de statut d'un OT, profil et poste vidés), version voilée, la même
                que celle de /api/versions ; le technicien écrit toujours au journal par ajout ;
    écrans      pour le technicien et pour la Direction, en mode comptes, les quatre usages marchent encore : la
                dérogation accordée est relue (bandeau de la fiche, passage à « Planifié »), l'historique d'un
                contrôle et de ses réserves s'affiche (technicien), l'attente de pièces se calcule (Direction :
                indicateurs et rapport) ; aucune lecture de /api/csv/journal.

Lancer depuis la racine du projet (tests à navigateur : au travers du verrou du chantier) :
    py -X utf8 -m unittest discover -s tests -p "test_journal_ferme_r2.py" -v
"""
import re
import unittest

from commun import attendre_pret, scenarios_demo
import test_acces_roles as roles

serveur = roles.serveur
SCENARIOS = scenarios_demo()
OT_BR = SCENARIOS["ot_a_planifier_br"]
TEC_ECHUE = SCENARIOS["technicien_br_echue"]
CONTROLE = SCENARIOS["controle_reserves"]
PANNE_ATTENTE = SCENARIOS["panne_attente_pieces"]
DATE = "2026-11-20"
DEROGATION = ("modification : technicien_id, date_prevue — préparation ; dérogation habilitation : %s le %s sans BR "
              "(échue) ; compte : nicolas.briand ; motif : électricien du site présent" % (TEC_ECHUE, DATE))
# Lignes ajoutées au journal de la démo : (id, table, id_ligne, action, profil, poste)
LIGNES = [
    ("J-20261110080000-R2AA", "ordres_travail", OT_BR, DEROGATION, "Responsable", "PC du bureau"),
    ("J-20261110080100-R2BB", "controles_reglementaires", CONTROLE, "modification : date_realisation — essai R2",
     "Responsable", "PC du bureau"),
    ("J-20261110080200-R2CC", "equipements", "EQ-0001", "modification de l'équipement — secret R2", "Responsable",
     "PC du bureau"),
    ("J-20261110080300-R2DD", "ordres_travail", OT_BR, "modification : titre — titre changé R2", "Responsable",
     "PC du bureau"),
]


def setUpModule():
    roles.setUpModule()


def ajouter_lignes(dossier):
    chemin = dossier / "journal.csv"
    entete, lignes = roles.lire_tableau(chemin.read_bytes())
    for identifiant, table, id_ligne, action, profil, poste in LIGNES:
        ligne = [""] * len(entete)
        for nom, valeur in (("id", identifiant), ("date_heure", "2026-11-10 08:00"), ("table", table),
                            ("id_ligne", id_ligne), ("action", action), ("profil", profil), ("poste", poste)):
            ligne[entete.index(nom)] = valeur
        lignes.append(ligne)
    chemin.write_bytes(roles.ecrire_tableau(entete, lignes))


class TestExtraitsPurs(unittest.TestCase):

    def test_seules_les_lignes_utiles_et_leurs_colonnes(self):
        entete = "id;date_heure;poste;profil;table;id_ligne;action"
        lignes = ["J-1;2026-11-10 08:00;P1;Responsable;ordres_travail;OT-1;" + DEROGATION.replace(";", ","),
                  "J-2;2026-11-10 08:00;P2;Technicien TEC-0002;ordres_travail;OT-1;modification : statut — statut En cours → En attente : Pièce : x",
                  "J-3;2026-11-10 08:00;P3;Responsable;ordres_travail;OT-1;création — création de l'OT (manuel)",
                  "J-4;2026-11-10 08:00;P4;Responsable;reserves_controle;RES-1;réserves relevées : 1",
                  "J-5;2026-11-10 08:00;P5;Responsable;equipements;EQ-1;création de l'équipement",
                  "J-6;2026-11-10 08:00;P6;Responsable;ordres_travail;OT-1;modification : titre — titre",
                  "J-7;2026-11-10 08:00;P7;Responsable;contrats_prestataires;CTP-1;résiliation notée : lettre du 01/10/2026"]
        octets = ("﻿" + "\r\n".join([entete] + lignes) + "\r\n").encode("utf-8")
        entete_lu, gardees = roles.lire_tableau(serveur.extraits_du_journal(octets))
        self.assertEqual(";".join(entete_lu), entete)
        par_id = {ligne[0]: ligne for ligne in gardees}
        self.assertEqual(sorted(par_id), ["J-1", "J-2", "J-3", "J-4"])
        self.assertEqual(par_id["J-1"][2:4], ["", "Responsable"])           # dérogation : profil gardé, poste vidé
        self.assertEqual(par_id["J-2"][2:4], ["", ""])                      # statut : ni profil ni poste
        self.assertEqual(par_id["J-3"][2:4], ["", ""])
        self.assertEqual(par_id["J-4"][2:4], ["P4", "Responsable"])         # contrôle : ligne entière


class CasJournalFerme(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        roles.lancer_serveur_comptes(cls)
        ajouter_lignes(cls.serveur.dossier)

    def requete(self, role, chemin, methode="GET", corps=None, **options):
        return self.client.requete(methode, chemin, corps, cookie=self.cookies[role], **options)

    def test_table_fermee_au_technicien_et_a_la_direction_responsable_inchange(self):
        disque = (self.serveur.dossier / "journal.csv").read_bytes()
        for role in ("technicien", "direction", "demandeur"):
            with self.subTest(role=role):
                self.assertTrue(self.requete(role, "/api/csv/journal").refus_de_role())
        lu = self.requete("responsable", "/api/csv/journal")
        self.assertEqual((lu.statut, lu.octets), (200, disque))

    def test_extraits_au_technicien_et_a_la_direction(self):
        self.assertTrue(self.requete("demandeur", "/api/journal/extraits").refus_de_role())
        disque = (self.serveur.dossier / "journal.csv").read_bytes()
        for role in ("technicien", "direction"):
            with self.subTest(role=role):
                lu = self.requete(role, "/api/journal/extraits")
                self.assertEqual(lu.statut, 200)
                texte = lu.octets.decode("utf-8-sig")
                self.assertIn("dérogation habilitation : %s le %s" % (TEC_ECHUE, DATE), texte)
                self.assertIn("essai R2", texte)
                self.assertIn("statut En cours → En attente", texte)
                self.assertNotIn("secret R2", texte)
                self.assertNotIn("titre changé R2", texte)
                self.assertNotIn("PC du bureau;Responsable;ordres_travail", texte)
                self.assertNotIn("Technicien TEC-0002", texte)            # profils des changements de statut vidés
                self.assertLess(len(lu.octets), len(disque))
                versions = self.requete(role, "/api/versions").json()["tables"]
                self.assertEqual(versions["journal"]["version"], lu.entetes["x-version"])
                self.assertNotEqual(lu.entetes["x-version"], roles.version_de(disque))

    def test_le_technicien_ecrit_toujours_au_journal(self):
        entete = roles.premiere_ligne((self.serveur.dossier / "journal.csv").read_bytes())
        ligne = "J-20261110090000-R2EE;2026-11-10 09:00;Poste;Technicien TEC-0001;ordres_travail;%s;note R2" % OT_BR
        reponse = self.requete("technicien", "/api/csv/journal/ajout", "POST",
                               entete + b"\r\n" + ligne.encode("utf-8") + b"\r\n")
        self.assertEqual(reponse.statut, 200, reponse.octets[:200])
        self.assertIn(b"note R2", (self.serveur.dossier / "journal.csv").read_bytes())


class TestEcransTechnicienEtDirection(roles.CasNavigateurComptes):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        ajouter_lignes(cls.serveur.dossier)

    def ouvrir(self, role, nom, technicien_id=""):
        self.poser_session(role, role, nom, technicien_id)
        page = self.page
        page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil.type"), role)
        return page

    def sans_lecture_du_journal(self):
        self.assertEqual([r for r in self.reponses if re.search(r"/api/csv/journal$", r[1]) and r[0] == "GET"], [])
        self.assertTrue(any(r[1].endswith("/api/journal/extraits") and r[2] == 200 for r in self.reponses))

    def derogation_relue(self, page):
        entree = page.evaluate("""([ot, tec, date]) => Ordres.derogationAccordee(ot, tec, date, [{ intitule: 'BR' }])""",
                               [OT_BR, TEC_ECHUE, DATE])
        self.assertIsNotNone(entree)
        self.assertIn("électricien du site présent", entree["action"])

    def test_technicien_derogation_et_historique_d_un_controle(self):
        page = self.ouvrir("technicien", "Julien Moreau", "TEC-0001")
        self.derogation_relue(page)
        page.evaluate("(id) => { location.hash = '#/controles/' + id; }", CONTROLE)
        page.wait_for_selector(".controles-historique")
        self.assertIn("essai R2", page.inner_text(".controles-historique"))
        self.sans_lecture_du_journal()

    def test_direction_derogation_et_attente_de_pieces(self):
        # Tables fermées depuis T520 (habilitations, wiki) : 403 vus comme absents ; le journal, lui, n'est jamais demandé.
        self.autoriser_erreur(re.compile(r"status of 403 .*/api/csv/(?:habilitations|wiki_pages|wiki_journal):"))
        page = self.ouvrir("direction", "Claire Dupont")
        self.derogation_relue(page)
        attente = page.evaluate("(id) => Indicateurs.attentePieces(id)", PANNE_ATTENTE)
        self.assertTrue(attente["complet"])
        self.assertGreater(attente["heures"], 0)
        page.evaluate("() => { location.hash = '#/indicateurs'; }")
        page.wait_for_selector(".indicateurs-onglets")
        self.sans_lecture_du_journal()


if __name__ == "__main__":
    unittest.main()
