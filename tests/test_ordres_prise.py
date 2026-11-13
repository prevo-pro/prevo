"""Tests de « Je prends cet OT » et de la reprise de l'OT d'un collègue (lot 1 ergonomie, A3, T516 ;
js/modules/ordres-prise.js, ARCHITECTURE.md §14.2 « Prises en charge »).

Familles :
    regles   : transitions RG3 (démarrer depuis Créé / Préparé dès qu'il y a un technicien), lecture et écriture de
               ordres_travail.prises_en_charge, geste proposé, reprises récentes, OT à prendre ;
    parcours : en mode serveur sans comptes, un technicien voit « À prendre », prend un OT, le démarre et coche la
               check-list ; un collègue reprend une panne en attente (confirmation qui le nomme) ; le premier le voit
               sur son accueil, le responsable sur le sien et sur la fiche ; RG8 refuse comme à l'affectation ;
               ni la Direction ni un OT au nom du technicien ne montrent de bouton ; raccourci de la liste ;
    serveur  : droits inchangés (PUT d'ordres_travail : technicien accepté, demandeur et direction 403).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_ordres_prise.py" -v
"""
import csv
import io
import re
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil
import test_acces_roles as roles

KARIM, JULIEN, THOMAS = "TEC-0002", "TEC-0001", "TEC-0004"       # techniciens du jeu de démo
LIGNE_PRISE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}\|([^|]+)\|([^|]*)$")


def lire_csv(dossier, nom):
    texte = (Path(dossier) / nom).read_text(encoding="utf-8-sig")
    return list(csv.DictReader(io.StringIO(texte), delimiter=";"))


def ot_sur_disque(dossier, ot_id):
    return next(o for o in lire_csv(dossier, "ordres_travail.csv") if o["id"] == ot_id)


class CasPrise(CasNavigateur):

    def ouvrir(self, serveur, route, profil="responsable", technicien_id="", nom=""):
        preregler_profil(self.contexte, profil, nom=nom, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)

    def changer_profil(self, serveur, route, profil, technicien_id="", nom=""):
        self.page.evaluate("p => localStorage.setItem('prevo.profil', JSON.stringify(p))",
                           {"type": profil, "nom": nom, "technicienId": technicien_id})
        self.page.goto(serveur.url + "/" + route)
        self.page.reload()
        attendre_pret(self.page)

    def creer_ot(self, valeurs, statut=None):
        """OT créé par l'écriture du module (profil responsable) ; statut : passage de Créé à ce statut."""
        ot_id = self.page.evaluate("v => Ordres.creer(v)", dict({
            "origine": "manuel", "type": "correctif différé", "priorite": "P3", "titre": "Essai A3",
            "technicien_id": "", "date_prevue": ""}, **valeurs))
        if statut == "En attente":
            self.page.evaluate("id => Ordres.changerStatut(id, 'Créé', 'En attente', { motif_attente: 'pièce' })", ot_id)
        return ot_id

    def attendre_disque(self, serveur, ot_id, condition, delai_s=10):
        import time
        fin = time.time() + delai_s
        while True:
            ligne = ot_sur_disque(serveur.dossier, ot_id)
            if condition(ligne) or time.time() > fin:
                return ligne
            time.sleep(0.2)

    def aller_fiche(self, ot_id):
        self.page.evaluate("id => { location.hash = '#/ot/' + id; }", ot_id)
        self.page.wait_for_function(
            "id => document.querySelector('.ot-fiche .ot-numero') && document.querySelector('.ot-fiche .ot-numero').textContent === id",
            arg=ot_id)


# ---------------------------------------------------------------------------
# Règles pures
# ---------------------------------------------------------------------------

class TestReglesPrise(CasPrise):

    def test_regles_transitions_lecture_et_geste(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            evaluer = self.page.evaluate
            # RG3 (A3) : démarrer depuis Créé et Préparé dès que l'OT a un technicien ; rien n'est retiré.
            self.assertEqual(evaluer("Ordres.transitionsPossibles({ statut: 'Créé', origine: 'préventif', technicien_id: 'TEC-0002' })"),
                             ["Préparé", "En cours", "En attente", "Annulé"])
            self.assertEqual(evaluer("Ordres.transitionsPossibles({ statut: 'Créé', origine: 'préventif', technicien_id: '' })"),
                             ["Préparé", "En attente", "Annulé"])
            self.assertEqual(evaluer("Ordres.transitionsPossibles({ statut: 'Préparé', technicien_id: 'TEC-0002' })"),
                             ["Planifié", "En cours", "En attente", "Annulé"])
            self.assertEqual(evaluer("Ordres.transitionsPossibles({ statut: 'Préparé', technicien_id: '' })"),
                             ["Planifié", "En attente", "Annulé"])
            self.assertTrue(evaluer("Ordres.verifierPassage({ id: 'X', statut: 'Créé', technicien_id: 'TEC-0002' }, 'En cours').ok"))
            # prises_en_charge : lecture (lignes illisibles ignorées), ajout
            self.assertEqual(evaluer("Ordres.lirePrises('2026-11-13 08:02|TEC-0002|\\n\\nbad\\n2026-11-13 14:10|TEC-0001|TEC-0002')"),
                             [{"date": "2026-11-13 08:02", "technicienId": "TEC-0002", "precedentId": ""},
                              {"date": "2026-11-13 14:10", "technicienId": "TEC-0001", "precedentId": "TEC-0002"}])
            self.assertEqual(evaluer("Ordres.ajouterPrise('', '2026-11-13 08:02', 'TEC-0002', '')"), "2026-11-13 08:02|TEC-0002|")
            self.assertEqual(evaluer("Ordres.ajouterPrise('a|B|\\n', '2026-11-13 09:00', 'TEC-0001', 'TEC-0002')"),
                             "a|B|\n2026-11-13 09:00|TEC-0001|TEC-0002")
            # geste proposé
            self.assertEqual(evaluer("Ordres.priseProposee({ statut: 'Créé', technicien_id: '' }, 'TEC-0002')"), "prendre")
            self.assertEqual(evaluer("Ordres.priseProposee({ statut: 'En attente', technicien_id: 'TEC-0001' }, 'TEC-0002')"), "reprendre")
            self.assertEqual(evaluer("Ordres.priseProposee({ statut: 'En cours', technicien_id: 'TEC-0002' }, 'TEC-0002')"), "")
            self.assertEqual(evaluer("Ordres.priseProposee({ statut: 'Clôturé techniquement', technicien_id: '' }, 'TEC-0002')"), "")
            self.assertEqual(evaluer("Ordres.priseProposee({ statut: 'Annulé', technicien_id: '' }, 'TEC-0002')"), "")
            self.assertEqual(evaluer("Ordres.priseProposee({ statut: 'Créé', technicien_id: '' }, '')"), "")
            # reprises récentes (7 jours) et OT à prendre (priorité puis date)
            self.assertEqual(evaluer("Ordres.joursAvant('2026-11-13', 7)"), "2026-11-06")
            reprises = evaluer("""Ordres.reprisesRecentes([
                { id: 'OT-1', prises_en_charge: '2026-11-01 08:00|TEC-0001|\\n2026-11-02 08:00|TEC-0002|TEC-0001' },
                { id: 'OT-2', prises_en_charge: '2026-11-10 08:00|TEC-0001|\\n2026-11-12 10:00|TEC-0003|TEC-0001' },
                { id: 'OT-3', prises_en_charge: '2026-11-11 08:00|TEC-0001|TEC-0004' }], '2026-11-06', 'TEC-0001')
                .map((r) => r.ot.id + ' ' + r.technicienId)""")
            self.assertEqual(reprises, ["OT-2 TEC-0003"])
            ordre = evaluer("""Ordres.otsAPrendre([
                { id: 'A', statut: 'Créé', priorite: 'P3', date_prevue: '2026-11-01', technicien_id: '' },
                { id: 'B', statut: 'Créé', priorite: 'P1', date_prevue: '2026-11-20', technicien_id: '' },
                { id: 'C', statut: 'Préparé', priorite: 'P3', date_prevue: '', technicien_id: '' },
                { id: 'D', statut: 'Créé', priorite: 'P1', date_prevue: '', technicien_id: 'TEC-0001' },
                { id: 'E', statut: 'Annulé', priorite: 'P1', date_prevue: '', technicien_id: '' }]).map((o) => o.id)""")
            self.assertEqual(ordre, ["B", "A", "C"])


# ---------------------------------------------------------------------------
# Parcours (mode serveur, sans comptes)
# ---------------------------------------------------------------------------

class TestParcoursPrise(CasPrise):

    def test_parcours_prendre_demarrer_reprendre_et_voir(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            preventif = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Graissage A3", "priorite": "P2"})
            self.page.evaluate("""id => Donnees.modifier('ot_operations', (lignes, outils) => {
                lignes.push({ id: outils.nouvelId(lignes), ot_id: id, ordre: '1', operation: 'Graisser les paliers',
                  valeur_attendue: '', fait: '0', valeur_mesuree: '' }); })""", preventif)
            panne = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Panne A3", "technicien_id": JULIEN},
                                  statut="En attente")

            # Karim (technicien) : carte « À prendre » sur l'accueil
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.page.wait_for_selector(".accueil-a-prendre")
            self.assertIn(preventif, self.page.inner_text(".accueil-a-prendre"))
            self.assertEqual(self.page.get_attribute(".accueil-a-prendre .accueil-voir-tout a", "href"), "#/ot?technicien=__aucun")

            # Fiche : pas de liste « Technicien » sans bouton ; « Je prends cet OT »
            self.aller_fiche(preventif)
            self.page.click(".onglet[data-onglet='preparation']")
            self.assertEqual(self.page.locator("#form-preparation select[name=technicien_id]").count(), 0)
            self.assertEqual(self.page.locator(".ot-technicien-lecture").count(), 1)
            self.assertEqual(self.page.locator(".ot-prise-preparation button[data-action=prendre-ot]").count(), 1)
            self.assertEqual(self.page.locator(".ot-actions button[data-cible='En cours']").count(), 0)
            self.page.click(".ot-actions button[data-action=prendre-ot]")
            ligne = self.attendre_disque(serveur, preventif, lambda o: o["technicien_id"] == KARIM)
            self.assertEqual(ligne["technicien_id"], KARIM)
            self.assertEqual(LIGNE_PRISE.match(ligne["prises_en_charge"]).groups(), (KARIM, ""))
            self.assertEqual(ligne["statut"], "Créé")
            # la suite : « Démarrer », puis la check-list se coche
            self.page.wait_for_selector(".ot-actions button[data-cible='En cours']")
            self.assertEqual(self.page.locator(".ot-actions button[data-action=prendre-ot]").count(), 0)
            self.assertIn("Karim a pris l'OT", self.page.inner_text(".ot-prises"))
            self.page.click(".ot-actions button[data-cible='En cours']")
            ligne = self.attendre_disque(serveur, preventif, lambda o: o["statut"] == "En cours")
            self.assertEqual(ligne["statut"], "En cours")
            aujourdhui = self.page.evaluate("Donnees.aujourdhui()")
            self.assertEqual(ligne["date_prevue"][:10], aujourdhui)                   # date prévue manquante
            # T528 : la fiche s'ouvre d'elle-même sur Exécution (la check-list), sans toucher l'onglet
            self.page.wait_for_selector(".onglet[data-onglet='execution'][aria-selected='true']")
            self.page.wait_for_selector("#form-execution .ot-fait")
            case =self.page.locator("#form-execution .ot-fait").first
            self.assertTrue(case.is_enabled())
            case.check()
            self.page.wait_for_function("() => document.querySelector('#form-execution .ot-fait').checked")

            # Karim reprend la panne de Julien : confirmation qui nomme Julien ; le statut ne change pas
            self.aller_fiche(panne)
            self.page.click(".ot-actions button[data-action=prendre-ot]")
            self.page.wait_for_selector("dialog.dialogue[open]")
            self.assertIn("Cet OT est au nom de Julien", self.page.inner_text("dialog.dialogue[open]"))
            self.page.click("dialog.dialogue[open] .fenetre-actions .btn-primaire")
            ligne = self.attendre_disque(serveur, panne, lambda o: o["technicien_id"] == KARIM)
            self.assertEqual(ligne["statut"], "En attente")
            lignes = ligne["prises_en_charge"].split("\n")
            self.assertEqual(len(lignes), 1, lignes)                    # affecté à la création : seule la reprise
            self.assertEqual(LIGNE_PRISE.match(lignes[-1]).groups(), (KARIM, JULIEN))
            journal = [j for j in lire_csv(serveur.dossier, "journal.csv") if j["id_ligne"] == panne]
            self.assertTrue(any("technicien_id" in j["action"] and "reprise de l'OT" in j["action"] for j in journal), journal)

            # Julien voit la reprise sur son accueil
            self.changer_profil(serveur, "#/accueil", "technicien", JULIEN, "Julien Moreau")
            self.page.wait_for_selector(".accueil-reprises")
            texte = self.page.inner_text(".accueil-reprises")
            self.assertIn("Karim a repris votre " + panne, texte)
            self.assertEqual(self.page.get_attribute(".accueil-reprises a", "href"), "#/ot/" + panne)

            # Le responsable : bloc « Reprises récentes » de l'accueil et historique de la fiche
            self.changer_profil(serveur, "#/accueil", "responsable")
            self.page.wait_for_selector(".accueil-reprises")
            self.assertIn(panne, self.page.inner_text(".accueil-reprises"))
            self.aller_fiche(panne)
            self.assertIn("Karim a repris l'OT (avant : Julien)", self.page.inner_text(".ot-prises"))
            self.assertEqual(self.page.locator(".ot-actions button[data-action=prendre-ot]").count(), 0)
            # Le responsable change le technicien dans Préparation : une ligne de plus (même format)
            self.page.click(".onglet[data-onglet='preparation']")
            self.page.select_option("#form-preparation [name=technicien_id]", JULIEN)
            self.page.click("#form-preparation button[type=submit]")
            ligne = self.attendre_disque(serveur, panne, lambda o: o["technicien_id"] == JULIEN)
            self.assertEqual(LIGNE_PRISE.match(ligne["prises_en_charge"].split("\n")[-1]).groups(), (JULIEN, KARIM))

            # Direction : lecture seule, aucun bouton ; le bloc est lisible
            self.changer_profil(serveur, "#/accueil", "direction")
            self.aller_fiche(panne)
            self.assertEqual(self.page.locator("button[data-action=prendre-ot]").count(), 0)
            self.assertIn("Julien a repris l'OT (avant : Karim)", self.page.inner_text(".ot-prises"))
            # Bon de travail : le bloc y est aussi
            html = self.page.evaluate("id => { const d = document.createElement('div'); UI.remplir(d, Ordres.bonDeTravailHtml(Donnees.trouver('ordres_travail', id))); return d.innerText; }", panne)
            self.assertIn("Karim a repris l'OT (avant : Julien)", html)

    def test_habilitation_refus_comme_l_affectation_et_raccourci_de_la_liste(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            exige = self.creer_ot({"equipement_id": "EQ-0012", "titre": "Armoire A3", "date_prevue": "2026-10-21"})
            libre = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Libre A3", "priorite": "P1"})
            # Thomas (sans BR valide) : refus avec le message de l'affectation, rien d'écrit
            self.changer_profil(serveur, "#/accueil", "technicien", THOMAS, "Thomas Garnier")
            self.autoriser_erreur("BR")
            self.aller_fiche(exige)
            avant = ot_sur_disque(serveur.dossier, exige)
            self.page.click(".ot-actions button[data-action=prendre-ot]")
            self.page.wait_for_selector("#toast")
            self.assertIn("BR", self.page.inner_text("#toast"))
            self.assertEqual(self.page.locator("dialog.dialogue[open]").count(), 0)                 # pas de dérogation pour lui
            self.assertEqual(ot_sur_disque(serveur.dossier, exige), avant)
            # Liste filtrée « Non affectés » : « Je prends » sur la ligne, puis la fiche ouverte
            self.page.evaluate("location.hash = '#/ot?technicien=__aucun'")
            bouton = ".ot-liste-tableau tr:has(a:text-is('%s')) button[data-action=prendre-ot]" % libre
            self.page.wait_for_selector(bouton)
            self.page.click(bouton)
            self.page.wait_for_function(
                "id => document.querySelector('.ot-fiche .ot-numero') && document.querySelector('.ot-fiche .ot-numero').textContent === id",
                arg=libre)
            ligne = self.attendre_disque(serveur, libre, lambda o: o["technicien_id"] == THOMAS)
            self.assertEqual(ligne["technicien_id"], THOMAS)
            self.page.wait_for_selector(".ot-actions button[data-cible='En cours']")


# ---------------------------------------------------------------------------
# Serveur : droits inchangés
# ---------------------------------------------------------------------------

class TestDroitsServeur(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        roles.setUpModule()
        roles.lancer_serveur_comptes(cls)

    def test_put_ordres_travail_technicien_accepte_demandeur_et_direction_refuses(self):
        chemin = self.serveur.dossier / "ordres_travail.csv"
        disque = chemin.read_bytes()
        entete, lignes = roles.lire_tableau(disque)
        p_tech, p_prises = entete.index("technicien_id"), entete.index("prises_en_charge")
        cible = next(l for l in lignes if l[entete.index("statut")] in ("Créé", "Préparé"))
        precedent = cible[p_tech]
        cible[p_tech] = "TEC-0001"
        cible[p_prises] = "2026-11-13 08:02|TEC-0001|" + precedent
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
        self.assertEqual(apres[cible[0]][p_tech], "TEC-0001")
        self.assertEqual(apres[cible[0]][p_prises], "2026-11-13 08:02|TEC-0001|" + precedent)


if __name__ == "__main__":
    unittest.main()
