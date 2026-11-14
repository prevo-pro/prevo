"""Taux horaire moyen du service (lot 2 ergonomie, T544, L30 ; D126) : la ligne « taux_horaire_moyen » de
parametres.csv n'est servie qu'au responsable et à la direction (qui voient les coûts) ; le technicien et le
demandeur lisent parametres sans elle, et la version de la table qu'ils reçoivent est voilée (T506) : ils ne
retrouvent pas le taux en recomposant le fichier avec un taux candidat.

Mode serveur avec comptes (vraies sessions, copie du jeu f4-v2.2.0, parametres.csv réduit à trois lignes). Sans
navigateur. Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_taux_horaire_moyen_serveur.py" -v
"""
import unittest

import test_version_colonnes_cachees as base

TAUX = "38.5"
CANDIDATS = ("35", TAUX, "40", "42.5")
ENTETE = ["cle", "valeur"]
LIGNES = [["entreprise_nom", "Atelier essai"], ["taux_horaire_moyen", TAUX], ["devise", "EUR"]]


def recomposer(octets_recus, taux):
    """Ce que ferait l'attaquant : le fichier entier, la ligne du taux remise à sa place avec un taux candidat."""
    _, lignes = base.lire_tableau(octets_recus)
    return base.ecrire_tableau(ENTETE, lignes[:1] + [["taux_horaire_moyen", taux]] + lignes[1:])


class CasTaux(base.CasServeur):

    def setUp(self):
        super().setUp()
        (self.serveur.dossier / "parametres.csv").write_bytes(base.ecrire_tableau(ENTETE, LIGNES))

    def test_cache_au_technicien_et_au_demandeur(self):
        for role in ("technicien", "demandeur"):
            with self.subTest(role=role):
                recu = self.lire(role, "parametres").octets
                self.assertNotIn(b"taux_horaire_moyen", recu)
                self.assertIn(b"entreprise_nom", recu)

    def test_servi_au_responsable(self):
        recu = self.lire("responsable", "parametres").octets
        self.assertIn(b"taux_horaire_moyen;38.5", recu)
        self.assertEqual(self.version("responsable", "parametres"), base.empreinte(self.fichier("parametres")))

    def test_version_voilee(self):
        recu = self.lire("technicien", "parametres").octets
        candidates = {taux: base.empreinte(recomposer(recu, taux)) for taux in CANDIDATS}
        self.assertEqual(candidates[TAUX], base.empreinte(self.fichier("parametres")), "l'essai ne recompose plus le fichier")
        for role in ("technicien", "demandeur"):
            vues = {self.version(role, "parametres"), self.version_listee(role, "parametres")}
            self.assertEqual(len(vues), 1, role)
            self.assertFalse(vues & set(candidates.values()), role)

    def test_le_technicien_n_ecrit_toujours_pas_parametres(self):
        lue = self.lire("technicien", "parametres")
        refus = self.requete("technicien", "PUT", "/api/csv/parametres", lue.octets, {"X-Version-Attendue": lue.entetes["x-version"]})
        self.assertEqual(refus.statut, 403, refus.octets[:300])
        self.assertIn(b"taux_horaire_moyen;38.5", self.fichier("parametres"))


if __name__ == "__main__":
    unittest.main()
