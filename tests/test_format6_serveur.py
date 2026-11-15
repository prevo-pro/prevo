"""Format 6 (T552, lot 2 ergonomie, livraison 2) côté serveur : la pièce hors magasin et ses droits.

Ce qui est vérifié, sans navigateur, sur serveur.py importé comme module (aucune donnée réelle : lignes fabriquées) :
    prix caché     mouvements_stock.prix_unitaire (prix d'une pièce hors magasin) suit la règle des prix cachés au
                   technicien (D126, comme articles.prix_unitaire) : à la lecture, le nom reste dans l'en-tête (colonne
                   d'un format suivant, comme cout_arret_h) et les valeurs sont vidées ; designation et les autres
                   cellules sont servies telles quelles ; le responsable et la Direction reçoivent le fichier tel quel ;
                   PUT du technicien : chaque prix du fichier gardé ligne par ligne, prix forgé ignoré, ligne nouvelle
                   sans prix ; ajout du technicien : prix vidé ; responsable : aucun contrôle ;
    demandeur      ne lit ni ordres_travail ni mouvements_stock (TABLES_DU_DEMANDEUR inchangée) ; aucune nouvelle colonne
                   n'est cachée à un autre rôle que le technicien ;
    hors magasin   une ligne « hors magasin » sans article passe le contrôle du contenu d'un PUT (article_id n'est exigé
                   ni par le schéma ni par le serveur).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_format6_serveur.py" -v
"""
import csv
import importlib.util
import io
import unittest

from commun import RACINE

TABLE = "mouvements_stock"
BOM = bytes((0xEF, 0xBB, 0xBF))


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_t552", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()
ENTETE = list(serveur.COLONNES_PAR_TABLE[TABLE])
# Une sortie d'article (prix vide : celui de l'article fait foi) et deux pièces hors magasin, une avec prix.
LIGNES = [
    ["MVT-000001", "2026-11-10 08:00", "ART-0001", "sortie", "1", "OT-2026-0001", "Julien", "", "", ""],
    ["MVT-000002", "2026-11-10 09:30", "", "hors magasin", "2", "OT-2026-0001", "Julien", "Achetée au comptoir",
     "Serre-câble inox 200 mm", "3.75"],
    ["MVT-000003", "2026-11-11 14:00", "", "hors magasin", "1", "OT-2026-0002", "Karim", "", "Joint torique 40x3",
     "12.5"],
]
TECHNICIEN = {"role": "technicien"}
RESPONSABLE = {"role": "responsable"}
DIRECTION = {"role": "direction"}


def octets_de(entete, lignes):
    return serveur.ecrire_tableau_csv(entete, lignes)


def lire(octets):
    lignes = [l for l in csv.reader(io.StringIO(octets.decode("utf-8-sig"), newline=""), delimiter=";") if l]
    return lignes[0], lignes[1:]


def corps_d_ajout(lignes):
    return "".join(";".join(serveur.cellule_csv(c) for c in ligne) + "\r\n" for ligne in lignes).encode("utf-8")


class TestPrixDeLaPieceHorsMagasin(unittest.TestCase):

    def setUp(self):
        self.fichier = octets_de(ENTETE, LIGNES)
        self.p_prix = ENTETE.index("prix_unitaire")

    def test_colonnes_du_format_6_en_fin_de_mouvements_stock(self):
        self.assertEqual(ENTETE[-2:], ["designation", "prix_unitaire"])
        self.assertEqual(serveur.PREMIER_FORMAT_DES_COLONNES[TABLE], {"designation": 6, "prix_unitaire": 6})

    def test_technicien_lit_l_en_tete_entier_et_aucun_prix(self):
        entete, lignes = lire(serveur.filtrer_csv_pour(TECHNICIEN, TABLE, self.fichier))
        self.assertEqual(entete, ENTETE)                                     # nom gardé : colonne d'un format suivant
        self.assertEqual({l[self.p_prix] for l in lignes}, {""})
        self.assertEqual([l[:self.p_prix] for l in lignes], [l[:self.p_prix] for l in LIGNES])
        self.assertNotIn(b"3.75", serveur.filtrer_csv_pour(TECHNICIEN, TABLE, self.fichier))

    def test_responsable_direction_et_sans_comptes_lisent_le_fichier_tel_quel(self):
        for identite in (RESPONSABLE, DIRECTION, None):
            with self.subTest(identite=identite):
                self.assertEqual(serveur.filtrer_csv_pour(identite, TABLE, self.fichier), self.fichier)

    def test_put_du_technicien_garde_chaque_prix_du_fichier(self):
        recues = [list(l) for l in LIGNES]
        recues[0][self.p_prix] = ""                       # ce qu'il a lu
        recues[1][self.p_prix] = "0.01"                   # prix forgé : ignoré
        recues[2][self.p_prix] = ""                       # lu vide : le prix du fichier revient
        recues.append(["MVT-000004", "2026-11-12 10:00", "", "hors magasin", "1", "OT-2026-0003", "Julien", "",
                       "Fusible 10 A", "999"])            # ligne nouvelle : sans prix
        controler = serveur.controle_d_ecriture(TECHNICIEN, TABLE)
        ecrites = controler(octets_de(ENTETE, recues), self.fichier)
        _, lignes = lire(ecrites)
        self.assertEqual([l[self.p_prix] for l in lignes], ["", "3.75", "12.5", ""])
        self.assertEqual(lignes[3][ENTETE.index("designation")], "Fusible 10 A")

    def test_ajout_du_technicien_sans_prix_responsable_avec(self):
        nouvelle = ["MVT-000004", "2026-11-12 10:00", "", "hors magasin", "1", "OT-2026-0003", "Julien", "",
                    "Fusible 10 A", "999"]
        entete = ";".join(ENTETE).encode("utf-8")
        ajoutees = serveur.controle_d_ajout(TECHNICIEN, TABLE)(entete, corps_d_ajout([nouvelle]), self.fichier)
        rangee = next(csv.reader(io.StringIO(ajoutees.decode("utf-8"), newline=""), delimiter=";"))
        self.assertEqual(rangee[self.p_prix], "")
        self.assertEqual(rangee[ENTETE.index("designation")], "Fusible 10 A")
        self.assertIsNone(serveur.controle_d_ajout(RESPONSABLE, TABLE))
        self.assertIsNone(serveur.controle_d_ecriture(RESPONSABLE, TABLE))


class TestDroitsInchanges(unittest.TestCase):

    def test_seul_le_technicien_a_une_colonne_nouvelle_cachee(self):
        nouvelles = {(t, c) for t, colonnes in serveur.PREMIER_FORMAT_DES_COLONNES.items()
                     for c, f in colonnes.items() if f == 6}
        for role, tables in serveur.COLONNES_CACHEES_PAR_ROLE.items():
            cachees = {(t, c) for t, colonnes in tables.items() for c in colonnes} & nouvelles
            with self.subTest(role=role):
                self.assertEqual(cachees, {(TABLE, "prix_unitaire")} if role == "technicien" else set())

    def test_le_demandeur_ne_lit_ni_les_ot_ni_les_mouvements(self):
        for table in ("ordres_travail", TABLE):
            self.assertNotIn(table, serveur.TABLES_DU_DEMANDEUR)


class TestHorsMagasinSansArticle(unittest.TestCase):

    def test_ligne_sans_article_acceptee_par_le_controle_du_contenu(self):
        octets = octets_de(ENTETE, LIGNES)
        self.assertTrue(octets.startswith(BOM))
        serveur.verifier_contenu_csv(TABLE, octets)       # aucune exception : article_id facultatif


if __name__ == "__main__":
    unittest.main()
