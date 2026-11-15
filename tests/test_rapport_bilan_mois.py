"""Bilan mensuel du patron (lot 1 ergonomie, T519, A6) : ce qui manque est nommé avec l'endroit où le renseigner, ce qui
se calcule sans réglage est affiché, le mois en cours (et le premier mois d'utilisation) se voit sans être figé.

Application complète en mode démo (file://), horloge au 20/11/2026, données remplacées par un mois d'essai calculé à
la main (novembre 2026, premier OT le 03/11) :
    machines   PI-01, PI-02, CP-01 : ni heures de fonctionnement par jour, ni coût d'une heure d'arrêt, ni valeur de
               remplacement ;
    équipe     Hugo Martin 45 €/h, Karim Benali sans taux horaire ; magasin : FLX-HP 38,50 €, JT-12 sans prix ;
    OT         OT-1 PI-01 panne avec arrêt de 1,5 h (Hugo 1,5 h, 1 flexible) ; OT-2 PI-01 correctif sans arrêt (Karim
               2 h, 2 joints) ; OT-3 CP-01 correctif sans arrêt (Hugo 0,5 h, Karim 0,5 h) ; OT-4 PI-02 préventif (Hugo 1 h).
    À la main  1 panne, 1,5 h d'arrêt, MTTR 1,5 h ; coût chiffré 3 h × 45 + 38,50 = 173,50 € (« 174 € »), partiel :
               2,5 h sans taux, 1 pièce (2 joints) sans prix ; préventif 1 / 5,5 h = 18,2 % ; disponibilité : à compléter
               (D35 : aucune valeur par défaut) ; activité : 3 correctifs (1 avec arrêt), 4 OT clôturés, 5,5 h.
Familles :
    règles     le tableau de bord compte les pannes, la durée d'arrêt et le MTTR de toutes les machines, même sans heures
               par jour (avant : 0 panne, 0 h — échoue sur la 2.2.0-beta.1) ; manquesCout ; activite ;
    rapport    « à compléter », coût « Partiel : … » (jamais un total exact), « non chiffré » au lieu de « 0 € », lignes
               « Ce qui manque » avec l'écran où renseigner, activité du mois, jetons de l'IA sans coût partiel ;
    mois       mois en cours provisoire (jamais figé, rien d'écrit), premier mois d'utilisation proposé une fois passé,
               « Voir le bilan » ouvre la page sans rien enregistrer.

Lancer depuis la racine du projet (navigateur : au travers du verrou) :
    py -X utf8 -m unittest discover -s tests -p "test_rapport_bilan_mois.py" -v
"""
import html
import unittest

from commun import CasNavigateur, attendre_pret, url_fichier
from commun import preregler_profil as _preregler_profil

# L30 (T544) : le tableau de bord replie ses familles d'office (état gardé sur le poste) ; ces tests lisent tous les
# chiffres et graphiques : familles dépliées sur ce poste, avant tout chargement.
DEPLIER_FAMILLES_JS = ("try { localStorage.setItem('prevo.indicateurs.familles', JSON.stringify(['fiabilite', 'preventif',"
                       " 'retards', 'couts', 'heures', 'equipements'])); } catch (e) { /* stockage refusé */ }")


def preregler_profil(contexte, *arguments, **options):
    _preregler_profil(contexte, *arguments, **options)
    contexte.add_init_script(DEPLIER_FAMILLES_JS)


CLOS = "Clôturé techniquement"


def csv(entete, lignes):
    return "\r\n".join([entete] + list(lignes)) + "\r\n"


TABLES = {
    "localisations": csv("id;libelle;parent_id;type", ["LOC-0001;Usine;;site", "LOC-0002;Injection;LOC-0001;atelier"]),
    "equipements": csv("id;repere;designation;criticite;statut;localisation_id;actif", [
        "EQ-0001;PI-01;Presse à injecter 1;A;en service;LOC-0002;1",
        "EQ-0002;PI-02;Presse à injecter 2;B;en service;LOC-0002;1",
        "EQ-0003;CP-01;Compresseur;B;en service;LOC-0002;1"]),
    "techniciens": csv("id;nom;prenom;taux_horaire;actif", ["TEC-0001;Martin;Hugo;45;1", "TEC-0002;Benali;Karim;;1"]),
    "articles": csv("id;reference;designation;unite;stock;prix_unitaire;actif", [
        "ART-0001;FLX-HP;Flexible haute pression;u;'5;38.50;1", "ART-0002;JT-12;Joint torique 12;u;'20;;1"]),
    "ordres_travail": csv("id;di_id;equipement_id;type;statut;titre;date_creation;date_debut;date_fin;arret_production;duree_arret_h;technicien_id", [
        "OT-2026-0001;;EQ-0001;correctif immédiat;%s;Fuite flexible;2026-11-03 08:00;2026-11-03 08:15;2026-11-03 10:00;1;1.5;TEC-0001" % CLOS,
        "OT-2026-0002;;EQ-0001;correctif différé;%s;Bavures, joint;2026-11-04 09:00;2026-11-05 08:00;2026-11-05 10:00;0;;TEC-0002" % CLOS,
        "OT-2026-0003;;EQ-0003;correctif immédiat;%s;Pression basse;2026-11-10 07:30;2026-11-10 08:00;2026-11-10 09:00;0;;TEC-0001" % CLOS,
        "OT-2026-0004;;EQ-0002;préventif systématique;%s;Visite mensuelle;2026-11-06 07:00;2026-11-06 07:00;2026-11-06 08:00;0;;TEC-0001" % CLOS]),
    "ot_temps": csv("id;ot_id;technicien_id;date;heures", [
        "OTT-000001;OT-2026-0001;TEC-0001;2026-11-03;1.5",
        "OTT-000002;OT-2026-0002;TEC-0002;2026-11-05;2",
        "OTT-000003;OT-2026-0003;TEC-0001;2026-11-10;0.5",
        "OTT-000004;OT-2026-0003;TEC-0002;2026-11-10;0.5",
        "OTT-000005;OT-2026-0004;TEC-0001;2026-11-06;1"]),
    "mouvements_stock": csv("id;date;type;article_id;quantite;ot_id", [
        "MVT-000001;2026-11-03 09:00;sortie;ART-0001;1;OT-2026-0001",
        "MVT-000002;2026-11-05 09:00;sortie;ART-0002;2;OT-2026-0002"]),
}


def blancs(texte):
    return html.unescape(texte).replace(" ", " ").replace(" ", " ")


class CasBilan(CasNavigateur):

    HORLOGE = "2026-11-20T09:00:00"

    def ouvrir(self, tables=None):
        self.contexte.clock.set_fixed_time(self.HORLOGE)
        preregler_profil(self.contexte, "responsable", "Responsable")
        self.page.goto(url_fichier("index.html"))
        self.page.click("#btn-demo")
        attendre_pret(self.page)
        self.page.evaluate("""async (tables) => {
          Donnees.initialiser(StockageDemo.creer(tables), { poste: 'Poste test', profil: 'Responsable test' });
          await Donnees.chargerTout();
        }""", tables or TABLES)

    def setUp(self):
        super().setUp()
        self.ouvrir()

    def donnees(self, mois="2026-11"):
        return self.page.evaluate("""(mois) => { const r = Rapport.donnees(mois, Donnees.aujourdhui(), '2026-11-20 09:00');
            return Object.assign({}, r, { phrases: Rapport.interne.phrasesActivite(r.activite), jetons: Rapport.jetonsCommentaire(r) }); }""", mois)

    @staticmethod
    def tuile(r, cle):
        return [t for t in r["tuiles"] if t["cle"] == cle][0]


class TestReglesBilan(CasBilan):

    def test_duree_d_arret_et_pannes_sans_heures_par_jour(self):
        g = self.page.evaluate("""() => { const g = Indicateurs.global(Indicateurs.periodeDuMois('2026-11'), {}, '2026-11-20');
            return { pannes: g.pannes.valeur, arret: g.dureeArret.valeur, arretEffectif: g.dureeArret.effectif, mttr: g.mttr.valeur,
                     disponibilite: g.disponibilite.valeur, mtbf: g.mtbf.valeur, perimetre: g.pannesDuPerimetre ? g.pannesDuPerimetre.valeur : null }; }""")
        # Avant T519 : 0 panne, 0 h d'arrêt, MTTR « aucune panne » (pannes limitées aux machines aux heures connues).
        self.assertEqual((g["pannes"], g["arret"], g["arretEffectif"], g["mttr"]), (1, 1.5, 1, 1.5))
        self.assertIsNone(g["disponibilite"])          # D35 : sans heures par jour, jamais de valeur par défaut
        self.assertIsNone(g["mtbf"])
        self.assertEqual(g["perimetre"], 0)

    def test_disponibilite_sur_les_machines_renseignees_seulement(self):
        # PI-02 a ses heures (8 h × 30 j = 240 h), sans panne : disponibilité 100 % sur PI-02 ; la panne de PI-01 compte
        # dans le nombre de pannes et la durée d'arrêt, pas dans la disponibilité.
        self.page.evaluate("""async () => { await Donnees.modifier('equipements', (lignes) => {
            lignes.find((e) => e.id === 'EQ-0002').heures_fonct_jour = '8'; }); }""")
        g = self.page.evaluate("""() => { const g = Indicateurs.global(Indicateurs.periodeDuMois('2026-11'), {}, '2026-11-20');
            return [g.tempsRequis.valeur, g.disponibilite.valeur, g.pannes.valeur, g.dureeArret.valeur, g.pannesDuPerimetre.valeur]; }""")
        self.assertEqual(g, [240, 1, 1, 1.5, 0])

    def test_manques_du_cout_et_activite(self):
        m = self.page.evaluate("""() => { const m = Indicateurs.manquesCout(Indicateurs.periodeDuMois('2026-11'));
            return { techniciens: m.techniciens.map((t) => [t.technicienId, t.heures]), articles: m.articles.map((a) => [a.articleId, a.quantite]), complet: m.complet }; }""")
        self.assertEqual(m, {"techniciens": [["TEC-0002", 2.5]], "articles": [["ART-0002", 2]], "complet": False})
        a = self.page.evaluate("() => Indicateurs.activite(Indicateurs.periodeDuMois('2026-11'))")
        self.assertEqual((a["correctifs"], a["correctifsAvecArret"], a["clotures"], a["cloturesCorrectifs"], a["cloturesPreventifs"], a["ouverts"]),
                         (3, 1, 4, 3, 1, 0))
        self.assertEqual(a["heures"], {"correctif": 4.5, "preventif": 1, "autres": 0, "total": 5.5})
        self.assertEqual([(l["equipementId"], l["n"], l["avecArret"]) for l in a["parMachine"]], [("EQ-0001", 2, 1), ("EQ-0003", 1, 0)])
        # Un 0 saisi est une valeur : rien ne manque plus.
        self.page.evaluate("""async () => {
            await Donnees.modifier('techniciens', (l) => { l.find((t) => t.id === 'TEC-0002').taux_horaire = '0'; });
            await Donnees.modifier('articles', (l) => { l.find((t) => t.id === 'ART-0002').prix_unitaire = '0'; }); }""")
        self.assertTrue(self.page.evaluate("() => Indicateurs.manquesCout(Indicateurs.periodeDuMois('2026-11')).complet"))


class TestTableauDeBord(CasBilan):

    def test_duree_d_arret_et_cout_partiel_au_tableau_de_bord(self):
        self.page.evaluate("() => { location.hash = '#/indicateurs?periode=mois'; }")
        bandeau = self.page.locator("#contenu .indicateurs-resultats")         # L30 : instruments rangés par famille
        bandeau.locator('[data-indicateur="cout"]').wait_for()
        arret = blancs(bandeau.locator('[data-indicateur="duree-arret"]').inner_text())
        self.assertIn("1 h 30", arret)                                    # avant T519 : « 0,0 h », « 0 panne avec une durée »
        self.assertIn("1 panne avec une durée", arret)
        cout = blancs(bandeau.locator('[data-indicateur="cout"]').inner_text())
        self.assertIn("173,50 €", cout)
        self.assertIn("Partiel : 2 h 30 sans taux horaire (Paramètres ou Équipe), 1 pièce sans prix (Magasin)", cout)


class TestRapportBilan(CasBilan):

    def test_tuiles_a_completer_et_cout_partiel(self):
        r = self.donnees()
        dispo, cout = self.tuile(r, "disponibilite"), self.tuile(r, "cout")
        self.assertEqual(dispo["texteValeur"], "à compléter")
        self.assertIn("heures de fonctionnement par jour", dispo["precision"])
        self.assertIn("Parc", dispo["precision"])
        self.assertEqual(blancs(cout["texteValeur"]), "174 €")
        self.assertEqual(blancs(cout["precision"]), "Partiel : 2 h 30 sans taux horaire, 1 pièce sans prix")
        self.assertTrue(cout["partiel"])
        self.assertNotIn("cout_du_mois", r["jetons"])                       # l'IA ne cite jamais un coût partiel
        self.assertIn("part_preventif", r["jetons"])
        self.assertEqual(blancs(self.tuile(r, "partPreventif")["texteValeur"]), "18,2 %")

    def test_ce_qui_manque_et_ou_le_renseigner(self):
        lignes = {l["libelle"]: (blancs(l["raison"]), l.get("ou")) for l in self.donnees()["nonCalculables"]}
        self.assertEqual(lignes["Coût de main-d'œuvre non chiffré"],
                         ("taux horaire non renseigné pour Karim Benali (2 h 30)",
                          "Paramètres › Taux horaire moyen du service, ou Équipe › fiche du technicien › Taux horaire"))
        self.assertEqual(lignes["Pièces sorties sans prix"], ("prix non renseigné pour JT-12 (2)", "Magasin › fiche de l'article › Prix unitaire"))
        self.assertEqual(lignes["Équipements hors disponibilité"][1], "Parc › fiche de la machine › Heures de fonctionnement par jour")
        self.assertEqual(lignes["Coût de l'arrêt — non chiffré"], ("PI-01 (1 h 30 d'arrêt)", "Parc › fiche de la machine › Coût d'une heure d'arrêt"))
        self.assertNotIn("Disponibilité", lignes)                            # dite une fois, par les machines sans heures

    def test_sans_aucun_taux_ni_prix_jamais_zero_euro(self):
        self.page.evaluate("""async () => {
            await Donnees.modifier('techniciens', (l) => { l.forEach((t) => { t.taux_horaire = ''; }); });
            await Donnees.modifier('articles', (l) => { l.forEach((a) => { a.prix_unitaire = ''; }); }); }""")
        cout = self.tuile(self.donnees(), "cout")
        self.assertIsNone(cout["valeur"])
        self.assertEqual(cout["texteValeur"], "non chiffré")
        self.assertEqual(blancs(cout["precision"]), "5 h 30 sans taux horaire, 2 pièces sans prix")
        page = blancs(self.page.evaluate("() => Rapport.html('2026-11', { apercu: true })"))
        bloc = page.split('data-cle="cout">')[1].split('data-cle="partPreventif"')[0]
        self.assertNotIn("0 €", bloc)
        self.assertIn("non chiffré", bloc)

    def test_ligne_vers_indicateurs_en_bas_du_bilan(self):
        """T559 (P08) : une ligne en bas du bilan renvoie au détail de l'écran Indicateurs ; texte simple dans le document
        (le bilan est un document isolé : ni script ni lien vers Prévo), imprimé comme enregistré."""
        page = blancs(self.page.evaluate("() => Rapport.html('2026-11', { apercu: true })"))
        ligne = '<p class="pied">Le détail par machine, atelier et technicien est dans Indicateurs.</p>'
        self.assertIn(ligne, page)
        self.assertLess(page.index("<main"), page.index(ligne))
        self.assertEqual(page.count(ligne), 1)

    def test_activite_du_mois_et_mois_en_cours_dans_la_page(self):
        r = self.donnees()
        self.assertEqual(r["etat"], {"provisoire": True, "auJour": "2026-11-20", "depuis": "2026-11-03"})
        self.assertEqual([blancs(p) for p in r["phrases"]], [
            "3 correctifs déclarés (1 avec arrêt de production)",
            "4 OT clôturés, dont 1 en préventif",
            "5 h 30 passées (4 h 30 en correctif, 1 h en préventif)",
            "1 h 30 d'arrêt saisie sur 1 panne",
            "correctifs par machine : PI-01 (2), CP-01 (1)",
            "0 OT en retard au 20/11/2026",                                      # L30 (T544) : deux lignes en plus
            "délai de prise en charge : rien à mesurer ce mois-ci (aucun OT démarré avec une priorité)"])
        page = blancs(self.page.evaluate("() => Rapport.html('2026-11', { apercu: true })"))
        self.assertIn("Mois en cours : chiffres provisoires au 20/11/2026.", page)
        self.assertIn("Premier mois d'utilisation : chiffres depuis le 03/11/2026", page)
        self.assertIn("Bilan affiché par Prévo, non enregistré", page)
        self.assertNotIn("Rapport figé par Prévo", page)
        self.assertIn('<p class="activite"><b>Activité du mois :</b> 3 correctifs déclarés', page)
        self.assertIn("<h2>Ce qui manque, et où le renseigner</h2>", page)
        self.assertIn("— à renseigner : Paramètres › Taux horaire moyen du service, ou Équipe › fiche du technicien › Taux horaire</li>", page)
        self.assertIn("MTTR : 1 h 30", page)
        self.assertIn("Mois en cours : chiffres provisoires au 20/11/2026.", blancs(r["courriel"]["corps"]))
        for interdit in ("NaN", "Infinity", "undefined", "null"):
            self.assertNotIn(interdit, page)



class TestMoisTermine(CasBilan):

    HORLOGE = "2027-01-04T09:00:00"

    def test_un_mois_termine_et_couvert_n_a_ni_mention_provisoire_ni_premier_mois(self):
        r = self.donnees("2026-12")
        self.assertEqual(r["etat"], {"provisoire": False, "auJour": "2027-01-04", "depuis": ""})
        self.assertEqual(r["phrases"], ["Aucune intervention saisie ce mois-ci", "0 OT en retard au 04/01/2027",
                                         "délai de prise en charge : rien à mesurer ce mois-ci (aucun OT démarré avec une priorité)"])


class TestMoisDuBilan(CasBilan):

    def test_le_mois_en_cours_ne_se_fige_jamais(self):
        message = self.page.evaluate("() => Rapport.figer('2026-11').then(() => 'figé', (e) => e.message)")
        self.assertEqual(message, "Mois pas encore terminé (novembre 2026) : son bilan est provisoire et ne s'enregistre pas. "
                                  "Affichez-le avec « Voir le bilan ».")
        self.assertEqual(self.page.evaluate("() => Rapport.rapportsFiges()"), [])

    def test_onglet_voir_le_bilan_du_mois_en_cours_sans_rien_enregistrer(self):
        self.page.evaluate("() => { location.hash = '#/indicateurs?onglet=rapports'; }")
        choix = self.page.locator("#rapports-apercu-mois option")
        self.page.locator("#rapports-apercu-mois").wait_for()
        self.assertEqual(choix.all_inner_texts(), ["novembre 2026 (en cours)"])
        self.assertIn("Aucun mois complet", self.page.inner_text(".rapports-figer"))     # rien à figer : règle inchangée
        with self.page.expect_popup() as attente:
            self.page.click(".rapports-apercu-formulaire button[type=submit]")
        fenetre = attente.value
        fenetre.wait_for_load_state()
        texte = blancs(fenetre.frame_locator("iframe").locator("body").inner_text())
        self.assertIn("Mois en cours : chiffres provisoires au 20/11/2026.", texte)
        self.assertIn("Activité du mois", texte)
        self.assertEqual(self.page.evaluate("() => Rapport.rapportsFiges()"), [])



class TestPremierMoisPasse(CasBilan):

    HORLOGE = "2026-12-04T09:00:00"

    def test_premier_mois_d_utilisation_visible_une_fois_passe(self):
        self.page.evaluate("() => { location.hash = '#/indicateurs?onglet=rapports'; }")
        choix = self.page.locator("#rapports-apercu-mois option")
        self.page.locator("#rapports-apercu-mois").wait_for()
        self.assertEqual(choix.all_inner_texts(), ["décembre 2026 (en cours)", "novembre 2026 (premier mois d'utilisation)"])
        r = self.donnees("2026-11")
        self.assertEqual(r["etat"], {"provisoire": False, "auJour": "2026-12-04", "depuis": "2026-11-03"})
        page = blancs(self.page.evaluate("() => Rapport.html('2026-11', { apercu: true })"))
        self.assertIn("Premier mois d'utilisation : chiffres depuis le 03/11/2026", page)
        self.assertNotIn("Mois en cours", page)


if __name__ == "__main__":
    unittest.main()
