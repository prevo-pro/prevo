"""Qui accepte une demande, côté serveur (lot 2 ergonomie, L17, T537 ; serveur.py : garder_les_decisions_au_responsable).

Mode serveur avec comptes (vraies sessions, copie temporaire de donnees/demo), sans navigateur. Le technicien (compte
julien.moreau, fiche TEC-0001) :
    réglage absent    (base existante sans réglage : « les techniciens aussi ») : il accepte une demande « Nouvelle »
                      avec un OT créé pour elle à SON nom (PUT d'ordres_travail puis de demandes, comme Demandes.prendre) ;
    « techniciens »   idem ;
    « responsable »   la même acceptation : 403, fichier inchangé ;
    toujours          refuser, différer, regrouper, accepter avec l'OT d'un collègue ou sans OT, accepter une demande
                      différée, supprimer une demande : 403 ; une demande ajoutée « Nouvelle » sans décision passe, une
                      demande ajoutée déjà « Acceptée » non (PUT et ajout) ; la demande qui suit son OT (Acceptée → En
                      cours) passe ;
    responsable       décide comme avant, quel que soit le réglage.
Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acceptation_demandes.py" -v
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import commun
from test_journal_roles import ecrire_tableau, lire_tableau, requete

TABLES = ("demandes", "ordres_travail", "parametres")
MOI, COLLEGUE = "TEC-0001", "TEC-0002"
REFUS = "Accès refusé : la décision sur une demande revient au responsable ; "


class CasAcceptation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.racine = Path(tempfile.mkdtemp(prefix="prevo-acceptation-"))
        cls.addClassCleanup(shutil.rmtree, cls.racine, True)
        cls.serveur = commun.ServeurPrevo(comptes=True)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = {role: cls.serveur.session(role) for role in ("technicien", "responsable")}
        cls.depart = {table: (cls.serveur.dossier / (table + ".csv")).read_bytes() for table in TABLES}

    def setUp(self):
        for table, octets in self.depart.items():
            (self.serveur.dossier / (table + ".csv")).write_bytes(octets)

    # --- outils -----------------------------------------------------------------------------------------------

    def tableau(self, table):
        entete, lignes = lire_tableau((self.serveur.dossier / (table + ".csv")).read_bytes())
        return entete, [dict(zip(entete, ligne + [""] * (len(entete) - len(ligne)))) for ligne in lignes]

    def mettre(self, role, table, entete, lignes):
        """PUT de la table entière (lignes : dictionnaires), avec la version servie à cette session."""
        versions = requete(self.serveur, "GET", "/api/versions", None, self.cookies[role])
        attendue = json.loads(versions[2].decode("utf-8"))["tables"][table]["version"]
        octets = ecrire_tableau(entete, [[ligne.get(colonne, "") for colonne in entete] for ligne in lignes])
        return requete(self.serveur, "PUT", "/api/csv/" + table, octets, self.cookies[role],
                       {"X-Version-Attendue": attendue})

    def regler(self, valeur):
        entete, lignes = self.tableau("parametres")
        lignes = [ligne for ligne in lignes if ligne["cle"] != "acceptation_demandes"]
        if valeur is not None:
            lignes.append({"cle": "acceptation_demandes", "valeur": valeur})
        octets = ecrire_tableau(entete, [[ligne.get(colonne, "") for colonne in entete] for ligne in lignes])
        (self.serveur.dossier / "parametres.csv").write_bytes(octets)

    def demande(self, statut="Nouvelle"):
        _, lignes = self.tableau("demandes")
        trouvee = next((ligne for ligne in lignes if ligne["statut"] == statut), None)
        self.assertIsNotNone(trouvee, "aucune demande « %s » dans la démo" % statut)
        return trouvee

    def creer_ot(self, demande, technicien):
        """OT créé pour la demande (di_id) au nom de ce technicien, écrit par le technicien (droit inchangé)."""
        entete, lignes = self.tableau("ordres_travail")
        ot_id = "OT-2099-0001"
        lignes.append({"id": ot_id, "origine": "DI", "di_id": demande["id"], "equipement_id": demande["equipement_id"],
                       "type": "correctif différé", "priorite": "P3", "statut": "Créé", "titre": "Essai L17",
                       "date_creation": "2026-11-14 08:02", "technicien_id": technicien,
                       "prises_en_charge": "2026-11-14 08:02|%s|" % technicien})
        self.assertEqual(self.mettre("technicien", "ordres_travail", entete, lignes)[0], 200)
        return ot_id

    def decider(self, role, identifiant, **champs):
        entete, lignes = self.tableau("demandes")
        for ligne in lignes:
            if ligne["id"] == identifiant:
                ligne.update(champs)
        return self.mettre(role, "demandes", entete, lignes)

    def accepter(self, demande, ot_id):
        return self.decider("technicien", demande["id"], statut="Acceptée", ot_id=ot_id, date_decision="2026-11-14 08:02")

    def assertRefus(self, reponse, raison=None):
        self.assertEqual(reponse[0], 403, reponse[2][:300])
        message = json.loads(reponse[2].decode("utf-8"))["erreur"]
        self.assertTrue(message.startswith(REFUS), message)
        if raison:
            self.assertIn(raison, message)

    def statut(self, identifiant):
        return next(ligne for ligne in self.tableau("demandes")[1] if ligne["id"] == identifiant)["statut"]


class TestReglage(CasAcceptation):

    def test_reglage_absent_ou_techniciens_le_technicien_accepte_avec_un_ot_a_son_nom(self):
        for valeur in (None, "techniciens"):
            with self.subTest(reglage=valeur):
                self.setUp()
                self.regler(valeur)
                demande = self.demande()
                ot_id = self.creer_ot(demande, MOI)
                reponse = self.accepter(demande, ot_id)
                self.assertEqual(reponse[0], 200, reponse[2][:300])
                self.assertEqual(self.statut(demande["id"]), "Acceptée")

    def test_reglage_responsable_seul_l_acceptation_du_technicien_est_refusee(self):
        self.regler("responsable")
        demande = self.demande()
        ot_id = self.creer_ot(demande, MOI)
        avant = (self.serveur.dossier / "demandes.csv").read_bytes()
        self.assertRefus(self.accepter(demande, ot_id), "réservé l'acceptation")
        self.assertEqual((self.serveur.dossier / "demandes.csv").read_bytes(), avant)
        # Le responsable, lui, accepte comme avant.
        reponse = self.decider("responsable", demande["id"], statut="Acceptée", ot_id=ot_id)
        self.assertEqual(reponse[0], 200, reponse[2][:300])


class TestSeulementCetteTransition(CasAcceptation):

    def test_ot_d_un_collegue_ou_sans_ot_refuse(self):
        demande = self.demande()
        self.assertRefus(self.accepter(demande, self.creer_ot(demande, COLLEGUE)), "à son nom")
        self.assertRefus(self.accepter(demande, ""), "à son nom")
        self.assertRefus(self.accepter(demande, "OT-2099-9999"), "à son nom")
        self.assertEqual(self.statut(demande["id"]), "Nouvelle")

    def test_refuser_differer_regrouper_supprimer_refuses_au_technicien(self):
        demande = self.demande()
        self.assertRefus(self.decider("technicien", demande["id"], statut="Refusée", motif_decision="non"), "revient au responsable")
        self.assertRefus(self.decider("technicien", demande["id"], statut="Différée", motif_decision="plus tard"))
        _, ordres = self.tableau("ordres_travail")
        self.assertRefus(self.decider("technicien", demande["id"], statut="Regroupée", ot_id=ordres[0]["id"]))
        self.assertRefus(self.decider("technicien", demande["id"], motif_decision="mot glissé"))
        entete, lignes = self.tableau("demandes")
        self.assertRefus(self.mettre("technicien", "demandes", entete, [l for l in lignes if l["id"] != demande["id"]]),
                         "ne se supprime pas")
        self.assertEqual(self.statut(demande["id"]), "Nouvelle")
        # Le responsable refuse comme avant.
        self.assertEqual(self.decider("responsable", demande["id"], statut="Refusée", motif_decision="non")[0], 200)

    def test_demande_differee_reste_au_responsable(self):
        demande = self.demande()
        self.assertEqual(self.decider("responsable", demande["id"], statut="Différée", motif_decision="arrêt")[0], 200)
        ot_id = self.creer_ot(demande, MOI)
        self.assertRefus(self.accepter(demande, ot_id))

    def test_suivi_de_l_ot_et_nouvelle_demande_passent(self):
        acceptee = self.demande("Acceptée")
        reponse = self.decider("technicien", acceptee["id"], statut="En cours")
        self.assertEqual(reponse[0], 200, reponse[2][:300])
        entete, lignes = self.tableau("demandes")
        nouvelle = dict(lignes[0], id="DI-2099-0001", statut="Nouvelle", motif_decision="", date_decision="", ot_id="",
                        mot_technicien="", date_reparation="", repare_par="")
        self.assertEqual(self.mettre("technicien", "demandes", entete, lignes + [nouvelle])[0], 200)
        entete, lignes = self.tableau("demandes")
        forcee = dict(nouvelle, id="DI-2099-0002", statut="Acceptée", ot_id="OT-2099-0001")
        self.assertRefus(self.mettre("technicien", "demandes", entete, lignes + [forcee]))

    def test_ajout_d_une_demande_deja_acceptee_refuse(self):
        entete, lignes = self.tableau("demandes")
        forcee = dict(lignes[0], id="DI-2099-0003", statut="Acceptée", ot_id="OT-2099-0001")
        octets = ecrire_tableau(entete, [[forcee.get(colonne, "") for colonne in entete]], bom=False)
        self.assertRefus(requete(self.serveur, "POST", "/api/csv/demandes/ajout", octets, self.cookies["technicien"]))
        existante = dict(lignes[0])
        octets = ecrire_tableau(entete, [[existante.get(colonne, "") for colonne in entete]], bom=False)
        self.assertRefus(requete(self.serveur, "POST", "/api/csv/demandes/ajout", octets, self.cookies["technicien"]))
        neuve = dict(lignes[0], id="DI-2099-0004", statut="Nouvelle", motif_decision="", date_decision="", ot_id="")
        octets = ecrire_tableau(entete, [[neuve.get(colonne, "") for colonne in entete]], bom=False)
        reponse = requete(self.serveur, "POST", "/api/csv/demandes/ajout", octets, self.cookies["technicien"])
        self.assertEqual(reponse[0], 200, reponse[2][:300])


if __name__ == "__main__":
    unittest.main()
