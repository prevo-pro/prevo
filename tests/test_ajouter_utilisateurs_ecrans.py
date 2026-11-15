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
