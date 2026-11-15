"""Codes cause et remède de la clôture (T515, correction A2 du lot 1 ergonomie ; js/modules/ordres-codes.js,
js/catalogue/codes-depart.js, serveur.py codes_de_depart ; ARCHITECTURE.md §10 RG4, §15.11).

Familles (le nom du test le dit) :
    catalogue    : liste de départ (sans navigateur) : causes, remèdes et symptômes attendus, codes uniques et courts,
                   libellé dans chaque langue déclarée, lue de la même façon par le serveur ;
    installation : « terminer » de l'assistant (sans navigateur) : base « vide » neuve ⇒ codes_defaillance.csv dans la
                   langue choisie ; base présente au départ ⇒ rien d'écrit ;
    regles       : RG4 dans la page (jeu de démo) : préventif et réglementaire sans cause ni remède exigés ;
                   correctif : un code OU une précision (« Autre ») ; « Autre » enregistré code vide ; Pareto des
                   causes (« Autre (précisé) ») et causes fréquentes (« Autre : … ») ;
    cloture      : onglet Compte rendu : « Autre (préciser) » enregistré puis réaffiché ; préventif sans champ cause ;
    liste_vide   : base sans codes : clôture non bloquée par les codes, message avec lien et liste de départ ;
                   Paramètres : « Ajouter la liste de départ », suppression d'un code non cité ;
    base_vide    : « Créer une base vide » du navigateur ⇒ codes de départ dans la langue choisie.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ordres_codes.py" -v
"""
import csv
import io
import re
import shutil
import tempfile
import time
import unittest
from pathlib import Path

import serveur
from commun import (DOSSIER_DEMO, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo)
from test_installation_api import CasAssistant

SCENARIOS = scenarios_demo()
OT_EN_COURS = SCENARIOS["ot_statut_en_cours"]       # correctif « En cours »
OT_PREVENTIF = SCENARIOS["ot_statut_cree"]          # préventif « Créé »
ERREUR_CSV_ABSENT = re.compile(r"status of 404.*/api/csv/")
MOTIF_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,11}$")       # MOTIF_CODE de parametres-codes.js
CAUSES_ATTENDUES = {"C-USURE", "C-MECA", "C-ELEC", "C-PNEU", "C-HYDRAU", "C-LUBRIF", "C-ENCRASSE", "C-REGLAGE",
                    "C-UTILISAT", "C-SURCHARGE", "C-MATIERE", "C-AUTOMAT", "C-EXTERIEUR", "C-INCONNUE"}
REMEDES_ATTENDUS = {"R-REMPLACE", "R-REPARE", "R-REGLAGE", "R-NETTOYAGE", "R-GRAISSAGE", "R-SERRAGE", "R-REARMEMENT",
                    "R-PROVISOIRE", "R-AMELIORE", "R-PRESTA", "R-CONTROLE"}
COMPLET = {"id": "X", "statut": "En cours", "date_debut": "2026-10-19 08:00", "date_fin": "2026-10-19 10:00",
           "compte_rendu": "Courroie usée remplacée, essai concluant.", "remise_service": "1"}
VERIFIER = "([ot, temps]) => Ordres.verifierCloture(ot, { temps })"


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def copie_demo_sans_codes():
    """Dossier temporaire : la démo, codes_defaillance.csv réduit à son en-tête (base existante sans codes)."""
    dossier = Path(tempfile.mkdtemp(prefix="prevo-codes-"))
    shutil.copytree(DOSSIER_DEMO, dossier / "donnees")
    fichier = dossier / "donnees" / "codes_defaillance.csv"
    fichier.write_bytes(fichier.read_bytes().split(b"\r\n")[0] + b"\r\n")
    return dossier


# ---------------------------------------------------------------------------
# Liste de départ (sans navigateur)
# ---------------------------------------------------------------------------

class TestCatalogue(unittest.TestCase):

    def test_catalogue_familles_codes_et_langues(self):
        lignes = serveur.codes_de_depart("fr")
        par_famille = {}
        for identifiant, famille, code, libelle in lignes:
            par_famille.setdefault(famille, set()).add(code)
            self.assertRegex(code, MOTIF_CODE)
            self.assertTrue(libelle.strip(), code)
        self.assertEqual([l[0] for l in lignes], ["CD-%04d" % rang for rang in range(1, len(lignes) + 1)])
        self.assertEqual(len({l[2] for l in lignes}), len(lignes))                     # codes uniques dans la table
        self.assertGreaterEqual(len(par_famille["cause"]), 15)
        self.assertGreaterEqual(len(par_famille["remède"]), 12)
        self.assertGreaterEqual(len(par_famille["symptôme"]), 5)
        self.assertLessEqual(CAUSES_ATTENDUES, par_famille["cause"])
        self.assertLessEqual(REMEDES_ATTENDUS, par_famille["remède"])
        for langue in serveur.langues_declarees():
            with self.subTest(langue=langue):
                traduites = serveur.codes_de_depart(langue)
                self.assertEqual([l[:3] for l in traduites], [l[:3] for l in lignes])
                if langue != "fr":
                    self.assertNotEqual([l[3] for l in traduites], [l[3] for l in lignes])
                for famille in ("cause", "remède", "symptôme"):           # libellés uniques dans leur famille
                    libelles = [l[3].casefold() for l in traduites if l[1] == famille]
                    self.assertEqual(len(set(libelles)), len(libelles))
        self.assertEqual(serveur.codes_de_depart("zz"), lignes)                     # langue inconnue : le français


class TestInstallation(CasAssistant):

    def terminer(self, source=None, langue=None):
        client, instance = self.lancer(source=source)
        self.ok(client.post("situation", {"situation": "seul"}))
        self.ok(client.post("portee", {"portee": "ce-pc"}))
        self.ok(client.post("compte", {"prenom": "Hugo", "nom": "Martin"}))
        corps = {"base": "vide"}
        if langue:
            corps["langue_defaut"] = langue
        self.ok(client.post("terminer", corps))
        return Path(instance.config.dossier_donnees)

    def test_installation_base_vide_neuve_recoit_la_liste_dans_sa_langue(self):
        donnees = self.terminer(langue="it")
        lignes = lire_csv(donnees, "codes_defaillance.csv")
        self.assertEqual([(l["id"], l["famille"], l["code"], l["libelle"]) for l in lignes],
                         [tuple(l) for l in serveur.codes_de_depart("it")])
        self.assertIn("Usura normale", [l["libelle"] for l in lignes])
        self.assertTrue((donnees / "codes_defaillance.csv").read_bytes().startswith(b"\xef\xbb\xbfid;famille;code;libelle\r\n"))

    def test_installation_base_presente_au_depart_rien_d_ecrit(self):
        source = Path(tempfile.mkdtemp(prefix="prevo-source-"))
        self.addCleanup(shutil.rmtree, source, True)
        (source / "equipements.csv").write_bytes((DOSSIER_DEMO / "equipements.csv").read_bytes())
        donnees = self.terminer(source=source)
        self.assertFalse((donnees / "codes_defaillance.csv").exists())


# ---------------------------------------------------------------------------
# Dans la page
# ---------------------------------------------------------------------------

class CasCodes(CasNavigateur):

    def ouvrir(self, serveur_prevo, route, profil="responsable", technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto(serveur_prevo.url + "/" + route)
        attendre_pret(self.page)

    def fiche_compte_rendu(self, ot_id):
        page = self.page
        page.evaluate("location.hash = %r" % ("#/ot/" + ot_id))
        page.wait_for_function("document.querySelector('.ot-fiche .ot-numero') && document.querySelector('.ot-fiche .ot-numero').textContent === %r" % ot_id)
        page.click(".onglet[data-onglet='compte-rendu']")
        page.wait_for_selector("#form-compte-rendu")


class TestRegles(CasCodes):

    def test_regles_cloture_preventif_correctif_autre_pareto_causes_frequentes(self):
        with ServeurPrevo() as serveur_prevo:
            self.ouvrir(serveur_prevo, "#/ot")
            page = self.page
            temps = [{"heures": "1"}]
            correctif = dict(COMPLET, type="correctif différé")
            manques = " | ".join(page.evaluate(VERIFIER, [correctif, temps]))
            self.assertIn("code cause", manques)
            self.assertIn("code remède", manques)
            # Un code OU une précision (« Autre ») suffit ; « Autre » sans texte ne suffit pas
            self.assertEqual(page.evaluate(VERIFIER, [dict(correctif, cause_precision="Courroie desserrée",
                                                           remede_code="R01"), temps]), [])
            self.assertEqual(page.evaluate(VERIFIER, [dict(correctif, cause_code="C01", remede_precision="Retendue"), temps]), [])
            self.assertEqual(len(page.evaluate(VERIFIER, [dict(correctif, cause_precision="  ", remede_code="R01"), temps])), 1)
            # Préventif (systématique, conditionnel) et réglementaire : ni cause ni remède exigés
            for type_ot in ("préventif systématique", "préventif conditionnel", "réglementaire"):
                with self.subTest(type=type_ot):
                    self.assertEqual(page.evaluate(VERIFIER, [dict(COMPLET, type=type_ot), temps]), [])
            self.assertEqual(len(page.evaluate(VERIFIER, [dict(COMPLET, type="amélioration"), temps])), 2)
            # Cause montrée sur un préventif seulement avec une anomalie (ou une cause déjà là)
            self.assertFalse(page.evaluate("Ordres.causeDemandee({ type: 'préventif systématique' })"))
            self.assertTrue(page.evaluate("Ordres.causeDemandee({ type: 'préventif systématique', anomalie_constatee: '1' })"))
            self.assertTrue(page.evaluate("Ordres.causeDemandee({ type: 'réglementaire', cause_code: 'C01' })"))
            self.assertTrue(page.evaluate("Ordres.causeDemandee({ type: 'correctif différé' })"))
            # « Autre » : code vide, précision gardée ; champ absent : rien
            saisis = page.evaluate("Ordres.codesSaisis({ cause_code: Ordres.CODE_AUTRE, cause_precision: ' Câble pincé ', "
                                   "remede_code: 'R01', compte_rendu: 'x' })")
            self.assertEqual(saisis, {"cause_code": "", "cause_precision": "Câble pincé", "remede_code": "R01"})
            self.assertEqual(page.evaluate("Ordres.libelleAutre('Câble pincé')"), "Autre : Câble pincé")
            self.assertEqual(page.evaluate("Ordres.libelleAutre(' ')"), "")

            # Causes fréquentes : tous les cas d'un symptôme passés en « Autre » ⇒ « Autre : <précision> »
            cas = page.evaluate("""() => {
              for (const ot of Donnees.lignes('ordres_travail')) {
                const r = CausesFrequentes.calculer(ot.equipement_id, ot.symptome_code);
                if (r.suffisant) return { eq: ot.equipement_id, s: ot.symptome_code, ots: r.causes.flatMap((c) => c.ots) };
              }
              return null;
            }""")
            self.assertIsNotNone(cas)
            page.evaluate("""(ots) => Donnees.modifier('ordres_travail', (lignes) => {
              lignes.forEach((l) => { if (ots.includes(l.id)) { l.cause_code = ''; l.cause_precision = 'Câble pincé'; } });
            }, { action: 'test' })""", cas["ots"])
            resultat = page.evaluate("([eq, s]) => CausesFrequentes.calculer(eq, s)", [cas["eq"], cas["s"]])
            self.assertIn("Autre : Câble pincé", [c["libelle"] for c in resultat["causes"]])
            # Pareto des causes : les causes précisées regroupées sous « Autre (précisé) », code vide, avant « sans code »
            causes = page.evaluate("Indicateurs.causes(Indicateurs.periode('12-mois', Donnees.aujourdhui()), {})"
                                   ".map((l) => [l.code, l.libelle, l.nombre])")
            libelles = [c[1] for c in causes]
            self.assertIn("Autre (précisé)", libelles)
            autre = causes[libelles.index("Autre (précisé)")]
            self.assertEqual(autre[0], "")
            self.assertTrue(all(c[0] for c in causes[:libelles.index("Autre (précisé)")]))


class TestCloture(CasCodes):

    def test_cloture_autre_preciser_enregistre_puis_reaffiche_et_preventif_sans_cause(self):
        with ServeurPrevo() as serveur_prevo:
            self.ouvrir(serveur_prevo, "#/ot")
            page = self.page
            self.fiche_compte_rendu(OT_EN_COURS)
            precision = "#form-compte-rendu [name=cause_precision]"
            self.assertFalse(page.is_visible(precision))
            autre = page.evaluate("Ordres.CODE_AUTRE")
            options = page.eval_on_selector_all("#form-compte-rendu [name=cause_code] option", "o => o.map(x => x.textContent)")
            self.assertEqual(options[1], "Autre (préciser)")            # L20 : « Autre » en tête, après « — »
            page.select_option("#form-compte-rendu [name=cause_code]", autre)
            self.assertTrue(page.is_visible(precision))
            self.assertIsNotNone(page.get_attribute(precision, "data-dictee"))
            page.fill(precision, "Courroie sortie de sa gorge")
            page.select_option("#form-compte-rendu [name=remede_code]", autre)
            page.fill("#form-compte-rendu [name=remede_precision]", "Courroie remise et retendue")
            page.click("#form-compte-rendu button[type=submit]")
            page.wait_for_function("Donnees.trouver('ordres_travail', %r).cause_precision === 'Courroie sortie de sa gorge'" % OT_EN_COURS)
            ligne = next(o for o in lire_csv(serveur_prevo.dossier, "ordres_travail.csv") if o["id"] == OT_EN_COURS)
            self.assertEqual((ligne["cause_code"], ligne["cause_precision"], ligne["remede_code"], ligne["remede_precision"]),
                             ("", "Courroie sortie de sa gorge", "", "Courroie remise et retendue"))
            # Rouvrir : « Autre (préciser) » et son texte ; la clôture refusée ne cite plus la cause
            page.reload()
            attendre_pret(page)
            self.fiche_compte_rendu(OT_EN_COURS)
            self.assertEqual(page.input_value("#form-compte-rendu [name=cause_code]"), autre)
            self.assertTrue(page.is_visible(precision))
            self.assertEqual(page.input_value(precision), "Courroie sortie de sa gorge")
            # L20 : la fenêtre de clôture unique dit ce qui manque encore : ni la cause ni le remède.
            page.click("#form-compte-rendu button[data-action='transition'][data-cible='Clôturé techniquement']")
            page.wait_for_selector("dialog .ot-cloture-manques .alerte")
            message = page.inner_text("dialog .ot-cloture-manques")
            self.assertNotIn("code cause", message)
            self.assertNotIn("code remède", message)
            page.click("dialog .fenetre-actions .btn-fantome")
            page.wait_for_selector("dialog", state="detached")
            # Choisir un vrai code efface la précision
            page.select_option("#form-compte-rendu [name=cause_code]", "C01")
            self.assertFalse(page.is_visible(precision))
            self.assertEqual(page.input_value(precision), "")
            # OT préventif : pas de champ cause (remède proposé, facultatif)
            self.fiche_compte_rendu(OT_PREVENTIF)
            self.assertEqual(page.locator("#form-compte-rendu [name=cause_code]").count(), 0)
            self.assertEqual(page.locator("#form-compte-rendu [name=remede_code]").count(), 1)
            self.assertIn("Facultatif", page.inner_text("#form-compte-rendu .ot-code[data-code='remede']"))


class TestListeVide(CasCodes):

    def test_liste_vide_cloture_non_bloquee_message_puis_liste_de_depart_et_suppression(self):
        dossier = copie_demo_sans_codes()
        self.addCleanup(shutil.rmtree, dossier, True)
        with ServeurPrevo(source=dossier / "donnees") as serveur_prevo:
            self.ouvrir(serveur_prevo, "#/ot")
            page = self.page
            self.assertEqual(page.evaluate(VERIFIER, [dict(COMPLET, type="correctif différé"), [{"heures": "1"}]]), [])
            self.fiche_compte_rendu(OT_EN_COURS)
            note = page.inner_text("#form-compte-rendu .ot-code[data-code='cause'] .ot-codes-vides")
            self.assertIn("Aucun code cause n'existe encore", note)
            self.assertIn("Paramètres › Codes de défaillance", note)
            self.assertEqual(page.get_attribute("#form-compte-rendu .ot-code[data-code='cause'] .ot-codes-vides a", "href"), "#/parametres")
            options = page.eval_on_selector_all("#form-compte-rendu [name=cause_code] option", "o => o.map(x => x.textContent)")
            self.assertEqual(options, ["—", "Autre (préciser)"])
            # Paramètres : la liste de départ, puis suppression d'un code qu'aucune fiche ne cite
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("#carte-codes .codes-zone-depart button")
            page.click("#carte-codes .codes-zone-depart button")
            page.wait_for_function("Donnees.lignes('codes_defaillance').length === %d" % len(serveur.codes_de_depart("fr")))
            page.wait_for_function("!document.querySelector('#carte-codes .codes-zone-depart button')")
            codes = lire_csv(serveur_prevo.dossier, "codes_defaillance.csv")
            self.assertEqual(len(codes), len(serveur.codes_de_depart("fr")))
            usure = next(c for c in codes if c["code"] == "C-USURE")
            page.click("[data-code-supprimer='%s']" % usure["id"])
            page.click("dialog .fenetre-actions .btn-danger")
            page.wait_for_function("!Donnees.lignes('codes_defaillance').some((c) => c.code === 'C-USURE')")
            self.assertNotIn("C-USURE", [c["code"] for c in lire_csv(serveur_prevo.dossier, "codes_defaillance.csv")])
            # Un code cité par un OT ne se supprime pas
            refus = page.evaluate("""async () => {
              await Donnees.modifier('ordres_travail', (l) => { l[0].cause_code = 'C-MECA'; }, { action: 'test' });
              try { await Parametres.supprimerCode(Donnees.lignes('codes_defaillance').find((c) => c.code === 'C-MECA').id); return ''; }
              catch (e) { return e.message; }
            }""")
            self.assertIn("C-MECA", refus)
            # Rien de plus à ajouter : la liste de départ n'ajoute que les codes absents (C-USURE revient)
            self.assertEqual(page.evaluate("Ordres.ajouterListeDeDepart()"), 1)
            self.assertEqual(page.evaluate("Ordres.ajouterListeDeDepart()"), 0)


class TestBaseVide(CasCodes):

    def test_base_vide_du_navigateur_recoit_la_liste_dans_la_langue_choisie(self):
        self.autoriser_erreur(ERREUR_CSV_ABSENT)
        page = self.page
        with ServeurPrevo(source=None) as serveur_prevo:
            page.goto(serveur_prevo.url + "/")
            page.wait_for_selector("#btn-base-vide", state="visible")
            page.select_option("#base-vide-langue", "pt-PT")
            page.click("#btn-base-vide")
            fichier = serveur_prevo.dossier / "codes_defaillance.csv"
            limite = time.time() + 15
            while not fichier.exists() and time.time() < limite:
                time.sleep(0.2)
            lignes = lire_csv(serveur_prevo.dossier, "codes_defaillance.csv")
            self.assertEqual([(l["id"], l["famille"], l["code"], l["libelle"]) for l in lignes],
                             [tuple(l) for l in serveur.codes_de_depart("pt-PT")])


if __name__ == "__main__":
    unittest.main()
