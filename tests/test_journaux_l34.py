"""Lot 2 ergonomie, L34 (tâche T547) — journaux lisibles par le responsable seul.

Ce qui est vérifié :
    erreurs d'écran  POST /api/erreur-ecran : chaque rôle connecté envoie (demandeur, technicien, responsable,
                     direction), une ligne bornée dans journal-serveur.log (rôle de la session, écran, version,
                     message sur une ligne, coupé à 300 caractères) et rien d'autre du corps ; 401 sans session, 400
                     sans message, 413 au-delà de 4 Ko ; sans comptes, ce PC envoie (« ce PC ») et le 21e envoi en
                     10 minutes n'est pas écrit (200, « note » faux) ; DebitParPoste compte par poste et oublie après la fenêtre.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_journaux_l34.py" -v
"""
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import commun
import test_acces_roles
from commun import attendre_pret
from test_acces_roles import CasNavigateurComptes, Client, lancer_serveur_comptes, preparer_source, serveur


def setUpModule():
    test_acces_roles.setUpModule()          # les comptes de test (COMPTES_JSON), créés une fois


def journal_serveur(dossier):
    chemin = Path(dossier) / "journal-serveur.log"
    return chemin.read_text(encoding="utf-8") if chemin.exists() else ""


class TestErreursEcranAvecComptes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        lancer_serveur_comptes(cls)

    def envoyer(self, corps, role=None, **options):
        cookie = self.cookies[role] if role else None
        return self.client.requete("POST", "/api/erreur-ecran", corps, cookie=cookie, **options)

    def test_chaque_role_envoie_une_ligne_bornee(self):
        for role in ("demandeur", "technicien", "responsable", "direction"):
            with self.subTest(role=role):
                message = "TypeError essai %s\nseconde ligne" % role
                reponse = self.envoyer({"message": message, "ecran": "#/ordres?id=OT-1", "version": "2.3.0",
                                        "formulaire": "secret-de-formulaire-%s" % role}, role)
                self.assertEqual(reponse.statut, 200, reponse.octets)
                journal = journal_serveur(self.serveur.dossier)
                self.assertIn("Erreur d'écran  127.0.0.1  %s  v2.3.0  #/ordres?id=OT-1 : TypeError essai %s seconde "
                              "ligne" % (role, role), journal)
                self.assertNotIn("secret-de-formulaire", journal)
        long = self.envoyer({"message": "x" * 1000}, "technicien")
        self.assertEqual(long.statut, 200, long.octets)
        self.assertIn("x" * 300 + "…", journal_serveur(self.serveur.dossier))
        self.assertNotIn("x" * 301, journal_serveur(self.serveur.dossier))

    def test_refus(self):
        self.assertEqual(self.envoyer({"message": "sans session"}).statut, 401)
        self.assertEqual(self.envoyer({"ecran": "#/accueil"}, "technicien").statut, 400)
        self.assertEqual(self.envoyer({"message": 12}, "technicien").statut, 400)
        trop = self.envoyer({"message": "y" * 5000}, "technicien")
        self.assertEqual(trop.statut, 413, trop.octets)
        self.assertNotIn("sans session", journal_serveur(self.serveur.dossier))


class TestErreursEcranSansComptes(unittest.TestCase):

    def test_ce_pc_envoie_et_le_debit_est_borne(self):
        racine = Path(tempfile.mkdtemp(prefix="prevo-l34-sans-"))
        self.addCleanup(shutil.rmtree, racine, True)
        source, _ = preparer_source(racine)
        lance = commun.ServeurPrevo(source=source)
        lance.demarrer()
        self.addCleanup(lance.arreter)
        client = Client(lance.url)
        notes = []
        for numero in range(serveur.ERREURS_ECRAN_PAR_POSTE + 1):
            reponse = client.requete("POST", "/api/erreur-ecran", {"message": "essai %d" % numero})
            self.assertEqual(reponse.statut, 200, reponse.octets)
            notes.append(reponse.json()["note"])
        self.assertEqual(notes, [True] * serveur.ERREURS_ECRAN_PAR_POSTE + [False])
        journal = journal_serveur(lance.dossier)
        self.assertIn("Erreur d'écran  127.0.0.1  ce PC  v?  ? : essai 0", journal)
        self.assertNotIn("essai %d" % serveur.ERREURS_ECRAN_PAR_POSTE, journal)


class TestDebitParPoste(unittest.TestCase):

    def test_par_poste_et_fenetre_glissante(self):
        debit = serveur.DebitParPoste(2, 10)
        self.assertEqual([debit.accepter("a", 0), debit.accepter("a", 1), debit.accepter("a", 2)], [True, True, False])
        self.assertTrue(debit.accepter("b", 2))
        self.assertTrue(debit.accepter("a", 10.5))          # l'envoi de l'instant 0 est sorti de la fenêtre
        debit.accepter("c", 100)
        self.assertEqual(set(debit.instants), {"c"})         # les postes sans envoi récent sont oubliés


class TestNavigateurErreurEcran(CasNavigateurComptes):
    """L'écran d'un technicien remonte une erreur non attrapée (window error) et une promesse rejetée."""

    def attendre_ligne(self, texte):
        limite = time.time() + 10
        while time.time() < limite:
            if texte in journal_serveur(self.serveur.dossier):
                return
            time.sleep(0.2)
        self.fail("ligne absente du journal du serveur : %s" % texte)

    def test_erreurs_de_l_ecran_au_journal_du_serveur(self):
        self.poser_session("technicien", "technicien", "Julien Moreau", "TEC-0001")
        self.autoriser_erreur("Essai L34")
        page = self.page
        page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(page)
        page.evaluate("setTimeout(() => { throw new Error('Essai L34 erreur'); }, 0)")
        self.attendre_ligne("technicien  v%s  #/accueil : Essai L34 erreur" % page.evaluate("App.version"))
        page.evaluate("() => { Promise.reject(new Error('Essai L34 promesse')); }")
        self.attendre_ligne("#/accueil : Essai L34 promesse")


if __name__ == "__main__":
    unittest.main()
