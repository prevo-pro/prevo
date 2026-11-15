"""Libellés d'affichage des statuts et des types d'OT (lot 2 ergonomie, T560, décision P10 du 15/11).

Les valeurs stockées dans les CSV ne changent pas (D155) ; seul l'affichage passe par Schema.libelleValeur
(valeurs.ordres_travail.<champ>.<valeur>) :
    - « Clôturé techniquement » s'affiche « Terminé, à valider », « Clôturé administrativement » s'affiche « Clôturé » ;
    - « correctif immédiat » s'affiche « Panne », « correctif différé » « Réparation programmée » ;
    - le bandeau d'un OT clôturé dit « OT clôturé le … à … » (une clé sans l'heure si la donnée n'en porte pas) ;
    - P07 : le champ « Consignes » de l'OT devient « Consignes de sécurité (responsable) » ;
    - les cinq langues portent les mêmes clés et les mêmes paramètres ; les anciens termes restent cités dans l'aide.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_libelles_p10.py" -v
"""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
LANGUES = ("fr", "en", "tr", "it", "pt-PT")
CLE_STATUT = "valeurs.ordres_travail.statut."
CLE_TYPE = "valeurs.ordres_travail.type."
CLE_BANDEAU = "ordres.bandeau_etat.ot_verrouille_cloture_administrativement"


def texte_de(langue, cle):
    source = (RACINE / "js" / "i18n" / (langue + ".js")).read_text(encoding="utf-8")
    m = re.search(r"^  '" + re.escape(cle) + r"': '((?:\\.|[^'\\\n])*)'", source, re.M)
    return m.group(1).replace("\\'", "'") if m else None


class LibellesP10(unittest.TestCase):
    def test_francais(self):
        attendu = {CLE_STATUT + "Clôturé techniquement": "Terminé, à valider",
                   CLE_STATUT + "Clôturé administrativement": "Clôturé",
                   CLE_TYPE + "correctif immédiat": "Panne",
                   CLE_TYPE + "correctif différé": "Réparation programmée"}
        for cle, libelle in attendu.items():
            self.assertEqual(texte_de("fr", cle), libelle, cle)

    def test_cinq_langues_libelles_distincts_des_anciens(self):
        for langue in LANGUES:
            for cle in (CLE_STATUT + "Clôturé techniquement", CLE_STATUT + "Clôturé administrativement",
                        CLE_TYPE + "correctif immédiat", CLE_TYPE + "correctif différé"):
                self.assertTrue(texte_de(langue, cle), (langue, cle))
            self.assertNotEqual(texte_de(langue, CLE_STATUT + "Clôturé techniquement"),
                                texte_de(langue, CLE_STATUT + "Clôturé administrativement"), langue)

    def test_bandeau_ot_cloture(self):
        self.assertEqual(texte_de("fr", CLE_BANDEAU),
                         "<b>OT clôturé</b> le {date} à {heure}. Pour reprendre ce travail, créez un nouvel OT lié.")
        for langue in LANGUES:
            avec = texte_de(langue, CLE_BANDEAU)
            sans = texte_de(langue, CLE_BANDEAU + "_sans_heure")
            self.assertEqual(sorted(re.findall(r"\{(\w+)\}", avec)), ["date", "heure"], langue)
            self.assertEqual(re.findall(r"\{(\w+)\}", sans), ["date"], langue)
            self.assertNotIn("verrouillé", avec.lower() if langue == "fr" else "", langue)

    def test_anciens_termes_dans_l_aide(self):
        aide = (RACINE / "js" / "i18n" / "aide" / "fr.js").read_text(encoding="utf-8")
        m = re.search(r"'aide\.ecran\.liste_ot\.responsable\.texte': '((?:\\.|[^'\\\n])*)'", aide)
        self.assertIsNotNone(m)
        self.assertIn("Terminé, à valider (la clôture technique)", m.group(1))
        self.assertIn("ancienne clôture administrative", m.group(1))


class ChampConsignes(unittest.TestCase):
    """P07 : le champ « Consignes » de l'OT (onglet Préparation, responsable) est renommé ; celui des gammes ne change pas."""

    def test_libelle(self):
        self.assertEqual(texte_de("fr", "schema.ordres_travail.consignes"), "Consignes de sécurité (responsable)")
        self.assertEqual(texte_de("fr", "schema.gammes.consignes"), "Consignes")
        for langue in LANGUES:
            self.assertTrue(texte_de(langue, "schema.ordres_travail.consignes"), langue)


if __name__ == "__main__":
    unittest.main()
