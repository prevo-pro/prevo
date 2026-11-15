"""Tests de L16 (lot 2 ergonomie, T557) : passation et renforts (js/modules/ordres-passation.js, ARCHITECTURE.md §14.2
« Passation et renforts »).

Familles :
    regles   : renforts (lecture, écriture), techniciens de l'OT, « Passer la main » proposé, temps manquants, mot de
               relève à montrer ; filtre de la liste sur un technicien (renforts compris) ;
    parcours : en mode serveur sans comptes, Karim passe la main à Julien avec un mot (en tête de la fiche, sur
               l'accueil de Julien), puis Julien à « qui est disponible » (l'OT retourne dans « À prendre » avec son
               mot) ; RG8 refuse un collègue sans l'habilitation ; « Journée terminée » (garder, passer) ; renforts :
               ajout, l'OT chez le renfort, rappel des temps manquants à la clôture sans bloquer, retrait ;
    serveur  : aucun droit nouveau (PUT d'ordres_travail avec relève et renforts : technicien accepté comme avant,
               demandeur et direction 403).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_passation.py" -v
"""
import time
import unittest

from commun import ServeurPrevo
import test_acces_roles as roles
from test_ordres_prise import CasPrise, ot_sur_disque, lire_csv, KARIM, JULIEN, THOMAS


class CasPassation(CasPrise):

    def attendre(self, serveur, ot_id, condition, delai_s=10):
        fin = time.time() + delai_s
        while True:
            ligne = ot_sur_disque(serveur.dossier, ot_id)
            if condition(ligne) or time.time() > fin:
                return ligne
            time.sleep(0.2)

    def fenetre(self):
        return "dialog.dialogue[open]"

    def valider_fenetre(self):
        self.page.click("dialog.dialogue[open] .fenetre-actions .btn-primaire")


class TestParcoursPassation(CasPassation):

    def test_passer_la_main_mot_en_tete_et_sur_l_accueil(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            ot = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Fuite L16", "technicien_id": KARIM,
                                "priorite": "P1", "date_prevue": "2026-01-02"})      # en tête de « À prendre » (5 OT)
            self.page.evaluate("id => Ordres.changerStatut(id, 'Créé', 'En cours', {})", ot)
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.aller_fiche(ot)
            self.page.click("#ot-passer-main")
            self.page.wait_for_selector(self.fenetre())
            # rien de choisi : la fenêtre le dit, rien n'est écrit
            self.valider_fenetre()
            self.page.wait_for_selector("dialog.dialogue[open] .erreur-champ:not([hidden])")
            self.assertEqual(ot_sur_disque(serveur.dossier, ot)["technicien_id"], KARIM)
            self.page.check("dialog.dialogue[open] input[name=releve_motif][value='pas le temps']")
            self.page.select_option("#ot-passation-a", JULIEN)
            self.assertEqual(self.page.locator("dialog.dialogue[open] textarea[name=releve_mot][data-dictee]").count(), 1)
            self.page.fill("dialog.dialogue[open] textarea[name=releve_mot]", "Joint changé, reste à resserrer la bride.")
            self.valider_fenetre()
            ligne = self.attendre(serveur, ot, lambda o: o["technicien_id"] == JULIEN)
            self.assertEqual((ligne["technicien_id"], ligne["statut"], ligne["releve_par"], ligne["releve_motif"]),
                             (JULIEN, "En cours", KARIM, "pas le temps"))
            self.assertEqual(ligne["releve_mot"], "Joint changé, reste à resserrer la bride.")
            self.assertRegex(ligne["releve_le"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
            journal = [j for j in lire_csv(serveur.dossier, "journal.csv") if j["id_ligne"] == ot]
            self.assertTrue(any("main passée à " + JULIEN in j["action"] for j in journal), journal)
            # le mot en tête de la fiche, avec le nom et l'heure ; plus de « Passer la main » pour Karim
            self.page.wait_for_selector(".ot-releve-bandeau")
            tete = self.page.inner_text(".ot-releve-bandeau")
            self.assertIn("Mot de relève de Karim", tete)
            self.assertIn(ligne["releve_le"][11:16], tete)
            self.assertIn("resserrer la bride", tete)
            self.assertEqual(self.page.locator("#ot-passer-main").count(), 0)

            # Julien : l'OT dans « Mes ordres de travail », avec le mot
            self.changer_profil(serveur, "#/accueil", "technicien", JULIEN, "Julien Moreau")
            self.page.wait_for_selector(".accueil-mes-ordres .accueil-releve")
            carte = self.page.inner_text(".accueil-mes-ordres li:has(a[href='#/ot/%s'])" % ot)
            self.assertIn("Mot de Karim", carte)
            self.assertIn("resserrer la bride", carte)
            # Julien la passe à qui est disponible : « À prendre », avec son mot (il n'en écrit pas : motif dit)
            self.aller_fiche(ot)
            self.page.click("#ot-passer-main")
            self.page.wait_for_selector(self.fenetre())
            self.page.check("dialog.dialogue[open] input[name=releve_motif][value='fin de journée']")
            self.page.select_option("#ot-passation-a", "__disponible")
            self.valider_fenetre()
            ligne = self.attendre(serveur, ot, lambda o: o["technicien_id"] == "")
            self.assertEqual((ligne["technicien_id"], ligne["releve_par"], ligne["releve_mot"]), ("", JULIEN, ""))
            self.changer_profil(serveur, "#/accueil", "technicien", THOMAS, "Thomas Garnier")
            self.page.wait_for_selector(".accueil-a-prendre")
            carte = self.page.inner_text(".accueil-a-prendre li:has(a[href='#/ot/%s'])" % ot)
            self.assertIn("Passé par Julien (fin de journée)", carte)


class TestDroitsServeurPassation(unittest.TestCase):
    """Aucun droit nouveau : un technicien écrit ordres_travail comme avant (pas de règle par OT au serveur), le
    demandeur et la Direction restent refusés, relève et renforts compris."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        roles.setUpModule()
        roles.lancer_serveur_comptes(cls)

    def test_put_releve_et_renforts(self):
        chemin = self.serveur.dossier / "ordres_travail.csv"
        disque = chemin.read_bytes()
        entete, lignes = roles.lire_tableau(disque)
        cible = next(l for l in lignes if l[entete.index("statut")] in ("En cours", "Créé", "Préparé"))
        for colonne, valeur in (("renforts", "TEC-0003"), ("releve_par", "TEC-0002"), ("releve_le", "2026-11-15 17:30"),
                                ("releve_motif", "fin de journée"), ("releve_mot", "Mot de relève d'essai")):
            cible[entete.index(colonne)] = valeur
        corps = roles.ecrire_tableau(entete, lignes)
        for role in ("demandeur", "direction"):
            with self.subTest(role=role):
                reponse = self.client.requete("PUT", "/api/csv/ordres_travail", corps, cookie=self.cookies[role],
                                              entetes={"X-Version-Attendue": roles.version_de(disque)})
                self.assertTrue(reponse.refus_de_role(), (reponse.statut, reponse.octets[:200]))
                self.assertEqual(chemin.read_bytes(), disque)
        recu = self.client.requete("GET", "/api/csv/ordres_travail", cookie=self.cookies["technicien"])
        reponse = self.client.requete("PUT", "/api/csv/ordres_travail", corps, cookie=self.cookies["technicien"],
                                      entetes={"X-Version-Attendue": recu.entetes["x-version"]})
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        apres = {l[0]: l for l in roles.lire_tableau(chemin.read_bytes())[1]}
        self.assertEqual(apres[cible[0]][entete.index("renforts")], "TEC-0003")
        self.assertEqual(apres[cible[0]][entete.index("releve_motif")], "fin de journée")


if __name__ == "__main__":
    unittest.main()
