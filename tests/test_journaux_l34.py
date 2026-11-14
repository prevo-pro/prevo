"""Lot 2 ergonomie, L34 (tâche T547) — journaux lisibles par le responsable seul.

Ce qui est vérifié :
    erreurs d'écran  POST /api/erreur-ecran : chaque rôle connecté envoie (demandeur, technicien, responsable,
                     direction), une ligne bornée dans journal-serveur.log (rôle de la session, écran, version,
                     message sur une ligne, coupé à 300 caractères) et rien d'autre du corps ; 401 sans session, 400
                     sans message, 413 au-delà de 4 Ko ; sans comptes, ce PC envoie (« ce PC ») et le 21e envoi en
                     10 minutes n'est pas écrit (200, « note » faux) ; DebitParPoste compte par poste et oublie après la fenêtre.
    diagnostic       GET /api/diagnostic : ZIP au responsable (diagnostic.json, configuration.json, journaux du serveur,
                     journal des connexions), 403 au technicien, au demandeur et à la direction, 401 sans session,
                     200 à ce PC sans comptes (Q5) ; aucun CSV de données, aucun secret (clé d'IA, certificat, clé
                     privée, identifiant dans l'adresse de l'IA, ligne de journal qui cite PREVO_IA_CLE), ni comptes,
                     ni sessions ; navigateur : la carte et son avertissement (Q6) chez le responsable, rien chez le
                     technicien.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_journaux_l34.py" -v
"""
import io
import json
import shutil
import tempfile
import time
import unittest
import zipfile
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

    def test_diagnostic_au_responsable_seul(self):
        reponse = self.client.requete("GET", "/api/diagnostic", cookie=self.cookies["responsable"])
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        self.assertEqual(reponse.entetes["content-type"], "application/zip")
        self.assertRegex(reponse.entetes["content-disposition"],
                         r'^attachment; filename="prevo-diagnostic-\d{4}-\d{2}-\d{2}-\d{4}\.zip"$')
        with zipfile.ZipFile(io.BytesIO(reponse.octets)) as archive:
            noms = set(archive.namelist())
            self.assertTrue({"diagnostic.json", "configuration.json", "journaux/journal-serveur.log",
                             "journaux/journal-acces.csv"} <= noms, noms)
            self.assertFalse([nom for nom in noms if nom.endswith(".csv") and nom != "journaux/journal-acces.csv"])
            self.assertIn("nicolas.briand", archive.read("journaux/journal-acces.csv").decode("utf-8-sig"))
            self.assertTrue(json.loads(archive.read("configuration.json"))["comptes"])
        for role in ("technicien", "demandeur", "direction"):
            with self.subTest(role=role):
                refus = self.client.requete("GET", "/api/diagnostic", cookie=self.cookies[role])
                self.assertEqual(refus.statut, 403, refus.octets[:300])
                self.assertTrue(refus.json()["erreur"].startswith("Accès refusé"))
        self.assertEqual(self.client.requete("GET", "/api/diagnostic").statut, 401)

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
        # Q5 : sans comptes, celui qui est devant le PC serveur prépare le fichier de diagnostic.
        diagnostic = client.requete("GET", "/api/diagnostic")
        self.assertEqual(diagnostic.statut, 200, diagnostic.octets[:300])
        with zipfile.ZipFile(io.BytesIO(diagnostic.octets)) as archive:
            self.assertIn("essai 0", archive.read("journaux/journal-serveur.log").decode("utf-8"))


class TestDiagnosticSansSecret(unittest.TestCase):

    def test_ni_secret_ni_donnees(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-l34-diag-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        config = serveur.Configuration(str(dossier / "donnees"), [])
        serveur.creer_dossiers(config)
        config.reglages.update({"_present": True, "ia_cle": "sk-secret-ia-123", "certificat": "C:/certs/atelier.pem",
                                "cle": "C:/certs/atelier-cle.pem", "ia_fournisseur": "openai",
                                "ia_url": "https://moi:motdepasse@ia.example:8443/v1?key=jeton-secret#x"})
        donnees = Path(config.dossier_donnees)
        (donnees / "journal-serveur.log").write_text("2026-11-14 08:00:00 démarrage\n2026-11-14 08:00:01 "
                                                     "PREVO_IA_CLE=sk-secret-ia-123\n", encoding="utf-8")
        (donnees / "journal-serveur.log.1").write_text("ancienne ligne\n", encoding="utf-8")
        (donnees / "journal-serveur.log.2").write_text("trop ancienne\n", encoding="utf-8")
        (donnees / "equipements.csv").write_bytes(b"id;nom\r\nEQ-0001;Presse secrete\r\n")
        (donnees / "acces").mkdir(exist_ok=True)
        (donnees / "acces" / "comptes.json").write_text('{"empreinte": "hachage-secret"}', encoding="utf-8")
        octets = serveur.archive_de_diagnostic(config)
        with zipfile.ZipFile(io.BytesIO(octets)) as archive:
            self.assertEqual(sorted(archive.namelist()), ["configuration.json", "diagnostic.json",
                                                          "journaux/journal-serveur.log",
                                                          "journaux/journal-serveur.log.1"])
            tout = b"".join(archive.read(nom) for nom in archive.namelist())
            configuration = json.loads(archive.read("configuration.json"))
            systeme = json.loads(archive.read("diagnostic.json"))
        for secret in (b"sk-secret-ia-123", b"atelier.pem", b"atelier-cle.pem", b"motdepasse", b"jeton-secret",
                       b"hachage-secret", b"Presse secrete", b"trop ancienne"):
            self.assertNotIn(secret, tout, secret)
        self.assertEqual(configuration["ia_url"], "https://ia.example:8443/v1")
        self.assertEqual(configuration["ia_cle"], serveur.LIBELLE_RETIRE)
        self.assertEqual(configuration["certificat"], serveur.LIBELLE_RETIRE)
        self.assertEqual(configuration["ia_fournisseur"], "openai")
        self.assertEqual(systeme["version"], serveur.VERSION_APPLICATION)
        self.assertIn(b"ancienne ligne", tout)


class TestJournalEnAttente(unittest.TestCase):

    def test_rien_ecrit_avant_le_controle_du_format_et_jamais_en_lecture_seule(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-l34-attente-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        ouvert = serveur.JournalServeur(str(dossier / "ouvert.log"), attente=True)
        ouvert.ecrire("ligne du démarrage")
        self.assertFalse((dossier / "ouvert.log").exists())
        ouvert.ouvrir()
        ouvert.ecrire("après le contrôle")
        lignes = (dossier / "ouvert.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual([ligne[20:] for ligne in lignes], ["ligne du démarrage", "après le contrôle"])
        lecture_seule = serveur.JournalServeur(str(dossier / "lecture-seule.log"), attente=True)
        lecture_seule.ecrire("ligne du démarrage")
        lecture_seule.abandonner()
        lecture_seule.ecrire("plus tard")
        self.assertFalse((dossier / "lecture-seule.log").exists())


class TestDernieresErreurs(unittest.TestCase):
    """Relevé T549 (D130) : Paramètres montre les dernières erreurs et avertissements du journal, pas les écritures."""

    def test_seules_les_alertes_marquees_sortent(self):
        dossier = Path(tempfile.mkdtemp(prefix="prevo-l34-alertes-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        journal = serveur.JournalServeur(str(dossier / serveur.NOM_JOURNAL_SERVEUR))
        journal.ecrire("10:00:00  127.0.0.1  POST '/api/tables/ordres_travail'  200")
        journal.ecrire(serveur.texte_de_la_console(serveur.traduisible("console.copie.impossible", "Copie impossible.")),
                       alerte=serveur.est_une_alerte(serveur.traduisible("console.copie.impossible", "Copie impossible.")))
        journal.ecrire("GET '/api/x' : Traceback (most recent call last):\n  File \"serveur.py\"\nValueError: essai",
                       alerte=True)
        journal.ecrire("une ligne qui cite PREVO_IA_CLE", alerte=True)
        journal.ecrire("Prévo 2.3.0 - serveur local de GMAO")
        config = type("Config", (), {"dossier_donnees": str(dossier)})()
        lignes = serveur.dernieres_lignes_du_journal(config)["lignes"]
        self.assertEqual(len(lignes), 4)
        self.assertTrue(lignes[0].endswith(" ! Copie impossible."))
        self.assertTrue(lignes[1].endswith(" ! GET '/api/x' : Traceback (most recent call last):"))
        self.assertEqual(lignes[2:], ['  File "serveur.py"', "ValueError: essai"])
        self.assertFalse(serveur.est_une_alerte(serveur.traduisible("console.copie.a_jour", "Copie à jour.")))
        # Rien que des écritures et le démarrage : aucune ligne (« Aucune erreur notée. » à l'écran).
        (dossier / serveur.NOM_JOURNAL_SERVEUR).write_text("2026-11-14 10:00:00 Prévo 2.3.0\n", encoding="utf-8")
        self.assertEqual(serveur.dernieres_lignes_du_journal(config)["lignes"], [])


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


class TestNavigateurDiagnostic(CasNavigateurComptes):
    """Carte « Fichier de diagnostic » de Paramètres : chez le responsable (avec l'avertissement du journal des
    connexions, Q6) et téléchargement du ZIP ; absente chez le technicien (qui n'a pas Paramètres)."""

    def test_carte_chez_le_responsable_et_telechargement(self):
        self.poser_session("responsable", "responsable", "Nicolas Briand")
        page = self.page
        page.goto(self.serveur.url + "/#/parametres")
        attendre_pret(page)
        page.wait_for_selector("#carte-diagnostic")
        self.assertIn("noms des comptes et les adresses des postes", page.inner_text("#diagnostic-connexions"))
        with page.expect_download() as attente:
            page.click("#btn-diagnostic")
        telechargement = attente.value
        self.assertRegex(telechargement.suggested_filename, r"^prevo-diagnostic-.*\.zip$")
        with zipfile.ZipFile(telechargement.path()) as archive:
            self.assertIn("diagnostic.json", archive.namelist())

    def test_rien_chez_le_technicien(self):
        self.poser_session("technicien", "technicien", "Julien Moreau", "TEC-0001")
        page = self.page
        page.goto(self.serveur.url + "/#/parametres")
        attendre_pret(page)
        page.wait_for_timeout(500)
        self.assertEqual(page.locator("#carte-diagnostic").count(), 0)
        self.assertEqual(page.locator("#btn-diagnostic").count(), 0)


if __name__ == "__main__":
    unittest.main()
