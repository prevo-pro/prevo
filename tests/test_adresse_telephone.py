"""Lot 2 ergonomie, L04 — une seule adresse pour les téléphones (défaut n° 35 du retest du 14/11).

Ce qui est vérifié (sans navigateur, sans réseau) :
    ordre          ordonner_adresses_ip, seul point de calcul : l'adresse de la carte qui porte la connexion du PC
                   (adresse source de la route par défaut) d'abord, les cartes virtuelles (WSL, Hyper-V, VPN) ensuite ;
                   sans route, l'ordre des adresses du nom du PC, une adresse « lien local » en dernier ; bouclage,
                   0.0.0.0, doublons et textes invalides écartés ;
    sortie         ip_de_sortie : un connect() UDP vers une adresse extérieure (aucun paquet), repli sur la suivante,
                   None sans route ;
    écrans         adresses_reseau (QR, étiquettes, /api/info) et la fiche d'accès rendent la principale en premier ;
    console        une seule ligne « Sur le réseau », les autres sur la ligne « Autres adresses » ;
    noms acceptés  le certificat couvre toujours toutes les adresses (rien ne change).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_adresse_telephone.py" -v
"""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from commun import RACINE

# Constat réel chez Nicolas (14/11) : la carte Wi-Fi et la carte virtuelle WSL / Hyper-V.
WIFI, WSL = "192.168.1.59", "172.19.0.1"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_adresse_telephone", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


class FausseConnexion:
    """Socket UDP simulé : connect() rend l'adresse source prévue pour chaque destination, ou OSError (pas de route)."""

    def __init__(self, sources, appels):
        self.sources, self.appels, self.destination = sources, appels, None

    def connect(self, adresse):
        self.appels.append(adresse[0])
        source = self.sources.get(adresse[0])
        if source is None:
            raise OSError("réseau injoignable")
        self.destination = adresse[0]

    def getsockname(self):
        return (self.sources[self.destination], 54321)

    def send(self, *arguments):                     # jamais appelé : aucun paquet ne part
        raise AssertionError("ip_de_sortie a envoyé un paquet")

    sendto = send

    def close(self):
        pass


class TestOrdre(unittest.TestCase):

    def test_la_carte_de_la_connexion_d_abord_meme_si_le_nom_du_pc_donne_la_virtuelle_en_premier(self):
        self.assertEqual(serveur.ordonner_adresses_ip(WIFI, [WSL, WIFI]), [WIFI, WSL])
        self.assertEqual(serveur.ordonner_adresses_ip(WIFI, [WIFI, WSL]), [WIFI, WSL])
        self.assertEqual(serveur.ordonner_adresses_ip("10.0.0.12", [WSL, "192.168.56.1", "10.0.0.12"]),
                         ["10.0.0.12", WSL, "192.168.56.1"])

    def test_sans_route_l_ordre_du_nom_du_pc_le_lien_local_en_dernier(self):
        self.assertEqual(serveur.ordonner_adresses_ip(None, [WSL, WIFI]), [WSL, WIFI])
        self.assertEqual(serveur.ordonner_adresses_ip(None, ["169.254.3.4", WIFI, WSL]), [WIFI, WSL, "169.254.3.4"])
        self.assertEqual(serveur.ordonner_adresses_ip(None, []), [])

    def test_bouclage_vide_doublons_et_textes_invalides_ecartes(self):
        self.assertEqual(serveur.ordonner_adresses_ip(WIFI, ["127.0.0.1", "0.0.0.0", "", None, WIFI, "pc-atelier",
                                                             "fe80::1", WSL, WSL]), [WIFI, WSL])
        self.assertEqual(serveur.ordonner_adresses_ip("127.0.1.1", [WIFI]), [WIFI])

    def test_adresses_ip_reseau_passe_par_le_seul_point_de_calcul(self):
        with mock.patch.object(serveur, "ip_de_sortie", return_value=WIFI), \
                mock.patch.object(serveur, "ips_du_nom_du_pc", return_value=[WSL, WIFI]):
            self.assertEqual(serveur.adresses_ip_reseau(), [WIFI, WSL])


class TestSortie(unittest.TestCase):

    def ip_de_sortie(self, sources):
        appels = []
        with mock.patch.object(serveur.socket, "socket", side_effect=lambda *a: FausseConnexion(sources, appels)):
            return serveur.ip_de_sortie(), appels

    def test_route_par_defaut_vers_une_adresse_exterieure(self):
        ip, appels = self.ip_de_sortie({"192.0.2.1": WIFI, "10.255.255.255": "10.8.0.2"})
        self.assertEqual((ip, appels), (WIFI, ["192.0.2.1"]))
        # La première destination n'est dans aucun réseau privé (ni celui d'une carte virtuelle ou d'un VPN).
        premiere = serveur.ipaddress.ip_address(serveur.DESTINATIONS_DE_SORTIE[0])
        for reseau in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "169.254.0.0/16", "100.64.0.0/10"):
            self.assertNotIn(premiere, serveur.ipaddress.ip_network(reseau))

    def test_repli_puis_aucune_route(self):
        self.assertEqual(self.ip_de_sortie({"10.255.255.255": "10.1.2.3"}), ("10.1.2.3", ["192.0.2.1", "10.255.255.255"]))
        self.assertEqual(self.ip_de_sortie({})[0], None)
        self.assertEqual(self.ip_de_sortie({"192.0.2.1": "0.0.0.0"})[0], None)


class CasConfiguration(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-l04-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        for cible, valeur in (("ip_de_sortie", WIFI), ("ips_du_nom_du_pc", [WSL, WIFI])):
            espion = mock.patch.object(serveur, cible, return_value=valeur)
            espion.start()
            self.addCleanup(espion.stop)
        self.config = serveur.Configuration(str(self.dossier / "donnees"), [])
        self.config.port = 8600


class TestEcrans(CasConfiguration):

    def test_adresses_reseau_la_principale_d_abord(self):
        self.config.ecoute = "0.0.0.0"
        self.assertEqual(self.config.adresses_reseau(), ["http://%s:8600/" % WIFI, "http://%s:8600/" % WSL])

    def test_le_certificat_couvre_toujours_toutes_les_adresses(self):
        noms = serveur.noms_du_certificat(self.config)
        self.assertIn(WIFI, noms)
        self.assertIn(WSL, noms)


class TestConsole(CasConfiguration):

    def console(self):
        lignes = []
        with mock.patch.object(serveur, "afficher", side_effect=lambda t, *a, **o: lignes.append(str(t))):
            serveur.afficher_accueil(self.config, 8600)
        return lignes

    def test_une_seule_adresse_pour_les_telephones_les_autres_a_part(self):
        self.config.ecoute = "0.0.0.0"
        self.config.reglages["_present"] = True
        lignes = self.console()
        reseau = [ligne for ligne in lignes if "Sur le réseau" in ligne]
        self.assertEqual(reseau, ["  Sur le réseau    : http://%s:8600/   (téléphones, tablettes)" % WIFI])
        self.assertIn("  Autres adresses  : http://%s:8600/   (autres cartes réseau de ce PC)" % WSL, lignes)
        self.assertLess(lignes.index(reseau[0]), lignes.index(
            "  Autres adresses  : http://%s:8600/   (autres cartes réseau de ce PC)" % WSL))

    def test_une_seule_carte_pas_de_ligne_autres_adresses(self):
        self.config.ecoute = "0.0.0.0"
        with mock.patch.object(serveur, "ips_du_nom_du_pc", return_value=[WIFI]):
            lignes = self.console()
        self.assertFalse(any("Autres adresses" in ligne for ligne in lignes))

    def test_en_portee_ce_pc_aucune_adresse_reseau(self):
        lignes = self.console()
        self.assertFalse(any("Sur le réseau" in ligne or "Autres adresses" in ligne for ligne in lignes))


if __name__ == "__main__":
    unittest.main()
