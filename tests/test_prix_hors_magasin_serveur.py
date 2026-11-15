"""Réglage « Les techniciens peuvent saisir le prix des pièces hors magasin » (T558, L25, décision de Nicolas du 15/11),
côté serveur (sans navigateur).

    désactivé   (défaut, ligne absente ou 0) : mouvements_stock.prix_unitaire reste caché au technicien comme
                articles.prix_unitaire (D126) : vidé à la lecture, remis depuis le fichier au PUT, vidé à l'ajout ;
    activé      le technicien lit et écrit cette colonne, et elle seule : articles.prix_unitaire reste caché ; un prix
                n'est gardé que sur une ligne « hors magasin » (sur une autre ligne, la valeur du fichier revient) ;
    version     X-Version voilée tant que la colonne est cachée, l'empreinte vraie quand elle ne l'est plus.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_prix_hors_magasin_serveur.py" -v
"""
import tempfile
import types
import unittest
from pathlib import Path

from test_format6_serveur import ENTETE, LIGNES, TABLE, TECHNICIEN, corps_d_ajout, lire, octets_de, serveur

P_PRIX = ENTETE.index("prix_unitaire")
NOUVELLE_HM = ["MVT-000004", "2026-11-12 10:00", "", "hors magasin", "1", "OT-2026-0003", "Julien", "", "Fusible 10 A", "4.2"]
NOUVELLE_SORTIE = ["MVT-000005", "2026-11-12 10:05", "ART-0001", "sortie", "1", "OT-2026-0003", "Julien", "", "", "7"]


class CasReglage(unittest.TestCase):

    VALEUR = None                     # None : ligne absente de parametres.csv

    def setUp(self):
        dossier = tempfile.TemporaryDirectory()
        self.addCleanup(dossier.cleanup)
        self.config = types.SimpleNamespace(dossier_donnees=dossier.name)
        lignes = [["devise", "EUR"]]
        if self.VALEUR is not None:
            lignes.append([serveur.PARAMETRE_TECHNICIENS_PRIX_HORS_MAGASIN, "'" + self.VALEUR])
        Path(dossier.name, "parametres.csv").write_bytes(serveur.ecrire_tableau_csv(["cle", "valeur"], lignes))
        self.fichier = octets_de(ENTETE, LIGNES)

    def lu_par_le_technicien(self):
        return lire(serveur.filtrer_csv_pour(TECHNICIEN, TABLE, self.fichier, self.config))[1]

    def ecrit_par_le_technicien(self, recues):
        return lire(serveur.controle_d_ecriture(TECHNICIEN, TABLE, self.config)(octets_de(ENTETE, recues), self.fichier))[1]

    def ajoute_par_le_technicien(self, lignes):
        entete = ";".join(ENTETE).encode("utf-8")
        ajoutees = serveur.controle_d_ajout(TECHNICIEN, TABLE, self.config)(entete, corps_d_ajout(lignes), self.fichier)
        return [l for l in lire(b"x\r\n" + ajoutees)[1]]

    def recues_avec_prix(self):
        recues = [list(l) for l in LIGNES]
        recues[0][P_PRIX] = "9.99"                  # sortie : un prix n'y a pas sa place
        recues[1][P_PRIX] = "4"                     # hors magasin : prix changé
        return recues + [list(NOUVELLE_HM)]


class TestDesactive(CasReglage):

    def test_prix_cache_a_la_lecture(self):
        self.assertEqual({l[P_PRIX] for l in self.lu_par_le_technicien()}, {""})

    def test_prix_efface_a_l_ecriture(self):
        self.assertEqual([l[P_PRIX] for l in self.ecrit_par_le_technicien(self.recues_avec_prix())], ["", "3.75", "12.5", ""])

    def test_prix_vide_a_l_ajout(self):
        self.assertEqual([l[P_PRIX] for l in self.ajoute_par_le_technicien([NOUVELLE_HM])], [""])

    def test_version_voilee(self):
        voile = serveur.voile_des_versions(self.config, TECHNICIEN, TABLE)
        self.assertNotEqual(voile("abc"), "abc")


class TestZero(TestDesactive):
    VALEUR = "0"


class TestActive(CasReglage):
    VALEUR = "1"

    def test_prix_lu(self):
        self.assertEqual([l[P_PRIX] for l in self.lu_par_le_technicien()], ["", "3.75", "12.5"])

    def test_prix_ecrit_sur_les_lignes_hors_magasin_seulement(self):
        self.assertEqual([l[P_PRIX] for l in self.ecrit_par_le_technicien(self.recues_avec_prix())], ["", "4", "12.5", "4.2"])

    def test_ajout_avec_prix_sur_une_ligne_hors_magasin_seulement(self):
        self.assertEqual([l[P_PRIX] for l in self.ajoute_par_le_technicien([NOUVELLE_HM, NOUVELLE_SORTIE])], ["4.2", ""])

    def test_version_vraie(self):
        self.assertEqual(serveur.voile_des_versions(self.config, TECHNICIEN, TABLE)("abc"), "abc")

    def test_prix_des_articles_toujours_cache(self):
        self.assertEqual(serveur.colonnes_cachees("technicien", "articles", self.config), ("prix_unitaire",))
        articles = serveur.ecrire_tableau_csv(["id", "reference", "prix_unitaire"], [["ART-0001", "FLX", "38.5"]])
        self.assertNotIn(b"38.5", serveur.filtrer_csv_pour(TECHNICIEN, "articles", articles, self.config))

    def test_autres_roles_inchanges(self):
        self.assertEqual(serveur.colonnes_cachees("technicien", TABLE, self.config), ())
        self.assertEqual(serveur.colonnes_cachees("demandeur", TABLE, self.config), ())
        self.assertIsNone(serveur.controle_d_ecriture({"role": "responsable"}, TABLE, self.config))

    def test_sans_config_le_prix_reste_cache(self):
        self.assertEqual(serveur.colonnes_cachees("technicien", TABLE, None), ("prix_unitaire",))


if __name__ == "__main__":
    unittest.main()
