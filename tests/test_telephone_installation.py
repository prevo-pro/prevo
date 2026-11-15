"""Lot 2 ergonomie, L02 puis R1 — le téléphone pendant l'installation (essai de Nicolas du 14/11, décision R1 du 15/11).

L02 : l'assistant ne donne plus une adresse qui ne peut pas répondre. R1 : Nicolas lève D122 / CS120 (jamais d'écoute
réseau sans compte responsable ni certificat) pour CETTE SEULE page : pendant l'assistant, la fiche d'accès ouvre la
page d'attente « Téléphone connecté. Prévo s'ouvrira quand l'installation sera terminée » sur les adresses réseau du
PC (au port de la future porte) et redonne l'adresse et le QR ; rien d'autre ne répond aux adresses non locales avant
« Terminer ».

Ce qui est vérifié, sur le vrai serveur.py lancé comme par Lancer_GMAO (sous-processus, dossier temporaire, port libre ;
aucune sortie du PC ; le téléphone simulé se connecte à l'adresse réseau du PC, comme tests/test_acces_porte.py) :
    démarrage      au premier lancement, sans configuration, et pendant l'assistant avant la fiche : rien n'écoute
                   sur l'adresse réseau (connexion refusée) ;
    page           la fiche (portée « Wi-Fi de l'atelier », responsable créé) ouvre la page d'attente : page_attente
                   vrai, adresse http://<ip>:<port>/ rendue, jamais d'adresse de confiance ; GET / (requête comprise)
                   rend 200, HTML statique : titre et phrase de R1, rechargement par meta refresh, aucun script, aucun
                   lien, aucune ressource externe, aucune donnée de l'installation (nom, identifiant, dossier, port de
                   l'application), politique « default-src 'none' », connexion fermée ;
    langue         celle du navigateur (Accept-Language) parmi les cinq ; sinon le français ;
    refus          /api/* (assistant compris), /index.html, /js/*, /css/*, /donnees/*, /acces/*, /favicon.*, une route
                   inventée : 404 sans corps ; un POST vers « terminer » n'est jamais lu (rien n'est écrit) ;
    PC             127.0.0.1 garde l'assistant pendant ce temps ;
    fermeture      portée « ce PC » choisie : la page n'est plus servie ; redémarrage au milieu de l'assistant : rien
                   n'écoute avant la fiche, la fiche la rouvre ; en processus, fermer_page_attente (appelée par
                   « Terminer », test_installation_api) la ferme vraiment, et les écouteurs ne prennent jamais
                   127.0.0.1 ;
    repli          configuration réseau écrite à la main sans aucun compte responsable : repli sur ce PC, rien sur le
                   réseau.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_telephone_installation.py" -v
"""
import http.client
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from commun import RACINE, port_libre
from atelier import adresse_reseau, charger_serveur

SCRIPT = RACINE / "serveur.py"
MOT_DE_PASSE = "Atelier-2026-essai"
TITRE_FR = "Téléphone connecté"
PHRASE_FR = "Prévo s'ouvrira quand l'installation sera terminée."
POLITIQUE_ATTENTE = ("default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; "
                     "form-action 'none'")
# Routes de l'application essayées sur l'adresse du réseau (pages, fichiers, API, assistant, porte).
ROUTES = ["/", "/index.html", "/api/ping", "/api/info", "/api/installation/etat", "/api/installation/fiche",
          "/acces/porte.html", "/acces/ca.crt", "/js/app.js", "/donnees/equipements.csv"]
# R1 : tout ce qui n'est pas « / » sur la page d'attente — 404 sans corps.
ROUTES_REFUSEES = ["/index.html", "/api/ping", "/api/info", "/api/installation/etat", "/api/installation/fiche",
                   "/api/csv/equipements", "/acces/porte.html", "/acces/porte.js", "/acces/ca.crt", "/js/app.js",
                   "/js/i18n/fr.js", "/css/style.css", "/donnees/equipements.csv", "/donnees/comptes.json",
                   "/favicon.ico", "/favicon.svg", "/GUIDE.html", "/route-inventee", "//api/ping", "/%2e%2e/serveur.py"]


def requete_brute(hote, port, methode, chemin, entetes=None, corps=None):
    """(statut, en-têtes en minuscules, corps) d'une requête http directe (sans suivre de redirection)."""
    connexion = http.client.HTTPConnection(hote, port, timeout=10)
    try:
        connexion.request(methode, chemin, body=corps, headers=entetes or {})
        reponse = connexion.getresponse()
        return reponse.status, {cle.lower(): valeur for cle, valeur in reponse.getheaders()}, reponse.read()
    finally:
        connexion.close()


class CasServeurReel(unittest.TestCase):

    def setUp(self):
        self.reseau = adresse_reseau()
        if self.reseau is None:
            self.skipTest("ce PC n'a pas d'adresse réseau")
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-l02-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.donnees = self.dossier / "donnees"
        self.config = self.dossier / "prevo.config.json"             # absent : premier lancement
        self.port = port_libre()

    def demarrer(self):
        commande = [sys.executable, str(SCRIPT), "--sans-navigateur", "--donnees", str(self.donnees),
                    "--config", str(self.config), "--port", str(self.port)]
        environnement = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                             PREVO_MKCERT=str(self.dossier / "nulle-part" / "mkcert.exe"),
                             PREVO_TAILSCALE=str(self.dossier / "nulle-part" / "tailscale.exe"))
        processus = subprocess.Popen(commande, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(RACINE),
                                     env=environnement)
        self.addCleanup(self.arreter, processus)
        lignes, limite = [], time.time() + 20
        while time.time() < limite:
            ligne = processus.stdout.readline().decode("utf-8", "replace")
            if not ligne:
                break
            lignes.append(ligne.rstrip())
            if "Ctrl+C" in ligne:
                break
        self.assertIsNone(processus.poll(), "\n".join(lignes))
        return processus, lignes

    @staticmethod
    def arreter(processus):
        if processus.poll() is None:
            processus.kill()
        processus.wait(timeout=10)
        processus.stdout.close()

    def requete(self, methode, chemin, corps=None):
        requete = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, chemin), method=methode,
                                         data=None if corps is None else json.dumps(corps).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "X-Prevo": "1"})
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return json.loads(reponse.read().decode("utf-8"))

    def assert_rien_ne_repond_sur_le_reseau(self, routes=ROUTES):
        """Ni connexion ni réponse sur l'adresse réseau du PC, pour aucune route ; le PC lui-même est servi. (Windows
        retente une connexion refusée pendant environ 2 s : chaque route essayée coûte ce temps.)"""
        self.assertEqual(self.requete("GET", "/api/ping")["application"], "Prévo")
        with self.assertRaises(OSError):
            socket.create_connection((self.reseau, self.port), timeout=3).close()
        for route in routes:
            with self.subTest(route=route), self.assertRaises(OSError):
                urllib.request.urlopen("http://%s:%d%s" % (self.reseau, self.port, route), timeout=3)

    def telephone(self, methode, chemin, **options):
        return requete_brute(self.reseau, self.port, methode, chemin, **options)

    def verifier_page_d_attente(self, statut, entetes, corps, titre=TITRE_FR, phrase=PHRASE_FR):
        self.assertEqual(statut, 200)
        self.assertTrue(entetes["content-type"].startswith("text/html"))
        self.assertEqual(entetes["content-security-policy"], POLITIQUE_ATTENTE)
        self.assertEqual((entetes["x-frame-options"], entetes["referrer-policy"], entetes.get("connection")),
                         ("DENY", "no-referrer", "close"))
        texte = corps.decode("utf-8")
        self.assertIn(titre, texte)
        self.assertIn(phrase, texte)
        self.assertIn('<meta http-equiv="refresh" content="5">', texte)
        for interdit in ("<script", "href", "src=", "url(", "<link", "<form", "<iframe", "<img", "http://", "https://"):
            self.assertNotIn(interdit, texte.lower(), interdit)
        # Aucune donnée de l'installation : ni le responsable, ni son identifiant, ni un dossier, ni l'application.
        for donnee in ("Nicolas", "Briand", "nicolas.briand", str(self.dossier), "donnees", "atelier", "/api",
                       "index.html", str(self.port)):
            self.assertNotIn(donnee.lower(), texte.lower(), donnee)


class TestPageAttenteDuTelephone(CasServeurReel):

    def test_page_d_attente_pendant_l_assistant_et_rien_d_autre(self):
        processus, lignes = self.demarrer()
        self.assertTrue(any("127.0.0.1" in ligne for ligne in lignes), lignes)
        self.assertFalse(any("Sur le réseau" in ligne for ligne in lignes), lignes)
        self.assert_rien_ne_repond_sur_le_reseau(routes=[])                  # premier lancement : rien sur le réseau
        # Pendant l'assistant : équipe, Wi-Fi de l'atelier, compte du responsable créé ; avant la fiche : rien encore.
        self.requete("POST", "/api/installation/situation", {"situation": "equipe"})
        # Port de la future porte : celui du serveur du test (le défaut, 8080, pourrait être pris sur ce PC).
        self.requete("POST", "/api/installation/portee", {"portee": "atelier", "port_http": self.port,
                                                          "port_https": port_libre()})
        self.requete("POST", "/api/installation/compte", {"prenom": "Nicolas", "nom": "Briand",
                                                          "mot_de_passe": MOT_DE_PASSE})
        self.assert_rien_ne_repond_sur_le_reseau(routes=["/"])
        # R1 : la fiche ouvre la page d'attente et redonne l'adresse (le QR) ; jamais l'adresse de confiance.
        fiche = self.requete("GET", "/api/installation/fiche")
        adresse = "http://%s:%d/" % (self.reseau, self.port)
        self.assertEqual((fiche["page_attente"], fiche["telephones_apres_terminer"], fiche["adresse_confiance"],
                          fiche["adresse_tailscale"], fiche["adresses_mandataire"]), (True, False, None, None, []))
        self.assertIn(adresse, fiche["adresses"])
        # Le téléphone : la page d'attente pour « / » (requête comprise), dans la langue de son navigateur.
        self.verifier_page_d_attente(*self.telephone("GET", "/"))
        self.verifier_page_d_attente(*self.telephone("GET", "/?machine=EQ-0001"))
        for langue, titre, phrase in (
                ("en-GB,en;q=0.9", "Phone connected", "Prévo will open once the installation is finished."),
                ("tr-TR", "Telefon bağlandı", "Kurulum tamamlandığında Prévo açılacak."),
                ("it", "Telefono collegato", "Prévo si aprirà quando l'installazione sarà terminata."),
                ("pt-BR,pt;q=0.9", "Telemóvel ligado", "O Prévo abre-se quando a instalação estiver concluída."),
                ("de-DE,de;q=0.9", TITRE_FR, PHRASE_FR)):
            with self.subTest(langue=langue):
                self.verifier_page_d_attente(*self.telephone("GET", "/", entetes={"Accept-Language": langue}),
                                             titre=titre, phrase=phrase)
        # Rien d'autre : 404 sans corps, pour les fichiers, l'API, l'assistant, la porte, le favicon, une route inventée.
        for route in ROUTES_REFUSEES:
            with self.subTest(route=route):
                statut, entetes, corps = self.telephone("GET", route)
                self.assertEqual((statut, corps, entetes.get("connection")), (404, b"", "close"))
        # Un envoi n'est jamais lu : « terminer » depuis le téléphone ne fait rien.
        for methode, route in (("POST", "/api/installation/terminer"), ("PUT", "/api/csv/equipements"), ("POST", "/")):
            with self.subTest(methode=methode, route=route):
                statut, _, corps = self.telephone(methode, route, corps=b'{"base": "demo"}',
                                                  entetes={"X-Prevo": "1", "Content-Type": "application/json"})
                self.assertEqual((statut, corps), (404, b""))
        self.assertFalse(self.config.exists())
        # Le PC, lui, garde l'assistant ; le brouillon est intact.
        etat = self.requete("GET", "/api/installation/etat")
        self.assertEqual((etat["portee"], etat["situation"]), ("atelier", "equipe"))
        # Redémarrage au milieu de l'assistant : rien sur le réseau avant la fiche, la fiche rouvre la page.
        self.arreter(processus)
        self.demarrer()
        self.assert_rien_ne_repond_sur_le_reseau(routes=["/"])
        self.assertTrue(self.requete("GET", "/api/installation/fiche")["page_attente"])
        self.verifier_page_d_attente(*self.telephone("GET", "/"))
        # « Ce PC » choisi : la page d'attente n'est plus servie, la fiche ne donne plus d'adresse.
        self.requete("POST", "/api/installation/portee", {"portee": "ce-pc"})
        self.assert_rien_ne_repond_sur_le_reseau(routes=["/"])
        fiche = self.requete("GET", "/api/installation/fiche")
        self.assertEqual((fiche["page_attente"], fiche["adresses"]), (False, []))

    def test_configuration_reseau_sans_responsable_repli_sur_ce_pc(self):
        self.config.write_text(json.dumps({"ecoute": "0.0.0.0", "comptes": True, "mandataire": True}), encoding="utf-8")
        _, lignes = self.demarrer()
        self.assertTrue(any("Aucun compte responsable" in ligne for ligne in lignes), lignes)
        self.assert_rien_ne_repond_sur_le_reseau(routes=["/", "/api/ping"])


class TestOuvertureEtFermeture(unittest.TestCase):
    """En processus : ouvrir_page_attente prend les adresses réseau du PC (jamais 127.0.0.1), fermer_page_attente
    (appelée par « Terminer ») les rend : plus rien ne répond."""

    def test_ouvrir_puis_fermer(self):
        reseau = adresse_reseau()
        if reseau is None:
            self.skipTest("ce PC n'a pas d'adresse réseau")
        serveur = charger_serveur("serveur_prevo_page_attente")
        dossier = Path(tempfile.mkdtemp(prefix="prevo-r1-"))
        self.addCleanup(shutil.rmtree, dossier, True)
        config = serveur.Configuration(str(dossier / "donnees"), [])
        self.addCleanup(serveur.fermer_page_attente, config)
        port = port_libre()
        ouvertes = serveur.ouvrir_page_attente(config, port)
        self.assertIn(reseau, ouvertes)
        self.assertFalse(any(ip.startswith("127.") or ip == "0.0.0.0" for ip in ouvertes), ouvertes)
        self.assertEqual(serveur.ouvrir_page_attente(config, port), ouvertes)        # déjà ouverte : la même
        statut, _, corps = requete_brute(reseau, port, "GET", "/")
        self.assertEqual(statut, 200)
        self.assertIn(TITRE_FR, corps.decode("utf-8"))
        with self.assertRaises(OSError):                                       # 127.0.0.1 : jamais la page d'attente
            socket.create_connection(("127.0.0.1", port), timeout=3).close()
        serveur.fermer_page_attente(config)
        self.assertEqual(config.ecouteurs_attente, [])
        with self.assertRaises(OSError):
            socket.create_connection((reseau, port), timeout=3).close()


if __name__ == "__main__":
    unittest.main()
