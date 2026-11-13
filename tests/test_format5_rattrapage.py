"""Rattrapage des demandes au passage au format 5 (T526, A4 du lot 1 ergonomie). Sans navigateur.

    py -X utf8 -m unittest discover -s tests -p "test_format5_rattrapage.py" -v

Avant le format 5, une demande restait « Acceptée » quoi que devienne son OT. Au passage 4→5, une demande « Acceptée »
ou « Regroupée » rattachée à un OT (demandes.ot_id) prend le statut que Demandes.suivreOt lui aurait donné :
  - OT En cours ou En attente → « En cours » (retour vide) ;
  - OT clôturé techniquement ou administrativement → « Réparée », date_reparation = date de fin de l'OT (à défaut sa
    date de clôture technique, puis administrative), repare_par = PRÉNOM du technicien de l'OT (vide sans technicien),
    mot_technicien vide ;
  - OT Créé, Préparé, Planifié, Annulé, OT absent, demande Nouvelle, Refusée, Différée : inchangée.
Vérifié sur une petite base au format 4 (données fictives, écrite dans un dossier temporaire) :
  1. serveur.py au démarrage (migrer_donnees_au_demarrage) : sauvegarde avant-format-v5, demandes.csv rattrapé, un
     second démarrage n'écrit rien ; l'étape 4→5 (migrer_tables) rejouée sur sa sortie ne change plus rien ;
  2. js/formats.js (Formats.migrer, chemin de l'import d'un ZIP) et js/donnees.js (Donnees.migrerAuFormatCourant,
     chemin du mode dossier et de la démo ; ici avec StockageDemo sous Node) : les mêmes valeurs que le serveur ;
     rejoué, rien ne change ;
  3. la règle de Formats.suiviDesDemandes est celle de Demandes.statutSelonOt (js/modules/demandes-retour.js) pour
     tous les statuts d'OT.
"""
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent


def charger_serveur():
    specification = importlib.util.spec_from_file_location("serveur_prevo_t526", RACINE / "serveur.py")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


serveur = charger_serveur()

# Petite base au format 4 : (id, statut, di_id, technicien_id, date_fin, date_cloture_tech, date_cloture_admin)
TECHNICIENS = [("TEC-0001", "Moreau", "Julien"), ("TEC-0002", "Benali", "Karim"), ("TEC-0003", "Duval", "=Zoé")]
OTS = [
    ("OT-2026-0001", "Clôturé techniquement", "DI-2026-0001", "TEC-0002", "2026-11-10 14:10", "2026-11-10 15:00", ""),
    ("OT-2026-0002", "En cours", "DI-2026-0003", "TEC-0001", "", "", ""),
    ("OT-2026-0003", "En attente", "DI-2026-0004", "TEC-0001", "", "", ""),
    ("OT-2026-0004", "Annulé", "DI-2026-0005", "", "", "", ""),
    ("OT-2026-0005", "Planifié", "DI-2026-0006", "TEC-0001", "", "", ""),
    ("OT-2026-0006", "Clôturé administrativement", "DI-2026-0007", "", "", "2026-11-01 09:00", "2026-11-02 10:00"),
    ("OT-2026-0007", "Clôturé techniquement", "DI-2026-0008", "TEC-0003", "2026-11-05 08:00", "2026-11-05 09:00", ""),
    ("OT-2026-0008", "Créé", "DI-2026-0009", "", "", "", ""),
    ("OT-2026-0009", "Préparé", "DI-2026-0010", "TEC-0002", "", "", ""),
]
# (id, statut, ot_id) → (statut, date_reparation, repare_par) attendus après le passage
DEMANDES = [
    (("DI-2026-0001", "Acceptée", "OT-2026-0001"), ("Réparée", "2026-11-10 14:10", "Karim")),
    (("DI-2026-0002", "Regroupée", "OT-2026-0001"), ("Réparée", "2026-11-10 14:10", "Karim")),
    (("DI-2026-0003", "Acceptée", "OT-2026-0002"), ("En cours", "", "")),
    (("DI-2026-0004", "Acceptée", "OT-2026-0003"), ("En cours", "", "")),
    (("DI-2026-0005", "Acceptée", "OT-2026-0004"), ("Acceptée", "", "")),
    (("DI-2026-0006", "Acceptée", "OT-2026-0005"), ("Acceptée", "", "")),
    (("DI-2026-0007", "Acceptée", "OT-2026-0006"), ("Réparée", "2026-11-01 09:00", "")),
    (("DI-2026-0008", "Acceptée", "OT-2026-0007"), ("Réparée", "2026-11-05 08:00", "=Zoé")),
    (("DI-2026-0009", "Acceptée", "OT-2026-0008"), ("Acceptée", "", "")),
    (("DI-2026-0010", "Acceptée", "OT-2026-0009"), ("Acceptée", "", "")),
    (("DI-2026-0011", "Nouvelle", ""), ("Nouvelle", "", "")),
    (("DI-2026-0012", "Refusée", "OT-2026-0001"), ("Refusée", "", "")),
    (("DI-2026-0013", "Différée", "OT-2026-0002"), ("Différée", "", "")),
    (("DI-2026-0014", "Acceptée", "OT-2026-0099"), ("Acceptée", "", "")),
]
ATTENDU = {demande[0]: list(attendu) for demande, attendu in DEMANDES}


def ligne(colonnes, valeurs):
    return [valeurs.get(colonne, "") for colonne in colonnes]


def fichiers_au_format_4():
    """{table: octets} de la petite base au format 4 (écrits comme Prévo les écrit : ecrire_valeur_texte)."""
    texte = serveur.ecrire_valeur_texte
    colonnes = {table: serveur.colonnes_du_format(table, 4) for table in
                ("demandes", "ordres_travail", "techniciens", "parametres")}
    demandes = [ligne(colonnes["demandes"], {
        "id": ident, "date_heure": "2026-10-20 07:30", "demandeur": "Laure Petit", "equipement_id": "EQ-0001",
        "symptome": "Courroie qui patine", "impact": "arrêt", "statut": statut, "ot_id": ot})
        for (ident, statut, ot), _ in DEMANDES]
    ots = [ligne(colonnes["ordres_travail"], {
        "id": ident, "origine": "DI", "di_id": di, "equipement_id": "EQ-0001", "type": "correctif différé",
        "priorite": "P3", "statut": statut, "titre": "Courroie", "date_creation": "2026-10-20 08:00",
        "technicien_id": tec, "date_fin": fin, "date_cloture_tech": tech, "date_cloture_admin": admin})
        for ident, statut, di, tec, fin, tech, admin in OTS]
    techniciens = [ligne(colonnes["techniciens"], {"id": ident, "nom": nom, "prenom": texte(prenom), "actif": "1"})
                   for ident, nom, prenom in TECHNICIENS]
    return {
        "demandes": serveur.ecrire_tableau_csv(colonnes["demandes"], demandes),
        "ordres_travail": serveur.ecrire_tableau_csv(colonnes["ordres_travail"], ots),
        "techniciens": serveur.ecrire_tableau_csv(colonnes["techniciens"], techniciens),
        "parametres": serveur.ecrire_tableau_csv(colonnes["parametres"], [["version_schema", "'4"]]),
    }


def demandes_lues(octets):
    """id → [statut, date_reparation, repare_par, mot_technicien] (valeurs relues sans l'apostrophe de protection)."""
    entete, lignes = serveur.lire_csv_tolerant(octets)
    resultat = {}
    for cellules in lignes:
        valeurs = dict(zip(entete, cellules))
        resultat[valeurs["id"]] = [serveur.relire_valeur_texte(valeurs.get(c, ""))
                                   for c in ("statut", "date_reparation", "repare_par", "mot_technicien")]
    return resultat


HARNAIS = r"""
const vm = require('vm'), fs = require('fs'), path = require('path');
const RACINE = process.argv[process.argv.length - 1];
const ENTREE = JSON.parse(fs.readFileSync(0, 'utf8'));
const SCRIPTS = ['js/i18n.js', 'js/i18n/langues.js', 'js/i18n/fr.js', 'js/lib/papaparse.min.js', 'js/schema.js',
  'js/formats.js', 'js/donnees.js', 'js/stockage-demo.js', 'js/interface.js', null, 'js/modules/demandes-regles.js',
  'js/modules/demandes-retour.js'];
const APP = `var App = { estResponsable: () => true, estTechnicien: () => false, estDemandeur: () => false,
  profil: { type: 'responsable', nom: '' }, comptesExiges: () => false, session: null, raisonErreur: (e) => e.message,
  technicienSolo: () => '' };`;
(async () => {
  const stock = new Map();
  const c = { console: { log() {}, warn() {}, error() {}, info() {} }, setTimeout, clearTimeout, TextEncoder, TextDecoder,
    Blob, EventTarget, CustomEvent, Event, URL, URLSearchParams, Intl, structuredClone, queueMicrotask,
    crypto: require('crypto').webcrypto,
    localStorage: { getItem: (k) => (stock.has(k) ? stock.get(k) : null), setItem: (k, v) => stock.set(k, String(v)), removeItem: (k) => stock.delete(k) },
    navigator: { language: 'fr-FR', languages: ['fr-FR'], userAgent: 'node' },
    location: { protocol: 'file:', hash: '', search: '', href: 'file:///x' } };
  const el = () => new Proxy(function () {}, { get: (t, p) => (p === Symbol.toPrimitive ? () => '' : p === 'length' ? 0 : el()), apply: () => el(), set: () => true });
  c.document = { documentElement: { lang: 'fr', setAttribute() {}, getAttribute() { return 'fr'; }, dataset: {}, style: {} },
    addEventListener() {}, querySelector: () => null, querySelectorAll: () => [], createElement: () => el(), body: el(), head: el(), currentScript: null };
  c.window = c; c.self = c; c.globalThis = c; c.addEventListener = () => {}; c.matchMedia = () => ({ matches: false, addEventListener() {} });
  vm.createContext(c);
  for (const s of SCRIPTS) {
    if (s === null) vm.runInContext(APP, c, { filename: 'app-essai' });
    else vm.runInContext(fs.readFileSync(path.join(RACINE, s), 'utf8'), c, { filename: s });
  }
  const run = (code) => vm.runInContext(code, c);
  c.tables = ENTREE.tables;
  const r = {};
  const resume = `Object.fromEntries(Donnees.lignes('demandes').map((d) => [d.id, [d.statut, d.date_reparation, d.repare_par, d.mot_technicien]]))`;

  // 1. Formats.migrer sur la base entière (import d'un ZIP) : puis l'étape 4→5 rejouée sur sa sortie.
  run(`adaptateur = StockageDemo.creer(tables)`);
  await run(`Donnees.initialiser(adaptateur, { poste: 'P', profil: 'Responsable' }); Donnees.chargerTout()`);
  r.zip = run(`(() => {
    const base = { tables: {} };
    for (const t of ['demandes', 'ordres_travail', 'techniciens', 'parametres']) {
      base.tables[t] = { entete: Donnees.entete ? Donnees.entete(t) : Object.keys(Donnees.lignes(t)[0] || {}),
        lignes: Donnees.lignes(t).map((l) => Object.assign({}, l)) };
    }
    const migree = Formats.migrer(base, 4, Formats.courant).base;
    const rejouee = Formats.ETAPES[3].appliquer(migree);
    const dire = (b) => Object.fromEntries(b.tables.demandes.lignes.map((d) => [d.id, [d.statut, d.date_reparation, d.repare_par, d.mot_technicien]]));
    return { migree: dire(migree), rejouee: JSON.stringify(rejouee.tables) === JSON.stringify(migree.tables),
      seule: JSON.stringify(Formats.migrer({ tables: { demandes: base.tables.demandes } }, 4, 5).base.tables.demandes.lignes.map((d) => d.statut)) };
  })()`);

  // 2. Donnees.migrerAuFormatCourant (mode dossier et démo ; ici la démo, sans sauvegarde) ; puis un second appel.
  r.passage = await run(`Donnees.migrerAuFormatCourant()`);
  await run(`Donnees.rechargerTable('demandes')`);
  r.dossier = run(resume);
  r.second = await run(`Donnees.migrerAuFormatCourant()`);
  r.journal = run(`Donnees.lignes('journal').map((l) => l.table + ' ' + l.id_ligne + ' ' + l.action)`);

  // 3. Même règle que Demandes.statutSelonOt, pour chaque statut d'OT et chaque statut suivi de la demande.
  const STATUTS_OT = ['Créé', 'Préparé', 'Planifié', 'En cours', 'En attente', 'Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  r.regle = [];
  for (const statutOt of STATUTS_OT) {
    for (const statutDemande of ['Acceptée', 'Regroupée']) {
      const ot = { id: 'OT-1', statut: statutOt, di_id: 'DI-1', technicien_id: '' };
      const demande = { id: 'DI-1', statut: statutDemande, ot_id: 'OT-1' };
      const champs = run('Formats').suiviDesDemandes([ot], [])(demande);
      r.regle.push([statutOt, statutDemande, champs ? champs.statut : statutDemande, run('Demandes').statutSelonOt(ot, demande)]);
    }
  }
  process.stdout.write(JSON.stringify(r));
})().catch((e) => { process.stdout.write(JSON.stringify({ erreur: String(e && e.stack || e) })); });
"""


class TestRattrapageFormat5(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.fichiers = fichiers_au_format_4()

    def demarrer(self, dossier):
        config = serveur.Configuration(str(dossier), [])
        serveur.creer_dossiers(config)
        with mock.patch.object(serveur, "afficher"):
            return serveur.migrer_donnees_au_demarrage(config)

    def test_serveur_au_demarrage(self):
        with tempfile.TemporaryDirectory(prefix="prevo-t526-") as temporaire:
            dossier = Path(temporaire) / "donnees"
            dossier.mkdir()
            for table, octets in self.fichiers.items():
                (dossier / (table + ".csv")).write_bytes(octets)
            etat = self.demarrer(dossier)
            self.assertEqual((etat["base"], etat["migration"]), (5, "faite"))
            sauvegardes = [c.name for c in (dossier / "sauvegardes").iterdir()]
            self.assertEqual(len(sauvegardes), 1)
            self.assertTrue(sauvegardes[0].endswith("_avant-format-v5"))
            sauvegarde = dossier / "sauvegardes" / sauvegardes[0]
            self.assertEqual((sauvegarde / "demandes.csv").read_bytes(), self.fichiers["demandes"])
            apres = demandes_lues((dossier / "demandes.csv").read_bytes())
            self.assertEqual({ident: valeurs[:3] for ident, valeurs in apres.items()}, ATTENDU)
            self.assertEqual({valeurs[3] for valeurs in apres.values()}, {""})
            # Prénom protégé comme Prévo l'écrit (« '=Zoé »), relu « =Zoé »
            self.assertIn("'=Zoé".encode("utf-8"), (dossier / "demandes.csv").read_bytes())
            # Les autres colonnes d'origine sont intactes
            entete_avant, lignes_avant = serveur.lire_csv_tolerant(self.fichiers["demandes"])
            entete_apres, lignes_apres = serveur.lire_csv_tolerant((dossier / "demandes.csv").read_bytes())
            for avant, apres_ in zip(lignes_avant, lignes_apres):
                for position, colonne in enumerate(entete_avant):
                    if colonne != "statut":
                        self.assertEqual(apres_[entete_apres.index(colonne)], avant[position], colonne)
            self.assertEqual((dossier / "ordres_travail.csv").read_bytes()[:3], b"\xef\xbb\xbf")
            # Second démarrage : rien à faire, aucun octet écrit
            avant_second = {c.relative_to(dossier).as_posix(): c.read_bytes()
                            for c in sorted(dossier.rglob("*")) if c.is_file()}
            etat = self.demarrer(dossier)
            self.assertEqual(etat["migration"], "rien")
            self.assertEqual({c.relative_to(dossier).as_posix(): c.read_bytes()
                              for c in sorted(dossier.rglob("*")) if c.is_file()}, avant_second)

    def test_serveur_demandes_deja_completees_reprise_rattrapee(self):
        """Passage interrompu (demandes.csv déjà réécrit au format 5 sans rattrapage, version_schema encore à 4) : le
        démarrage suivant rattrape quand même les demandes."""
        with tempfile.TemporaryDirectory(prefix="prevo-t526-") as temporaire:
            dossier = Path(temporaire) / "donnees"
            dossier.mkdir()
            for table, octets in self.fichiers.items():
                (dossier / (table + ".csv")).write_bytes(octets)
            entete, lignes = serveur.lire_csv_tolerant(self.fichiers["demandes"])
            completee = serveur.table_au_format_courant("demandes", {"entete": entete, "lignes": lignes, "format": 4})
            (dossier / "demandes.csv").write_bytes(serveur.ecrire_tableau_csv(*completee))
            self.assertEqual(self.demarrer(dossier)["migration"], "faite")
            apres = demandes_lues((dossier / "demandes.csv").read_bytes())
            self.assertEqual({ident: valeurs[:3] for ident, valeurs in apres.items()}, ATTENDU)

    def test_etape_pure_idempotente(self):
        base = {}
        for table, octets in self.fichiers.items():
            entete, lignes = serveur.lire_csv_tolerant(octets)
            base[table] = {"entete": entete, "lignes": [dict(zip(entete, cellules)) for cellules in lignes]}
        une, _, _ = serveur.migrer_tables(base, 4, 5)
        self.assertEqual({l["id"]: [l["statut"], l["date_reparation"], serveur.relire_valeur_texte(l["repare_par"])]
                          for l in une["demandes"]["lignes"]}, ATTENDU)
        self.assertEqual(serveur.ETAPES_FORMAT[3].appliquer(une), une)
        # Une table seule (sonde de table_au_format_courant) : aucune demande ne change
        seule, _, _ = serveur.migrer_tables({"demandes": base["demandes"]}, 4, 5)
        self.assertEqual([l["statut"] for l in seule["demandes"]["lignes"]], [d[0][1] for d in DEMANDES])

    @unittest.skipUnless(shutil.which("node"), "Node.js absent")
    def test_navigateur_memes_valeurs_que_le_serveur(self):
        tables = {table: octets.decode("utf-8-sig") for table, octets in self.fichiers.items()}
        tables["journal"] = "id;date_heure;poste;profil;table;id_ligne;action\r\n"
        sortie = subprocess.run(["node", "-e", HARNAIS, str(RACINE)], input=json.dumps({"tables": tables}),
                                capture_output=True, text=True, encoding="utf-8", timeout=120)
        r = json.loads(sortie.stdout or "{}")
        self.assertNotIn("erreur", r, r.get("erreur"))
        attendu = {ident: valeurs + [""] for ident, valeurs in ATTENDU.items()}
        self.assertEqual(r["zip"]["migree"], attendu)
        self.assertTrue(r["zip"]["rejouee"])
        self.assertEqual(json.loads(r["zip"]["seule"]), [d[0][1] for d in DEMANDES])
        self.assertTrue(r["passage"]["misAJour"])
        self.assertIn("demandes", r["passage"]["tables"])
        self.assertEqual(r["dossier"], attendu)
        self.assertFalse(r["second"]["misAJour"])
        # Une ligne de journal pour le passage, aucune par demande
        self.assertEqual([l for l in r["journal"] if l.startswith("demandes ")], [])
        self.assertEqual(len([l for l in r["journal"] if "passage au format 5 du fichier" in l]), 1)
        self.assertEqual(len(r["regle"]), 16)
        for statut_ot, statut_demande, rattrape, selon_ot in r["regle"]:
            with self.subTest(ot=statut_ot, demande=statut_demande):
                self.assertEqual(rattrape, selon_ot)


if __name__ == "__main__":
    unittest.main()
