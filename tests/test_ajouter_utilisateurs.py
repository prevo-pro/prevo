"""Lot 2 ergonomie, L05 (tâche T555) — « Ajouter des utilisateurs » : le serveur.

Ce qui est vérifié (serveur dans ce processus, horloge simulée, copie de la démo ; mêmes aides que
tests/test_acces_appareils.py) :
    table          POST /api/premier-acces est une route publique (le jeton décide) ; POST /api/acces/invitations est
                   ouverte au technicien (droit nouveau, le seul) ; la liste des invitations, les comptes et le journal
                   restent au responsable ;
    technicien     il invite un opérateur (téléphone, demandeur) ; 403 pour un poste de déclaration ; 403 sur la liste
                   des invitations, les comptes et le journal ; sa ligne « invitation » au journal ;
    compte par QR  le responsable crée un technicien (fiche créée avec son métier, ou reprise si une fiche à ce nom n'a
                   pas de compte) ou la Direction (sans fiche) : aucun mot de passe rendu, le chemin du QR
                   (/#/premier-acces/<jeton>) ; personne ne peut se connecter avant ; refus pour un autre rôle ;
    jeton du QR    usage unique (refusé une fois le mot de passe choisi, même message), durée de vie des invitations
                   d'appareils (24 h par défaut, invitation_heures), lié à ce compte seul (un autre compte n'est pas
                   touché ; un nouveau QR, une réinitialisation ou la désactivation l'annulent), seule son empreinte
                   est écrite ; jamais dans un fichier d'accès, le journal ou la console ;
    mot de passe   règles inchangées (12 caractères au moins : 400, le jeton sert encore) ; une session ouverte
                   ensuite, la connexion avec le mot de passe choisi marche ;
    formulaire     P05 A : « nouvelle_fiche » sans QR rend le mot de passe provisoire comme avant ; le refus « même
                   personne » (T301) n'écrit aucune fiche.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ajouter_utilisateurs.py" -v
"""
import csv
import unittest

import test_acces_appareils as base
from test_acces_appareils import (CasAppareils, HEURE, DEPART, iso, empreinte, lignes_du_journal,
                                  MOT_DE_PASSE_TECHNICIEN, MOT_DE_PASSE_DEMANDEUR, MOT_DE_PASSE_RESPONSABLE)

serveur = base.serveur
NOUVEAU = "mon mot de passe de technicien"


def setUpModule():
    base.setUpModule()


def techniciens(dossier):
    with open(dossier / "techniciens.csv", encoding="utf-8-sig", newline="") as fichier:
        return list(csv.DictReader(fichier, delimiter=";"))


class TestTable(unittest.TestCase):

    def test_routes(self):
        self.assertIn(("POST", "premier-acces"), serveur.ROUTES_PUBLIQUES)
        self.assertEqual(serveur.ROLES_PAR_ROUTE[("POST", "premier-acces")], serveur.TOUS)
        self.assertEqual(serveur.ROLES_PAR_ROUTE[("POST", "acces/invitations")], serveur.INTERVENANTS)
        for route in (("GET", "acces/invitations"), ("GET", "acces/comptes"), ("POST", "acces/comptes"),
                      ("POST", "acces/comptes/<identifiant>"), ("GET", "acces/journal"),
                      ("POST", "acces/invitations/<id>/revoquer"), ("POST", "acces/appareils/revoquer-tous")):
            with self.subTest(route=route):
                self.assertEqual(serveur.ROLES_PAR_ROUTE[route], serveur.RESPONSABLE)


class CasUtilisateurs(CasAppareils):

    def creer(self, corps, statut=200):
        reponse = self.client.requete("POST", "/api/acces/comptes", corps, cookie=self.responsable_frais())
        self.assertEqual(reponse.statut, statut, reponse.octets)
        donnees = reponse.json()
        if "chemin" in donnees:
            self.jetons.append(donnees["chemin"].rsplit("/", 1)[1])
        return donnees

    def technicien_par_qr(self, prenom="Karim", nom="Haddad", metier="Mécanicien"):
        donnees = self.creer({"prenom": prenom, "nom": nom, "role": "technicien", "nouvelle_fiche": True,
                              "metier": metier, "qr": True})
        return donnees, donnees["chemin"].rsplit("/", 1)[1]

    def premier_acces(self, corps, cookie=None):
        return self.client.requete("POST", "/api/premier-acces", corps, cookie=cookie)

    def compte(self, identifiant):
        return serveur.trouver_compte(serveur.lire_comptes(self.serveur.config), identifiant)


class TestLeTechnicienInvite(CasUtilisateurs):

    def test_le_technicien_invite_un_operateur_et_rien_de_plus(self):
        technicien = self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        donnees = self.inviter({}, cookie=technicien)
        self.assertEqual(donnees["chemin"], "/#/enroler/" + donnees["jeton"])
        self.assertFalse(donnees["invitation"]["poste"])
        journal = lignes_du_journal(self.donnees)
        self.assertEqual((journal[-1]["qui"], journal[-1]["resultat"]), ("julien.moreau", "invitation"))
        # L'opérateur flashe : son téléphone devient un appareil (droits du demandeur).
        _, session = self.appareil(donnees["jeton"], nom="Marc Petit")
        self.assertEqual((session["role"], session["appareil"]), ("demandeur", True))
        # Pas de poste de déclaration, ni liste, ni comptes, ni journal, ni révocation.
        poste = self.client.requete("POST", "/api/acces/invitations", {"poste": True}, cookie=technicien)
        self.assertEqual(poste.statut, 403, poste.octets)
        for methode, chemin in (("GET", "/api/acces/invitations"), ("GET", "/api/acces/comptes"),
                                ("GET", "/api/acces/journal"), ("POST", "/api/acces/comptes"),
                                ("POST", "/api/acces/invitations/INV-0000/revoquer"),
                                ("POST", "/api/acces/appareils/revoquer-tous")):
            with self.subTest(chemin=chemin):
                reponse = self.client.requete(methode, chemin, b"{}" if methode == "POST" else None, cookie=technicien)
                self.assertEqual(reponse.statut, 403, reponse.octets)
        self.assertEqual(len(self.fichier_appareils()["invitations"]), 1)
        # Le demandeur et l'appareil n'invitent pas.
        demandeur = self.client.connecter("lea.martin", MOT_DE_PASSE_DEMANDEUR)
        cookie_appareil, _ = self.appareil()
        for cookie in (demandeur, cookie_appareil):
            reponse = self.client.requete("POST", "/api/acces/invitations", b"{}", cookie=cookie)
            self.assertEqual(reponse.statut, 403, reponse.octets)
        self.verifier_aucun_secret()


class TestCompteParQr(CasUtilisateurs):

    def test_technicien_cree_avec_sa_fiche_puis_choisit_son_mot_de_passe(self):
        donnees, jeton = self.technicien_par_qr()
        compte = donnees["compte"]
        self.assertNotIn("mot_de_passe_provisoire", donnees)
        self.assertEqual(donnees["chemin"], "/#/premier-acces/" + jeton)
        self.assertRegex(jeton, r"^[A-Za-z0-9_-]{43}$")
        self.assertEqual(donnees["expire_le"], iso(DEPART + 24 * HEURE))
        self.assertEqual(compte["premier_acces_expire_le"], iso(DEPART + 24 * HEURE))
        self.assertNotIn("premier_acces", compte)
        self.assertEqual((compte["identifiant"], compte["role"], compte["a_changer"]), ("karim.haddad", "technicien", True))
        fiche = [t for t in techniciens(self.donnees) if t["id"] == compte["technicien_id"]]
        self.assertEqual([(t["prenom"], t["nom"], t["metier"], t["actif"]) for t in fiche],
                         [("Karim", "Haddad", "Mécanicien", "1")])
        self.assertEqual(self.compte("karim.haddad")["premier_acces"]["empreinte"], empreinte(jeton))
        # Le responsable voit le compte « en attente du QR », jamais l'empreinte.
        liste = self.client.requete("GET", "/api/acces/comptes", cookie=self.responsable).json()["comptes"]
        karim = next(c for c in liste if c["identifiant"] == "karim.haddad")
        self.assertNotIn("premier_acces", karim)
        self.assertEqual(karim["premier_acces_expire_le"], iso(DEPART + 24 * HEURE))
        # Lecture du QR : qui est-ce, rien de changé.
        lu = self.premier_acces({"jeton": jeton})
        self.assertEqual(lu.statut, 200, lu.octets)
        self.assertEqual(lu.json()["compte"], {"identifiant": "karim.haddad", "prenom": "Karim", "nom": "Haddad"})
        # Règle du mot de passe inchangée : trop court, 400, le jeton sert encore.
        court = self.premier_acces({"jeton": jeton, "nouveau": "court"})
        self.assertEqual(court.statut, 400, court.octets)
        choisi = self.premier_acces({"jeton": jeton, "nouveau": NOUVEAU})
        self.assertEqual(choisi.statut, 200, choisi.octets)
        session = choisi.json()["session"]
        self.assertEqual((session["identifiant"], session["role"], session["a_changer"]), ("karim.haddad", "technicien", False))
        self.assertEqual(self.client.session(choisi.cookie)["identifiant"], "karim.haddad")
        # Décision 4b de Nicolas (19/11) : la session du premier accès est en « rester connecté » (30 jours, cookie
        # avec Max-Age), pas de nouvelle connexion dès le lendemain.
        self.assertIn("Max-Age=%d" % (30 * 86400), choisi.set_cookie)
        sessions = base.serveur.lire_sessions(self.serveur.config)
        self.assertEqual([s["longue"] for s in sessions.values() if s["identifiant"] == "karim.haddad"], [True])
        self.assertNotIn("premier_acces", self.compte("karim.haddad"))
        # Usage unique : le même QR ne sert plus, même message que pour un jeton inconnu.
        for corps in ({"jeton": jeton}, {"jeton": jeton, "nouveau": "un autre mot de passe long"},
                      {"jeton": "x" * 43}, {"jeton": "pas un jeton"}):
            with self.subTest(corps=corps):
                refus = self.premier_acces(corps)
                self.assertEqual(refus.statut, 401, refus.octets)
                self.assertEqual(refus.json()["erreur"], serveur.MESSAGE_PREMIER_ACCES_REFUSE)
        self.assertTrue(self.client.connecter("karim.haddad", NOUVEAU))
        journal = [(l["qui"], l["resultat"]) for l in lignes_du_journal(self.donnees)]
        self.assertIn(("karim.haddad", "creation"), journal)
        self.assertIn(("karim.haddad", "modification"), journal)
        self.verifier_aucun_secret()

    def test_avant_le_qr_personne_ne_se_connecte(self):
        donnees, _ = self.technicien_par_qr()
        refus = self.client.requete("POST", "/api/connexion", {"identifiant": "karim.haddad", "mot_de_passe": "x" * 16,
                                                               "rester": False})
        self.assertEqual(refus.statut, 401, refus.octets)

    def test_duree_de_vie_celle_des_invitations(self):
        _, jeton = self.technicien_par_qr()
        self.serveur.avancer(24 * HEURE)
        self.assertEqual(self.premier_acces({"jeton": jeton}).statut, 200)
        self.serveur.avancer(1)
        self.assertEqual(self.premier_acces({"jeton": jeton, "nouveau": NOUVEAU}).statut, 401)
        # Le responsable en refait un (l'ancien reste refusé), à la durée réglée pour les invitations.
        self.serveur.config.reglages["invitation_heures"] = 2
        reponse = self.client.requete("POST", "/api/acces/comptes/karim.haddad", {"action": "qr"},
                                      cookie=self.responsable_frais())
        self.assertEqual(reponse.statut, 200, reponse.octets)
        neuf = reponse.json()["chemin"].rsplit("/", 1)[1]
        self.jetons.append(neuf)
        self.assertEqual(reponse.json()["expire_le"], iso(self.serveur.instant + 2 * HEURE))
        self.assertEqual(self.premier_acces({"jeton": jeton}).statut, 401)
        self.assertEqual(self.premier_acces({"jeton": neuf, "nouveau": NOUVEAU}).statut, 200)
        # Mot de passe choisi : plus de QR possible pour ce compte (« Réinitialiser » d'abord).
        refus = self.client.requete("POST", "/api/acces/comptes/karim.haddad", {"action": "qr"},
                                    cookie=self.responsable_frais())
        self.assertEqual(refus.statut, 400, refus.octets)
        self.verifier_aucun_secret()

    def test_jeton_lie_a_ce_compte_seul(self):
        _, jeton_karim = self.technicien_par_qr()
        _, jeton_ines = self.technicien_par_qr("Inès", "Roux", "Électricienne")
        self.assertEqual(self.premier_acces({"jeton": jeton_karim, "nouveau": NOUVEAU}).json()["session"]["identifiant"],
                         "karim.haddad")
        ines = self.compte("ines.roux")
        self.assertTrue(ines["a_changer"])
        self.assertEqual(ines["premier_acces"]["empreinte"], empreinte(jeton_ines))
        # Le responsable réinitialise Inès : son QR ne sert plus ; désactivé : un QR neuf non plus.
        reinit = self.client.requete("POST", "/api/acces/comptes/ines.roux", {"action": "reinitialiser"},
                                     cookie=self.responsable)
        self.assertEqual(reinit.statut, 200, reinit.octets)
        self.assertEqual(self.premier_acces({"jeton": jeton_ines}).statut, 401)
        neuf = self.client.requete("POST", "/api/acces/comptes/ines.roux", {"action": "qr"},
                                   cookie=self.responsable).json()["chemin"].rsplit("/", 1)[1]
        self.jetons.append(neuf)
        self.client.requete("POST", "/api/acces/comptes/ines.roux", {"action": "desactiver"}, cookie=self.responsable)
        self.assertEqual(self.premier_acces({"jeton": neuf, "nouveau": NOUVEAU}).statut, 401)
        # Karim garde son mot de passe : le QR d'Inès n'a touché que le compte d'Inès.
        self.assertTrue(self.client.connecter("karim.haddad", NOUVEAU))
        self.verifier_aucun_secret()

    def test_direction_par_qr_sans_fiche_et_roles_refuses(self):
        avant = len(techniciens(self.donnees))
        donnees = self.creer({"prenom": "Claire", "nom": "Dupont", "role": "direction", "qr": True})
        self.assertEqual((donnees["compte"]["role"], donnees["compte"]["technicien_id"]), ("direction", ""))
        self.assertEqual(len(techniciens(self.donnees)), avant)
        jeton = donnees["chemin"].rsplit("/", 1)[1]
        self.assertEqual(self.premier_acces({"jeton": jeton, "nouveau": NOUVEAU}).json()["session"]["role"], "direction")
        for corps in ({"prenom": "Léon", "role": "demandeur", "qr": True},
                      {"prenom": "Léon", "role": "responsable", "qr": True},
                      {"prenom": "Léon", "role": "direction", "nouvelle_fiche": True},
                      {"prenom": "Léon", "role": "technicien", "nouvelle_fiche": True, "technicien_id": "TEC-0002"},
                      {"prenom": "Léon", "role": "technicien", "technicien_id": "TEC-0002", "metier": "Soudeur"},
                      {"prenom": "Léon", "role": "technicien", "nouvelle_fiche": "oui"}):
            with self.subTest(corps=corps):
                self.creer(corps, statut=400)
        # Le technicien ne crée aucun compte, par QR ou non.
        technicien = self.client.connecter("julien.moreau", MOT_DE_PASSE_TECHNICIEN)
        reponse = self.client.requete("POST", "/api/acces/comptes", {"prenom": "Léon", "role": "technicien",
                                                                     "nouvelle_fiche": True, "qr": True},
                                      cookie=technicien)
        self.assertEqual(reponse.statut, 403, reponse.octets)
        self.assertEqual(len(techniciens(self.donnees)), avant)
        self.verifier_aucun_secret()


class TestNouvelleFicheDuFormulaire(CasUtilisateurs):
    """P05 A : « Créer un compte », technicien, « Nouvelle fiche à ce nom »."""

    def test_nouvelle_fiche_mot_de_passe_provisoire_comme_avant(self):
        donnees = self.creer({"prenom": "Hugo", "nom": "Blanc", "role": "technicien", "nouvelle_fiche": True})
        self.assertEqual(len(donnees["mot_de_passe_provisoire"]), serveur.LONGUEUR_PROVISOIRE)
        fiche = [t for t in techniciens(self.donnees) if t["id"] == donnees["compte"]["technicien_id"]]
        self.assertEqual([(t["prenom"], t["nom"], t["metier"]) for t in fiche], [("Hugo", "Blanc", "")])

    def test_fiche_existante_sans_compte_reprise(self):
        avant = len(techniciens(self.donnees))
        donnees = self.creer({"prenom": "Karim", "nom": "Benali", "role": "technicien", "nouvelle_fiche": True,
                              "metier": "Soudeur"})
        self.assertEqual(donnees["compte"]["technicien_id"], "TEC-0002")
        self.assertEqual(len(techniciens(self.donnees)), avant)
        self.assertEqual(techniciens(self.donnees)[1]["metier"], "Mécanicien")      # jamais modifiée

    def test_meme_personne_refusee_sans_ecrire_de_fiche(self):
        avant = techniciens(self.donnees)
        reponse = self.client.requete("POST", "/api/acces/comptes", {"prenom": "Julien", "nom": "Moreau",
                                                                     "role": "technicien", "nouvelle_fiche": True},
                                      cookie=self.responsable)
        self.assertEqual(reponse.statut, 400, reponse.octets)
        self.assertEqual(reponse.json()["erreur_code"], "comptes.meme_personne")
        self.assertEqual(techniciens(self.donnees), avant)


del CasAppareils

if __name__ == "__main__":
    unittest.main()
