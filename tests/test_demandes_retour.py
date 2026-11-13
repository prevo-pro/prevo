"""Retour vers l'opérateur (T517, A4 du lot 1 ergonomie ; format 5 des données). Sans navigateur.

    py -X utf8 -m unittest discover -s tests -p "test_demandes_retour.py" -v

Les scripts classiques de Prévo sont chargés sous Node (contexte vm), sur des tables d'essai en mémoire (StockageDemo) :
aucune donnée réelle. Ce qui est vérifié :
  1. le statut d'une demande suit son OT : « Acceptée » tant que l'OT est Créé, Préparé ou Planifié, « En cours » quand
     il démarre et pendant « En attente », « Réparée » à la clôture technique (date de fin, PRÉNOM du technicien, mot
     pour l'opérateur), rouvert → « En cours » et retour effacé, annulé → « Acceptée » (jamais dite réparée) ;
  2. toutes les demandes rattachées suivent (la regroupée aussi, et redevient « Regroupée » si l'OT est annulé) ; les
     autres (Nouvelle, autre OT) ne bougent pas ;
  3. « Clore » (clôture en une étape) : « Réparée » avec le mot ; la clôture administrative après la clôture technique
     ne réécrit pas le mot ;
  4. la transition aboutit même si demandes.csv ne peut pas être écrit (avertissement seulement) ;
  5. le mot est réduit à une ligne de 300 caractères ; le prénom seul, jamais le nom ni l'identifiant du technicien
     (OT sans technicien : le prénom du technicien qui clôture) ;
  6. textes pour l'opérateur (« Reçue », « Réparée le 13/11 à 14 h 10 par Karim ») et « Vos dernières demandes » : la
     même règle que l'accueil du demandeur (nom du profil), 3 au plus, 90 jours au plus.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

HARNAIS = r"""
const vm = require('vm'), fs = require('fs'), path = require('path');
const RACINE = process.argv[2];
const SCRIPTS = ['js/i18n.js', 'js/i18n/langues.js', 'js/i18n/fr.js', 'js/lib/papaparse.min.js', 'js/schema.js',
  'js/donnees.js', 'js/stockage-demo.js', 'js/interface.js', null, 'js/modules/demandes-regles.js',
  'js/modules/demandes-retour.js', 'js/modules/ordres-regles.js', 'js/modules/ordres-codes.js', 'js/modules/ordres-ecritures.js'];
const APP = `var profil = 'responsable'; var nomProfil = ''; var technicienProfil = '';
  var App = { estResponsable: () => profil === 'responsable', estTechnicien: () => profil === 'technicien',
    estDemandeur: () => profil === 'demandeur', get profil() { return { type: profil, nom: nomProfil, technicienId: technicienProfil }; },
    comptesExiges: () => false, session: null, raisonErreur: (e) => e.message, technicienSolo: () => '' };`;
const csv = (entete, lignes) => [entete].concat(lignes).join('\r\n') + '\r\n';
const DEMANDES = 'id;date_heure;demandeur;equipement_id;symptome;impact;statut;motif_decision;date_decision;ot_id;mot_technicien;date_reparation;repare_par';
const ENTETE_OT = 'id;statut;type;priorite;origine;di_id;equipement_id;technicien_id;date_prevue;date_creation;titre;date_debut;date_fin;cause_code;remede_code;compte_rendu;remise_service;motif_attente';
// OT prêt à être clôturé (RG4) dès qu'il est En cours : date de fin, codes, compte rendu, remise en service, temps.
const OT = (id, statut, di) => [id, statut, 'correctif différé', 'P3', 'DI', di, 'EQ-0001', 'TEC-0001', '2026-11-13',
  '2026-11-10 07:50', 'Courroie', '2026-11-10 08:00', '2026-11-10 14:10', 'C01', 'R01', 'Courroie usée remplacée par une neuve.', '1', ''].join(';');

async function contexte(ots, demandes, temps) {
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
  c.run = (code) => vm.runInContext(code, c);
  c.tables = {
    equipements: csv('id;repere;designation;statut;actif', ['EQ-0001;CV-01;Convoyeur;en service;1', 'EQ-0002;PO-01;Pompe;en service;1']),
    techniciens: csv('id;nom;prenom;actif', ['TEC-0001;Benali;Karim;1']),
    ordres_travail: csv(ENTETE_OT, ots),
    ot_temps: csv('id;ot_id;technicien_id;date;heures', temps || ['T-1;OT-2026-0001;TEC-0001;2026-11-13;1,5', 'T-2;OT-2026-0002;TEC-0001;2026-11-13;1']),
    demandes: csv(DEMANDES, demandes),
    parametres: csv('cle;valeur', ['cloture_une_etape;1']),
    journal: csv('id;date_heure;poste;profil;table;id_ligne;action', []),
  };
  c.adaptateur = c.run('StockageDemo.creer(tables)');
  const enregistrer = c.adaptateur.enregistrer.bind(c.adaptateur);
  c.panneDemandes = false;
  c.adaptateur.enregistrer = async (table, ...reste) => {
    if (table === 'demandes' && c.panneDemandes) throw new Error('demandes.csv verrouillé (ouvert dans Excel)');
    return enregistrer(table, ...reste);
  };
  await c.run(`Donnees.initialiser(adaptateur, { poste: 'P', profil: 'Responsable' }); Donnees.chargerTout()`);
  c.essai = async (code) => {
    try { return { rendu: await c.run(code) }; }
    catch (e) { return { refus: e.message, classe: e.name }; }
  };
  // Demandes relues sur le « disque » (pas le cache) : id → [statut, mot, date de réparation, réparé par].
  c.demandes = async () => {
    await c.run(`Donnees.rechargerTable('demandes')`);
    return c.run(`Object.fromEntries(Donnees.lignes('demandes').map((d) => [d.id, [d.statut, d.mot_technicien, d.date_reparation, d.repare_par]]))`);
  };
  c.statutOt = (id) => c.run(`Donnees.trouver('ordres_travail', '${id}').statut`);
  return c;
}
const D = (id, statut, ot, demandeur, date, equipement) => [id, date || '2026-11-13 07:30', demandeur || 'Laure Petit',
  equipement || 'EQ-0001', 'Courroie qui patine', 'arrêt', statut, '', '', ot || '', '', '', ''].join(';');
const BASE = [D('DI-2026-0001', 'Acceptée', 'OT-2026-0001'), D('DI-2026-0002', 'Regroupée', 'OT-2026-0001', 'Marc Roy'),
  D('DI-2026-0003', 'Nouvelle'), D('DI-2026-0004', 'Acceptée', 'OT-2026-0002')];
const CHANGER = (id, de, vers, complement) => `Ordres.changerStatut('${id}', '${de}', '${vers}', ${JSON.stringify(complement || {})})`;

(async () => {
  const r = {};

  // 1. Cycle complet : Planifié → En cours → En attente → En cours → Clôturé techniquement (mot) → rouvert → reclôturé
  //    → Clôturé administrativement.
  let c = await contexte([OT('OT-2026-0001', 'Planifié', 'DI-2026-0001'), OT('OT-2026-0002', 'Planifié', 'DI-2026-0004')], BASE);
  r.depart = await c.demandes();
  r.demarrer = await c.essai(CHANGER('OT-2026-0001', 'Planifié', 'En cours'));
  r.en_cours = await c.demandes();
  r.attente = await c.essai(CHANGER('OT-2026-0001', 'En cours', 'En attente', { motif_attente: 'Pièce : courroie' }));
  r.en_attente = await c.demandes();
  r.reprendre = await c.essai(CHANGER('OT-2026-0001', 'En attente', 'En cours'));
  const motLong = '  Courroie changée,\n vous pouvez   redémarrer. ' + 'x'.repeat(400);
  r.cloturer = await c.essai(CHANGER('OT-2026-0001', 'En cours', 'Clôturé techniquement', { mot_operateur: motLong }));
  r.reparee = await c.demandes();
  r.journal = c.run(`Donnees.lignes('journal').map((l) => l.table + ' ' + l.id_ligne + ' ' + l.action)`);
  r.rouvrir = await c.essai(CHANGER('OT-2026-0001', 'Clôturé techniquement', 'En cours'));
  r.rouverte = await c.demandes();
  r.recloturer = await c.essai(CHANGER('OT-2026-0001', 'En cours', 'Clôturé techniquement', { mot_operateur: 'Courroie changée, vous pouvez redémarrer' }));
  r.admin = await c.essai(CHANGER('OT-2026-0001', 'Clôturé techniquement', 'Clôturé administrativement'));
  r.apres_admin = await c.demandes();

  // 2. Annulation : En cours → En attente → Annulé : la demande n'est pas dite réparée (Acceptée / Regroupée).
  c = await contexte([OT('OT-2026-0001', 'En cours', 'DI-2026-0001')],
    [D('DI-2026-0001', 'En cours', 'OT-2026-0001'), D('DI-2026-0002', 'En cours', 'OT-2026-0001', 'Marc Roy')]);
  await c.essai(CHANGER('OT-2026-0001', 'En cours', 'En attente', { motif_attente: 'Pièce' }));
  r.annuler = await c.essai(CHANGER('OT-2026-0001', 'En attente', 'Annulé', { motif_annulation: 'Doublon' }));
  r.annulee = await c.demandes();

  // 3. « Clore » (clôture en une étape) avec le mot ; puis un OT sans demande : rien n'est écrit dans demandes.
  c = await contexte([OT('OT-2026-0001', 'En cours', 'DI-2026-0001'), OT('OT-2026-0003', 'En cours', '')], BASE,
    ['T-1;OT-2026-0001;TEC-0001;2026-11-13;1', 'T-3;OT-2026-0003;TEC-0001;2026-11-13;1']);
  r.clore = await c.essai(`Ordres.clore(Donnees.trouver('ordres_travail', 'OT-2026-0001'), { mot_operateur: 'Réglé, vous pouvez repartir.' })`);
  r.close = await c.demandes();
  r.statut_clos = c.statutOt('OT-2026-0001');
  const avant = c.run(`Donnees.lignes('journal').filter((l) => l.table === 'demandes').length`);
  r.sans_demande = await c.essai(CHANGER('OT-2026-0003', 'En cours', 'Clôturé techniquement'));
  r.sans_demande_journal = c.run(`Donnees.lignes('journal').filter((l) => l.table === 'demandes').length`) - avant;
  r.vient_demande = c.run(`[Demandes.champsMotOperateur(Donnees.trouver('ordres_travail', 'OT-2026-0001')).length,
    Demandes.champsMotOperateur(Donnees.trouver('ordres_travail', 'OT-2026-0003')).length]`);

  // 4. demandes.csv verrouillé : la transition aboutit, la demande ne suit pas, rien n'est levé.
  c = await contexte([OT('OT-2026-0001', 'Planifié', 'DI-2026-0001')], BASE);
  c.panneDemandes = true;
  r.panne = await c.essai(CHANGER('OT-2026-0001', 'Planifié', 'En cours'));
  r.panne_ot = c.statutOt('OT-2026-0001');
  c.panneDemandes = false;
  r.panne_demandes = await c.demandes();
  // Demande disparue entre-temps (ligne retirée à la main) : la transition aboutit aussi.
  c = await contexte([OT('OT-2026-0001', 'Planifié', 'DI-2026-0009')], [D('DI-2026-0003', 'Nouvelle')]);
  r.disparue = await c.essai(CHANGER('OT-2026-0001', 'Planifié', 'En cours'));

  // 5. Prénom inconnu (fiche technicien sans prénom) : repare_par vide, jamais le nom.
  c = await contexte([OT('OT-2026-0001', 'En cours', 'DI-2026-0001')], BASE);
  await c.run(`Donnees.modifier('techniciens', (l) => { l[0].prenom = ''; })`);
  await c.essai(CHANGER('OT-2026-0001', 'En cours', 'Clôturé techniquement'));
  r.sans_prenom = (await c.demandes())['DI-2026-0001'];
  // OT sans technicien, clôturé par un technicien (profil lié à TEC-0001) : son prénom.
  c = await contexte([OT('OT-2026-0001', 'En cours', 'DI-2026-0001').replace(';TEC-0001;', ';;')], BASE);
  c.run(`profil = 'technicien'; technicienProfil = 'TEC-0001'`);
  r.ot_sans_technicien = await c.essai(CHANGER('OT-2026-0001', 'En cours', 'Clôturé techniquement'));
  r.prenom_du_profil = (await c.demandes())['DI-2026-0001'];

  // 6. Textes pour l'opérateur et « Vos dernières demandes ».
  c = await contexte([], [
    D('DI-2026-0010', 'Réparée', 'OT-2026-0001', 'Laure Petit', '2026-11-12 08:00'),
    D('DI-2026-0011', 'Nouvelle', '', 'laure petit ', '2026-11-13 08:00'),
    D('DI-2026-0012', 'En cours', 'OT-2026-0002', 'Laure Petit', '2026-11-11 08:00'),
    D('DI-2026-0013', 'Acceptée', 'OT-2026-0003', 'Laure Petit', '2026-11-10 08:00'),
    D('DI-2026-0014', 'Nouvelle', '', 'Marc Roy', '2026-11-13 09:00'),
    D('DI-2026-0015', 'Nouvelle', '', 'Laure Petit', '2026-11-13 09:30', 'EQ-0002'),
    D('DI-2025-0001', 'Réparée', 'OT-2025-0001', 'Laure Petit', '2025-01-10 08:00')]);
  const aujourdhui = c.run(`Donnees.aujourdhui()`);
  r.aujourdhui = aujourdhui;
  r.phrases = c.run(`[
    Demandes.phraseReparee({ statut: 'Réparée', date_reparation: '2026-11-13 14:10', repare_par: 'Karim' }),
    Demandes.phraseReparee({ statut: 'Réparée', date_reparation: '2026-11-13 14:10', repare_par: '' }),
    Demandes.phraseReparee({ statut: 'Réparée', date_reparation: '', repare_par: 'Karim' }),
    Demandes.phraseSuivi({ statut: 'Acceptée' }), Demandes.phraseSuivi({ statut: 'En cours' }), Demandes.phraseSuivi({ statut: 'Nouvelle' })]`);
  r.libelles = c.run(`['Nouvelle', 'Acceptée', 'Regroupée', 'En cours', 'Réparée', 'Différée', 'Refusée'].map((s) => Demandes.libelleAtelier({ statut: s }))`);
  c.run(`profil = 'demandeur'; nomProfil = 'Laure Petit'`);
  r.dernieres = c.run(`Demandes.dernieresDemandes('EQ-0001').map((d) => d.id)`);
  c.run(`nomProfil = ''`);
  r.dernieres_sans_nom = c.run(`Demandes.dernieresDemandes('EQ-0001').length`);
  r.regle_pure = c.run(`[
    Demandes.statutSelonOt({ statut: 'Planifié', di_id: 'DI-1' }, { id: 'DI-1', statut: 'Acceptée' }),
    Demandes.statutSelonOt({ statut: 'En attente', di_id: 'DI-1' }, { id: 'DI-1', statut: 'Acceptée' }),
    Demandes.statutSelonOt({ statut: 'Clôturé administrativement', di_id: 'DI-1' }, { id: 'DI-2', statut: 'Regroupée' }),
    Demandes.statutSelonOt({ statut: 'Annulé', di_id: 'DI-1' }, { id: 'DI-1', statut: 'En cours' }),
    Demandes.statutSelonOt({ statut: 'Annulé', di_id: '' }, { id: 'DI-2', statut: 'En cours' })]`);

  process.stdout.write('RESULTAT ' + JSON.stringify(r) + '\n');
})().catch((e) => { process.stderr.write('ECHEC ' + (e && e.stack || e) + '\n'); process.exit(1); });
"""

MOT_ATTENDU = "Courroie changée, vous pouvez redémarrer. " + "x" * (300 - len("Courroie changée, vous pouvez redémarrer. "))


@unittest.skipUnless(shutil.which("node"), "Node absent : modules non chargés")
class RetourVersLOperateur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "harnais.js"
            script.write_text(HARNAIS, encoding="utf-8")
            fini = subprocess.run(["node", str(script), str(RACINE)], capture_output=True, encoding="utf-8", timeout=120)
        if fini.returncode != 0:
            raise AssertionError("harnais Node : " + fini.stderr[-2000:])
        ligne = [l for l in fini.stdout.splitlines() if l.startswith("RESULTAT ")][-1]
        cls.r = json.loads(ligne[len("RESULTAT "):])

    def test_le_statut_suit_l_ot_jusqu_a_reparee(self):
        r = self.r
        self.assertEqual(r["depart"]["DI-2026-0001"][0], "Acceptée")
        self.assertEqual(r["demarrer"].get("rendu"), "En cours", r["demarrer"])
        self.assertEqual(r["en_cours"]["DI-2026-0001"], ["En cours", "", "", ""])
        self.assertEqual(r["en_cours"]["DI-2026-0002"][0], "En cours")                  # la regroupée suit aussi
        self.assertEqual(r["en_attente"]["DI-2026-0001"][0], "En cours")                # En attente : « En cours »
        self.assertEqual(r["cloturer"].get("rendu"), "Clôturé techniquement", r["cloturer"])
        self.assertEqual(r["reparee"]["DI-2026-0001"], ["Réparée", MOT_ATTENDU, "2026-11-10 14:10", "Karim"])
        self.assertEqual(r["reparee"]["DI-2026-0002"], ["Réparée", MOT_ATTENDU, "2026-11-10 14:10", "Karim"])
        self.assertTrue(any(a.startswith("demandes DI-2026-0001 ") and "suit OT-2026-0001" in a for a in r["journal"]),
                        r["journal"])

    def test_les_autres_demandes_ne_bougent_pas(self):
        r = self.r
        for etape in ("en_cours", "reparee", "apres_admin"):
            self.assertEqual(r[etape]["DI-2026-0003"], ["Nouvelle", "", "", ""], etape)
            self.assertEqual(r[etape]["DI-2026-0004"], ["Acceptée", "", "", ""], etape)

    def test_rouvert_puis_clos_administrativement(self):
        r = self.r
        self.assertEqual(r["rouvrir"].get("rendu"), "En cours", r["rouvrir"])
        self.assertEqual(r["rouverte"]["DI-2026-0001"], ["En cours", "", "", ""])         # retour effacé
        self.assertEqual(r["recloturer"].get("rendu"), "Clôturé techniquement")
        self.assertEqual(r["admin"].get("rendu"), "Clôturé administrativement", r["admin"])
        # La clôture administrative ne réécrit pas le mot ni la date.
        self.assertEqual(r["apres_admin"]["DI-2026-0001"],
                         ["Réparée", "Courroie changée, vous pouvez redémarrer", "2026-11-10 14:10", "Karim"])

    def test_annule_jamais_dite_reparee(self):
        r = self.r
        self.assertEqual(r["annuler"].get("rendu"), "Annulé", r["annuler"])
        self.assertEqual(r["annulee"]["DI-2026-0001"], ["Acceptée", "", "", ""])
        self.assertEqual(r["annulee"]["DI-2026-0002"], ["Regroupée", "", "", ""])        # l'OT n'était pas le sien

    def test_clore_en_une_etape(self):
        r = self.r
        self.assertEqual(r["clore"].get("rendu"), "Clôturé administrativement", r["clore"])
        self.assertEqual(r["statut_clos"], "Clôturé administrativement")
        self.assertEqual(r["close"]["DI-2026-0001"], ["Réparée", "Réglé, vous pouvez repartir.", "2026-11-10 14:10", "Karim"])
        self.assertEqual(r["close"]["DI-2026-0004"][0], "Acceptée")
        self.assertEqual(r["sans_demande"].get("rendu"), "Clôturé techniquement", r["sans_demande"])
        self.assertEqual(r["sans_demande_journal"], 0)                                   # rien écrit dans demandes
        self.assertEqual(r["vient_demande"], [1, 0])                                      # champ du mot : OT de demande

    def test_la_transition_aboutit_meme_si_la_demande_ne_suit_pas(self):
        r = self.r
        self.assertEqual(r["panne"].get("rendu"), "En cours", r["panne"])
        self.assertEqual(r["panne_ot"], "En cours")
        self.assertEqual(r["panne_demandes"]["DI-2026-0001"][0], "Acceptée")
        self.assertEqual(r["disparue"].get("rendu"), "En cours", r["disparue"])

    def test_ot_sans_technicien_prenom_de_celui_qui_cloture(self):
        self.assertEqual(self.r["ot_sans_technicien"].get("rendu"), "Clôturé techniquement", self.r["ot_sans_technicien"])
        self.assertEqual(self.r["prenom_du_profil"][0::3], ["Réparée", "Karim"])

    def test_prenom_seul_jamais_le_nom(self):
        self.assertEqual(self.r["sans_prenom"][0], "Réparée")
        self.assertEqual(self.r["sans_prenom"][3], "")
        for etape in ("reparee", "close"):
            for valeurs in self.r[etape].values():
                self.assertNotIn("Benali", valeurs)
                self.assertNotIn("TEC-0001", valeurs)

    def test_textes_pour_l_operateur(self):
        r = self.r
        self.assertEqual(r["phrases"], ["Réparée le 13/11 à 14 h 10 par Karim", "Réparée le 13/11 à 14 h 10",
                                        "Réparée par Karim", "Acceptée : l'intervention est prévue.",
                                        "En cours : un technicien s'en occupe.", ""])
        self.assertEqual(r["libelles"], ["Reçue", "Acceptée", "Acceptée", "En cours", "Réparée", "Différée", "Refusée"])

    def test_vos_dernieres_demandes(self):
        r = self.r
        # Même règle que l'accueil du demandeur (nom du profil, casse et espaces ignorés) ; cette machine ; 3 au plus,
        # les plus récentes d'abord ; 90 jours au plus (DI-2025-0001 trop ancienne) ; rien sans nom de profil.
        if r["aujourdhui"] < "2027-02-01":
            self.assertEqual(r["dernieres"], ["DI-2026-0011", "DI-2026-0010", "DI-2026-0012"])
        self.assertNotIn("DI-2025-0001", r["dernieres"])
        self.assertNotIn("DI-2026-0014", r["dernieres"])
        self.assertNotIn("DI-2026-0015", r["dernieres"])
        self.assertEqual(r["dernieres_sans_nom"], 0)

    def test_regle_pure(self):
        self.assertEqual(self.r["regle_pure"], ["Acceptée", "En cours", "Réparée", "Acceptée", "Regroupée"])


if __name__ == "__main__":
    unittest.main()
