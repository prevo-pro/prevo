"""Mode Solo sans la couche équipe (lot 1 ergonomie, B, T521 ; js/modules/solo-flux.js, solo-accueil.js ;
ARCHITECTURE.md §22.11).

En mode serveur sans comptes, sur une copie de la démo, profil Responsable avec mode_solo = 1 :
    - les demandes « Nouvelle » des opérateurs deviennent des OT au nom du technicien seul (une ligne de prise en charge,
      type et priorité comme « Accepter »), à l'ouverture et à l'accueil ; l'accueil dit « Nouvelle panne déclarée
      par … » avec le lien de l'OT ;
    - deux onglets qui convertissent en même temps ne créent qu'un OT pour la même demande ;
    - sa propre déclaration (« Signaler un problème ») ouvre aussitôt l'OT à son nom ;
    - tout OT créé (manuel, préventif généré) naît à son nom ; la fiche montre trois états, « Démarrer » tout de suite,
      « Marquer préparé » et « Planifier » sous « Plus d'options » ; aucun champ « Technicien » ;
    - habilitation exigée : un rappel, jamais de refus ni de dérogation (D191 inchangée en équipe) ;
    - menu sans Équipe ni Planning, liste des OT sans colonne ni filtre « Technicien » ;
    - mode Équipe (mode_solo = 0) : rien ne change (demandes laissées « Nouvelle », bento, refus RG8).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_solo_flux.py" -v
"""
import csv
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil

MOI = "TEC-0004"                         # Thomas, technicien du jeu de démo (sans BR valide), pris comme technicien seul
LIGNE_PRISE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}\|TEC-0004\|$")


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


class CasSolo(CasNavigateur):

    def ouvrir(self, serveur, route, page=None):
        page = page or self.page
        page.goto(serveur.url + "/" + route)
        attendre_pret(page)
        return page

    def poser_mode(self, page, solo):
        """mode_solo (et le technicien seul) écrits comme le fait Paramètres, puis la page rechargée."""
        page.evaluate("""solo => Donnees.modifier('parametres', (lignes) => {
            const poser = (cle, valeur) => { const l = lignes.find((x) => x.cle === cle);
              if (l) l.valeur = valeur; else lignes.push({ cle, valeur }); };
            poser('mode_solo', solo ? '1' : '0'); poser('solo_technicien_id', 'TEC-0004'); poser('cloture_une_etape', '1');
        })""", solo)
        page.reload()
        attendre_pret(page)

    def nouvelle_demande(self, page, equipement="EQ-0005", impact="arrêt", demandeur="Léa Opératrice"):
        return page.evaluate("""([equipement, impact, demandeur]) => Demandes.creer({ equipement_id: equipement,
            symptome: 'Bruit anormal', impact, description: 'Essai T521', demandeur })""", [equipement, impact, demandeur])


class TestConversion(CasSolo):

    def test_demandes_converties_a_l_ouverture_et_accueil(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", nom="Thomas")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            nouvelles = [di["id"] for di in lire_csv(serveur.dossier, "demandes.csv") if di["statut"] == "Nouvelle"]
            self.assertTrue(nouvelles, "le jeu de démo a des demandes « Nouvelle »")
            ma_di = self.nouvelle_demande(page)
            self.poser_mode(page, True)
            page.wait_for_selector("#solo-accueil")
            page.wait_for_selector("#solo-pannes li")
            demandes = {di["id"]: di for di in lire_csv(serveur.dossier, "demandes.csv")}
            ordres = lire_csv(serveur.dossier, "ordres_travail.csv")
            for di_id in nouvelles + [ma_di]:
                with self.subTest(demande=di_id):
                    di = demandes[di_id]
                    self.assertEqual(di["statut"], "Acceptée")
                    lies = [ot for ot in ordres if ot["di_id"] == di_id]
                    self.assertEqual(len(lies), 1)
                    self.assertEqual(lies[0]["id"], di["ot_id"])
                    self.assertEqual(lies[0]["technicien_id"], MOI)
                    self.assertRegex(lies[0]["prises_en_charge"], LIGNE_PRISE)
                    self.assertEqual(lies[0]["statut"], "Créé")
            ot = next(o for o in ordres if o["di_id"] == ma_di)
            # Impact « arrêt » : priorité et type comme « Accepter » (Demandes.accepter)
            attendu = page.evaluate("""id => { const di = Donnees.trouver('demandes', id);
                const p = Demandes.interne.prioriteDeLaDemande(di) || 'P3'; return [p, Demandes.typePropose(p)]; }""", ma_di)
            self.assertEqual([ot["priorite"], ot["type"]], attendu)
            # Accueil : « Nouvelle panne déclarée par Léa Opératrice : PO-02 … », lien vers l'OT
            texte = page.inner_text("#solo-pannes")
            self.assertIn("Nouvelle panne déclarée par Léa Opératrice", texte)
            self.assertEqual(page.locator('#solo-pannes a[href="#/ot/%s"]' % ot["id"]).count(), 1)
            for zone in ("#accueil-nouvel-ot", "#accueil-signaler", "#solo-en-cours", "#solo-preventif", "#solo-a-faire"):
                self.assertEqual(page.locator(zone).count(), 1, zone)
            self.assertEqual(page.locator("#bento").count(), 0)
            self.assertEqual(page.locator("#reprises-recentes, #a-prendre").count(), 0)
            # Fiche de la demande : plus de décision à prendre (Accepter, Regrouper, Différer, Refuser)
            page.evaluate("id => { location.hash = '#/di/' + encodeURIComponent(id); }", ma_di)
            page.wait_for_selector("#contenu h1")
            self.assertEqual(page.locator("#contenu [data-decision], #di-accepter").count(), 0)

    def test_deux_onglets_un_seul_ot_par_demande(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", nom="Thomas")
        with ServeurPrevo() as serveur:
            # Deux onglets qui écrivent en même temps : des conflits (409) relus et rejoués, c'est attendu.
            self.autoriser_erreur("409 (Conflict)")
            self.ouvrir(serveur, "#/ot")
            self.poser_mode(page, True)
            autre = self.contexte.new_page()
            self.surveiller(autre)
            self.ouvrir(serveur, "#/ot", autre)
            for essai in range(3):
                di_id = self.nouvelle_demande(page, equipement="EQ-0006", impact="dégradé", demandeur="Essai %d" % essai)
                # Les deux onglets convertissent en même temps (le second est lancé sans attendre).
                autre.evaluate("() => { window.__conversion = Solo.convertirDemandes(); }")
                page.evaluate("Solo.convertirDemandes()")
                autre.evaluate("() => window.__conversion")
                lies = [ot for ot in lire_csv(serveur.dossier, "ordres_travail.csv") if ot["di_id"] == di_id]
                self.assertEqual(len(lies), 1, "essai %d : %d OT pour %s" % (essai, len(lies), di_id))
                di = next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["id"] == di_id)
                self.assertEqual((di["statut"], di["ot_id"]), ("Acceptée", lies[0]["id"]))
                self.assertEqual(lies[0]["statut"], "Créé")
            autre.close()

    def test_sa_propre_declaration_ouvre_l_ot_a_son_nom(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", nom="Thomas")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            self.poser_mode(page, True)
            page.click("#accueil-signaler")
            page.wait_for_selector(".di-formulaire")
            page.evaluate("location.hash = '#/di/nouvelle?equipement=EQ-0005'")
            page.wait_for_selector(".selecteur-choisi")
            page.click(".di-puce[data-symptome='Fuite']")
            page.click("label.tuile:has(input[value='dégradé'])")
            page.click(".di-envoyer")
            page.wait_for_function("/^#\\/ot\\/OT-/.test(location.hash)")
            ot_id = page.evaluate("decodeURIComponent(location.hash.slice(5))")
            ot = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
            self.assertEqual((ot["technicien_id"], ot["origine"], ot["statut"]), (MOI, "DI", "Créé"))
            self.assertEqual(next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["id"] == ot["di_id"])["statut"],
                             "Acceptée")
            # Fiche : « Démarrer » proposé tout de suite, trois états, rien d'obligatoire avant
            page.wait_for_selector(".solo-etapes")
            self.assertEqual(page.locator(".solo-etapes li").count(), 3)
            self.assertEqual(page.locator('.ot-actions > .actions button[data-cible="En cours"]').count(), 1)


class TestFicheEtCreation(CasSolo):

    def test_ot_crees_a_son_nom_fiche_allegee_et_rappel_d_habilitation(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", nom="Thomas")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            evaluer = page.evaluate
            # Équipe : RG8 refuse (D191 inchangée)
            self.poser_mode(page, False)
            refus = evaluer("""() => Ordres.creer({ origine: 'manuel', equipement_id: 'EQ-0012', titre: 'Armoire',
                type: 'correctif différé', priorite: 'P3', technicien_id: 'TEC-0004', date_prevue: '2026-10-21' })
                .then(() => 'écrit', (e) => e.habilitation ? 'refus' : String(e))""")
            self.assertEqual(refus, "refus")
            # Solo : ni refus ni dérogation, l'OT naît à son nom même sans technicien donné
            self.poser_mode(page, True)
            ot_id = evaluer("""() => Ordres.creer({ origine: 'manuel', equipement_id: 'EQ-0012', titre: 'Armoire',
                type: 'correctif différé', priorite: 'P3', technicien_id: '', date_prevue: '2026-10-21' })""")
            ot = next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)
            self.assertEqual(ot["technicien_id"], MOI)
            self.assertRegex(ot["prises_en_charge"], LIGNE_PRISE)
            journal = (serveur.dossier / "journal.csv").read_text(encoding="utf-8-sig")
            self.assertEqual([l for l in journal.splitlines() if ot_id in l and "dérogation" in l], [])
            # Préventif généré : à son nom
            crees = evaluer("Preventif.genererOTEchus({ aujourdhui: '2030-01-01' })")
            self.assertTrue(crees, "des gammes échues au 1er janvier 2030")
            ordres = {o["id"]: o for o in lire_csv(serveur.dossier, "ordres_travail.csv")}
            for cree in crees:
                self.assertEqual(ordres[cree]["technicien_id"], MOI, cree)
            # Fiche : rappel d'habilitation, trois états, « Démarrer », « Plus d'options »
            evaluer("id => { location.hash = '#/ot/' + encodeURIComponent(id); }", ot_id)
            page.wait_for_selector(".ot-fiche .solo-etapes")
            self.assertIn("Rappel d'habilitation", page.inner_text("#solo-rappel-habilitation"))
            self.assertEqual(page.locator('.ot-actions > .actions button[data-cible="En cours"]').count(), 1)
            self.assertEqual(page.locator('#solo-plus-options button[data-cible="Préparé"]').count(), 1)
            self.assertEqual(page.locator('.ot-actions > .actions button[data-cible="Préparé"]').count(), 0)
            self.assertTrue(page.is_hidden('#solo-plus-options button[data-cible="Préparé"]'))      # replié
            # Onglet Préparation : pas de champ « Technicien » à l'écran (la valeur reste)
            page.wait_for_selector("#form-preparation [name='travail_a_faire']")
            self.assertTrue(page.is_hidden("#form-preparation [name='technicien_id']"))
            self.assertTrue(page.is_hidden(".ot-actions-preparation"))
            # Démarrer : sans planifier ni préparer, ni dérogation
            page.click('.ot-actions > .actions button[data-cible="En cours"]')
            page.wait_for_function("id => Donnees.trouver('ordres_travail', id).statut === 'En cours'", arg=ot_id)
            self.assertEqual(page.locator("dialog[open]").count(), 0)
            # Liste : ni colonne ni filtre « Technicien »
            evaluer("location.hash = '#/ot'")
            page.wait_for_selector("#ot-filtres")
            self.assertTrue(page.is_hidden("#ot-filtre-technicien"))
            self.assertNotIn("Technicien", page.evaluate("[...document.querySelectorAll('#contenu th')].map(t => t.textContent).join('|')"))
            menu = evaluer("[...document.querySelectorAll('#menu > a')].map(a => a.dataset.ecran)")
            self.assertNotIn("equipe", menu)
            self.assertNotIn("planning", menu)


class TestEquipeInchangee(CasSolo):

    def test_mode_equipe_demandes_laissees_et_bento(self):
        page = self.page
        preregler_profil(self.contexte, "responsable", nom="Thomas")
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/accueil")
            di_id = self.nouvelle_demande(page)
            self.poser_mode(page, False)
            page.wait_for_selector("#bento")
            self.assertEqual(page.locator("#solo-accueil").count(), 0)
            self.assertFalse(page.evaluate("document.documentElement.hasAttribute('data-solo')"))
            self.assertEqual(page.evaluate("Solo.convertirDemandes()"), [])
            di = next(d for d in lire_csv(serveur.dossier, "demandes.csv") if d["id"] == di_id)
            self.assertEqual((di["statut"], di["ot_id"]), ("Nouvelle", ""))
            self.assertEqual([o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["di_id"] == di_id], [])
            # Un OT créé sans technicien reste sans technicien ; menu complet
            ot_id = page.evaluate("""() => Ordres.creer({ origine: 'manuel', equipement_id: 'EQ-0005', titre: 'Équipe',
                type: 'correctif différé', priorite: 'P3', technicien_id: '', date_prevue: '' })""")
            self.assertEqual(next(o for o in lire_csv(serveur.dossier, "ordres_travail.csv") if o["id"] == ot_id)["technicien_id"], "")
            menu = page.evaluate("[...document.querySelectorAll('#menu > a')].map(a => a.dataset.ecran)")
            self.assertIn("equipe", menu)
            self.assertIn("planning", menu)


if __name__ == "__main__":
    unittest.main()
