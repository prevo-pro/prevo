'use strict';
// Solo — le mode Solo sans la couche équipe (lot 1 ergonomie, B, T521 ; ARCHITECTURE.md §22.11 ; CDC D132). Rien ici ne
// vaut hors du mode Solo (App.modeSolo() : mode_solo = 1 dans parametres.csv et profil responsable) : en équipe, chaque
// fonction rend sans rien changer.
//   - OT neufs au nom du technicien seul : Solo.completerOt(ligne), appelé dans la mutation qui crée un OT (Ordres.creer,
//     Demandes.accepter, génération du préventif) : technicien_id = solo_technicien_id et une ligne de prises_en_charge
//     (Ordres.interne.noterPrise, A3).
//   - Demandes des opérateurs acceptées d'elles-mêmes : Solo.convertirDemandes() passe chaque demande « Nouvelle » sans
//     OT par Demandes.accepter, les mêmes écritures que le bouton « Accepter » (type et priorité déduits de l'impact ; OT
//     réutilisé s'il porte déjà ce di_id ; statut de la demande relu dans la mutation) : une seule conversion par demande,
//     même avec deux onglets ou deux appareils (le second trouve l'OT du premier, ou la demande déjà acceptée). Le
//     demandeur ne peut pas écrire d'OT (droits du serveur, inchangés) : la conversion se fait dans le navigateur du
//     technicien seul, à l'ouverture (Solo.auDemarrage), à l'arrivée sur l'accueil (solo-accueil.js) et quand
//     demandes.csv change ailleurs (rafraîchissement périodique). Un OT créé à tort se traite par « Annuler l'OT ».
//   - Sa propre déclaration (« Signaler un problème ») : Solo.apresSignalement(diId) l'accepte aussitôt (OT à son nom).
//   - Habilitations (RG8, D191 remplacée en Solo par un rappel) : Solo.sansRefusHabilitation() est lu par
//     refusHabilitation (ordres-regles.js) : jamais de refus ni de dérogation à soi-même ; Solo.ajusterFiche pose le
//     rappel sur la fiche de l'OT quand sa fiche de technicien ne porte pas l'habilitation exigée.
//   - Fiche d'un OT : Solo.ajusterFiche(racine, ot) : trois états lisibles (à faire, en cours ou en attente, fini) au
//     lieu des étapes ; « Marquer préparé », « Planifier » (et la clôture en deux temps quand « Clore » est là) rangés
//     sous « Plus d'options ».
//   - <html data-solo> (Solo.marquer, appelé par js/app.js avec le menu) : css/modules/solo.css cache le champ
//     « Technicien » et les filtres d'équipe.
// L'accueil du Solo est dans solo-accueil.js. Chargé après ordres-prise.js ; les autres modules l'appellent par
// « typeof Solo !== 'undefined' » au moment de l'appel.

const Solo = (() => {

  const STATUTS_A_FAIRE = ['Créé', 'Préparé', 'Planifié'];
  const STATUTS_EN_COURS = ['En cours', 'En attente'];
  const STATUTS_FINIS = ['Clôturé techniquement', 'Clôturé administrativement'];
  // Boutons de la fiche rangés sous « Plus d'options » (la clôture en deux temps seulement si « Clore » est là).
  const CIBLES_REPLIEES = ['Préparé', 'Planifié'];
  const CIBLES_CLOTURE = ['Clôturé techniquement', 'Clôturé administrativement'];

  let file = Promise.resolve([]);   // conversions de cet onglet, l'une après l'autre

  const texte = (valeur) => String(valeur === undefined || valeur === null ? '' : valeur).trim();

  function actif() {
    return typeof App !== 'undefined' && typeof App.modeSolo === 'function' && App.modeSolo();
  }

  /** Technicien seul (solo_technicien_id reconnu) en mode Solo, '' sinon. */
  function moi() {
    return actif() ? texte(App.technicienSolo()) : '';
  }

  /** Marque <html data-solo> d'après le mode (css/modules/solo.css). */
  function marquer() {
    document.documentElement.toggleAttribute('data-solo', actif());
  }

  // ===========================================================================================
  // 1. Règles
  // ===========================================================================================

  /** État lisible d'un OT en Solo : 'a_faire', 'en_cours' (En cours, En attente), 'fini', 'annule'. */
  function etatSimple(ot) {
    const statut = texte(ot && ot.statut);
    if (STATUTS_EN_COURS.includes(statut)) return 'en_cours';
    if (STATUTS_FINIS.includes(statut)) return 'fini';
    if (statut === 'Annulé') return 'annule';
    return 'a_faire';
  }

  /** RG8 : en Solo, aucun refus à l'affectation ni à la planification (un rappel à la place, D191 en équipe). */
  function sansRefusHabilitation() {
    return actif();
  }

  /** Demandes à convertir : « Nouvelle », sans OT. */
  function demandesAConvertir(demandes) {
    return (demandes || []).filter((di) => texte(di.statut) === 'Nouvelle' && !texte(di.ot_id));
  }

  // ===========================================================================================
  // 2. Écritures
  // ===========================================================================================

  /**
   * À appeler dans la fonction de mutation qui crée un OT, sur la ligne neuve avant de la pousser : en Solo, sans
   * technicien, elle passe au nom du technicien seul (et sa ligne de prise en charge). Rien hors Solo.
   */
  function completerOt(ligne) {
    const id = moi();
    if (!id || !ligne || texte(ligne.technicien_id)) return;
    if (Ordres.interne && typeof Ordres.interne.noterPrise === 'function') Ordres.interne.noterPrise(ligne, id);
    ligne.technicien_id = id;
  }

  /**
   * Accepte une demande comme le bouton « Accepter » (Demandes.accepter) ; rend l'identifiant de l'OT, ou '' si la
   * demande a été traitée ailleurs entre-temps (deux onglets, deux appareils : rien de doublé, rien à dire).
   */
  async function accepterSansDecision(diId) {
    try {
      return await Demandes.accepter(diId);
    } catch (erreur) {
      if (erreur instanceof Donnees.ErreurValidation) return '';
      throw erreur;
    }
  }

  /** Un passage : relit demandes.csv, puis accepte chaque demande à convertir, l'une après l'autre. */
  async function convertirUneFois() {
    const faites = [];
    const demandes = await Donnees.rechargerTable('demandes');
    for (const di of demandesAConvertir(demandes)) {
      if (!moi()) break;                      // passé en équipe entre-temps : plus rien d'automatique
      try {
        const otId = await accepterSansDecision(di.id);
        if (otId) faites.push({ diId: di.id, otId });
      } catch (erreur) {
        console.warn('Prévo (Solo) : demande ' + di.id + ' non convertie (' + (erreur && erreur.message) + ').', erreur);
      }
    }
    return faites;
  }

  /**
   * Convertit les demandes « Nouvelle » (relues sur le disque avant d'écrire) en OT au nom du technicien seul.
   * Rend [{ diId, otId }] des demandes converties par CET appel. Les appels de cet onglet passent l'un après l'autre
   * (file) : un appel fait pendant une conversion relit les demandes après elle (une demande arrivée entre-temps n'est
   * pas oubliée). Rien hors Solo, sans technicien seul reconnu, ou en lecture seule.
   */
  function convertirDemandes() {
    if (!moi() || Donnees.lectureSeule()) return Promise.resolve([]);
    const tour = file.then(convertirUneFois, convertirUneFois);
    file = tour.catch(() => []);
    return tour;
  }

  /** Toast « Nouvelle panne déclarée par … : … » pour chaque demande convertie en dehors de l'accueil. */
  function annoncer(faites) {
    faites.forEach(({ diId, otId }) => {
      const di = Donnees.trouver('demandes', diId);
      if (!di) return;
      UI.toast(I18n.t('ordres.solo.toast_panne', { nom: texte(di.demandeur), machine: libelleMachine(di.equipement_id), otId }), 'info');
    });
  }

  /** Sa propre déclaration : OT créé aussitôt à son nom. Rend l'identifiant de l'OT, '' hors Solo. */
  async function apresSignalement(diId) {
    if (!moi()) return '';
    return accepterSansDecision(diId);
  }

  // ===========================================================================================
  // 3. Fiche d'un OT
  // ===========================================================================================

  function libelleMachine(equipementId) {
    const equipement = Donnees.trouver('equipements', texte(equipementId));
    return equipement ? texte(equipement.repere) + (texte(equipement.designation) ? ' — ' + texte(equipement.designation) : '') : texte(equipementId);
  }

  function libelleEtat(cle) {
    return I18n.t('ordres.solo.etat_' + cle);
  }

  /** Les trois états du Solo à la place des étapes de la fiche. */
  function etapesSolo(ot) {
    const etat = etatSimple(ot);
    const rang = { a_faire: 0, en_cours: 1, fini: 2 }[etat];
    const etats = ['a_faire', 'en_cours', 'fini'];
    const liste = UI.element(UI.html`<ol class="etapes ot-etapes solo-etapes" aria-label="${I18n.t('ordres.etapes.avancement_ot')}">
      ${etats.map((cle, i) => {
        let classe = '';
        if (rang !== undefined && i < rang) classe = 'fait';
        if (i === rang) classe = etat === 'fini' ? 'fait' : 'courant';
        const libelle = cle === 'en_cours' && texte(ot.statut) === 'En attente' ? I18n.t('ordres.solo.etat_en_attente') : libelleEtat(cle);
        return UI.html`<li class="${classe}" data-etat="${cle}"${i === rang ? UI.brut(' aria-current="step"') : ''}>${libelle}</li>`;
      })}
      ${etat === 'annule' ? UI.html`<li class="hors" aria-current="step">${Schema.libelleValeur('ordres_travail', 'statut', ot.statut)}</li>` : ''}
    </ol>`);
    return liste;
  }

  /** Rappel d'habilitation (jamais un refus en Solo) : '' quand sa fiche porte tout ce que l'OT exige. */
  function rappelHabilitation(ot) {
    const id = moi();
    if (!id || etatSimple(ot) === 'fini' || etatSimple(ot) === 'annule') return null;
    const controle = Ordres.controleHabilitation(ot, id);
    if (!controle.bloque) return null;
    const liste = controle.manquantes.map((m) => Ordres.interne.libelleManquante(m)).join(', ');
    const bandeau = UI.bandeau('attention', UI.html`${I18n.html('ordres.solo.rappel_habilitation', { liste, lien: '#/equipe/' + encodeURIComponent(id) })}`);
    bandeau.id = 'solo-rappel-habilitation';
    return bandeau;
  }

  /** Range sous « Plus d'options » les boutons qui ne sont pas un passage obligé en Solo. */
  function replierActions(racine) {
    const zone = UI.$('.ot-actions > .actions', racine);
    if (!zone) return;
    const clore = UI.$('#ot-clore', zone);
    const cibles = CIBLES_REPLIEES.concat(clore ? CIBLES_CLOTURE : []);
    const boutons = UI.$$('button[data-action="transition"]', zone).filter((bouton) => cibles.includes(bouton.dataset.cible));
    // L18 : le « Plus d'options » de la carte (Marquer préparé, Annuler) s'il est là, un seul pour tout.
    const existant = UI.$('.ot-actions .ot-plus-options', racine);
    if (existant) Object.assign(existant, { id: 'solo-plus-options' }).classList.add('solo-plus-options');
    if (!boutons.length) return;
    const plus = existant || UI.element(UI.html`<details class="solo-plus-options ot-plus-options" id="solo-plus-options">
      <summary>${I18n.t('ordres.solo.plus_options')}</summary><div class="actions"></div></details>`);
    boutons.forEach((bouton) => UI.$('.actions', plus).appendChild(bouton));
    if (!existant) zone.closest('.ot-actions').appendChild(plus);
  }

  /** Fiche d'un OT en Solo (appelé par ordres-fiche.js après l'affichage) : rien hors Solo. */
  function ajusterFiche(racine, ot) {
    if (!actif() || !racine || !ot) return;
    const etapes = UI.$('.ot-etapes', racine);
    if (etapes) etapes.replaceWith(etapesSolo(ot));
    const rappel = rappelHabilitation(ot);
    const zone = UI.$('.ot-bandeau-etat', racine);
    if (rappel && zone) zone.appendChild(rappel);
    replierActions(racine);
  }

  // ===========================================================================================
  // 4. Déclenchement : ouverture, données changées ailleurs
  // ===========================================================================================

  /** Appelé par js/app.js une fois l'application prête : marque, puis convertit (sans attendre). */
  function auDemarrage() {
    marquer();
    if (!moi()) return;
    convertirDemandes().then((faites) => { if (!/^#\/accueil/.test(location.hash)) annoncer(faites); })
      .catch((erreur) => console.warn('Prévo (Solo) : conversion à l\'ouverture impossible.', erreur));
  }

  // demandes.csv changé sur un autre poste (rafraîchissement périodique) : conversion ; l'accueil, s'il est affiché, se
  // réaffiche de lui-même (il convertit aussi) : le toast n'est dit qu'ailleurs.
  function surChangement(evenement) {
    const detail = (evenement && evenement.detail) || {};
    if (detail.origine !== 'distant' || !(detail.tables || []).includes('demandes') || !moi()) return;
    convertirDemandes().then((faites) => { if (!/^#\/accueil/.test(location.hash)) annoncer(faites); })
      .catch((erreur) => console.warn('Prévo (Solo) : conversion impossible.', erreur));
  }

  // Aide à l'écran de la fiche d'un OT en Solo (variante « solo », lue par aide-ecrans.js) : sans « Planifier » ni
  // refus d'habilitation, qui ne valent qu'en équipe. AideEcransTextes est produit par un outil : ajout au chargement.
  if (typeof AideEcransTextes !== 'undefined' && AideEcransTextes['fiche-ot'] && AideEcransTextes['fiche-ot'].profils) {
    AideEcransTextes['fiche-ot'].profils.solo = {
      get texte() { return I18n.t('ordres.solo.aide_texte'); },
      get essayez() { return I18n.t('ordres.solo.aide_essayez'); },
    };
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof Donnees !== 'undefined' && Donnees.evenements) Donnees.evenements.addEventListener('changement', surChangement);
  });

  return {
    actif, moi, marquer, etatSimple, sansRefusHabilitation, demandesAConvertir, completerOt, convertirDemandes,
    apresSignalement, ajusterFiche, auDemarrage, libelleMachine, annoncer,
  };
})();
