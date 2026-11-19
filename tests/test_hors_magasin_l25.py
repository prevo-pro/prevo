"""Pièces hors magasin (lot 2 ergonomie, T558, décision L25 points 1 et 2 ; format 6 de T552).

Une pièce prise ailleurs qu'au magasin se note sur l'OT : ligne « hors magasin » de mouvements_stock (article vide,
désignation, quantité, prix facultatif). Elle ne compte pas dans le stock ; son prix compte dans le coût (RG7) partout
de la même façon (Ordres.cout, indicateurs, bilan) ; sans prix, elle est « non chiffrée » (aucune valeur inventée).
Le technicien saisit désignation et quantité, jamais de prix (D126 : le serveur le lui cache) ; le responsable oui.
    coût        mois d'essai de tests/test_rapport_bilan_mois.py (173,50 € chiffrés) plus deux pièces hors magasin :
                2 courroies à 12,50 € sur OT-2026-0001 (+ 25 €) et 1 joint spi sans prix sur OT-2026-0003 (manque) ;
    saisie      onglet Exécution de l'OT (responsable avec prix, technicien sans le champ) ; fenêtre de clôture unique ;
    liste       Magasin > « Hors magasin » du responsable : prix, « Créer l'article » pré-rempli, ligne reliée (traitée).

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_hors_magasin_l25.py" -v
"""
import json
import unittest

import test_rapport_bilan_mois as base
from commun import CasNavigateur, attendre_pret, figer_a_midi, preregler_profil, scenarios_demo, url_fichier

OT = scenarios_demo()["ot_statut_en_cours"]          # correctif « En cours » de la démo

TABLES = dict(base.TABLES)
TABLES["mouvements_stock"] = base.csv("id;date;type;article_id;quantite;ot_id;designation;prix_unitaire", [
    "MVT-000001;2026-11-03 09:00;sortie;ART-0001;1;OT-2026-0001;;",
    "MVT-000002;2026-11-05 09:00;sortie;ART-0002;2;OT-2026-0002;;",
    "MVT-000003;2026-11-03 09:30;hors magasin;;2;OT-2026-0001;Courroie SPA 1250;12.5",
    "MVT-000004;2026-11-10 08:30;hors magasin;;1;OT-2026-0003;Joint spi 40x52;"])


class TestCoutHorsMagasin(base.CasBilan):

    def setUp(self):
        CasNavigateur.setUp(self)
        self.ouvrir(TABLES)

    def test_meme_cout_a_l_ot_et_aux_indicateurs(self):
        r = self.page.evaluate("""() => {
          const ot1 = Ordres.cout(Donnees.trouver('ordres_travail', 'OT-2026-0001'));
          const ot3 = Ordres.cout(Donnees.trouver('ordres_travail', 'OT-2026-0003'));
          const g = Indicateurs.global(Indicateurs.periodeDuMois('2026-11'), {}, '2026-11-20');
          return { pieces1: ot1.pieces, total1: ot1.total, hm3: ot3.detail.pieces.filter((p) => p.horsMagasin),
            cout: g.cout.valeur, stock: Donnees.stockArticle('') }; }""")
        self.assertAlmostEqual(r["pieces1"], 38.5 + 25, places=2)
        self.assertAlmostEqual(r["total1"], 1.5 * 45 + 38.5 + 25, places=2)
        self.assertAlmostEqual(r["cout"], 173.5 + 25, places=2)
        self.assertEqual([(p["libelle"], p["quantite"], p["prix"], p["montant"]) for p in r["hm3"]], [("Joint spi 40x52", 1, None, 0)])
        self.assertEqual(r["stock"], 0)

    def test_sans_prix_non_chiffre_dans_ce_qui_manque(self):
        manques = self.page.evaluate("() => Indicateurs.manquesCout(Indicateurs.periodeDuMois('2026-11'))")
        self.assertFalse(manques["complet"])
        noms = [(a["article"] or {}).get("designation") or a["articleId"] for a in manques["articles"]]
        self.assertIn("Joint spi 40x52", noms)
        self.assertNotIn("Courroie SPA 1250", noms)
        self.assertEqual(len(manques["articles"]), 2)             # JT-12 sans prix (mois d'essai) et le joint spi
        r = self.donnees()
        self.assertIn("Joint spi 40x52", json.dumps(r, ensure_ascii=False))       # « Ce qui manque » du bilan


class CasOt(CasNavigateur):

    def ouvrir_demo(self, profil, technicien_id=""):
        preregler_profil(self.contexte, profil, "Essai", technicien_id)
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        return self.page

    def ouvrir_execution(self, page):
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".onglet[data-onglet='execution']")
        page.click(".onglet[data-onglet='execution']")
        page.wait_for_selector("#ot-bloc-sorties .ot-hors-magasin-form")

    def lignes_hors_magasin(self, page):
        return page.evaluate("""(id) => Donnees.lignes('mouvements_stock').filter((m) => m.ot_id === id && m.type === 'hors magasin')
          .map((m) => ({ article_id: m.article_id, designation: m.designation, quantite: m.quantite, prix_unitaire: m.prix_unitaire }))""", OT)


class TestSaisieSurLOt(CasOt):

    def test_responsable_note_une_piece_avec_son_prix(self):
        page = self.ouvrir_demo("responsable")
        self.ouvrir_execution(page)
        page.fill("#ot-hm-designation", "Courroie SPA 1250")
        page.fill("#ot-hm-quantite", "2")
        page.fill("#ot-hm-prix", "12,50")
        page.click(".ot-hors-magasin-form button[type=submit]")
        page.wait_for_selector("#ot-bloc-sorties .ot-table-hors-magasin")
        self.assertEqual(self.lignes_hors_magasin(page),
                         [{"article_id": "", "designation": "Courroie SPA 1250", "quantite": "2", "prix_unitaire": "12.5"}])
        self.assertIn("25,00", page.inner_text("#ot-bloc-sorties .ot-table-hors-magasin").replace(" ", " "))
        # Le coût de l'OT la compte ; un prix effacé la rend « non chiffrée » (montant 0, aucune valeur inventée).
        avant = page.evaluate("(id) => Ordres.cout(Donnees.trouver('ordres_travail', id)).pieces", OT)
        page.click("#ot-bloc-sorties button.ot-prix-hors-magasin")
        page.fill("dialog [name='prix']", "")
        page.click("dialog .fenetre-actions .btn-primaire")
        page.wait_for_function("(id) => Donnees.lignes('mouvements_stock').some((m) => m.ot_id === id && m.type === 'hors magasin' && m.prix_unitaire === '')", arg=OT)
        apres = page.evaluate("(id) => Ordres.cout(Donnees.trouver('ordres_travail', id)).pieces", OT)
        self.assertAlmostEqual(avant - apres, 25, places=2)
        page.wait_for_selector("#ot-bloc-sorties .ot-table-hors-magasin")
        self.assertIn("non chiffré", page.inner_text("#ot-bloc-sorties .ot-table-hors-magasin"))

    def test_designation_obligatoire(self):
        page = self.ouvrir_demo("responsable")
        self.ouvrir_execution(page)
        page.click(".ot-hors-magasin-form button[type=submit]")
        page.wait_for_selector("#ot-bloc-sorties .ot-hm-message .alerte, #ot-bloc-sorties .ot-hm-message *")
        self.assertIn("désignation", page.inner_text("#ot-bloc-sorties .ot-hm-message"))
        self.assertEqual(self.lignes_hors_magasin(page), [])

    def test_technicien_sans_prix(self):
        page = self.ouvrir_demo("responsable")
        technicien = page.evaluate("(id) => Donnees.trouver('ordres_travail', id).technicien_id", OT)
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        preregler_profil(contexte, "technicien", "Essai", technicien)
        page = contexte.new_page()
        self.surveiller(page)
        page.goto(url_fichier("index.html"))
        page.click("#btn-demo")
        attendre_pret(page)
        self.ouvrir_execution(page)
        self.assertEqual(page.locator("#ot-hm-prix").count(), 0)
        page.fill("#ot-hm-designation", "Courroie SPA 1250")
        page.click(".ot-hors-magasin-form button[type=submit]")
        page.wait_for_selector("#ot-bloc-sorties .ot-table-hors-magasin")
        self.assertEqual(page.locator("#ot-bloc-sorties .ot-table-hors-magasin th").count(), 2)   # désignation, quantité
        self.assertEqual(page.locator("button.ot-prix-hors-magasin").count(), 0)
        # Même appelée avec un prix, l'écriture du technicien n'en met pas (D126).
        page.evaluate("(id) => Magasin.noterHorsMagasin(id, { designation: 'Joint', quantite: '1', prix: '9' })", OT)
        self.assertEqual([l["prix_unitaire"] for l in self.lignes_hors_magasin(page)], ["", ""])
        refus = page.evaluate("""async () => { const id = Donnees.lignes('mouvements_stock').find((m) => m.type === 'hors magasin').id;
          try { await Magasin.completerHorsMagasin(id, { prix: '9' }); return ''; } catch (e) { return e.message; } }""")
        self.assertIn("réservé", refus)


class TestFenetreDeCloture(CasOt):

    def test_piece_hors_magasin_dans_la_fenetre(self):
        figer_a_midi(self.contexte)         # clôture de l'OT « en cours » de la démo
        page = self.ouvrir_demo("responsable")
        page.evaluate("location.hash = %r" % ("#/ot/" + OT))
        page.wait_for_selector(".ot-actions [data-cible='Clôturé techniquement']")
        page.click(".ot-actions [data-cible='Clôturé techniquement']")
        fenetre = "dialog.dialogue[open]"
        page.wait_for_selector(fenetre + " [name='compte_rendu']", state="visible")
        resume = page.inner_text(fenetre + " .ot-cloture-facultatif > summary")
        self.assertIn("hors magasin", resume)
        page.click(fenetre + " .ot-cloture-facultatif > summary")
        page.fill(fenetre + " [name='designation_hm']", "Courroie SPA 1250")
        page.fill(fenetre + " [name='quantite_hm']", "1")
        page.fill(fenetre + " [name='prix_hm']", "12,5")
        # Le reste de la clôture : codes, compte rendu, case (date de fin et temps proposés).
        for nom in ("cause_code", "remede_code"):
            valeur = page.locator(fenetre + " [name='%s'] option" % nom).nth(2).get_attribute("value")
            page.select_option(fenetre + " [name='%s']" % nom, valeur)
        if page.locator(fenetre + " [name='symptome_code']").count():
            valeur = page.locator(fenetre + " [name='symptome_code'] option").nth(2).get_attribute("value")
            page.select_option(fenetre + " [name='symptome_code']", valeur)
        if not page.input_value(fenetre + " [name='heures']"):
            page.fill(fenetre + " [name='heures']", "1")
        page.fill(fenetre + " [name='compte_rendu']", "Courroie usée remplacée, tension réglée.")
        page.check(fenetre + " [name='remise_service']")
        page.click(fenetre + " .fenetre-actions .btn-primaire")
        page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'", arg=OT)
        self.assertEqual(self.lignes_hors_magasin(page),
                         [{"article_id": "", "designation": "Courroie SPA 1250", "quantite": "1", "prix_unitaire": "12.5"}])


class TestListeDuResponsable(CasOt):
    """Point 2 : Magasin > « Hors magasin » (responsable) : à traiter en tête, « Saisir le prix », « Créer l'article »
    pré-rempli ; l'article créé est relié à la ligne (traitée), qui reste hors du stock."""

    NOTER = """(id) => Magasin.noterHorsMagasin(id, { designation: 'Courroie SPA 1250', quantite: '2', prix: '' })"""

    def test_creer_l_article_depuis_la_liste(self):
        page = self.ouvrir_demo("responsable")
        page.evaluate(self.NOTER, OT)
        page.evaluate("location.hash = '#/magasin?onglet=hors-magasin'")
        page.wait_for_selector(".magasin-hors-magasin a.magasin-hm-creer")
        self.assertIn("1 pièce à traiter", page.inner_text(".magasin-compteur"))
        self.assertIn("non chiffré", page.inner_text(".magasin-hors-magasin"))
        # Prix saisi dans la liste
        page.click(".magasin-hors-magasin button.magasin-hm-prix")
        page.fill("dialog [name='prix']", "12,5")
        page.click("dialog .fenetre-actions .btn-primaire")
        page.wait_for_function("() => Donnees.lignes('mouvements_stock').some((m) => m.type === 'hors magasin' && m.prix_unitaire === '12.5')")
        # « Créer l'article » : désignation et prix pré-remplis
        page.wait_for_selector(".magasin-hors-magasin a.magasin-hm-creer")
        page.click(".magasin-hors-magasin a.magasin-hm-creer")
        page.wait_for_selector("#form-article [name='designation']")
        self.assertEqual(page.input_value("#form-article [name='designation']"), "Courroie SPA 1250")
        self.assertIn("12", page.input_value("#form-article [name='prix_unitaire']"))
        self.assertIn(OT, page.inner_text(".magasin-depuis-hors-magasin"))
        page.fill("#form-article [name='reference']", "CRO-SPA1250")
        page.click("#form-article button[type=submit]")
        page.wait_for_function("() => location.hash === '#/magasin?onglet=hors-magasin'")
        ligne = page.evaluate("() => Donnees.lignes('mouvements_stock').find((m) => m.type === 'hors magasin')")
        article = page.evaluate("(id) => Donnees.trouver('articles', id)", ligne["article_id"])
        self.assertEqual((article["reference"], article["designation"]), ("CRO-SPA1250", "Courroie SPA 1250"))
        self.assertEqual(ligne["prix_unitaire"], "12.5")
        # Traitée : plus de bouton, lien vers l'article ; le stock de l'article nouveau reste 0 ; le coût ne change pas.
        page.wait_for_selector(".magasin-hors-magasin a[href^='#/magasin/article/ART-']")
        self.assertEqual(page.locator(".magasin-hors-magasin a.magasin-hm-creer").count(), 0)
        self.assertIn("0 pièce à traiter", page.inner_text(".magasin-compteur"))
        self.assertEqual(page.evaluate("(id) => Donnees.stockArticle(id)", ligne["article_id"]), 0)
        self.assertAlmostEqual(page.evaluate("(id) => Ordres.cout(Donnees.trouver('ordres_travail', id)).detail.pieces"
                                             ".filter((p) => p.horsMagasin)[0].montant", OT), 25, places=2)

    def test_prix_de_l_article_repris_si_la_piece_n_en_avait_pas(self):
        page = self.ouvrir_demo("responsable")
        page.evaluate(self.NOTER, OT)
        mvt = page.evaluate("() => Donnees.lignes('mouvements_stock').find((m) => m.type === 'hors magasin').id")
        page.evaluate("location.hash = %r" % ("#/magasin/article/nouveau?hors=" + mvt))
        page.wait_for_selector("#form-article [name='designation']")
        page.fill("#form-article [name='reference']", "CRO-SPA1250")
        page.fill("#form-article [name='prix_unitaire']", "11")
        page.click("#form-article button[type=submit]")
        page.wait_for_function("() => location.hash === '#/magasin?onglet=hors-magasin'")
        ligne = page.evaluate("() => Donnees.lignes('mouvements_stock').find((m) => m.type === 'hors magasin')")
        self.assertTrue(ligne["article_id"].startswith("ART-"))
        self.assertEqual(ligne["prix_unitaire"], "11")

    def test_onglet_reserve_au_responsable(self):
        page = self.ouvrir_demo("technicien", "TEC-0001")
        page.evaluate("location.hash = '#/magasin'")
        page.wait_for_selector(".magasin-onglets .onglet")
        self.assertNotIn("Hors magasin", " ".join(page.locator(".magasin-onglets .onglet").all_inner_texts()))


class TestReglagePrixDuTechnicien(CasOt):
    """Réglage « Les techniciens peuvent saisir le prix des pièces hors magasin » (désactivé par défaut) : dans
    Paramètres ; activé, le technicien voit et saisit le prix (sur l'OT et dans la fenêtre de clôture)."""

    def page_technicien(self, actif):
        page = self.ouvrir_demo("responsable")
        technicien = page.evaluate("(id) => Donnees.trouver('ordres_travail', id).technicien_id", OT)
        self.assertEqual(page.evaluate("() => Donnees.parametre('techniciens_prix_hors_magasin', '0')"), "0")
        page.evaluate("location.hash = '#/parametres'")
        case = page.locator("#form-parametres [name='techniciens_prix_hors_magasin']")
        case.wait_for()
        self.assertFalse(case.is_checked())
        if actif:
            case.click()
            page.click("#form-parametres button[type=submit]")
            page.wait_for_function("() => Donnees.parametre('techniciens_prix_hors_magasin', '') === '1'")
        contexte = self.navigateur.new_context(locale="fr-FR", viewport={"width": 1280, "height": 800})
        self.addCleanup(contexte.close)
        preregler_profil(contexte, "technicien", "Essai", technicien)
        autre = contexte.new_page()
        self.surveiller(autre)
        autre.goto(url_fichier("index.html"))
        autre.click("#btn-demo")
        attendre_pret(autre)
        if actif:          # la démo est propre à chaque page : le réglage est posé ici comme le responsable l'a fait
            autre.evaluate("""() => Donnees.modifier('parametres', (lignes) => {
              const l = lignes.find((x) => x.cle === 'techniciens_prix_hors_magasin');
              if (l) l.valeur = '1'; else lignes.push({ cle: 'techniciens_prix_hors_magasin', valeur: '1' }); }, { action: 'essai' })""")
        self.ouvrir_execution(autre)
        return autre

    def test_desactive_par_defaut(self):
        page = self.page_technicien(False)
        self.assertEqual(page.locator("#ot-hm-prix").count(), 0)

    def test_active_le_technicien_saisit_le_prix(self):
        page = self.page_technicien(True)
        page.fill("#ot-hm-designation", "Courroie SPA 1250")
        page.fill("#ot-hm-prix", "12,5")
        page.click(".ot-hors-magasin-form button[type=submit]")
        page.wait_for_selector("#ot-bloc-sorties button.ot-prix-hors-magasin")
        self.assertEqual([l["prix_unitaire"] for l in self.lignes_hors_magasin(page)], ["12.5"])
        page.click(".ot-actions [data-cible='Clôturé techniquement']")
        page.wait_for_selector("dialog.dialogue[open] [name='compte_rendu']", state="visible")
        self.assertEqual(page.locator("dialog.dialogue[open] [name='prix_hm']").count(), 1)


if __name__ == "__main__":
    unittest.main()
