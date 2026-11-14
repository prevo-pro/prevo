"""Lot 2 ergonomie, L02 — le téléphone pendant l'installation (essai de Nicolas du 14/11).

Voie retenue : le réseau reste fermé jusqu'à « Terminer » (D122, CS120 : jamais d'écoute réseau sans compte
responsable ni certificat, aucune option qui contourne) ; l'assistant ne donne plus d'adresse ni de QR pour les
téléphones tant que l'installation n'est pas terminée (fiche d'accès : « telephones_apres_terminer »).

Ce qui est vérifié, sur le vrai serveur.py lancé comme par Lancer_GMAO (sous-processus, dossier temporaire, port libre ;
aucune sortie du PC) : aucune route de l'application ne répond à une adresse non locale du PC (la connexion même est
refusée : rien n'écoute hors de 127.0.0.1)
    - au premier lancement, sans configuration ;
    - pendant l'assistant, portée « Wi-Fi de l'atelier » choisie et compte du responsable créé ;
    - après un redémarrage au milieu de l'assistant (brouillon « atelier » et responsable présents) ;
    - configuration réseau écrite à la main sans aucun compte responsable (repli sur ce PC) ;
et la fiche d'accès de l'assistant ne donne alors ni adresse ni QR pour les téléphones.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_telephone_installation.py" -v
"""
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
from atelier import adresse_reseau

SCRIPT = RACINE / "serveur.py"
MOT_DE_PASSE = "Atelier-2026-essai"
# Routes de l'application essayées sur l'adresse du réseau (pages, fichiers, API, assistant, porte).
ROUTES = ["/", "/index.html", "/api/ping", "/api/info", "/api/installation/etat", "/api/installation/fiche",
          "/acces/porte.html", "/acces/ca.crt", "/js/app.js", "/donnees/equipements.csv"]


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


class TestReseauFermeAvantTerminer(CasServeurReel):

    def test_premier_lancement_puis_assistant_puis_redemarrage(self):
        processus, lignes = self.demarrer()
        self.assertTrue(any("127.0.0.1" in ligne for ligne in lignes), lignes)
        self.assertFalse(any("Sur le réseau" in ligne for ligne in lignes), lignes)
        self.assert_rien_ne_repond_sur_le_reseau(routes=[])
        # Pendant l'assistant : équipe, Wi-Fi de l'atelier, compte du responsable créé.
        self.requete("POST", "/api/installation/situation", {"situation": "equipe"})
        self.requete("POST", "/api/installation/portee", {"portee": "atelier"})
        self.requete("POST", "/api/installation/compte", {"prenom": "Nicolas", "nom": "Briand",
                                                          "mot_de_passe": MOT_DE_PASSE})
        self.assert_rien_ne_repond_sur_le_reseau()
        fiche = self.requete("GET", "/api/installation/fiche")
        self.assertEqual((fiche["adresses"], fiche["adresse_confiance"], fiche["adresse_tailscale"],
                          fiche["adresses_mandataire"], fiche["telephones_apres_terminer"]), ([], None, None, [], True))
        # Redémarrage au milieu de l'assistant (brouillon « atelier », responsable présent, pas de configuration).
        self.arreter(processus)
        self.demarrer()
        self.assertEqual(self.requete("GET", "/api/installation/etat")["portee"], "atelier")
        self.assert_rien_ne_repond_sur_le_reseau(routes=["/", "/api/ping"])
        self.assertTrue(self.requete("GET", "/api/installation/fiche")["telephones_apres_terminer"])

    def test_configuration_reseau_sans_responsable_repli_sur_ce_pc(self):
        self.config.write_text(json.dumps({"ecoute": "0.0.0.0", "comptes": True, "mandataire": True}), encoding="utf-8")
        _, lignes = self.demarrer()
        self.assertTrue(any("Aucun compte responsable" in ligne for ligne in lignes), lignes)
        self.assert_rien_ne_repond_sur_le_reseau(routes=["/", "/api/ping"])


if __name__ == "__main__":
    unittest.main()
