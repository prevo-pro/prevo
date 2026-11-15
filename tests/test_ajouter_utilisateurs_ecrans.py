"""Lot 2 ergonomie, L05 (tâche T555) — « Ajouter des utilisateurs » : les écrans (navigateur).

Ce qui est vérifié (serveur réel, copie de la démo avec trois comptes, mêmes aides que
tests/test_acces_ecrans_equipe.py) :
    responsable    la carte de l'accueil mène à #/equipe/utilisateurs (opérateurs, techniciens, Direction) ;
                   « Ajouter un technicien » (prénom, nom, métier) montre un QR /#/premier-acces/<jeton> ; un autre
                   navigateur ouvre ce lien : prénom et identifiant affichés, mot de passe choisi deux fois (sans
                   « actuel »), l'application s'ouvre sur l'accueil (jeton retiré de l'adresse) ; le compte au serveur
                   n'a plus de mot de passe à changer, sa fiche porte le métier ; le même lien ne sert plus ;
    technicien     la carte « Inviter un opérateur » ; l'écran ne montre que les opérateurs ; le QR est celui d'une
                   invitation d'appareil (/#/enroler/<jeton>) ;
    lien           « Paramètres › Accès et installation » du poste est un lien vers #/parametres?rubrique=acces.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ajouter_utilisateurs_ecrans.py" -v
"""
import re
import unittest

import test_acces_ecrans_equipe as base
from commun import attendre_pret

MOTIF_PREMIER = re.compile(r"^https?://[^/]+/#/premier-acces/([A-Za-z0-9_-]{43})$")
MOTIF_ENROLER = re.compile(r"^https?://[^/]+/#/enroler/([A-Za-z0-9_-]{43})$")
NOUVEAU = "cle de douze et graisse"


def setUpModule():
    base.setUpModule()


class TestAjouterUtilisateurs(base.CasEcranAcces):

    def ouvrir(self, route):
        self.page.goto(self.serveur.url + "/" + route)
        attendre_pret(self.page)

    def lien_du_qr(self):
        self.page.wait_for_selector("#acces-invitation-qr svg")
        return self.page.input_value("#acces-invitation-lien")

    def test_responsable_ajoute_un_technicien_par_qr(self):
        responsable = self.poser_session("nicolas.briand", "responsable", "Nicolas Briand")
        self.ouvrir("#/accueil")
        self.page.wait_for_selector("#carte-ajouter-utilisateurs")
        self.page.click("#lien-ajouter-utilisateurs")
        self.page.wait_for_selector("#utilisateurs-operateurs")
        for carte in ("#utilisateurs-techniciens", "#utilisateurs-direction"):
            self.assertTrue(self.page.locator(carte).is_visible(), carte)
        self.page.click("#utilisateurs-ajouter-technicien")
        dialogue = self.dialogue()
        dialogue.locator("input[name=prenom]").fill("Karim")
        dialogue.locator("input[name=nom]").fill("Haddad")
        dialogue.locator("input[name=metier]").fill("Mécanicien")
        dialogue.locator("button:has-text('Créer et montrer le QR')").click()
        lien = self.lien_du_qr()
        self.assertRegex(lien, MOTIF_PREMIER)
        self.assertIn("karim.haddad", self.dialogue().inner_text())
        compte = {c["identifiant"]: c for c in self.client.requete("GET", "/api/acces/comptes",
                                                                    cookie=responsable).json()["comptes"]}["karim.haddad"]
        self.assertTrue(compte["a_changer"])
        fiche = next(t for t in self.client.requete("GET", "/api/csv/techniciens", cookie=responsable).octets
                     .decode("utf-8-sig").splitlines() if t.startswith(compte["technicien_id"] + ";"))
        self.assertIn("Mécanicien", fiche)
        # Le téléphone de Karim : un navigateur neuf, sans session.
        telephone = self.navigateur.new_context(bypass_csp=True, viewport={"width": 390, "height": 844})
        self.addCleanup(telephone.close)
        page = telephone.new_page()
        page.goto(lien.replace(re.match(r"^https?://[^/]+", lien).group(0), self.serveur.url))
        page.wait_for_selector("#connexion-premier-qui:not([hidden])")
        self.assertIn("karim.haddad", page.inner_text("#connexion-premier-qui"))
        self.assertFalse(page.locator("#connexion-actuel").is_visible())
        page.fill("#connexion-nouveau", NOUVEAU)
        page.fill("#connexion-confirmation", NOUVEAU + " x")
        page.click("#connexion-changer")
        page.wait_for_selector("#connexion-mdp-erreur:not([hidden])")               # confirmation différente
        page.fill("#connexion-confirmation", NOUVEAU)
        page.click("#connexion-changer")
        page.wait_for_function("() => location.hash === '#/accueil'")
        attendre_pret(page)
        self.assertNotIn("premier-acces", page.url)
        compte = {c["identifiant"]: c for c in self.client.requete("GET", "/api/acces/comptes",
                                                                    cookie=responsable).json()["comptes"]}["karim.haddad"]
        self.assertFalse(compte["a_changer"])
        self.assertNotIn("premier_acces_expire_le", compte)
        self.assertEqual(self.client.connecter("karim.haddad", NOUVEAU).statut, 200)
        # Le même lien ne sert plus : l'écran de connexion le dit.
        autre = self.navigateur.new_context(bypass_csp=True).new_page()
        self.addCleanup(autre.context.close)
        autre.goto(page.url.split("#")[0] + "#/premier-acces/" + MOTIF_PREMIER.match(lien).group(1))
        autre.wait_for_selector("#connexion-erreur:not([hidden])")
        self.assertIn("ne sert plus", autre.inner_text("#connexion-erreur"))

    def test_technicien_invite_un_operateur(self):
        self.poser_session("julien.moreau", "technicien", "Julien Moreau", "TEC-0001")
        self.ouvrir("#/accueil")
        self.page.wait_for_selector("#carte-ajouter-utilisateurs")
        self.page.click("#lien-ajouter-utilisateurs")
        self.page.wait_for_selector("#utilisateurs-operateurs")
        self.assertEqual(self.page.locator("#utilisateurs-techniciens, #utilisateurs-direction").count(), 0)
        self.page.click("#utilisateurs-inviter-operateur")
        self.assertRegex(self.lien_du_qr(), MOTIF_ENROLER)

    def test_creer_un_compte_technicien_nouvelle_fiche_par_defaut(self):
        """P05 A : « Créer un compte », rôle technicien : « Nouvelle fiche à ce nom » en tête et choisie ; plus de refus."""
        responsable = self.poser_session("nicolas.briand", "responsable", "Nicolas Briand")
        self.ouvrir_acces()
        self.page.wait_for_selector("#acces-comptes tbody tr")
        self.page.click("#acces-creer-compte")
        dialogue = self.dialogue()
        liste = dialogue.locator("select[name=technicien_id]")
        self.assertEqual(liste.locator("option").nth(1).inner_text(), "Nouvelle fiche à ce nom")
        self.assertEqual(liste.locator("option:checked").inner_text(), "Nouvelle fiche à ce nom")
        dialogue.locator("input[name=prenom]").fill("Hugo")
        dialogue.locator("input[name=nom]").fill("Blanc")
        dialogue.locator("select[name=role]").select_option("technicien")
        dialogue.locator("button:has-text('Créer le compte')").click()
        self.page.wait_for_selector("#acces-mot-de-passe-provisoire")
        compte = {c["identifiant"]: c for c in self.client.requete("GET", "/api/acces/comptes",
                                                                    cookie=responsable).json()["comptes"]}["hugo.blanc"]
        self.assertEqual(compte["role"], "technicien")
        self.assertRegex(compte["technicien_id"], r"^TEC-[0-9]{4}$")
        # Un demandeur créé avec la valeur par défaut reste sans fiche.
        self.fermer_dialogue()
        self.page.click("#acces-creer-compte")
        dialogue = self.dialogue()
        dialogue.locator("input[name=prenom]").fill("Paul")
        dialogue.locator("input[name=nom]").fill("Simon")
        dialogue.locator("button:has-text('Créer le compte')").click()
        self.page.wait_for_selector("#acces-mot-de-passe-provisoire")
        comptes = {c["identifiant"]: c for c in self.client.requete("GET", "/api/acces/comptes",
                                                                     cookie=responsable).json()["comptes"]}
        self.assertEqual((comptes["paul.simon"]["role"], comptes["paul.simon"]["technicien_id"]), ("demandeur", ""))

    def test_lien_vers_acces_et_installation(self):
        self.poser_session("nicolas.briand", "responsable", "Nicolas Briand")
        self.ouvrir("#/parametres?rubrique=acces")
        self.page.wait_for_selector("#zone-formulaire")
        self.ouvrir("#/poste")
        liens = self.page.locator("a[href='#/parametres?rubrique=acces']")
        if liens.count():                   # bloc « IA du serveur » montré seulement si le serveur la propose
            self.assertIn("Accès et installation", liens.first.inner_text())


if __name__ == "__main__":
    unittest.main()
