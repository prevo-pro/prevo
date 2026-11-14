"""Pannes récurrentes (lot 2 ergonomie, décision L29 ; js/modules/pannes-recurrentes.js).

Deux familles :
    regles : jeu construit à la main (StockageDemo), aujourd'hui = 30/10/2026 : 3 pannes en 30 jours (bornes au jour
             près), une demande et son OT comptés une fois (par demandes.ot_id comme par ordres_travail.di_id),
             demande refusée ou regroupée, OT annulé ou préventif écartés, même cause (code, « Autre »), réglages lus
             dans parametres.csv (bornes), alerte vue depuis une panne (comptée jusqu'à son jour), ordre de l'accueil ;
    ecrans : serveur.py sur une copie de la démo à laquelle on ajoute quatre pannes datées d'aujourd'hui sur une machine
             calme : tuile « Pannes récurrentes » de l'accueil du responsable, bandeau sur la demande qu'il traite,
             bandeau sur l'OT correctif ouvert du technicien (interventions précédentes en lien), réglage du seuil dans
             Paramètres (écrit dans parametres.csv, la machine sort de la tuile).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_pannes_recurrentes.py" -v
"""
import csv as module_csv
import io
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from commun import CasNavigateur, DOSSIER_DEMO, ServeurPrevo, attendre_pret, charger_scripts, preregler_profil

SCRIPTS = ["js/lib/papaparse.min.js", "js/schema.js", "js/donnees.js", "js/stockage-demo.js", "js/interface.js",
           "js/modules/pannes-recurrentes.js"]
AUJOURDHUI = "2026-10-30"


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


class Jeu:
    def __init__(self):
        self.ots, self.dis = [], []

    def di(self, equipement, jour, statut="Nouvelle", ot=""):
        identifiant = "DI-2026-%04d" % (len(self.dis) + 1)
        self.dis.append(";".join([identifiant, equipement, jour + " 09:00", "Fuite", statut, ot]))
        return identifiant

    def ot(self, equipement, jour, type_ot="correctif immédiat", statut="En cours", di="", cause="", precision=""):
        identifiant = "OT-2026-%04d" % (len(self.ots) + 1)
        self.ots.append(";".join([identifiant, equipement, type_ot, statut, jour + " 10:00", di, cause, precision,
                                  "Réparer"]))
        return identifiant

    def tables(self, parametres=()):
        return {
            "equipements": csv("id;repere;designation", ["EQ-0001;PO-01;Pompe", "EQ-0002;CV-01;Convoyeur",
                                                         "EQ-0003;PR-01;Presse", "EQ-0004;VE-01;Ventilation"]),
            "codes_defaillance": csv("id;famille;code;libelle", ["CD-0001;cause;C01;Garniture usée",
                                                                 "CD-0002;cause;C02;Desserrage"]),
            "demandes": csv("id;equipement_id;date_heure;symptome;statut;ot_id", self.dis),
            "ordres_travail": csv("id;equipement_id;type;statut;date_creation;di_id;cause_code;cause_precision;titre",
                                  self.ots),
            "parametres": csv("cle;valeur", list(parametres)),
        }


def jeu_de_base():
    j = Jeu()
    # PO-01 : 3 pannes du 01/10 au 30/10 (fenêtre de 30 jours, bornes comprises) ; le 30/09 est dehors
    j.ot("EQ-0001", "2026-09-30", cause="C01")
    j.ot("EQ-0001", "2026-10-01", statut="Clôturé techniquement", cause="C01")
    j.ot("EQ-0001", "2026-10-15", statut="Clôturé techniquement", cause="C01")
    j.di("EQ-0001", "2026-10-30")
    # CV-01 : demande et OT liés deux fois (ot_id ; di_id) → 2 pannes seulement, plus une 3e seule ; mêmes « Autre »
    ot1 = j.ot("EQ-0002", "2026-10-11", precision="Bande usée ")
    j.di("EQ-0002", "2026-10-10", statut="Acceptée", ot=ot1)
    di2 = j.di("EQ-0002", "2026-10-20", statut="Acceptée")
    j.ot("EQ-0002", "2026-10-21", di=di2, precision="bande usée")
    j.di("EQ-0002", "2026-10-25")
    # PR-01 : écartés — demande refusée, regroupée, OT annulé, préventif, demande dont l'OT est annulé → 2 pannes
    j.di("EQ-0003", "2026-10-10", statut="Refusée")
    j.di("EQ-0003", "2026-10-11", statut="Regroupée")
    j.ot("EQ-0003", "2026-10-12", statut="Annulé")
    j.ot("EQ-0003", "2026-10-13", type_ot="préventif systématique")
    annule = j.ot("EQ-0003", "2026-10-14", statut="Annulé")
    j.di("EQ-0003", "2026-10-14", statut="Acceptée", ot=annule)
    j.ot("EQ-0003", "2026-10-20", type_ot="correctif différé", cause="C01")
    j.ot("EQ-0003", "2026-10-21", cause="C02")
    # VE-01 : 4 pannes, causes toutes différentes
    for jour in ("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"):
        j.di("EQ-0004", jour)
    return j


class TestReglesPannesRecurrentes(CasNavigateur):

    def setUp(self):
        super().setUp()
        charger_scripts(self.page, SCRIPTS)

    def charger(self, tables):
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable' });
          await Donnees.chargerTout();
        }""", tables)

    def alertes(self, jour=AUJOURDHUI):
        return self.page.evaluate("""(jour) => PannesRecurrentes.machinesEnAlerte(jour).map((a) => ({
            equipement: a.equipementId, nombre: a.nombre, ids: a.pannes.map((p) => p.id),
            cause: a.memeCause && [a.memeCause.libelle, a.memeCause.nombre] }))""", jour)

    def test_seuil_fenetre_double_compte_et_ecartees(self):
        self.charger(jeu_de_base().tables())
        alertes = self.alertes()
        # VE-01 (4) d'abord, puis PO-01 et CV-01 (3 chacune, la panne la plus récente d'abord) ; PR-01 : 2, pas d'alerte
        self.assertEqual([a["equipement"] for a in alertes], ["EQ-0004", "EQ-0001", "EQ-0002"])
        po01, cv01 = alertes[1], alertes[2]
        self.assertEqual(po01["ids"], ["OT-2026-0002", "OT-2026-0003", "DI-2026-0001"])     # le 30/09 est dehors
        self.assertEqual(po01["cause"], ["Garniture usée", 2])
        self.assertIsNone(alertes[0]["cause"])
        # CV-01 : DI-2 représentée par OT-4 (ot_id), DI-3 par OT-5 (di_id, daté du signalement), DI-4 seule ;
        # « Autre » comparé sans la casse ni les espaces du bord
        self.assertEqual(cv01["ids"], ["OT-2026-0004", "OT-2026-0005", "DI-2026-0004"])
        self.assertEqual(cv01["cause"], ["Autre : Bande usée", 2])
        # La veille (29/10) : fenêtre du 30/09 au 29/10 pour PO-01
        veille = {a["equipement"]: a for a in self.alertes("2026-10-29")}
        self.assertEqual(veille["EQ-0001"]["ids"], ["OT-2026-0001", "OT-2026-0002", "OT-2026-0003"])
        # PR-01 : demande refusée, regroupée, OT annulés, préventif, demande dont l'OT est annulé écartés → 2 pannes
        self.charger(jeu_de_base().tables(parametres=["pannes_recurrentes_seuil;2"]))
        par_machine = {a["equipement"]: a for a in self.alertes()}
        self.assertEqual(par_machine["EQ-0003"]["ids"], ["OT-2026-0009", "OT-2026-0010"])

    def test_meme_cause_autre_precisee(self):
        j = Jeu()
        for jour in ("2026-10-01", "2026-10-02", "2026-10-03"):
            j.ot("EQ-0002", jour, precision="Bande usée")
        self.charger(j.tables())
        self.assertEqual(self.alertes()[0]["cause"], ["Autre : Bande usée", 3])

    def test_reglages_lus_dans_parametres_avec_leurs_bornes(self):
        cas = (([], (3, 30)), (["pannes_recurrentes_seuil;4", "pannes_recurrentes_jours;10"], (4, 10)),
               (["pannes_recurrentes_seuil;1", "pannes_recurrentes_jours;366"], (3, 30)),
               (["pannes_recurrentes_seuil;abc", "pannes_recurrentes_jours;6"], (3, 30)),
               (["pannes_recurrentes_seuil;20", "pannes_recurrentes_jours;7"], (20, 7)))
        for parametres, attendu in cas:
            with self.subTest(parametres=parametres):
                self.charger(jeu_de_base().tables(parametres=parametres))
                lu = self.page.evaluate("(() => { const r = PannesRecurrentes.reglages(); return [r.seuil, r.jours]; })()")
                self.assertEqual(tuple(lu), attendu)
        # Fenêtre de 10 jours (21/10 au 30/10) : une seule panne par machine, aucune alerte
        self.charger(jeu_de_base().tables(parametres=["pannes_recurrentes_jours;10"]))
        self.assertEqual(self.alertes(), [])

    def test_alerte_vue_depuis_une_panne(self):
        self.charger(jeu_de_base().tables())
        # Depuis la demande du 30/10 de PO-01 : 3 pannes, la courante comprise
        vue = self.page.evaluate("""(() => { const a = PannesRecurrentes.alertePour('EQ-0001', ['DI-2026-0001']);
            return a && [a.nombre, a.courante.id]; })()""")
        self.assertEqual(vue, [3, "DI-2026-0001"])
        # Depuis l'OT du 15/10 : comptée jusqu'au 15/10 (16/09 au 15/10) : 30/09, 01/10, 15/10 → 3
        vue = self.page.evaluate("(() => { const a = PannesRecurrentes.alertePour('EQ-0001', ['OT-2026-0003']); return a && a.nombre; })()")
        self.assertEqual(vue, 3)
        # Depuis l'OT du 01/10 : 2 pannes seulement → pas d'alerte ; un identifiant inconnu → rien
        self.assertIsNone(self.page.evaluate("PannesRecurrentes.alertePour('EQ-0001', ['OT-2026-0002'])"))
        self.assertIsNone(self.page.evaluate("PannesRecurrentes.alertePour('EQ-0001', ['OT-2026-9999'])"))
        # Une demande représentée par son OT : l'alerte la retrouve par l'identifiant de l'OT
        self.charger(jeu_de_base().tables(parametres=["pannes_recurrentes_seuil;2"]))
        vue = self.page.evaluate("""(() => { const a = PannesRecurrentes.alertePour('EQ-0002', ['DI-2026-0003', 'OT-2026-0005']);
            return a && [a.nombre, a.courante.id]; })()""")
        self.assertEqual(vue, [2, "OT-2026-0005"])


# ---------------------------------------------------------------------------
# Écrans (serveur.py sur une copie de la démo, quatre pannes ajoutées aujourd'hui)
# ---------------------------------------------------------------------------

def lire_brut(chemin):
    texte = Path(chemin).read_bytes().decode("utf-8-sig")
    return list(module_csv.DictReader(io.StringIO(texte, newline=""), delimiter=";"))


def ajouter_lignes(chemin, lignes):
    """Ajoute des lignes (dictionnaires) à un CSV de Prévo (BOM, « ; », CRLF), colonnes dans l'ordre de l'en-tête."""
    octets = Path(chemin).read_bytes()
    entete = octets.decode("utf-8-sig").split("\r\n", 1)[0].split(";")
    texte = "".join(";".join(ligne.get(colonne, "") for colonne in entete) + "\r\n" for ligne in lignes)
    if not octets.endswith(b"\r\n"):
        texte = "\r\n" + texte
    Path(chemin).write_bytes(octets + texte.encode("utf-8"))


class TestEcransPannesRecurrentes(CasNavigateur):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dossier = Path(tempfile.mkdtemp(prefix="prevo-recurrentes-"))
        cls.addClassCleanup(shutil.rmtree, cls.dossier, True)
        copie = cls.dossier / "donnees"
        shutil.copytree(DOSSIER_DEMO, copie)
        ordres, demandes = lire_brut(copie / "ordres_travail.csv"), lire_brut(copie / "demandes.csv")
        aujourdhui = date.today()
        limite = (aujourdhui - timedelta(days=60)).isoformat()
        recents = {o["equipement_id"] for o in ordres if o["date_creation"][:10] >= limite} \
            | {d["equipement_id"] for d in demandes if d["date_heure"][:10] >= limite}
        equipements = lire_brut(copie / "equipements.csv")
        machine = next(e for e in equipements if e["actif"] != "0" and e["id"] not in recents)
        cls.machine, cls.repere = machine["id"], machine["repere"].lstrip("'")
        cls.cause = next(c["libelle"] for c in lire_brut(copie / "codes_defaillance.csv")
                         if c["famille"] == "cause" and c["code"] == "C01")
        cls.technicien = next(t["id"] for t in lire_brut(copie / "techniciens.csv") if t["actif"] != "0")
        jour = lambda n: (aujourdhui - timedelta(days=n)).isoformat()
        d = lambda i, n, statut, ot="": {"id": "DI-2026-09%02d" % i, "date_heure": jour(n) + " 08:00", "demandeur": "Test",
                                         "equipement_id": cls.machine, "symptome": "Fuite n° %d" % i, "impact": "arrêt",
                                         "statut": statut, "ot_id": ot}
        o = lambda i, n, statut, di="", cause="": {
            "id": "OT-2026-09%02d" % i, "origine": "DI" if di else "manuel", "di_id": di, "equipement_id": cls.machine,
            "type": "correctif immédiat", "priorite": "P2", "statut": statut, "titre": "Réparation n° %d" % i,
            "date_creation": jour(n) + " 09:00", "technicien_id": cls.technicien, "cause_code": cause}
        ajouter_lignes(copie / "demandes.csv", [
            d(1, 10, "Réparée", "OT-2026-0901"), d(2, 5, "En cours", "OT-2026-0902"), d(3, 1, "Acceptée", "OT-2026-0903"),
            d(4, 0, "Nouvelle"), d(5, 2, "Refusée")])
        ajouter_lignes(copie / "ordres_travail.csv", [
            o(1, 10, "Clôturé techniquement", "DI-2026-0901", "C01"), o(2, 5, "En cours", "DI-2026-0902", "C01"),
            o(3, 1, "Créé", "DI-2026-0903"), o(4, 3, "Annulé")])
        cls.copie = copie

    def ouvrir(self, serveur, profil, route, technicien_id=""):
        preregler_profil(self.contexte, profil, technicien_id=technicien_id)
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)

    def test_tuile_bandeaux_et_reglage(self):
        page = self.page
        with ServeurPrevo(source=self.copie) as serveur:
            # Accueil du responsable : la machine, 4 pannes (la demande refusée et l'OT annulé ne comptent pas)
            self.ouvrir(serveur, "responsable", "#/accueil")
            page.wait_for_selector("#bento-recurrentes")
            lien = page.locator("#bento-recurrente-" + self.machine)
            self.assertEqual(lien.get_attribute("href"), "#/equipement/" + self.machine)
            texte = lien.inner_text()
            self.assertIn("%s : 4 pannes en 30 jours" % self.repere, texte)
            self.assertIn("même cause 2 fois : " + self.cause, texte)
            # La demande du jour, que le responsable traite : bandeau, interventions précédentes en lien
            page.evaluate("location.hash = '#/di/DI-2026-0904'")
            bandeau = page.wait_for_selector(".di-zone-securite .pannes-recurrentes")
            self.assertIn("4 pannes sur %s en 30 jours" % self.repere, bandeau.inner_text())
            self.assertIn("Même cause enregistrée 2 fois : %s." % self.cause, bandeau.inner_text())
            liens = page.eval_on_selector_all(".pannes-recurrentes-liste a", "l => l.map(a => a.getAttribute('href'))")
            self.assertEqual(liens, ["#/ot/OT-2026-0903", "#/ot/OT-2026-0902", "#/ot/OT-2026-0901"])
            # Une demande déjà traitée : pas de bandeau
            page.evaluate("location.hash = '#/di/DI-2026-0901'")
            page.wait_for_selector(".di-suivi")
            self.assertEqual(page.locator(".pannes-recurrentes").count(), 0)
            # Paramètres : seuil à 5, écrit dans parametres.csv ; la machine sort de la tuile
            page.evaluate("location.hash = '#/parametres'")
            page.wait_for_selector("#form-parametres [name=pannes_recurrentes_seuil]")
            self.assertEqual(page.input_value("#form-parametres [name=pannes_recurrentes_seuil]"), "3")
            self.assertEqual(page.input_value("#form-parametres [name=pannes_recurrentes_jours]"), "30")
            page.fill("#form-parametres [name=pannes_recurrentes_seuil]", "5")
            page.click("#form-parametres button[type=submit]")
            page.wait_for_function("() => document.getElementById('toast').textContent.includes('Paramètres enregistrés')")
            valeurs = {l["cle"]: l["valeur"].lstrip("'") for l in lire_brut(serveur.dossier / "parametres.csv")}
            self.assertEqual(valeurs.get("pannes_recurrentes_seuil"), "5")
            page.evaluate("location.hash = '#/accueil'")
            page.wait_for_selector("#bento-recurrentes")
            self.assertEqual(page.locator("#bento-recurrente-" + self.machine).count(), 0)

    def test_technicien_bandeau_sur_l_ot_ouvert(self):
        page = self.page
        with ServeurPrevo(source=self.copie) as serveur:
            self.ouvrir(serveur, "technicien", "#/ot/OT-2026-0903", technicien_id=self.technicien)
            bandeau = page.wait_for_selector(".ot-bandeau-etat .pannes-recurrentes")
            # Comptée jusqu'au jour de la demande de l'OT (hier) : 3 pannes
            self.assertIn("3 pannes sur %s en 30 jours" % self.repere, bandeau.inner_text())
            liens = page.eval_on_selector_all(".pannes-recurrentes-liste a", "l => l.map(a => a.getAttribute('href'))")
            self.assertEqual(liens, ["#/ot/OT-2026-0902", "#/ot/OT-2026-0901"])
            self.assertEqual(page.get_attribute(".pannes-recurrentes-historique", "href"), "#/equipement/" + self.machine)
            # OT clôturé : pas de bandeau
            page.evaluate("location.hash = '#/ot/OT-2026-0901'")
            page.wait_for_selector(".ot-onglets")
            self.assertEqual(page.locator(".pannes-recurrentes").count(), 0)


if __name__ == "__main__":
    unittest.main()
