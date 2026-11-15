"""Jeux de fichiers d'exemple des formats de données (T182) : tests/fixtures/formats/.

Couvre : chaque jeu se matérialise ; version_schema et nombre de tables attendus (plus-recent : format 7 simulé) ;
12 enregistrements au plus par table ; BOM présent ou absent selon le jeu ; données fictives ; les jeux de la 2.2
(T378) : f3-v2.1.0 et reserves-a-reprendre lus au format 3 par le serveur (format_du_fichier, version_de_base ; côté
navigateur : tests/test_formats_js.py), controles_reglementaires.csv de reserves-a-reprendre écrit comme Prévo
l'écrit, réserves attendues (règle D183 de CONCEPTION-L1 §3.2, recopiée ici) égales à celles de LISEZMOI.md ; le jeu
f4-v2.2.0 (T394, base au format 4) : 27 tables aux colonnes exactes du format 4, lu au format 4 par le serveur, rien
à migrer ni à reprendre, réécrit aux mêmes octets (côté navigateur : tests/test_formats_js.py et
test_formats_serveur.py), les 20 tables sans colonne nouvelle identiques à f3-v2.1.0, les quatre autres complétées
sans changer une cellule, les valeurs du format 4 et les réserves du LISEZMOI ; depuis le format 5 (T513), f4-v2.2.0
passe au format 5 (demandes et ordres_travail complétés, aucune valeur changée : ses demandes « Acceptée » le restent) ;
le jeu f5-v2.2.0 (T513, base au format 5) : 27 tables aux colonnes exactes du format 5, rien à migrer, réécrit aux mêmes
octets, tiré de f4-v2.2.0 (seuls demandes, ordres_travail et parametres changent ; valeurs du LISEZMOI) ; depuis le
format 6 (T552), f4-v2.2.0 et f5-v2.2.0 passent au format 6 (colonnes vides en fin, aucune valeur changée) ; le jeu
f6-v2.4.0 (T552, base au format 6) : 27 tables aux colonnes exactes du format 6, rien à migrer, réécrit aux mêmes
octets, tiré de f5-v2.2.0 (seuls equipements, ordres_travail, mouvements_stock et parametres changent ; valeurs du
LISEZMOI, dont une pièce hors magasin) ; plus-recent : f6-v2.4.0 plus ses ajouts du format 7 ; f4-windows-1252 et f4-entete-tronque (T404) : f4-v2.2.0 avec le seul fichier abîmé de windows-1252 ou
entete-tronque, même fabrication, base au format 4 (rien à migrer : le cas pur) ; et, si git et les étiquettes v1.1.0,
v1.2.0 et v2.1.0 sont là, le générateur rejoué redonne exactement les mêmes octets.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_formats_fixtures.py" -v
"""
import base64
import csv
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jeux_formats import DOSSIER_JEUX, JEUX, copier_jeu, lire_variante, retour_attendu

RACINE = Path(__file__).resolve().parent.parent
GENERATEUR = RACINE / "outils" / "generer_fixtures_formats.py"
LISEZMOI = DOSSIER_JEUX / "LISEZMOI.md"
ETIQUETTES = ("v1.1.0", "v1.2.0", "v2.1.0")
BOM = b"\xef\xbb\xbf"
MAX_ENREGISTREMENTS = 12
# Même règle que tests/test_audit_divers.py (G3) : aucun numéro français hors des plages fictives de l'ARCEP
MOTIF_TELEPHONE = re.compile(r"(?<![\w.,])(?:(?:\+|00)33[ .-]?(?:\(0\)[ .-]?)?|0)([1-9])([ .-]?)(\d{2})\2(\d{2})\2(\d{2})\2(\d{2})(?!\w)")
PLAGES_FICTIVES = ("04657100", "06399800")

# jeu -> version_schema attendu (None : absent, soit le format 1)
VERSION_SCHEMA = {"f1": None, "f2-v1.1.0": "2", "f3-v1.2.0": "3", "f3-v2.0.0": "3", "plus-recent": "7",
                  "melange": "3", "f3-v2.1.0": "3", "reserves-a-reprendre": "3", "f4-v2.2.0": "4",
                  "f4-windows-1252": "4", "f4-entete-tronque": "4", "f5-v2.2.0": "5", "f5-windows-1252": "5",
                  "f5-entete-tronque": "5", "f6-v2.4.0": "6", "f6-windows-1252": "6", "f6-entete-tronque": "6"}
NB_TABLES = {"f2-v1.1.0": 22, "f3-v1.2.0": 24, "f3-v2.0.0": 24, "table-absente": 22, "plus-recent": 28,
             "f3-v2.1.0": 24, "reserves-a-reprendre": 24, "f4-v2.2.0": 27, "f4-windows-1252": 27,
             "f4-entete-tronque": 27, "f5-v2.2.0": 27, "f5-windows-1252": 27, "f5-entete-tronque": 27,
             "f6-v2.4.0": 27, "f6-windows-1252": 27, "f6-entete-tronque": 27}
# Jeux de la 2.2 (T378), au format 3 : chaque fichier, et la base
JEUX_DE_LA_2_2 = ("f3-v2.1.0", "reserves-a-reprendre")
COMMENTAIRE_LEVEE_REPRISE = "levée avant la 2.2, date inconnue"
# Réserves attendues de la reprise des observations (D183), dans l'ordre : (id, controle_id, date_controle, texte,
# levee) ; gravite, echeance_levee, date_levee et ot_id vides ; commentaire_levee : COMMENTAIRE_LEVEE_REPRISE si levee
# vaut '1', vide sinon.
RESERVES_ATTENDUES = {
    "f3-v2.1.0": [
        ("RES-00001", "CTR-0004", "2025-04-03",
         "Purgeur automatique du réservoir défectueux : à remplacer avant la prochaine inspection.", "0"),
    ],
    "reserves-a-reprendre": [
        ("RES-00001", "CTR-0001", "2026-02-10", "Garde-corps de la passerelle desserré", "0"),
        ("RES-00002", "CTR-0001", "2026-02-10", "Fin de course haut à régler", "0"),
        ("RES-00003", "CTR-0001", "2026-02-10", "Câble de levage : un toron cassé", "0"),
        ("RES-00004", "CTR-0002", "2026-03-18", "Klaxon de recul inaudible", "1"),
        ("RES-00005", "CTR-0002", "2026-03-18", "Ceinture du siège conducteur usée", "1"),
        ("RES-00006", "CTR-0005", "2026-03-24", "- Raccord de la vanne 3 suintant", "0"),
        ("RES-00007", "CTR-0005", "2026-03-24", "= Pression basse à surveiller", "0"),
        ("RES-00008", "CTR-0005", "2026-03-24", "- Étiquette du fluide illisible", "0"),
        ("RES-00009", "CTR-0006", "2026-06-02", 'Gaine "B" percée ; débit insuffisant', "0"),
        ("RES-00010", "CTR-0006", "2026-06-02", 'Filtre du caisson "F7" colmaté', "0"),
        ("RES-00011", "CTR-0007", "2026-01-15", "Cellule de sécurité inopérante", "0"),
        ("RES-00012", "CTR-0007", "2026-01-15", "Bord sensible fendu", "0"),
        ("RES-00013", "CTR-0007", "2026-01-15", "Signalisation au sol effacée", "0"),
        ("RES-00014", "CTR-0007", "2026-01-15", "Notice absente du local", "0"),
        ("RES-00015", "CTR-0008", "", "Rapport du contrôle initial non retrouvé", "0"),
    ],
}
# Jeu f4-v2.2.0 (T394) : tables que le format 4 complète (colonnes en fin) et tables qu'il ajoute ; réserves (id,
# controle_id, date_controle, texte, gravite, echeance_levee, levee, date_levee, commentaire_levee, ot_id), recopiées
# de LISEZMOI.md : la première est la reprise des observations de f3-v2.1.0 (RESERVES_ATTENDUES).
JEU_F4 = "f4-v2.2.0"
COLONNES_DU_FORMAT_4 = {
    "equipements": ["cout_arret_h"], "ordres_travail": ["habilitation_requise"],
    "habilitations": ["recyclage_mois", "justificatif", "catalogue_id", "nature_source"],
    "controles_reglementaires": ["source_periodicite", "nature_source", "catalogue_id", "catalogue_relu_le"]}
TABLES_DU_FORMAT_4 = ("reserves_controle", "garanties", "contrats_prestataires")
RESERVES_DU_F4 = [
    ("RES-00001", "CTR-0004", "2025-04-03",
     "Purgeur automatique du réservoir défectueux : à remplacer avant la prochaine inspection.", "", "", "0", "", "", ""),
    ("RES-00002", "CTR-0001", "2026-02-10", "Fin de course haut du palan à régler", "majeure", "2026-03-12", "0", "", "",
     ""),
    ("RES-00003", "CTR-0002", "2026-03-18", "Avertisseur sonore de recul inaudible", "mineure", "2026-04-17", "1",
     "2026-04-02", "Avertisseur remplacé, essai concluant", ""),
]
# Jeu f5-v2.2.0 (T513) : colonnes que le format 5 ajoute en fin de table (vides au passage 4→5) ; valeurs du jeu,
# recopiées de LISEZMOI.md.
JEU_F5 = "f5-v2.2.0"
COLONNES_DU_FORMAT_5 = {"demandes": ["mot_technicien", "date_reparation", "repare_par"],
                        "ordres_travail": ["cause_precision", "remede_precision", "prises_en_charge"]}
VALEURS_DU_F5 = {
    "demandes": {"DI-2025-0001": {"statut": "Réparée",
                                  "mot_technicien": "Capteur nettoyé et réglé, le tapis repart normalement.",
                                  "date_reparation": "2025-09-25 14:51", "repare_par": "Julien"}},
    "ordres_travail": {
        "OT-2025-0001": {"cause_precision": "Bride desserrée par les vibrations"},
        "OT-2025-0002": {"prises_en_charge": "2025-09-25 13:40|TEC-0002|\n2025-09-25 13:51|TEC-0001|TEC-0002"},
        "OT-2025-0005": {"cause_precision": "Câble pincé sous le carter", "remede_precision": "Câble remplacé et protégé"}},
}
# Jeu f6-v2.4.0 (T552) : colonnes que le format 6 ajoute en fin de table (vides au passage 5→6) ; valeurs du jeu,
# recopiées de LISEZMOI.md (MVT-000012 : toute la ligne, une pièce hors magasin à la place d'un inventaire).
JEU_F6 = "f6-v2.4.0"
COLONNES_DU_FORMAT_6 = {"equipements": ["risque_electrique"],
                        "ordres_travail": ["renforts", "releve_mot", "releve_par", "releve_le", "releve_motif",
                                           "remise_en_etat"],
                        "mouvements_stock": ["designation", "prix_unitaire"]}
VALEURS_DU_F6 = {
    "equipements": {"EQ-0001": {"risque_electrique": "basse tension"},
                    "EQ-0007": {"risque_electrique": "haute tension"}},
    "ordres_travail": {
        "OT-2025-0001": {"remise_en_etat": "Bride provisoire en place, à remplacer au prochain arrêt"},
        "OT-2025-0002": {"renforts": "TEC-0002"},
        "OT-2025-0005": {"releve_mot": "Carter démonté, câble commandé\nReste à le passer et à refermer",
                         "releve_par": "TEC-0001", "releve_le": "2025-09-26 17:05", "releve_motif": "fin de journée"}},
    "mouvements_stock": {"MVT-000012": {"date": "2025-09-26 16:40", "article_id": "", "type": "hors magasin",
                                        "quantite": "2", "ot_id": "OT-2025-0005", "utilisateur": "Julien",
                                        "commentaire": "Achetée au comptoir du fournisseur",
                                        "designation": "Serre-câble inox 200 mm", "prix_unitaire": "3.75"}},
}
# Fichiers sans BOM, par jeu (tous les autres CSV non vides en ont un) ; « * » : aucun CSV n'en a.
SANS_BOM = {"sans-bom": "*", "windows-1252": {"equipements.csv"}, "f4-windows-1252": {"equipements.csv"},
            "f5-windows-1252": {"equipements.csv"}, "f6-windows-1252": {"equipements.csv"}}
# Jeux dont equipements.csv est en Windows-1252 ; variantes abîmées tirées de f4-v2.2.0 (T404) : jeu → (variante
# tirée de f3-v1.2.0 faite de même, seul fichier qui change).
JEUX_WINDOWS_1252 = ("windows-1252", "f4-windows-1252", "f5-windows-1252", "f6-windows-1252")
ABIMES_DU_F4 = {"f4-windows-1252": ("windows-1252", "equipements.csv"),
                "f4-entete-tronque": ("entete-tronque", "ordres_travail.csv")}


def etiquettes_presentes():
    try:
        for etiquette in ETIQUETTES:
            subprocess.check_output(["git", "rev-parse", "--verify", "--quiet", etiquette + "^{commit}"],
                                    cwd=str(RACINE), stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def enregistrements(octets):
    """Nombre d'enregistrements CSV (en-tête exclu) : une fin de ligne entre guillemets n'en ouvre pas un."""
    n, entre_guillemets, debut = 0, False, 0
    for i, octet in enumerate(octets):
        if octet == 0x22:
            entre_guillemets = not entre_guillemets
        elif octet == 0x0A and not entre_guillemets:
            n, debut = n + 1, i + 1
    if debut < len(octets):
        n += 1
    return max(n - 1, 0)


def numeros_hors_plage(texte):
    return [m.group(0) for m in MOTIF_TELEPHONE.finditer(texte)
            if not ("0" + "".join(m.group(i) for i in (1, 3, 4, 5, 6))).startswith(PLAGES_FICTIVES)]


def version_schema(dossier):
    for ligne in (dossier / "parametres.csv").read_bytes().decode("utf-8-sig").splitlines():
        if ligne.startswith("version_schema;"):
            return ligne.split(";", 1)[1].lstrip("'")
    return None


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_formats_fixtures", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def lignes_en_dictionnaires(octets):
    """Lignes d'un CSV lu par le serveur (lire_csv_tolerant, cellules brutes) : {colonne: cellule}."""
    entete, lignes = serveur.lire_csv_tolerant(octets)
    return [{nom: (ligne[i] if i < len(ligne) else "") for i, nom in enumerate(entete)} for ligne in lignes]


def reserves_reprises(octets_controles):
    """Réserves que la reprise des observations (D183) doit créer à partir de controles_reglementaires.csv, sans
    réserve existante : règle de CONCEPTION-L1 §3.2 recopiée pour un jeu canonique (dates AAAA-MM-JJ ou vides, booléens
    0/1 : dateLue et booleenLu rendent la cellule telle quelle). (id, controle_id, date_controle, texte, levee)."""
    trim = serveur.sans_blancs_js_aux_bords
    reserves = []
    for controle in lignes_en_dictionnaires(octets_controles):
        identifiant = trim(controle["id"])
        texte = serveur.relire_valeur_texte(controle["observations"])
        if not identifiant or not trim(texte):
            continue
        levee = "1" if controle["observations_levees"] == "1" else "0"
        for morceau in re.split(r"\r\n|\r|\n", texte):
            if trim(morceau):
                reserves.append(("RES-%05d" % (len(reserves) + 1), identifiant, controle["derniere_date"], trim(morceau),
                                 levee))
    return reserves


class TestJeux(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def jeu(self, nom):
        return copier_jeu(nom, self.tmp / nom)

    def test_liste_des_jeux(self):
        self.assertEqual(sorted(JEUX), sorted([
            "f1", "f2-v1.1.0", "f3-v1.2.0", "f3-v2.0.0", "vide", "entete-tronque", "colonnes-manquantes",
            "colonnes-en-trop", "sans-bom", "table-absente", "melange", "windows-1252", "plus-recent", "f3-v2.1.0",
            "reserves-a-reprendre", "f4-v2.2.0", "f4-windows-1252", "f4-entete-tronque", "f5-v2.2.0",
            "f5-windows-1252", "f5-entete-tronque", "f6-v2.4.0", "f6-windows-1252", "f6-entete-tronque"]))

    def test_chaque_jeu_se_materialise(self):
        for nom in JEUX:
            with self.subTest(jeu=nom):
                dossier = self.jeu(nom)
                self.assertTrue((dossier / "parametres.csv").is_file())
                self.assertFalse((dossier / "variante.json").exists())
        with self.assertRaises(KeyError):
            copier_jeu("inconnu", self.tmp / "x")

    def test_les_variantes_ont_une_base_connue_et_une_description(self):
        for nom in JEUX:
            variante = lire_variante(nom)
            if variante is None:
                continue
            with self.subTest(jeu=nom):
                self.assertIn(variante["base"], JEUX)
                self.assertTrue(variante["description"])
                self.assertIsInstance(variante["supprimer"], list)
                self.assertIsInstance(variante["vider"], list)

    def test_version_schema(self):
        for nom, attendu in VERSION_SCHEMA.items():
            with self.subTest(jeu=nom):
                obtenu = version_schema(self.jeu(nom))
                if attendu is None:
                    self.assertIn(obtenu, (None, "1"))
                else:
                    self.assertEqual(obtenu, attendu)

    def test_nombre_de_tables(self):
        for nom, attendu in NB_TABLES.items():
            with self.subTest(jeu=nom):
                self.assertEqual(len(list(self.jeu(nom).glob("*.csv"))), attendu)

    def test_douze_enregistrements_au_plus(self):
        for nom in JEUX:
            dossier = self.jeu(nom)
            for chemin in sorted(dossier.glob("*.csv")):
                if chemin.name == "parametres.csv":
                    continue
                with self.subTest(jeu=nom, table=chemin.name):
                    self.assertLessEqual(enregistrements(chemin.read_bytes()), MAX_ENREGISTREMENTS)

    def test_les_bases_sont_tronquees(self):
        dossier = self.jeu("f3-v1.2.0")
        self.assertEqual(enregistrements((dossier / "equipements.csv").read_bytes()), 12)
        # une cellule multiligne reste entière : le premier enregistrement d'equipements en porte une
        corps = (dossier / "equipements.csv").read_bytes().split(b"\r\n", 1)[1]
        self.assertIn(b"\n", corps.split(b'"')[1])

    def test_bom(self):
        for nom in JEUX:
            dossier = self.jeu(nom)
            sans = SANS_BOM.get(nom, set())
            for chemin in sorted(dossier.glob("*.csv")):
                if chemin.stat().st_size == 0:
                    continue
                attendu = not (sans == "*" or chemin.name in sans)
                with self.subTest(jeu=nom, fichier=chemin.name):
                    self.assertEqual(chemin.read_bytes().startswith(BOM), attendu)

    def test_variantes_specifiques(self):
        self.assertEqual((self.jeu("vide") / "equipements.csv").stat().st_size, 0)
        self.assertFalse((self.jeu("table-absente") / "wiki_pages.csv").exists())
        self.assertFalse((self.jeu("table-absente") / "articles.csv").exists())
        entete = (self.jeu("entete-tronque") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0]
        self.assertTrue(entete.endswith(b"temps_pr"))
        entete = (self.jeu("melange") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0]
        self.assertNotIn(b"astuce", entete)
        entete = (self.jeu("plus-recent") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0]
        self.assertTrue(entete.endswith(
            b";prises_en_charge;renforts;releve_mot;releve_par;releve_le;releve_motif;remise_en_etat;nouvelle_colonne_v7"))
        # La table inconnue du format 7 (LISEZMOI : 3 colonnes, 2 lignes) ; la liste exacte des tables du jeu est vérifiée
        # par test_plus_recent_est_f6_plus_les_ajouts_du_format_7.
        pieces = (self.jeu("plus-recent") / "pieces_v7.csv").read_bytes()
        self.assertEqual(pieces.split(b"\r\n", 1)[0], BOM + b"id;designation;stock")
        self.assertEqual(len(lignes_en_dictionnaires(pieces)), 2)
        eq = (self.jeu("windows-1252") / "equipements.csv").read_bytes()
        with self.assertRaises(UnicodeDecodeError):
            eq.decode("utf-8")
        self.assertRegex(eq.decode("cp1252"), r";\d{2}/\d{2}/\d{4};")
        en_trop = (self.jeu("colonnes-en-trop") / "equipements.csv").read_bytes().decode("utf-8-sig").split("\r\n", 1)[0]
        self.assertIn("designation;colonne_maison;localisation_id", en_trop)
        self.assertTrue(en_trop.endswith(";note_maison"))
        manquantes = (self.jeu("colonnes-manquantes") / "equipements.csv").read_bytes().decode("utf-8-sig").split("\r\n", 1)[0].split(";")
        self.assertNotIn("modele", manquantes)
        self.assertNotIn("valeur_remplacement", manquantes)

    def test_jeux_de_la_2_2_au_format_3_cote_serveur(self):
        # Chaque fichier porte exactement les colonnes du format 3 (plus la colonne inconnue de reserves-a-reprendre)
        # et la base vaut 3 : ni plus récente, ni à passer au format 3 (lecture du navigateur : test_formats_js.py).
        for nom in JEUX_DE_LA_2_2:
            dossier = self.jeu(nom)
            with self.subTest(jeu=nom):
                self.assertEqual(serveur.version_de_base(lignes_en_dictionnaires(
                    (dossier / "parametres.csv").read_bytes())), 3)
                self.assertEqual(sorted(c.stem for c in dossier.glob("*.csv")), sorted(serveur.tables_du_format(3)))
                for chemin in sorted(dossier.glob("*.csv")):
                    entete, _ = serveur.lire_csv_tolerant(chemin.read_bytes())
                    attendu = serveur.colonnes_du_format(chemin.stem, 3)
                    if (nom, chemin.stem) == ("reserves-a-reprendre", "controles_reglementaires"):
                        attendu = attendu + ["remarque_maison"]
                    self.assertEqual(entete, attendu, chemin.name)
        self.assertNotEqual((self.jeu("f3-v2.1.0") / "controles_reglementaires.csv").read_bytes(),
                            (self.jeu("reserves-a-reprendre") / "controles_reglementaires.csv").read_bytes())

    def test_f4_au_format_4_cote_serveur_passe_au_format_5(self):
        # 27 tables, chacune aux colonnes exactes du format 4, base au format 4 : rien à reprendre (CTR-0004 a sa
        # réserve) ; relue et réécrite par le serveur, chaque table redonne ses octets. Depuis le format 5 (T513) :
        # format_du_fichier 4 pour demandes et ordres_travail (colonnes du format 5 absentes) ; depuis le format 6
        # (T552), 5 pour equipements et mouvements_stock (colonnes du format 6 absentes), 6 pour les autres ; le
        # passage 4→5→6 ajoute les colonnes des formats 5 et 6, vides, en fin, et ne change aucune autre valeur que le retour
        # des 5 demandes « Acceptée » dont l'OT est clôturé (T526 : « Réparée », date de fin, prénom du technicien ;
        # les 7 autres renvoient à un OT absent du jeu).
        dossier = self.jeu(JEU_F4)
        fichiers = {c.stem: c.read_bytes() for c in sorted(dossier.glob("*.csv"))}
        self.assertEqual(sorted(fichiers), sorted(serveur.tables_du_format(4)))
        base = {}
        for table, octets in fichiers.items():
            with self.subTest(table=table):
                entete, lignes = serveur.lire_csv_tolerant(octets)
                self.assertEqual(entete, serveur.colonnes_du_format(table, 4))
                self.assertEqual(serveur.format_du_fichier(table, entete), 4 if table in COLONNES_DU_FORMAT_5
                                 else 5 if table in COLONNES_DU_FORMAT_6 else 6)
                self.assertEqual(serveur.ecrire_tableau_csv(entete, lignes), octets)
                base[table] = {"entete": entete, "lignes": lignes_en_dictionnaires(octets)}
        self.assertEqual(serveur.version_de_base(base["parametres"]["lignes"]), 4)
        self.assertEqual({l["statut"] for l in base["demandes"]["lignes"]}, {"Acceptée"})
        migree, journal, etapes = serveur.migrer_tables(base, 4, serveur.VERSION_SCHEMA_CSV)
        self.assertEqual(journal, ["passage au format 5 du fichier", "passage au format 6 du fichier"])
        self.assertEqual([(e["de"], e["vers"]) for e in etapes], [(4, 5), (5, 6)])
        for table in base:
            with self.subTest(table=table):
                ajoutees = COLONNES_DU_FORMAT_5.get(table, []) + COLONNES_DU_FORMAT_6.get(table, [])
                if table == "parametres":
                    continue
                self.assertEqual(migree[table]["entete"], base[table]["entete"] + ajoutees)
                retours = [(retour_attendu(base, l) if table == "demandes" else None) or {}
                           for l in base[table]["lignes"]]
                self.assertEqual([{c: l[c] for c in base[table]["entete"]} for l in migree[table]["lignes"]],
                                 [dict(l, **{c: v for c, v in r.items() if c == "statut"})
                                  for l, r in zip(base[table]["lignes"], retours)])
                self.assertEqual([{c: l[c] for c in ajoutees} for l in migree[table]["lignes"]],
                                 [{c: r.get(c, "") for c in ajoutees} for r in retours])
        self.assertEqual([l["statut"] for l in migree["demandes"]["lignes"]], ["Réparée"] * 5 + ["Acceptée"] * 7)
        self.assertEqual(serveur.version_de_base(migree["parametres"]["lignes"]), 6)
        self.assertEqual(serveur.reserves_reprises(base["controles_reglementaires"]["lignes"],
                                                   base["reserves_controle"]["lignes"]), [])

    def test_f5_au_format_5_cote_serveur_passe_au_format_6(self):
        # T513 : 27 tables, chacune aux colonnes exactes du format 5 ; relue et réécrite par le serveur, chaque table
        # redonne ses octets. T552 : format_du_fichier 5 pour equipements, ordres_travail et mouvements_stock (colonnes
        # du format 6 absentes), 6 pour les autres ; le passage 5→6 ajoute les colonnes du format 6, vides, en fin, et
        # ne change aucune autre valeur.
        dossier = self.jeu(JEU_F5)
        fichiers = {c.stem: c.read_bytes() for c in sorted(dossier.glob("*.csv"))}
        self.assertEqual(sorted(fichiers), sorted(serveur.tables_du_format(5)))
        base = {}
        for table, octets in fichiers.items():
            with self.subTest(table=table):
                entete, lignes = serveur.lire_csv_tolerant(octets)
                self.assertEqual(entete, serveur.colonnes_du_format(table, 5))
                self.assertEqual(serveur.format_du_fichier(table, entete), 5 if table in COLONNES_DU_FORMAT_6 else 6)
                self.assertEqual(serveur.ecrire_tableau_csv(entete, lignes), octets)
                base[table] = {"entete": entete, "lignes": lignes_en_dictionnaires(octets)}
        self.assertEqual(serveur.version_de_base(base["parametres"]["lignes"]), 5)
        migree, journal, etapes = serveur.migrer_tables(base, 5, serveur.VERSION_SCHEMA_CSV)
        self.assertEqual(journal, ["passage au format 6 du fichier"])
        self.assertEqual([(e["de"], e["vers"]) for e in etapes], [(5, 6)])
        for table in base:
            if table == "parametres":
                continue
            with self.subTest(table=table):
                ajoutees = COLONNES_DU_FORMAT_6.get(table, [])
                self.assertEqual(migree[table]["entete"], base[table]["entete"] + ajoutees)
                self.assertEqual(migree[table]["lignes"],
                                 [dict(l, **{c: "" for c in ajoutees}) for l in base[table]["lignes"]])
        self.assertEqual(serveur.version_de_base(migree["parametres"]["lignes"]), 6)

    def test_f6_au_format_6_cote_serveur_rien_a_migrer(self):
        # T552 : 27 tables, chacune aux colonnes exactes du format 6 (format_du_fichier 6), base au format 6 : rien à
        # migrer ni à reprendre ; relue et réécrite par le serveur, chaque table redonne ses octets.
        dossier = self.jeu(JEU_F6)
        fichiers = {c.stem: c.read_bytes() for c in sorted(dossier.glob("*.csv"))}
        self.assertEqual(sorted(fichiers), sorted(serveur.tables_du_format(6)))
        base = {}
        for table, octets in fichiers.items():
            with self.subTest(table=table):
                entete, lignes = serveur.lire_csv_tolerant(octets)
                self.assertEqual(entete, serveur.colonnes_du_format(table, 6))
                self.assertEqual(serveur.format_du_fichier(table, entete), 6)
                self.assertEqual(serveur.ecrire_tableau_csv(entete, lignes), octets)
                base[table] = {"entete": entete, "lignes": lignes_en_dictionnaires(octets)}
        self.assertEqual(serveur.version_de_base(base["parametres"]["lignes"]), 6)
        migree, journal, etapes = serveur.migrer_tables(base, 6, serveur.VERSION_SCHEMA_CSV)
        self.assertIs(migree, base)
        self.assertEqual((journal, etapes), ([], []))

    def test_f6_tire_de_f5_avec_les_valeurs_du_format_6(self):
        # T552 : seuls equipements, ordres_travail, mouvements_stock et parametres diffèrent de f5-v2.2.0 ; colonnes du
        # format 6 en fin, cellules d'avant inchangées sauf la ligne MVT-000012 (pièce hors magasin) ; valeurs du
        # LISEZMOI.
        f6, f5 = self.jeu(JEU_F6), self.jeu(JEU_F5)
        self.assertEqual(sorted(c.name for c in f6.glob("*.csv")), sorted(c.name for c in f5.glob("*.csv")))
        for chemin in sorted(f5.glob("*.csv")):
            table = chemin.stem
            with self.subTest(table=table):
                if table == "parametres":
                    self.assertEqual((f6 / chemin.name).read_bytes(), chemin.read_bytes().replace(
                        b"version_schema;'5\r\n", b"version_schema;'6\r\n"))
                    continue
                if table not in COLONNES_DU_FORMAT_6:
                    self.assertEqual((f6 / chemin.name).read_bytes(), chemin.read_bytes())
                    continue
                entete_avant, _ = serveur.lire_csv_tolerant(chemin.read_bytes())
                entete_apres, _ = serveur.lire_csv_tolerant((f6 / chemin.name).read_bytes())
                self.assertEqual(entete_apres, entete_avant + COLONNES_DU_FORMAT_6[table])
                avant = lignes_en_dictionnaires(chemin.read_bytes())
                apres = lignes_en_dictionnaires((f6 / chemin.name).read_bytes())
                self.assertEqual(len(apres), len(avant))
                valeurs = VALEURS_DU_F6[table]
                for a, l in zip(avant, apres):
                    attendu = dict(a, **{c: "" for c in COLONNES_DU_FORMAT_6[table]})
                    attendu.update(valeurs.get(a["id"], {}))
                    self.assertEqual(l, attendu, a["id"])
        mouvements = lignes_en_dictionnaires((f6 / "mouvements_stock.csv").read_bytes())
        self.assertEqual([l["id"] for l in mouvements if l["type"] == "hors magasin"], ["MVT-000012"])
        lisezmoi = LISEZMOI.read_text(encoding="utf-8")
        self.assertIn("**f6-v2.4.0**", lisezmoi)
        for valeur in ("Serre-câble inox 200 mm", "`prix_unitaire` `3.75`", "Bride provisoire en place",
                       "`renforts` `TEC-0002`", "motif `fin de journée`"):
            self.assertIn(valeur, lisezmoi)

    def test_f5_tire_de_f4_avec_les_valeurs_du_format_5(self):
        # T513 : seuls demandes, ordres_travail et parametres diffèrent de f4-v2.2.0 ; colonnes du format 5 en fin,
        # cellules d'avant inchangées sauf le statut de DI-2025-0001 (« Réparée ») ; valeurs du LISEZMOI.
        f5, f4 = self.jeu(JEU_F5), self.jeu(JEU_F4)
        self.assertEqual(sorted(c.name for c in f5.glob("*.csv")), sorted(c.name for c in f4.glob("*.csv")))
        for chemin in sorted(f4.glob("*.csv")):
            table = chemin.stem
            with self.subTest(table=table):
                if table == "parametres":
                    self.assertEqual((f5 / chemin.name).read_bytes(), chemin.read_bytes().replace(
                        b"version_schema;'4\r\n", b"version_schema;'5\r\n"))
                    continue
                if table not in COLONNES_DU_FORMAT_5:
                    self.assertEqual((f5 / chemin.name).read_bytes(), chemin.read_bytes())
                    continue
                entete_avant, _ = serveur.lire_csv_tolerant(chemin.read_bytes())
                entete_apres, _ = serveur.lire_csv_tolerant((f5 / chemin.name).read_bytes())
                self.assertEqual(entete_apres, entete_avant + COLONNES_DU_FORMAT_5[table])
                avant = lignes_en_dictionnaires(chemin.read_bytes())
                apres = lignes_en_dictionnaires((f5 / chemin.name).read_bytes())
                self.assertEqual(len(apres), len(avant))
                valeurs = VALEURS_DU_F5[table]
                for a, l in zip(avant, apres):
                    attendu = dict(a, **{c: "" for c in COLONNES_DU_FORMAT_5[table]})
                    attendu.update(valeurs.get(a["id"], {}))
                    self.assertEqual(l, attendu, a["id"])
        statuts = [l["statut"] for l in lignes_en_dictionnaires((f5 / "demandes.csv").read_bytes())]
        self.assertEqual(statuts, ["Réparée"] + ["Acceptée"] * 11)
        lisezmoi = LISEZMOI.read_text(encoding="utf-8")
        self.assertIn("**f5-v2.2.0**", lisezmoi)
        for valeur in ("Capteur nettoyé et réglé, le tapis", "`repare_par` `Julien`", "2025-09-25 13:40|TEC-0002|",
                       "2025-09-25 13:51|TEC-0001|TEC-0002"):
            self.assertIn(valeur, lisezmoi)

    def test_f4_tire_de_f3_v2_1_0_avec_les_valeurs_du_format_4(self):
        f4, f3 = self.jeu(JEU_F4), self.jeu("f3-v2.1.0")
        for chemin in sorted(f3.glob("*.csv")):
            table = chemin.stem
            with self.subTest(table=table):
                if table == "parametres":
                    self.assertEqual((f4 / chemin.name).read_bytes(), chemin.read_bytes().replace(
                        b"version_schema;'3\r\n", b"version_schema;'4\r\n"))
                    continue
                if table not in COLONNES_DU_FORMAT_4:
                    self.assertEqual((f4 / chemin.name).read_bytes(), chemin.read_bytes())
                    continue
                # Colonnes du format 4 en fin, les cellules de la 2.1 inchangées, ligne pour ligne
                entete_avant, _ = serveur.lire_csv_tolerant(chemin.read_bytes())
                entete_apres, _ = serveur.lire_csv_tolerant((f4 / chemin.name).read_bytes())
                self.assertEqual(entete_apres, entete_avant + COLONNES_DU_FORMAT_4[table])
                avant = lignes_en_dictionnaires(chemin.read_bytes())
                apres = lignes_en_dictionnaires((f4 / chemin.name).read_bytes())
                self.assertEqual(len(apres), len(avant))
                self.assertEqual([{c: l[c] for c in a} for a, l in zip(avant, apres)], avant)
        valeurs = {table: lignes_en_dictionnaires((f4 / (table + ".csv")).read_bytes())
                   for table in list(COLONNES_DU_FORMAT_4) + list(TABLES_DU_FORMAT_4)}

        def remplies(table, colonne):
            return [l["id"] for l in valeurs[table] if l[colonne]]

        self.assertEqual(remplies("equipements", "cout_arret_h"), ["EQ-0001", "EQ-0007"])
        self.assertEqual(remplies("ordres_travail", "habilitation_requise"), ["OT-2025-0005"])
        for colonne in COLONNES_DU_FORMAT_4["habilitations"]:
            self.assertEqual(remplies("habilitations", colonne), ["HAB-0001", "HAB-0004"], colonne)
        controles = valeurs["controles_reglementaires"]
        self.assertEqual([(l["id"], l["source_periodicite"], l["nature_source"], l["catalogue_id"])
                          for l in controles if l["source_periodicite"] != "saisie" or l["nature_source"]],
                         [("CTR-0001", "catalogue", "obligation", "C01"), ("CTR-0002", "catalogue", "obligation", "C03")])
        self.assertEqual(len([l for l in controles if l["source_periodicite"] == "saisie"]), len(controles) - 2)
        # Réserves : la reprise de la 2.1 (règle D183 sur f3-v2.1.0), une ouverte, une levée datée ; LISEZMOI.md
        self.assertEqual([tuple(l.values()) for l in valeurs["reserves_controle"]], RESERVES_DU_F4)
        self.assertEqual([r[:4] + (r[6],) for r in RESERVES_DU_F4[:1]],
                         reserves_reprises((f3 / "controles_reglementaires.csv").read_bytes()))
        ouverte, levee = RESERVES_DU_F4[1], RESERVES_DU_F4[2]
        self.assertEqual((ouverte[6], ouverte[7]), ("0", ""))
        self.assertEqual(levee[6], "1")
        self.assertRegex(levee[7], r"\A\d{4}-\d{2}-\d{2}\Z")
        lisezmoi = LISEZMOI.read_text(encoding="utf-8")
        for reserve in RESERVES_DU_F4:
            self.assertIn("| " + " | ".join(c or "(vide)" for c in reserve) + " |", lisezmoi)
        self.assertEqual([l["id"] for l in valeurs["garanties"]], ["GAR-0001", "GAR-0002"])
        self.assertEqual([(l["id"], l["reconduction_tacite"]) for l in valeurs["contrats_prestataires"]],
                         [("CTP-0001", "1"), ("CTP-0002", "0")])

    def test_plus_recent_est_f6_plus_les_ajouts_du_format_7(self):
        # Toutes les tables et colonnes du format 6 (aucune à compléter), plus nouvelle_colonne_v7 en fin des OT et la
        # table pieces_v7, et aucun justificatif cité (le jeu ne fournit pas de documents) ; les autres fichiers sont
        # ceux de f6-v2.4.0, à l'octet.
        recent, f4 = self.jeu("plus-recent"), self.jeu(JEU_F6)
        self.assertEqual(sorted(c.name for c in recent.glob("*.csv")),
                         sorted([c.name for c in f4.glob("*.csv")] + ["pieces_v7.csv"]))
        for chemin in sorted(f4.glob("*.csv")):
            with self.subTest(fichier=chemin.name):
                if chemin.name in ("parametres.csv", "ordres_travail.csv", "habilitations.csv"):
                    continue
                self.assertEqual((recent / chemin.name).read_bytes(), chemin.read_bytes())
        habilitations = lignes_en_dictionnaires((recent / "habilitations.csv").read_bytes())
        self.assertEqual({l["justificatif"] for l in habilitations}, {""})
        self.assertEqual([dict(l, justificatif="") for l in lignes_en_dictionnaires(
            (f4 / "habilitations.csv").read_bytes())], habilitations)
        self.assertEqual((recent / "parametres.csv").read_bytes(), (f4 / "parametres.csv").read_bytes().replace(
            b"version_schema;'6\r\n", b"version_schema;'7\r\n"))
        entete, lignes = serveur.lire_csv_tolerant((recent / "ordres_travail.csv").read_bytes())
        entete_f4, lignes_f4 = serveur.lire_csv_tolerant((f4 / "ordres_travail.csv").read_bytes())
        self.assertEqual(entete, entete_f4 + ["nouvelle_colonne_v7"])
        self.assertEqual([l[:-1] for l in lignes], lignes_f4)
        self.assertEqual([l[-1] for l in lignes], ["v7-%d" % n for n in range(1, len(lignes) + 1)])

    def test_abimes_tires_de_f4_seul_le_fichier_abime_change(self):
        # T404 : f4-v2.2.0 à l'octet près, sauf le fichier abîmé, fabriqué comme dans la variante tirée de f3-v1.2.0 ;
        # base au format 4 et autres fichiers au format 4 : aucun passage de format avant le contrôle (le cas pur).
        f4 = self.jeu(JEU_F4)
        for nom, (variante_f3, fichier) in sorted(ABIMES_DU_F4.items()):
            dossier = self.jeu(nom)
            with self.subTest(jeu=nom):
                self.assertEqual(lire_variante(nom)["base"], JEU_F4)
                self.assertEqual(sorted(c.name for c in dossier.glob("*.csv")), sorted(c.name for c in f4.glob("*.csv")))
                for chemin in sorted(f4.glob("*.csv")):
                    if chemin.name != fichier:
                        self.assertEqual((dossier / chemin.name).read_bytes(), chemin.read_bytes(), chemin.name)
                self.assertNotEqual((dossier / fichier).read_bytes(), (f4 / fichier).read_bytes())
                self.assertNotEqual((dossier / fichier).read_bytes(), (self.jeu(variante_f3) / fichier).read_bytes())
                self.assertEqual(serveur.version_de_base(lignes_en_dictionnaires(
                    (dossier / "parametres.csv").read_bytes())), 4)
        # f4-entete-tronque : le même en-tête coupé que entete-tronque (habilitation_requise venait après), les lignes
        # de données de f4-v2.2.0 à l'octet ; en-tête illisible pour le serveur (format 0).
        tronque = (self.jeu("f4-entete-tronque") / "ordres_travail.csv").read_bytes()
        entete, corps = tronque.split(b"\r\n", 1)
        entete_f4, corps_f4 = (f4 / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)
        self.assertEqual(corps, corps_f4)
        self.assertTrue(entete.endswith(b"temps_pr") and entete_f4.startswith(entete))
        self.assertEqual(entete, (self.jeu("entete-tronque") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0])
        self.assertEqual(serveur.format_du_fichier("ordres_travail", serveur.lire_csv_tolerant(tronque)[0]), 0)
        # f4-windows-1252 : sans BOM, illisible en UTF-8 ; relu en Windows-1252, les cellules de f4-v2.2.0, dates
        # date_mes en JJ/MM/AAAA (aucun caractère de ce fichier n'est hors de Windows-1252 : aucun « ? »).
        octets = (self.jeu("f4-windows-1252") / "equipements.csv").read_bytes()
        self.assertFalse(octets.startswith(BOM))
        with self.assertRaises(UnicodeDecodeError):
            octets.decode("utf-8")
        lues = list(csv.reader(io.StringIO(octets.decode("cp1252"), newline=""), delimiter=";"))
        propres = list(csv.reader(io.StringIO((f4 / "equipements.csv").read_bytes().decode("utf-8-sig"), newline=""),
                                  delimiter=";"))
        self.assertEqual(lues[0], propres[0])
        date_mes = lues[0].index("date_mes")
        self.assertTrue(all(re.fullmatch(r"(\d{2}/\d{2}/\d{4})?", l[date_mes]) for l in lues[1:]))
        self.assertTrue(any(l[date_mes] for l in lues[1:]))
        self.assertEqual([[re.sub(r"\A(\d{2})/(\d{2})/(\d{4})\Z", r"\3-\2-\1", c) if i == date_mes else c
                           for i, c in enumerate(l)] for l in lues[1:]], propres[1:])

    def test_abimes_tires_de_f5_seul_le_fichier_abime_change(self):
        # T513 : f5-v2.2.0 à l'octet près, sauf le fichier abîmé, le même que dans la variante tirée de f4-v2.2.0
        # (equipements) ou fabriqué de même (en-tête d'ordres_travail coupé, lignes de f5-v2.2.0) ; base au format 5.
        f5 = self.jeu(JEU_F5)
        for nom, (variante_f4, fichier) in sorted({"f5-windows-1252": ("f4-windows-1252", "equipements.csv"),
                                                   "f5-entete-tronque": ("f4-entete-tronque",
                                                                         "ordres_travail.csv")}.items()):
            dossier = self.jeu(nom)
            with self.subTest(jeu=nom):
                self.assertEqual(lire_variante(nom)["base"], JEU_F5)
                self.assertEqual(sorted(c.name for c in dossier.glob("*.csv")), sorted(c.name for c in f5.glob("*.csv")))
                for chemin in sorted(f5.glob("*.csv")):
                    if chemin.name != fichier:
                        self.assertEqual((dossier / chemin.name).read_bytes(), chemin.read_bytes(), chemin.name)
                self.assertNotEqual((dossier / fichier).read_bytes(), (f5 / fichier).read_bytes())
                self.assertEqual(serveur.version_de_base(lignes_en_dictionnaires(
                    (dossier / "parametres.csv").read_bytes())), 5)
        self.assertEqual((self.jeu("f5-windows-1252") / "equipements.csv").read_bytes(),
                         (self.jeu("f4-windows-1252") / "equipements.csv").read_bytes())
        tronque = (self.jeu("f5-entete-tronque") / "ordres_travail.csv").read_bytes()
        entete, corps = tronque.split(b"\r\n", 1)
        self.assertEqual(corps, (f5 / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[1])
        self.assertEqual(entete, (self.jeu("entete-tronque") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0])
        self.assertEqual(serveur.format_du_fichier("ordres_travail", serveur.lire_csv_tolerant(tronque)[0]), 0)

    def test_abimes_tires_de_f6_seul_le_fichier_abime_change(self):
        # T552 : f6-v2.4.0 à l'octet près, sauf le fichier abîmé (equipements.csv de f6-v2.4.0 en Windows-1252, dates en
        # JJ/MM/AAAA ; en-tête d'ordres_travail coupé, lignes de f6-v2.4.0) ; base au format 6 : le cas pur.
        f6 = self.jeu(JEU_F6)
        for nom, fichier in (("f6-windows-1252", "equipements.csv"), ("f6-entete-tronque", "ordres_travail.csv")):
            dossier = self.jeu(nom)
            with self.subTest(jeu=nom):
                self.assertEqual(lire_variante(nom)["base"], JEU_F6)
                self.assertEqual(sorted(c.name for c in dossier.glob("*.csv")), sorted(c.name for c in f6.glob("*.csv")))
                for chemin in sorted(f6.glob("*.csv")):
                    if chemin.name != fichier:
                        self.assertEqual((dossier / chemin.name).read_bytes(), chemin.read_bytes(), chemin.name)
                self.assertNotEqual((dossier / fichier).read_bytes(), (f6 / fichier).read_bytes())
                self.assertEqual(serveur.version_de_base(lignes_en_dictionnaires(
                    (dossier / "parametres.csv").read_bytes())), 6)
        octets = (self.jeu("f6-windows-1252") / "equipements.csv").read_bytes()
        self.assertFalse(octets.startswith(BOM))
        lues = list(csv.reader(io.StringIO(octets.decode("cp1252"), newline=""), delimiter=";"))
        propres = list(csv.reader(io.StringIO((f6 / "equipements.csv").read_bytes().decode("utf-8-sig"), newline=""),
                                  delimiter=";"))
        self.assertEqual(lues[0], propres[0])
        self.assertEqual(lues[0][-1], "risque_electrique")
        date_mes = lues[0].index("date_mes")
        self.assertEqual([[re.sub(r"\A(\d{2})/(\d{2})/(\d{4})\Z", r"\3-\2-\1", c) if i == date_mes else c
                           for i, c in enumerate(l)] for l in lues[1:]], propres[1:])
        tronque = (self.jeu("f6-entete-tronque") / "ordres_travail.csv").read_bytes()
        entete, corps = tronque.split(b"\r\n", 1)
        self.assertEqual(corps, (f6 / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[1])
        self.assertEqual(entete, (self.jeu("entete-tronque") / "ordres_travail.csv").read_bytes().split(b"\r\n", 1)[0])
        self.assertEqual(serveur.format_du_fichier("ordres_travail", serveur.lire_csv_tolerant(tronque)[0]), 0)

    def test_controles_a_reprendre_ecrits_comme_prevo(self):
        octets = (self.jeu("reserves-a-reprendre") / "controles_reglementaires.csv").read_bytes()
        entete, lignes = serveur.lire_csv_tolerant(octets)
        # Réécrites par Prévo, les cellules redonnent les octets du fichier (BOM, « ; », CRLF, guillemets)
        self.assertEqual(serveur.ecrire_tableau_csv(entete, lignes), octets)
        self.assertLessEqual(len(lignes), MAX_ENREGISTREMENTS)
        for numero, controle in enumerate(lignes_en_dictionnaires(octets), start=2):
            with self.subTest(ligne=numero):
                for colonne in ("derniere_date", "prochaine_date"):
                    self.assertRegex(controle[colonne], r"\A(\d{4}-\d{2}-\d{2})?\Z")
                self.assertIn(controle["observations_levees"], ("0", "1"))
                for colonne, cellule in controle.items():
                    # Donnees.csv.analyser retirerait une espace, une tabulation ou un CR en fin de cellule
                    self.assertNotRegex(cellule, r"[ \t\r]\Z", colonne)
                texte = serveur.relire_valeur_texte(controle["observations"])
                self.assertEqual(serveur.ecrire_valeur_texte(texte), controle["observations"])  # apostrophe juste
        observations = [serveur.relire_valeur_texte(c["observations"]) for c in lignes_en_dictionnaires(octets)]
        tout = "\n".join(observations)
        for motif in (r"\r\n", r"\r(?!\n)", r"(?<!\r)\n", ";", '"', r"(?m)^- ", r"(?m)^= ", r"(?m)^[ \t]+$"):
            self.assertRegex(tout, motif)
        self.assertTrue(any(re.search(r"\r\n", t) and re.search(r"\r(?!\n)", t) and re.search(r"(?<!\r)\n", t)
                            for t in observations), "CRLF, LF et CR dans une même cellule")
        self.assertTrue(observations[4].startswith("- "))
        self.assertTrue(lignes[4][entete.index("observations")].startswith("'- "))
        sans_date = [c for c in lignes_en_dictionnaires(octets) if c["observations"] and not c["derniere_date"]]
        self.assertEqual(len(sans_date), 1)
        vides = {(c["observations"], c["observations_levees"]) for c in lignes_en_dictionnaires(octets)}
        self.assertTrue({("", "0"), ("", "1")} <= vides)

    def test_reserves_attendues_selon_d183(self):
        lisezmoi = LISEZMOI.read_text(encoding="utf-8")
        self.assertIn(COMMENTAIRE_LEVEE_REPRISE, lisezmoi)
        for nom, attendues in sorted(RESERVES_ATTENDUES.items()):
            dossier = self.jeu(nom)
            with self.subTest(jeu=nom):
                self.assertFalse((dossier / "reserves_controle.csv").exists())
                self.assertEqual(reserves_reprises((dossier / "controles_reglementaires.csv").read_bytes()), attendues)
                for identifiant, controle, date, texte, levee in attendues:
                    ligne = "| %s | %s | %s | %s | %s |" % (identifiant, controle, date or "(vide)", texte, levee)
                    self.assertIn(ligne, lisezmoi)

    def test_comptes_de_la_2_0(self):
        dossier = self.jeu("f3-v2.0.0")
        contenu = json.loads((dossier / "acces" / "comptes.json").read_text(encoding="utf-8"))
        self.assertEqual(contenu["version"], 1)
        self.assertEqual([c["role"] for c in contenu["comptes"]], ["responsable"])
        parametres = (dossier / "parametres.csv").read_bytes().decode("utf-8-sig")
        for cle in ("mode_solo;'1", "cloture_une_etape;'1", "solo_technicien_id;TEC-0001"):
            self.assertIn(cle, parametres)
        # le mot de passe documenté retombe sur l'empreinte stockée
        compte = contenu["comptes"][0]
        calcule = hashlib.scrypt(b"essai-formats-prevo", salt=base64.b64decode(compte["sel"]), n=2 ** 15, r=8, p=3,
                                 maxmem=64 * 1024 * 1024, dklen=32)
        self.assertEqual(base64.b64encode(calcule).decode("ascii"), compte["empreinte"])

    def test_donnees_fictives(self):
        for nom in JEUX:
            for chemin in sorted(self.jeu(nom).rglob("*.csv")):
                texte = chemin.read_bytes().decode("cp1252" if nom in JEUX_WINDOWS_1252 else "utf-8", "replace")
                with self.subTest(jeu=nom, fichier=chemin.name):
                    self.assertEqual(numeros_hors_plage(texte), [])
                    for courriel in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)*", texte):
                        self.assertTrue(courriel.endswith(".example"), courriel)


class TestGenerateurReproductible(unittest.TestCase):
    def test_le_generateur_redonne_les_memes_octets(self):
        if not etiquettes_presentes():
            self.skipTest("git ou les étiquettes %s sont indisponibles" % ", ".join(ETIQUETTES))
        with tempfile.TemporaryDirectory() as tmp:
            sortie = Path(tmp) / "formats"
            subprocess.check_call([sys.executable, "-I", str(GENERATEUR), "--sortie", str(sortie)],
                                  stdout=subprocess.DEVNULL, cwd=str(RACINE))
            attendus = {c.relative_to(DOSSIER_JEUX).as_posix(): c.read_bytes() for c in DOSSIER_JEUX.rglob("*")
                        if c.is_file() and c.name != "LISEZMOI.md"}
            obtenus = {c.relative_to(sortie).as_posix(): c.read_bytes() for c in sortie.rglob("*")
                       if c.is_file() and c.name != "LISEZMOI.md"}
            self.assertEqual(sorted(obtenus), sorted(attendus))
            for nom in sorted(attendus):
                with self.subTest(fichier=nom):
                    self.assertEqual(obtenus[nom], attendus[nom])


if __name__ == "__main__":
    unittest.main()
