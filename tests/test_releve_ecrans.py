"""L32 (T545, décision de Nicolas du 14/11) — écrans tenus à jour sans recharger la page, en mode serveur.

Ce qui est vérifié :
    serveur     : GET /api/versions joint un « jeton » ; avec l'en-tête X-Jeton-Versions égal au jeton courant, il
                  répond {"inchange": true} sans liste ; un fichier changé sur le disque (Excel, autre poste) change le
                  jeton ; le jeton d'un rôle n'est pas celui d'un autre ; celui du demandeur ne suit que ses tables
                  (un OT changé ne lui apprend rien) ;
    navigateur  : (deux postes, comptes) le responsable qui revient sur l'accueil voit tout de suite la panne envoyée
                  par l'opérateur (relève à l'arrivée sur l'écran) ; resté sur l'accueil, il la voit en quelques
                  secondes (relève rapide conditionnelle, 5 s) et, entre deux changements, le serveur répond
                  « inchangé » ; « Mes demandes » de l'opérateur suit la demande réparée ; une saisie en cours n'est
                  jamais redessinée (bandeau « données changées ») ; en mode fichier (démo file://), aucune relève de plus.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_releve_ecrans.py" -v
"""
import json
import time
import unittest
import urllib.request

from atelier import motif_refus_du_demandeur
from commun import COMPTES_DE_TEST, CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, url_fichier

CREER_DI_JS = """([symptome]) => Demandes.creer({ equipement_id: Donnees.lignes('equipements')[0].id, symptome,
  impact: 'sécurité' })"""
TEXTE_JS = "() => document.querySelector('#contenu').innerText"


def versions(serveur, cookie, jeton=None):
    entetes = {"Cookie": cookie, "User-Agent": "tests-prevo/1.0"}
    if jeton is not None:
        entetes["X-Jeton-Versions"] = jeton
    requete = urllib.request.Request(serveur.url + "/api/versions", headers=entetes)
    with urllib.request.urlopen(requete, timeout=10) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def ajouter_au_fichier(serveur, table):
    """Un autre outil (Excel, un poste sans Prévo) change le fichier : une ligne de plus sur le disque."""
    chemin = serveur.dossier / (table + ".csv")
    chemin.write_bytes(chemin.read_bytes() + b"\r\n")


class TestJetonDesVersions(unittest.TestCase):
    """Serveur réel en mode comptes (copie de la démo), sans navigateur."""

    @classmethod
    def setUpClass(cls):
        cls.serveur = ServeurPrevo(comptes=True)
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)
        cls.cookies = {role: cls.serveur.session(role) for role in COMPTES_DE_TEST}

    def test_inchange_puis_liste_complete_apres_un_changement_sur_le_disque(self):
        complet = versions(self.serveur, self.cookies["responsable"])
        jeton = complet["jeton"]
        self.assertEqual(len(jeton), 16)
        self.assertIn("demandes", complet["tables"])
        self.assertEqual(versions(self.serveur, self.cookies["responsable"], jeton), {"inchange": True, "jeton": jeton})
        ancien = versions(self.serveur, self.cookies["responsable"], "0" * 16)              # jeton périmé : liste complète
        self.assertEqual(ancien["tables"], complet["tables"])
        ajouter_au_fichier(self.serveur, "releves")
        apres = versions(self.serveur, self.cookies["responsable"], jeton)
        self.assertNotIn("inchange", apres)
        self.assertNotEqual(apres["jeton"], jeton)
        self.assertNotEqual(apres["tables"]["releves"]["version"], complet["tables"]["releves"]["version"])
        self.assertEqual(versions(self.serveur, self.cookies["responsable"], apres["jeton"])["inchange"], True)

    def test_jeton_propre_au_role_et_aux_tables_du_demandeur(self):
        jetons = {role: versions(self.serveur, cookie)["jeton"] for role, cookie in self.cookies.items()}
        self.assertEqual(len(set(jetons.values())), 3, jetons)
        # Le demandeur ne lit pas ordres_travail : un OT changé ne change pas son jeton (il n'apprend rien).
        ajouter_au_fichier(self.serveur, "ordres_travail")
        self.assertEqual(versions(self.serveur, self.cookies["demandeur"], jetons["demandeur"]),
                         {"inchange": True, "jeton": jetons["demandeur"]})
        self.assertNotIn("inchange", versions(self.serveur, self.cookies["technicien"], jetons["technicien"]))
        ajouter_au_fichier(self.serveur, "demandes")
        self.assertNotIn("inchange", versions(self.serveur, self.cookies["demandeur"], jetons["demandeur"]))


class TestReleveDesEcrans(CasNavigateur):
    """Deux postes sur un serveur neuf en mode comptes : le responsable (PC) et l'opératrice Léa (téléphone)."""

    def setUp(self):
        super().setUp()
        self.autoriser_erreur(motif_refus_du_demandeur())                # tables refusées à Léa (demandeur)
        self.serveur = ServeurPrevo(comptes=True)
        self.serveur.demarrer()
        self.addCleanup(self.serveur.arreter)
        self.serveur.poser_session(self.contexte, "responsable")
        self.versions = []                                                # (jeton envoyé ?, réponse « inchangé » ?)
        self.page.on("requestfinished", self.noter_versions)
        operatrice = self.navigateur.new_context(locale="fr-FR", viewport={"width": 390, "height": 844},
                                                 is_mobile=True, has_touch=True)
        self.addCleanup(operatrice.close)
        self.serveur.poser_session(operatrice, "demandeur")
        self.lea = operatrice.new_page()
        self.surveiller(self.lea)
        self.lea.goto(self.serveur.url + "/#/accueil")
        attendre_pret(self.lea)

    def noter_versions(self, requete):
        if "/api/versions" not in requete.url:
            return
        reponse = requete.response()
        corps = reponse.json() if reponse else {}
        self.versions.append(("x-jeton-versions" in requete.headers, corps.get("inchange") is True))

    def ouvrir_responsable(self, route):
        self.page.goto(self.serveur.url + "/" + route)
        attendre_pret(self.page)

    def attendre_texte(self, page, texte, delai_ms):
        page.wait_for_function("(t) => document.querySelector('#contenu').innerText.includes(t)", arg=texte,
                               timeout=delai_ms)

    def test_retour_sur_l_accueil_montre_aussitot_la_panne_envoyee(self):
        self.ouvrir_responsable("#/ot")
        di = self.lea.evaluate(CREER_DI_JS, ["Fuite d'huile L32 retour"])
        self.page.evaluate("() => { location.hash = '#/accueil'; }")            # clic sur « Accueil »
        debut = time.monotonic()
        self.attendre_texte(self.page, di, 3000)                                  # avant : jusqu'à 20 s
        self.assertLess(time.monotonic() - debut, 3)

    def test_reste_sur_l_accueil_la_panne_urgente_arrive_en_quelques_secondes(self):
        self.ouvrir_responsable("#/accueil")
        self.page.wait_for_timeout(6000)                                          # au moins une relève rapide à vide
        self.assertIn((True, True), self.versions, self.versions)               # conditionnelle, « inchangé »
        di = self.lea.evaluate(CREER_DI_JS, ["Fuite d'huile L32 urgente"])
        debut = time.monotonic()
        self.attendre_texte(self.page, di, 8000)
        self.assertLess(time.monotonic() - debut, 8)

    def test_mes_demandes_suit_la_reparation(self):
        di = self.lea.evaluate(CREER_DI_JS, ["Fuite d'huile L32 réparée"])
        self.lea.evaluate("() => { location.hash = '#/di'; }")
        self.attendre_texte(self.lea, di, 5000)
        self.ouvrir_responsable("#/ot")
        # Ce qu'écrit la clôture de l'OT pour l'opérateur (Demandes.suivreOt) : statut, date, prénom.
        self.page.evaluate("""(d) => Donnees.modifier('demandes', (lignes) => { const l = lignes.find((x) => x.id === d);
            l.statut = 'Réparée'; l.date_reparation = '2026-11-14 10:00'; l.repare_par = 'Julien'; },
            { action: 'essai L32' })""", di)
        self.lea.evaluate("() => { location.hash = '#/accueil'; }")
        self.lea.wait_for_timeout(300)
        self.lea.evaluate("() => { location.hash = '#/di'; }")                    # retour sur « Mes demandes »
        self.lea.wait_for_function("""(d) => Array.from(document.querySelectorAll('#contenu *')).some((e) =>
            e.children.length === 0 && e.textContent.includes(d) && /Réparée/.test((e.closest('li, tr, a, article') || e).innerText))""",
                                   arg=di, timeout=3000)

    def test_saisie_en_cours_jamais_redessinee(self):
        self.ouvrir_responsable("#/accueil")
        self.page.evaluate("() => { App.marquerSaisie(); document.querySelector('#contenu').dataset.marqueL32 = '1'; }")
        di = self.lea.evaluate(CREER_DI_JS, ["Fuite d'huile L32 saisie"])
        self.page.wait_for_selector("#bandeau-changement", state="visible", timeout=8000)
        self.assertNotIn(di, self.page.evaluate(TEXTE_JS))
        self.assertEqual(self.page.evaluate("() => document.querySelector('#contenu').dataset.marqueL32"), "1")

    def test_fenetre_ouverte_jamais_redessinee(self):
        self.ouvrir_responsable("#/accueil")
        self.page.evaluate("""() => { const d = document.createElement('dialog'); d.id = 'fenetre-l32';
            document.body.appendChild(d); d.showModal(); }""")
        di = self.lea.evaluate(CREER_DI_JS, ["Fuite d'huile L32 fenêtre"])
        self.page.wait_for_selector("#bandeau-changement", state="visible", timeout=8000)
        self.assertNotIn(di, self.page.evaluate(TEXTE_JS))


class TestModeFichier(CasNavigateur):
    """Démo en file:// : rien de plus qu'avant (aucune relève à l'arrivée sur l'accueil, pas de relève rapide)."""

    def test_aucune_releve_de_plus_hors_du_mode_serveur(self):
        preregler_profil(self.contexte, "responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.page.evaluate("""() => { window.relevesL32 = 0; const a = App.adaptateur; const vraie = a.listerVersions;
            a.listerVersions = function () { window.relevesL32 += 1; return vraie.apply(this, arguments); }; }""")
        self.page.evaluate("() => { location.hash = '#/di'; }")
        self.page.wait_for_timeout(300)
        self.page.evaluate("() => { location.hash = '#/accueil'; }")
        self.page.wait_for_timeout(6000)
        self.assertEqual(self.page.evaluate("window.relevesL32"), 0)


if __name__ == "__main__":
    unittest.main()
