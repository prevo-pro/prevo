"""Lot 2 ergonomie, L06 (T533) : le responsable est aussi technicien (défaut 28 du retest).

Ce qui est vérifié :
    fiche        relier_fiche_du_responsable : un compte responsable actif sans fiche reçoit une fiche de technicien
                 (TEC-nnnn suivant, son prénom et son nom, actif) liée à son compte ; une fiche au même prénom et nom
                 est reprise (aucun doublon), sauf si un autre compte y est déjà lié ; idempotent (rien de réécrit au
                 second appel) ; une fiche existante n'est jamais modifiée ; Direction, technicien, demandeur et
                 compte désactivé : rien ;
    ouverture    fiche_a_l_ouverture (bases d'avant) : la session d'un responsable actif sans fiche la reçoit, une
                 fois ; rien pour un appareil, un autre rôle, ni en lecture seule (D169) ;
    serveur      rien au démarrage (techniciens.csv et comptes.json à l'octet) ; à la connexion du responsable, sa
                 fiche ; GET /api/session relie aussi une session ouverte avant (« rester connecté ») ;
                 POST /api/acces/comptes : un responsable créé reçoit sa fiche, la Direction non ; un demandeur devenu
                 responsable la reçoit ; un responsable devenu Direction la quitte ;
    écran        (navigateur) le responsable connecté garde son accueil de responsable, se voit proposer « Je prends
                 cet OT » et met l'OT à son nom (sa fiche) ; Équipe › Accès accepte une fiche pour un responsable et la
                 refuse pour la Direction.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_responsable_technicien.py" -v
"""
import csv
import importlib.util
import io
import json
import shutil
import tempfile
import unittest
import urllib.request
from pathlib import Path

import commun
from commun import RACINE, CasNavigateur, ServeurPrevo, attendre_pret

SCRIPT = RACINE / "serveur.py"
MOT_DE_PASSE = "une phrase de passe assez longue"


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_l06", SCRIPT)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()


def techniciens(dossier):
    chemin = Path(dossier) / "techniciens.csv"
    return list(csv.DictReader(io.StringIO(chemin.read_text(encoding="utf-8-sig")), delimiter=";"))


class CasFiche(unittest.TestCase):

    def setUp(self):
        self.dossier = Path(tempfile.mkdtemp(prefix="prevo-l06-"))
        self.addCleanup(shutil.rmtree, self.dossier, True)
        self.donnees = self.dossier / "donnees"
        shutil.copytree(commun.DOSSIER_DEMO, self.donnees)
        self.config = serveur.Configuration(str(self.donnees), [])
        serveur.creer_dossiers(self.config)

    def comptes(self):
        return {c["identifiant"]: c for c in
                json.loads((self.donnees / "acces" / "comptes.json").read_text(encoding="utf-8"))["comptes"]}

    def creer(self, prenom, nom, role, technicien_id="", **options):
        return serveur.creer_compte(self.config, prenom, nom, role, MOT_DE_PASSE, technicien_id=technicien_id,
                                    **options)["identifiant"]


class TestFicheDuResponsable(CasFiche):

    def test_fiche_creee_liee_puis_idempotent(self):
        avant = techniciens(self.donnees)
        identifiant = self.creer("Nicolas", "Briand", "responsable")
        compte = serveur.relier_fiche_du_responsable(self.config, identifiant)
        self.assertEqual(compte["technicien_id"], "TEC-0005")
        self.assertNotIn("empreinte", compte)
        apres = techniciens(self.donnees)
        self.assertEqual(apres[:len(avant)], avant)                        # les fiches existantes intactes
        self.assertEqual((apres[-1]["id"], apres[-1]["prenom"], apres[-1]["nom"], apres[-1]["actif"]),
                         ("TEC-0005", "Nicolas", "Briand", "1"))
        self.assertEqual(self.comptes()[identifiant]["technicien_id"], "TEC-0005")
        octets = (self.donnees / "techniciens.csv").read_bytes()
        self.assertEqual(serveur.relier_fiche_du_responsable(self.config, identifiant)["technicien_id"], "TEC-0005")
        self.assertEqual(serveur.fiche_a_l_ouverture(self.config, self.comptes()[identifiant]), "TEC-0005")
        self.assertEqual((self.donnees / "techniciens.csv").read_bytes(), octets)

    def test_fiche_au_meme_nom_reprise_sans_doublon(self):
        karim = next(t for t in techniciens(self.donnees) if t["id"] == "TEC-0002")
        octets = (self.donnees / "techniciens.csv").read_bytes()
        identifiant = self.creer(karim["prenom"].upper(), karim["nom"], "responsable")      # casse ignorée
        self.assertEqual(serveur.relier_fiche_du_responsable(self.config, identifiant)["technicien_id"], "TEC-0002")
        self.assertEqual((self.donnees / "techniciens.csv").read_bytes(), octets)

    def test_fiche_deja_liee_a_un_autre_compte_non_partagee(self):
        karim = next(t for t in techniciens(self.donnees) if t["id"] == "TEC-0002")
        self.creer(karim["prenom"], karim["nom"], "technicien", technicien_id="TEC-0002")
        identifiant = self.creer(karim["prenom"], karim["nom"], "responsable", autre_personne=True)
        self.assertEqual(serveur.relier_fiche_du_responsable(self.config, identifiant)["technicien_id"], "TEC-0005")
        self.assertEqual(len(techniciens(self.donnees)), 5)

    def test_autres_roles_et_compte_desactive_inchanges(self):
        self.creer("Nicolas", "Briand", "responsable")
        direction = self.creer("Claire", "Dumas", "direction")
        demandeur = self.creer("Léa", "Martin", "demandeur")
        technicien = self.creer("Julien", "Moreau", "technicien", technicien_id="TEC-0001")
        ancien = self.creer("Paul", "Ancien", "responsable")
        serveur.modifier_compte(self.config, ancien, actif=False)
        for compte in self.comptes().values():
            serveur.fiche_a_l_ouverture(self.config, compte)
        comptes = self.comptes()
        self.assertEqual({nom: comptes[nom]["technicien_id"] for nom in (direction, demandeur, technicien, ancien)},
                         {direction: "", demandeur: "", technicien: "TEC-0001", ancien: ""})
        self.assertEqual(comptes["nicolas.briand"]["technicien_id"], "TEC-0005")
        self.assertEqual(len(techniciens(self.donnees)), 5)
        for identifiant in (direction, demandeur, technicien, ancien):
            self.assertEqual(serveur.relier_fiche_du_responsable(self.config, identifiant)["technicien_id"],
                             comptes[identifiant]["technicien_id"])
        self.assertEqual(len(techniciens(self.donnees)), 5)

    def test_ouverture_appareil_et_lecture_seule(self):
        identifiant = self.creer("Nicolas", "Briand", "responsable")
        session = dict(self.comptes()[identifiant], cle="x")
        self.assertEqual(serveur.fiche_a_l_ouverture(self.config, None), "")
        self.assertEqual(serveur.fiche_a_l_ouverture(self.config, dict(session, appareil=True)), "")
        self.config.format_donnees = {"plus_recent": True, "base": 99}
        self.assertEqual(serveur.fiche_a_l_ouverture(self.config, session), "")
        self.assertEqual(self.comptes()[identifiant]["technicien_id"], "")
        self.assertEqual(len(techniciens(self.donnees)), 4)
        self.config.format_donnees = None
        self.assertEqual(serveur.fiche_a_l_ouverture(self.config, session), "TEC-0005")
        self.assertEqual(self.comptes()[identifiant]["technicien_id"], "TEC-0005")


class TestServeurReel(unittest.TestCase):
    """Le serveur lancé sur une base d'avant L06 (responsable de COMPTES_DE_TEST sans fiche) et Équipe › Accès."""

    def requete(self, srv, chemin, corps, cookie):
        requete = urllib.request.Request(srv.url + chemin, data=json.dumps(corps).encode("utf-8"), method="POST",
                                         headers={"Content-Type": "application/json; charset=utf-8", "X-Prevo": "1",
                                                  "Cookie": cookie})
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            return json.loads(reponse.read().decode("utf-8"))

    def session(self, srv, cookie):
        requete = urllib.request.Request(srv.url + "/api/session", headers={"Cookie": cookie, "X-Prevo": "1"})
        with urllib.request.urlopen(requete, timeout=10) as reponse:
            return json.loads(reponse.read().decode("utf-8"))["session"]

    def test_connexion_ouverture_et_equipe_acces(self):
        with ServeurPrevo(comptes=True) as srv:
            # Rien au démarrage : la base d'avant reste à l'octet tant que le responsable ne s'est pas connecté.
            demo = (commun.DOSSIER_DEMO / "techniciens.csv").read_bytes()
            self.assertEqual((srv.dossier / "techniciens.csv").read_bytes(), demo)
            technicien = srv.session("technicien")
            self.assertEqual(self.session(srv, technicien)["technicien_id"], "TEC-0001")
            self.assertEqual((srv.dossier / "techniciens.csv").read_bytes(), demo)
            cookie = srv.session("responsable")                                  # connexion : la fiche
            session = self.session(srv, cookie)
            self.assertEqual((session["role"], session["technicien_id"]), ("responsable", "TEC-0005"))
            fiche = next(t for t in techniciens(srv.dossier) if t["id"] == "TEC-0005")
            self.assertEqual((fiche["prenom"], fiche["nom"], fiche["actif"]), ("Nicolas", "Briand", "1"))
            # Session ouverte avant la mise à jour (« rester connecté ») : GET /api/session relie, même fiche.
            chemin = srv.dossier / "acces" / "comptes.json"
            contenu = json.loads(chemin.read_text(encoding="utf-8"))
            next(c for c in contenu["comptes"] if c["identifiant"] == "nicolas.briand")["technicien_id"] = ""
            chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertEqual(self.session(srv, cookie)["technicien_id"], "TEC-0005")
            self.assertEqual(len(techniciens(srv.dossier)), 5)
            # Équipe › Accès : un responsable créé reçoit sa fiche, la Direction non.
            cree = self.requete(srv, "/api/acces/comptes", {"prenom": "Hugo", "nom": "Vasseur",
                                                            "role": "responsable"}, cookie)
            self.assertEqual(cree["compte"]["technicien_id"], "TEC-0006")
            direction = self.requete(srv, "/api/acces/comptes", {"prenom": "Claire", "nom": "Dumas",
                                                                 "role": "direction"}, cookie)
            self.assertEqual(direction["compte"]["technicien_id"], "")
            # Un compte demandeur devenu responsable reçoit la sienne (Léa Martin, COMPTES_DE_TEST).
            change = self.requete(srv, "/api/acces/comptes/lea.martin", {"action": "modifier", "role": "responsable"},
                                  cookie)
            self.assertEqual(change["compte"]["technicien_id"], "TEC-0007")
            self.assertEqual(len(techniciens(srv.dossier)), 7)
            # Devenu Direction (sans technicien_id envoyé) : il quitte sa fiche, qui reste dans Équipe.
            change = self.requete(srv, "/api/acces/comptes/lea.martin", {"action": "modifier", "role": "direction"},
                                  cookie)
            self.assertEqual((change["compte"]["role"], change["compte"]["technicien_id"]), ("direction", ""))
            self.assertEqual(len(techniciens(srv.dossier)), 7)


class TestEcranResponsableTechnicien(CasNavigateur):

    def test_accueil_responsable_prise_et_controle_acces(self):
        with ServeurPrevo(comptes=True) as srv:
            srv.poser_session(self.contexte, "responsable", profil=False)
            self.page.goto(srv.url + "/#/accueil")
            attendre_pret(self.page)
            self.assertEqual(self.page.evaluate("[App.profil.type, App.profil.technicienId, App.estTechnicien()]"),
                             ["responsable", "TEC-0005", False])
            titre = self.page.evaluate("I18n.t('accueil.accueil_technicien.accueil')")
            self.assertNotEqual(self.page.locator("h1").first.text_content().strip(), titre)   # accueil du responsable
            ot_id = self.page.evaluate("""() => Ordres.creer({ origine: 'manuel', type: 'correctif différé',
                priorite: 'P3', titre: 'Essai L06', technicien_id: '', date_prevue: '' })""")
            self.page.evaluate("id => { location.hash = '#/ot/' + id; }", ot_id)
            bouton = self.page.locator('.ot-fiche [data-action="prendre-ot"]').first
            bouton.click()
            self.page.wait_for_function(
                "id => (Donnees.trouver('ordres_travail', id) || {}).technicien_id === 'TEC-0005'", arg=ot_id)
            # Équipe › Accès : une fiche pour un responsable passe la vérification, pas pour la Direction.
            erreurs = self.page.evaluate("""() => [
                EquipeAcces.verifierCompte({ prenom: 'A', role: 'responsable', technicien_id: 'TEC-0001' }),
                EquipeAcces.verifierCompte({ prenom: 'A', role: 'technicien', technicien_id: 'TEC-0001' }),
                EquipeAcces.verifierCompte({ prenom: 'A', role: 'responsable', technicien_id: '' }),
                EquipeAcces.verifierCompte({ prenom: 'A', role: 'direction', technicien_id: 'TEC-0001' }).map((e) => e.message),
                EquipeAcces.verifierCompte({ prenom: 'A', role: 'technicien', technicien_id: '' }).length]""")
            self.assertEqual(erreurs[:3], [[], [], []])
            self.assertEqual(erreurs[3], [self.page.evaluate("I18n.t('equipe.verifier_compte.direction_sans_fiche')")])
            self.assertEqual(erreurs[4], 1)                     # technicien sans fiche : toujours refusé


if __name__ == "__main__":
    unittest.main()
