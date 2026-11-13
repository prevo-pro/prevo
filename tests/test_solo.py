"""Tests du mode Solo, partie interface (tâche T173, ARCHITECTURE.md §22.11, CDC D132).

Le mode Solo est le profil Responsable avec le réglage mode_solo = 1 de parametres.csv (pas un quatrième
profil). Mode démo (file://), profil Responsable préréglé :
    - « Passer en mode Solo » (Paramètres) crée le technicien « moi » et écrit mode_solo et
      solo_technicien_id (lus dans les données en mémoire) ;
    - accueil du Solo (T521, solo-accueil.js) : « Nouvel OT » avant « Signaler un problème » ;
    - menu : ni Équipe ni Planning (T521 ; avant : sous « Plus »), leurs routes restent ;
    - nouvel OT : technicien « moi » pré-rempli ;
    - fiche équipement : « Créer un OT » avant « Signaler un problème » ;
    - « Quitter le mode Solo » rétablit le menu sans rien supprimer ; profils Demandeur et Technicien
      toujours proposés.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_solo.py" -v
"""
import unittest

from commun import CasNavigateur, attendre_pret, preregler_profil, url_fichier

EQUIPEMENT = "EQ-0002"


class TestModeSolo(CasNavigateur):

    def ouvrir_demo(self):
        preregler_profil(self.contexte, "responsable")
        page = self.page
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        return page

    def aller(self, route, selecteur):
        self.page.evaluate("location.hash = %r" % route)
        self.page.wait_for_selector(selecteur)

    def passer_en_solo(self, prenom="Camille", nom="Soliste", metier="Mécanicien"):
        page = self.page
        # T521 : « Revenir en Solo » ne passe que sans autre technicien actif ; ici, aucun : la fiche « moi » est créée.
        page.evaluate("() => Donnees.modifier('techniciens', (l) => { l.forEach((t) => { t.actif = '0'; }); })")
        self.aller("#/parametres", "#btn-passer-solo")
        page.click("#btn-passer-solo")
        page.wait_for_selector("dialog [name='prenom']", state="visible")
        page.fill("dialog [name='prenom']", prenom)
        page.fill("dialog [name='nom']", nom)
        page.fill("dialog [name='metier']", metier)
        page.click("dialog .fenetre-actions .btn-primaire")
        # T521 : les OT ouverts des techniciens désactivés passent à son nom, après confirmation.
        page.wait_for_selector("#solo-confirmation")
        page.click("dialog[open] .btn-primaire")
        page.wait_for_selector("#btn-passer-equipe")
        self.assertEqual(page.locator("dialog").count(), 0)
        return page.evaluate("Donnees.parametre('solo_technicien_id', '')")

    def entrees_menu(self):
        return self.page.evaluate("""() => ({
          principales: [...document.querySelectorAll('#menu > a')].map(a => a.dataset.ecran),
        })""")

    def sans_defilement_horizontal(self):
        largeur = self.page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        self.assertLessEqual(largeur, 0)

    # ------------------------------------------------------------------------------------------------

    def test_hors_mode_solo_rien_ne_change(self):
        page = self.ouvrir_demo()
        self.assertFalse(page.evaluate("App.modeSolo()"))
        self.assertEqual(page.evaluate("App.technicienSolo()"), "")
        self.assertEqual(page.locator("#accueil-solo").count(), 0)
        self.assertFalse(page.evaluate("document.documentElement.hasAttribute('data-solo')"))
        menu = self.entrees_menu()
        self.assertIn("equipe", menu["principales"])
        self.assertIn("planning", menu["principales"])
        self.aller("#/ot/nouveau", "#form-nouvel-ot")
        self.assertEqual(page.input_value("#form-nouvel-ot [name='technicien_id']"), "")
        self.aller("#/equipement/" + EQUIPEMENT, ".parc-actions")
        self.assertEqual(page.locator("#parc-creer-ot").count(), 0)
        self.assertIn("btn-primaire", page.get_attribute(".parc-actions .parc-signaler", "class"))

    def test_passer_en_mode_solo_puis_quitter(self):
        page = self.ouvrir_demo()
        nombre_avant = page.evaluate("Donnees.lignes('techniciens').length")
        technicien_id = self.passer_en_solo()

        # Technicien « moi » créé dans techniciens (données en mémoire), réglages écrits
        self.assertTrue(technicien_id)
        technicien = page.evaluate("(id) => Donnees.trouver('techniciens', id)", technicien_id)
        self.assertIsNotNone(technicien)
        self.assertEqual((technicien["prenom"], technicien["nom"], technicien["metier"], technicien["actif"]),
                         ("Camille", "Soliste", "Mécanicien", "1"))
        self.assertEqual(page.evaluate("Donnees.lignes('techniciens').length"), nombre_avant + 1)
        self.assertEqual(page.evaluate("Donnees.parametre('mode_solo', '0')"), "1")
        self.assertTrue(page.evaluate("App.modeSolo()"))
        self.assertEqual(page.evaluate("App.technicienSolo()"), technicien_id)
        self.assertIn(technicien_id, page.inner_text("#solo-technicien"))

        # Accueil du Solo (T521) : « Nouvel OT » en premier, « Signaler un problème » en second ; pas de bento
        self.aller("#/accueil", "#solo-accueil")
        self.assertEqual(page.locator("#bento").count(), 0)
        self.assertTrue(page.evaluate("document.documentElement.hasAttribute('data-solo')"))
        boutons = page.evaluate("[...document.querySelectorAll('#accueil-solo .btn')].map(b => b.id)")
        self.assertEqual(boutons, ["accueil-nouvel-ot", "accueil-signaler"])
        self.assertEqual(page.get_attribute("#accueil-nouvel-ot", "href"), "#/ot/nouveau")
        self.assertEqual(page.get_attribute("#accueil-signaler", "href"), "#/di/nouvelle")
        hauteur = page.evaluate("Math.min(...[...document.querySelectorAll('#accueil-solo .btn')].map(b => b.getBoundingClientRect().height))")
        self.assertGreaterEqual(hauteur, 48)

        # Menu à 1280 px (T521) : ni Équipe ni Planning, pas de groupe « Plus » ; les routes restent
        menu = self.entrees_menu()
        self.assertNotIn("equipe", menu["principales"])
        self.assertNotIn("planning", menu["principales"])
        self.assertEqual(page.locator("#btn-menu-plus").count(), 0)
        self.aller("#/equipe", "#contenu h1")
        self.assertEqual(page.evaluate("App.ecranCourant.id"), "equipe")

        # Nouvel OT : technicien « moi » pré-rempli, champ caché à l'écran (T521)
        self.aller("#/ot/nouveau", "#form-nouvel-ot")
        self.assertEqual(page.input_value("#form-nouvel-ot [name='technicien_id']"), technicien_id)
        self.assertTrue(page.is_hidden("#form-nouvel-ot [name='technicien_id']"))

        # Fiche équipement : « Créer un OT » avant « Signaler un problème »
        self.aller("#/equipement/" + EQUIPEMENT, ".parc-actions")
        ordre = page.evaluate("""[...document.querySelectorAll('.parc-actions a')].map(a => a.getAttribute('href'))""")
        self.assertEqual(ordre[0], "#/ot/nouveau?equipement=" + EQUIPEMENT)
        self.assertEqual(ordre[1], "#/di/nouvelle?equipement=" + EQUIPEMENT)
        self.assertEqual(sum(1 for lien in ordre if lien.startswith("#/ot/nouveau")), 1)
        page.click("#parc-creer-ot")
        page.wait_for_selector("#form-nouvel-ot")
        self.assertEqual(page.input_value("#form-nouvel-ot [name='technicien_id']"), technicien_id)

        # Téléphone (375 px) : ni Équipe ni Planning, même dans le « Plus » de la barre du bas ; pas de défilement
        page.set_viewport_size({"width": 375, "height": 812})
        self.aller("#/accueil", "#solo-accueil")
        self.sans_defilement_horizontal()
        en_bas = page.evaluate("[...document.querySelectorAll('#barre-bas a')].map(a => a.dataset.ecran)")
        self.assertNotIn("equipe", en_bas)
        self.assertNotIn("planning", en_bas)
        page.click("#btn-plus")
        page.wait_for_selector("dialog .liste-plus", state="visible")
        self.assertEqual(page.locator("dialog .liste-plus a[href='#/equipe']").count(), 0)
        self.assertEqual(page.locator("dialog .liste-plus a[href='#/planning']").count(), 0)
        page.click("dialog .liste-plus a[href='#/parametres']")
        page.wait_for_function("location.hash === '#/parametres'")
        self.aller("#/equipement/" + EQUIPEMENT, "#parc-creer-ot")
        self.sans_defilement_horizontal()
        self.aller("#/parametres", "#btn-passer-equipe")
        self.sans_defilement_horizontal()

        # Quitter le mode Solo : menu rétabli, technicien gardé
        page.set_viewport_size({"width": 1280, "height": 800})
        page.click("#btn-passer-equipe")
        page.wait_for_selector("#solo-ensuite")                       # T521 : quoi faire ensuite, avec les liens
        page.keyboard.press("Escape")
        page.wait_for_selector("#btn-passer-solo")
        self.assertEqual(page.evaluate("Donnees.parametre('mode_solo', '1')"), "0")
        self.assertFalse(page.evaluate("App.modeSolo()"))
        self.assertIsNotNone(page.evaluate("(id) => Donnees.trouver('techniciens', id)", technicien_id))
        self.assertEqual(page.evaluate("Donnees.lignes('techniciens').length"), nombre_avant + 1)
        self.assertEqual(page.locator("#btn-menu-plus").count(), 0)
        menu = self.entrees_menu()
        self.assertIn("equipe", menu["principales"])
        self.assertIn("planning", menu["principales"])
        self.aller("#/accueil", "#bento")
        self.assertEqual(page.locator("#accueil-solo").count(), 0)
        self.aller("#/ot/nouveau", "#form-nouvel-ot")
        self.assertEqual(page.input_value("#form-nouvel-ot [name='technicien_id']"), "")

    def test_profils_demandeur_et_technicien_restent_proposes(self):
        page = self.ouvrir_demo()
        self.passer_en_solo()
        page.evaluate("() => { App.changerProfil(); }")
        page.wait_for_selector("#profil-choix", state="visible")
        self.assertTrue(page.is_visible("#profil-demandeur"))
        self.assertTrue(page.is_visible("#profil-technicien"))
        self.assertTrue(page.is_visible("#profil-responsable"))
        # Le technicien « moi » est choisissable comme profil Technicien ; le mode Solo ne s'applique pas à lui
        technicien_id = page.evaluate("Donnees.parametre('solo_technicien_id', '')")
        page.click("#profil-technicien")
        page.click("#profil-techniciens [data-technicien='%s']" % technicien_id)
        attendre_pret(page)
        page.wait_for_function("App.profil.type === 'technicien'")
        self.assertFalse(page.evaluate("App.modeSolo()"))
        self.assertEqual(page.locator("#btn-menu-plus").count(), 0)

    def test_themes_clair_et_sombre_boutons_de_l_accueil(self):
        page = self.ouvrir_demo()
        self.passer_en_solo(prenom="Dominique", nom="Clair")
        self.aller("#/accueil", "#accueil-solo")
        lecture = """() => {
          const b = document.querySelector('#accueil-signaler');
          const carte = document.querySelector('#solo-pannes');
          return { couleur: getComputedStyle(carte).backgroundColor, hauteur: b.getBoundingClientRect().height };
        }"""
        page.evaluate("document.documentElement.dataset.theme = 'clair'")
        clair = page.evaluate(lecture)
        page.evaluate("document.documentElement.removeAttribute('data-theme')")
        sombre = page.evaluate(lecture)
        # Couleurs prises dans les variables du thème : elles changent avec lui (carte) ; gros bouton
        self.assertNotEqual(clair["couleur"], sombre["couleur"])
        self.assertGreaterEqual(min(clair["hauteur"], sombre["hauteur"]), 48)


if __name__ == "__main__":
    unittest.main()
