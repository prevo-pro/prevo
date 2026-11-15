"""Rôle « Direction » en lecture seule (Prévo 2.2, lot 1 ergonomie, correction A7 ; tâche T520 ; ARCHITECTURE.md §22.5).

Le patron lit le tableau de bord, les rapports mensuels et l'historique, coûts compris, et n'écrit rien. Les cases de
ROLES_PAR_ROUTE (une colonne « direction ») sont jouées par tests/test_acces_roles.py ; ici, ce qui est propre au rôle :

    documents      rapport mensuel figé lu (T478 le réserve au responsable : la Direction le voit), justificatif
                   d'habilitation et document de contrat refusés (D196, par colonne et par nom), avec la phrase qui
                   dit quoi faire ; le demandeur garde son refus (le droit ne change pas) ;
    navigation     un lien de document refusé ouvert dans le navigateur (Sec-Fetch-Mode « navigate ») mène à
                   /#/document-ferme (303), un appel de l'application garde son 403 JSON ; T527 : ouvert sans session,
                   il mène à /#/document/<nom> (303, nom valide seulement : jamais une autre adresse), un appel de
                   l'application et un appareil refusé gardent leur 401 JSON ; dans le navigateur, l'écran de
                   connexion le dit, puis le document s'ouvre (refusé au rôle : la page « document fermé ») ;
    lecture        aucune colonne cachée (taux horaire, prix, coût d'arrêt : les octets du disque), ni habilitations
                   ni wiki ; /api/versions réduit à ses tables ; /api/info réduit au port ;
    écriture       PUT, ajout, document, sauvegarde, IA : 403 au message « lecture seule » ; rien n'est écrit ;
    comptes        un compte Direction n'a pas de technicien lié (création et modification : 400) ; il ne compte pas
                   comme responsable (tests/test_acces_roles.py, dernier responsable gardé) ;
    assistant      étape « compte » : accès facultatif de la direction créé avec un mot de passe provisoire rendu une
                   fois, refusé avant toute écriture s'il est mal formé ou si c'est la personne du responsable ;
    navigateur     écrans de la Direction : menu réduit, aucun bouton d'écriture, écran interdit → page lisible.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_acces_direction.py" -v
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import commun
from commun import attendre_pret
import test_acces_roles as roles
import test_installation_api as installation

serveur = roles.serveur
RAPPORT = "rapport-mensuel-2026-09.html"
JUSTIFICATIF = "justif-essai.pdf"
JUSTIFICATIF_PAR_NOM = "20261020-101500-habilitation-TEC-0001-essai.pdf"
CONTRAT_PAR_NOM = "contrat-CTP-0001-essai.pdf"
HTML = b"<!doctype html><title>Rapport</title><p>Essai</p>"
LECTURE_SEULE = "acces.direction_lecture_seule"


def setUpModule():
    roles.setUpModule()          # comptes de test_acces_roles (dont claire.dupont, direction)


def ecrire_parametre(dossier, cle, valeur):
    chemin = dossier / "parametres.csv"
    entete, lignes = roles.lire_tableau(chemin.read_bytes())
    lignes = [ligne for ligne in lignes if ligne[entete.index("cle")] != cle]
    nouvelle = [""] * len(entete)
    nouvelle[entete.index("cle")], nouvelle[entete.index("valeur")] = cle, valeur
    chemin.write_bytes(roles.ecrire_tableau(entete, lignes + [nouvelle]))


class CasDirection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        roles.lancer_serveur_comptes(cls)
        dossier = cls.serveur.dossier
        documents = dossier / "documents"
        (documents / RAPPORT).write_bytes(HTML)
        for nom in (JUSTIFICATIF, JUSTIFICATIF_PAR_NOM, CONTRAT_PAR_NOM):
            (documents / nom).write_bytes(roles.PDF)
        ecrire_parametre(dossier, "rapports_mensuels", RAPPORT)
        chemin = dossier / "habilitations.csv"
        entete, lignes = roles.lire_tableau(chemin.read_bytes())
        lignes[0][entete.index("justificatif")] = JUSTIFICATIF
        chemin.write_bytes(roles.ecrire_tableau(entete, lignes))

    def requete(self, methode, chemin, corps=None, role="direction", **options):
        return self.client.requete(methode, chemin, corps, cookie=self.cookies[role], **options)


class TestDocumentsDeLaDirection(CasDirection):

    def test_rapport_fige_lu_documents_reserves_refuses_avec_la_phrase_qui_dit_quoi_faire(self):
        lu = self.requete("GET", "/api/documents/" + RAPPORT)
        self.assertEqual((lu.statut, lu.octets), (200, HTML))
        self.assertEqual(self.requete("GET", "/api/documents/" + roles.DOCUMENT_EQUIPEMENT).statut, 200)
        for nom in (JUSTIFICATIF, JUSTIFICATIF_PAR_NOM, CONTRAT_PAR_NOM, JUSTIFICATIF.upper()):
            with self.subTest(nom=nom):
                refus = self.requete("GET", "/api/documents/" + nom)
                self.assertEqual(refus.statut, 403, refus.octets)
                self.assertEqual(refus.json(), {"erreur": serveur.MESSAGE_DOCUMENT_FERME,
                                                "erreur_code": "acces.document_ferme"})
                self.assertIn("demandez-lui", refus.json()["erreur"])
                self.assertNotIn("demandeur", refus.json()["erreur"])
        # Le droit des autres rôles ne change pas : rapport figé réservé au responsable (T478).
        for role in ("demandeur", "technicien"):
            with self.subTest(role=role):
                refus = self.requete("GET", "/api/documents/" + RAPPORT, role=role)
                self.assertEqual((refus.statut, refus.json()["erreur_code"]), (403, "acces.document_ferme"))
        self.assertEqual(self.requete("GET", "/api/documents/" + RAPPORT, role="responsable").statut, 200)

    def test_lien_ouvert_dans_le_navigateur_mene_a_une_page_de_prevo(self):
        navigation = {"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document",
                      "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
        refus = self.requete("GET", "/api/documents/" + RAPPORT, role="demandeur", entetes=navigation)
        self.assertEqual((refus.statut, refus.entetes.get("location"), refus.octets), (303, "/#/document-ferme", b""))
        sans_sec_fetch = self.requete("GET", "/api/documents/" + JUSTIFICATIF, entetes={"Accept": "text/html"})
        self.assertEqual(sans_sec_fetch.statut, 303)
        # Un appel de l'application (fetch) garde le 403 JSON ; un document permis s'ouvre.
        appel = self.requete("GET", "/api/documents/" + RAPPORT, role="demandeur",
                             entetes={"Sec-Fetch-Mode": "cors", "Accept": "*/*"})
        self.assertEqual((appel.statut, appel.json()["erreur_code"]), (403, "acces.document_ferme"))
        self.assertEqual(self.requete("GET", "/api/documents/" + RAPPORT, entetes=navigation).statut, 200)
        # Une autre adresse refusée ne change pas (table fermée : 403 JSON).
        self.assertEqual(self.requete("GET", "/api/csv/habilitations", entetes=navigation).statut, 403)

    def test_lien_ouvert_sans_session_mene_a_la_connexion_avec_le_document_en_retour(self):
        navigation = {"Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document",
                      "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
        sans_session = lambda chemin, entetes: self.client.requete("GET", chemin, entetes=entetes)
        for nom in (RAPPORT, JUSTIFICATIF, JUSTIFICATIF_PAR_NOM, "absent-2026.pdf"):
            with self.subTest(nom=nom):
                renvoi = sans_session("/api/documents/" + nom, navigation)
                self.assertEqual((renvoi.statut, renvoi.entetes.get("location"), renvoi.octets),
                                 (303, "/#/document/" + nom, b""))
        self.assertEqual(sans_session("/api/documents/" + RAPPORT + "?v=1", {"Accept": "text/html"}).entetes.get("location"),
                         "/#/document/" + RAPPORT)
        # Appel de l'application (X-Prevo, fetch) : 401 JSON, comme avant.
        for entetes in ({"X-Prevo": "1", "Accept": "text/html"}, {"Sec-Fetch-Mode": "cors", "Accept": "*/*"}, {}):
            with self.subTest(entetes=entetes):
                appel = sans_session("/api/documents/" + RAPPORT, entetes)
                self.assertEqual((appel.statut, appel.json()["erreur_code"]), (401, "sessions.absente"))
                self.assertIsNone(appel.entetes.get("location"))
        # Aucune autre adresse de retour : nom invalide, encodé, cible externe, hors documents → 401 JSON, sans renvoi.
        for chemin in ("/api/documents/a..b.pdf", "/api/documents/%2e%2e%2fcomptes.json", "/api/documents/..",
                       "/api/documents/http:%2F%2Fexemple.invalid%2Fx.pdf", "/api/documents/x.pdf%23https://exemple.invalid",
                       "/api/documents/", "/api/documents/-x.pdf", "/api/csv/ordres_travail", "/api/session"):
            with self.subTest(chemin=chemin):
                refus = sans_session(chemin, navigation)
                self.assertNotEqual(refus.statut, 303, refus.entetes.get("location"))
                self.assertIsNone(refus.entetes.get("location"))
        for chemin in ("//exemple.invalid/x.pdf", "https://exemple.invalid/x.pdf", "/api/documents/x.pdf/../../a",
                       "/api/csv/x.pdf", "/api/documents/a b.pdf", "/api/documents/%41.pdf"):
            with self.subTest(retour=chemin):
                self.assertIsNone(serveur.retour_vers_document(chemin))
        self.assertEqual(serveur.retour_vers_document("/api/documents/" + JUSTIFICATIF_PAR_NOM + "?x=1#y"),
                         "/#/document/" + JUSTIFICATIF_PAR_NOM)
        # Un appareil refusé garde son 401, son cookie effacé et son message (écran d'invitation, D125).
        appareil = self.client.requete("GET", "/api/documents/" + RAPPORT, cookie="appareil=" + "A" * 43,
                                       entetes=navigation)
        self.assertEqual((appareil.statut, appareil.json().get("appareil_refuse")), (401, True))
        self.assertIn("Max-Age=0", appareil.entetes.get("set-cookie", ""))


class TestLectureEtEcrituresDeLaDirection(CasDirection):

    def test_couts_compris_ni_habilitations_ni_wiki_versions_et_info_reduites(self):
        for table in ("techniciens", "articles", "achats", "equipements", "contrats_prestataires", "ordres_travail",
                      "ot_temps", "mouvements_stock", "parametres"):     # journal : fermé (R2, T556)
            with self.subTest(table=table):
                lu = self.requete("GET", "/api/csv/" + table)
                self.assertEqual(lu.statut, 200, lu.octets[:200])
                disque = (self.serveur.dossier / (table + ".csv")).read_bytes()
                self.assertEqual(lu.octets, disque)
                self.assertEqual(lu.entetes["x-version"], roles.version_de(disque))
        self.assertIn(b"taux_horaire", self.requete("GET", "/api/csv/techniciens").octets)
        for table in sorted(roles.TOUTES_LES_TABLES - roles.TABLES_DE_LA_DIRECTION):
            with self.subTest(table=table):
                self.assertTrue(self.requete("GET", "/api/csv/" + table).refus_de_role())
        versions = self.requete("GET", "/api/versions").json()["tables"]
        # R2 (T556) : le journal, fermé, reste suivi (version voilée) pour ses extraits (GET /api/journal/extraits).
        self.assertEqual(set(versions), set(roles.TABLES_DE_LA_DIRECTION) | {"journal"})
        self.assertNotEqual(versions["journal"]["version"], roles.version_de((self.serveur.dossier / "journal.csv").read_bytes()))
        self.assertEqual(self.requete("GET", "/api/info").json(), {"port": self.serveur.port})
        self.assertIn("adresses_reseau", self.requete("GET", "/api/info", role="responsable").json())

    def test_aucune_ecriture_et_rien_n_est_ecrit(self):
        avant = {chemin.name: chemin.read_bytes() for chemin in self.serveur.dossier.glob("*.csv")}
        documents = sorted(chemin.name for chemin in (self.serveur.dossier / "documents").iterdir())
        for methode, chemin, corps in (
                ("PUT", "/api/csv/parametres", roles.BOM + b"cle;valeur\r\n"),
                ("PUT", "/api/csv/ordres_travail", roles.BOM + b"id\r\n"),
                ("POST", "/api/csv/journal/ajout", b"id;date\r\n"),
                ("POST", "/api/csv/demandes/ajout", b"id\r\n"),
                ("PUT", "/api/documents/photo-20261026-101530-WXYZ.jpg", roles.JPEG),
                ("PUT", "/api/documents/rapport-mensuel-2026-10.html", HTML)):
            with self.subTest(methode=methode, chemin=chemin):
                refus = self.requete(methode, chemin, corps)
                self.assertEqual((refus.statut, refus.json()["erreur_code"]), (403, LECTURE_SEULE), refus.octets)
        for methode, chemin, corps in (("POST", "/api/sauvegarde", {"motif": "avant-import"}),
                                       ("GET", "/api/sauvegardes", None), ("GET", "/api/acces/comptes", None),
                                       ("GET", "/api/acces/journal", None), ("GET", "/api/acces/invitations", None),
                                       ("POST", "/api/restauration", {"sauvegarde": self.sauvegarde}),
                                       ("GET", "/api/installation/etat", None)):
            with self.subTest(methode=methode, chemin=chemin):
                refus = self.requete(methode, chemin, corps)
                self.assertEqual((refus.statut, refus.json()["erreur_code"]), (403, "acces.reserve_au_responsable"))
        for methode, chemin, corps in (("POST", "/api/ia", {"chemin": "api/tags", "methode": "GET"}),
                                       ("GET", "/api/ia/reglages", None)):
            with self.subTest(methode=methode, chemin=chemin):
                self.assertTrue(self.requete(methode, chemin, corps).refus_de_role())
        self.assertEqual({chemin.name: chemin.read_bytes() for chemin in self.serveur.dossier.glob("*.csv")}, avant)
        self.assertEqual(sorted(chemin.name for chemin in (self.serveur.dossier / "documents").iterdir()), documents)
        # Ce que tout compte peut : sa session, sa langue.
        session = self.requete("GET", "/api/session").json()["session"]
        self.assertEqual((session["identifiant"], session["role"], session["technicien_id"]),
                         ("claire.dupont", "direction", ""))
        langue = self.requete("POST", "/api/mot-de-passe", {"langue": "en"})
        self.assertEqual(langue.statut, 200, langue.octets)


class TestComptesDirection(CasDirection):

    def test_aucun_technicien_lie(self):
        refus = self.requete("POST", "/api/acces/comptes", {"prenom": "Henri", "nom": "Patron", "role": "direction",
                                                            "technicien_id": "TEC-0002"}, role="responsable")
        self.assertEqual((refus.statut, refus.json()["erreur_code"]), (400, "comptes.direction_sans_technicien"))
        cree = self.requete("POST", "/api/acces/comptes", {"prenom": "Henri", "nom": "Patron", "role": "direction"},
                            role="responsable")
        self.assertEqual(cree.statut, 200, cree.octets)
        self.assertEqual((cree.json()["compte"]["role"], cree.json()["compte"]["technicien_id"]), ("direction", ""))
        entree = self.client.connecter_brut("henri.patron", cree.json()["mot_de_passe_provisoire"])
        self.assertEqual((entree.statut, entree.json()["session"]["role"]), (200, "direction"))
        # Technicien passé en Direction en gardant sa fiche liée : refusé ; sans elle : permis.
        garde = self.requete("POST", "/api/acces/comptes/julien.moreau", {"action": "modifier", "role": "direction"},
                             role="responsable")
        self.assertEqual((garde.statut, garde.json()["erreur_code"]), (400, "comptes.direction_sans_technicien"))
        passe = self.requete("POST", "/api/acces/comptes/paul.essai", {"action": "modifier", "role": "direction"},
                             role="responsable")
        self.assertEqual((passe.statut, passe.json()["compte"]["role"]), (200, "direction"))
        inconnu = self.requete("POST", "/api/acces/comptes", {"prenom": "Zoe", "role": "patron"}, role="responsable")
        self.assertEqual(inconnu.statut, 400)
        self.assertIn("direction", inconnu.json()["erreur"])


class TestAssistantDirection(installation.CasAssistant):

    def preparer(self):
        client, instance = self.lancer(source=commun.DOSSIER_DEMO)
        self.ok(client.post("situation", {"situation": "equipe"}))
        self.ok(client.post("portee", {"portee": "atelier"}))
        return client, instance

    def comptes(self, instance):
        chemin = Path(instance.config.dossier_donnees, "acces", "comptes.json")
        return json.loads(chemin.read_text(encoding="utf-8"))["comptes"] if chemin.exists() else []

    def test_acces_de_la_direction_cree_avec_un_mot_de_passe_provisoire(self):
        client, instance = self.preparer()
        reponse = self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand",
                                                 "mot_de_passe": installation.MOT_DE_PASSE,
                                                 "direction": {"prenom": "Laurent", "nom": "Girard"}}))
        self.assertEqual(reponse["compte"]["role"], "responsable")
        direction = reponse["direction"]
        self.assertEqual((direction["compte"]["identifiant"], direction["compte"]["role"],
                          direction["compte"]["technicien_id"], direction["compte"]["a_changer"]),
                         ("laurent.girard", "direction", "", True))
        provisoire = direction["mot_de_passe_provisoire"]
        self.assertEqual(len(provisoire), 16)
        self.assertEqual([(c["identifiant"], c["role"]) for c in self.comptes(instance)],
                         [("nicolas.briand", "responsable"), ("laurent.girard", "direction")])
        for fichier in Path(instance.config.dossier_donnees).rglob("*"):
            if fichier.is_file():
                self.assertNotIn(provisoire.encode("utf-8"), fichier.read_bytes(), fichier.name)

    def test_acces_de_la_direction_refuse_avant_toute_ecriture(self):
        client, instance = self.preparer()
        for direction, code in (({"prenom": ""}, "installation.direction_prenom"),
                                ("Laurent", "installation.direction_forme"),
                                ({"prenom": 3}, "installation.direction_forme"),
                                ({"prenom": "nicolas", "nom": "BRIAND"}, "installation.direction_meme_personne")):
            with self.subTest(direction=direction):
                refus = client.post("compte", {"prenom": "Nicolas", "nom": "Briand",
                                               "mot_de_passe": installation.MOT_DE_PASSE, "direction": direction})
                self.assertEqual((refus.statut, refus.json()["erreur_code"]), (400, code), refus.octets)
                self.assertEqual(self.comptes(instance), [])
        reponse = self.ok(client.post("compte", {"prenom": "Nicolas", "nom": "Briand",
                                                 "mot_de_passe": installation.MOT_DE_PASSE}))
        self.assertNotIn("direction", reponse)


class TestNavigateurDirection(roles.CasNavigateurComptes):
    """Le patron connecté : menu réduit, écrans en lecture, aucun bouton d'écriture, écran interdit → page lisible."""

    BOUTONS_D_ECRITURE = ("#parc-activite", 'a[href$="/modifier"]', 'a[href^="#/ot/nouveau"]', 'a[href^="#/di/nouvelle"]',
                          "#ot-priorite", "[data-action=transition]", ".rapports-formulaire",
                          "[data-action=recalculer]", ".parc-saisir-releve", 'a[href^="#/equipement/nouveau"]')

    def ouvrir(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def sans_bouton_d_ecriture(self):
        for selecteur in self.BOUTONS_D_ECRITURE:
            self.assertEqual(self.page.locator("#contenu " + selecteur).count(), 0, selecteur)

    def test_ecrans_de_la_direction_en_lecture_seule(self):
        self.poser_session("direction", "direction", "Claire Dupont")
        # Tables fermées à la Direction : 403, vues comme absentes (stockage-serveur.js) ; ces refus-là seulement.
        fermees = sorted(roles.TOUTES_LES_TABLES - roles.TABLES_DE_LA_DIRECTION)
        self.autoriser_erreur(re.compile(r"status of 403 .*/api/csv/(?:%s):" % "|".join(fermees)))
        page = self.page
        page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil.type"), "direction")
        menu = page.evaluate("Array.from(document.querySelectorAll('#menu a')).map((a) => a.dataset.ecran)")
        self.assertEqual(menu, ["accueil", "liste-ot", "parc", "indicateurs", "apropos"])
        self.ouvrir("#/accueil", ".accueil-direction")
        self.sans_bouton_d_ecriture()
        self.ouvrir("#/indicateurs", ".indicateurs-onglets")
        self.ouvrir("#/indicateurs?onglet=rapports", ".rapports-liste")
        self.sans_bouton_d_ecriture()
        self.assertGreaterEqual(page.locator(".rapports-bilan").count(), 1)
        self.ouvrir("#/parc", "#parc-arbre")
        self.sans_bouton_d_ecriture()
        self.ouvrir("#/equipement/EQ-0001", ".parc-complements")
        self.sans_bouton_d_ecriture()
        self.ouvrir("#/ot", ".ot-zone-tableau, .liste-ot, #contenu table")
        self.sans_bouton_d_ecriture()
        self.ouvrir("#/ot/" + roles.OT_EN_COURS, ".ot-entete")
        self.sans_bouton_d_ecriture()
        # T528 : sur la fiche d'un OT (en cours, puis clos), les onglets montrent les informations en texte, sans
        # champ grisé, sans bouton dans un formulaire, sans la mention « Lecture seule »
        clos = page.evaluate("() => Donnees.lignes('ordres_travail').find((o) => o.statut === 'Clôturé administrativement'"
                             " && o.compte_rendu).id")
        for ot_id in (roles.OT_EN_COURS, clos):
            self.ouvrir("#/ot/" + ot_id, ".ot-entete")
            for onglet in ("preparation", "execution", "compte-rendu"):
                with self.subTest(ot=ot_id, onglet=onglet):
                    page.click(".onglet[data-onglet='%s']" % onglet)
                    page.wait_for_selector(".ot-onglets .panneau-onglet[data-onglet=%s] fieldset.ot-lecture" % onglet)
                    champs = ".ot-onglets fieldset :is(input:not([type=hidden]), select, textarea)"
                    self.assertEqual(page.locator(champs).count(), 0)
                    self.assertEqual(page.locator(".ot-onglets fieldset[disabled], .ot-onglets form button").count(), 0)
                    self.assertNotIn("Lecture seule", page.inner_text(".ot-onglets"))
        compte_rendu = page.evaluate("id => Donnees.trouver('ordres_travail', id).compte_rendu", clos)
        self.assertIn(compte_rendu.splitlines()[0].strip(), page.inner_text("#form-compte-rendu .ot-valeur-texte"))
        for route in ("#/parametres", "#/equipe/acces", "#/di/nouvelle", "#/import"):
            with self.subTest(route=route):
                self.ouvrir(route, ".ecran-ferme")
                self.assertIn("Direction", page.inner_text("#contenu"))
        self.ouvrir("#/document-ferme", ".document-ferme")
        self.assertIn("responsable", page.inner_text("#contenu"))
        self.assertEqual([r for r in self.reponses if r[0] in ("PUT", "POST")], [])
        for methode, adresse, statut in self.reponses:
            if statut >= 400:
                self.assertTrue(statut == 403 and adresse.rsplit("/api/csv/", 1)[-1] in fermees, (methode, adresse, statut))


class TestNavigateurLienSansSession(roles.CasNavigateurComptes):
    """T527 (A7) : le lien d'un document ouvert sans session (le patron, sa session finie) : l'écran de connexion de
    Prévo le dit, puis le document s'ouvre avec les droits du compte connecté ; refusé au rôle : « document fermé »."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        (cls.serveur.dossier / "documents" / RAPPORT).write_bytes(HTML)
        ecrire_parametre(cls.serveur.dossier, "rapports_mensuels", RAPPORT)

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(re.compile(r"status of 401 .*/api/"))       # la sonde d'App, sans session

    def ouvrir_le_lien(self):
        page = self.page
        page.goto(self.serveur.url + "/api/documents/" + RAPPORT)
        page.wait_for_selector("#connexion-document", state="visible")
        self.assertTrue(page.url.endswith("/#/document/" + RAPPORT), page.url)
        self.assertIn("Connectez-vous pour ouvrir ce document", page.inner_text("#connexion-alertes"))
        self.assertEqual(page.get_attribute("#connexion-document", "role"), "status")

    def connecter(self, identifiant):
        self.page.fill("#connexion-identifiant", identifiant)
        self.page.fill("#connexion-mot-de-passe", roles.MOTS_DE_PASSE[identifiant])
        self.page.click("#connexion-valider")

    def test_patron_connecte_le_document_s_ouvre(self):
        page = self.page
        fermees = sorted(roles.TOUTES_LES_TABLES - roles.TABLES_DE_LA_DIRECTION)
        self.autoriser_erreur(re.compile(r"status of 403 .*/api/csv/(?:%s):" % "|".join(fermees)))
        self.ouvrir_le_lien()
        self.connecter("claire.dupont")
        page.wait_for_url(self.serveur.url + "/api/documents/" + RAPPORT)
        self.assertIn("Essai", page.inner_text("body"))
        # Le retour ne sert que des noms valides de ce serveur : une autre cible reste dans Prévo, sans rien ouvrir.
        page.goto(self.serveur.url + "/#/accueil")
        attendre_pret(page)
        self.assertEqual(page.evaluate("""(nom) => ['#/document/https://exemple.invalid/x.pdf', '#/document//exemple.invalid',
            '#/document/..%2Fcsv%2Fordres_travail', '#/document/a..b.pdf', '#/document/x.pdf?y', '#/document/',
            '#/documentx/r.pdf', '#/document/' + nom].map((h) => Connexion.documentDeLaRoute(h))""", RAPPORT),
                         [""] * 7 + [RAPPORT])
        page.evaluate("() => { location.hash = '#/document/https:%2F%2Fexemple.invalid%2Fx.pdf'; }")
        page.wait_for_selector("#contenu .document-ferme")
        self.assertIn("ne mène pas à un document", page.inner_text("#contenu"))
        self.assertTrue(page.url.startswith(self.serveur.url + "/"), page.url)

    def test_document_refuse_au_role_toujours_la_page_document_ferme(self):
        page = self.page
        fermees = sorted(roles.TOUTES_LES_TABLES - roles.TABLES_DU_DEMANDEUR)
        self.autoriser_erreur(re.compile(r"status of 403 .*/api/csv/(?:%s):" % "|".join(fermees)))
        self.ouvrir_le_lien()
        self.connecter("lea.martin")
        page.wait_for_selector("#contenu .document-ferme")
        self.assertTrue(page.url.endswith("/#/document-ferme"), page.url)
        self.assertIn("responsable", page.inner_text("#contenu"))
        self.assertNotIn("Essai", page.inner_text("body"))


class TestNavigateurSansComptes(commun.CasNavigateur):
    """Mode sans comptes (« ce PC ») : le profil Direction se choisit sur le poste ; l'écran fait foi."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = commun.ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def test_profil_direction_choisi_sur_le_poste(self):
        page = self.page
        page.goto(self.serveur.url + "/#/accueil")
        page.wait_for_selector("#profil-direction")
        self.assertIn("Lecture seule", page.inner_text("#profil-direction"))
        page.click("#profil-direction")
        attendre_pret(page)
        self.assertEqual(page.evaluate("App.profil.type"), "direction")
        menu = page.evaluate("Array.from(document.querySelectorAll('#menu a')).map((a) => a.dataset.ecran)")
        self.assertEqual(menu, ["accueil", "liste-ot", "parc", "indicateurs", "apropos"])
        page.wait_for_selector(".accueil-direction")
        page.evaluate("() => { location.hash = '#/parametres'; }")
        page.wait_for_selector(".ecran-ferme")
        page.evaluate("() => { location.hash = '#/equipement/EQ-0001'; }")
        page.wait_for_selector(".parc-lecture-seule")
        self.assertEqual(page.locator("#contenu .parc-signaler, #contenu #parc-activite").count(), 0)


if __name__ == "__main__":
    unittest.main()
