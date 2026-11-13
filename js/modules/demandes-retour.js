'use strict';
// Demandes (retour) — retour vers l'opérateur (lot 1 ergonomie, A4 ; format 5 des données) :
//   1. le statut d'une demande suit l'OT auquel elle est rattachée (ot_id) : « Acceptée » (ou « Regroupée ») tant que
//      l'OT est Créé, Préparé ou Planifié, « En cours » quand il est En cours ou En attente, « Réparée » à la clôture
//      technique (ou à « Clore »), avec date_reparation (date de fin de l'OT) et repare_par (le PRÉNOM du
//      technicien de l'OT, rien d'autre) ; OT rouvert → « En cours », retour effacé ; OT annulé → la demande
//      reprend « Acceptée » ou « Regroupée » (jamais dite réparée) ;
//   2. le « mot pour l'opérateur » (demandes.mot_technicien, 300 caractères au plus, jamais obligatoire), saisi à la
//      clôture technique et dans « Clore », seulement quand l'OT vient d'une demande ;
//   3. ce que lit l'opérateur : statut en mots d'atelier (« Reçue », « Acceptée », « En cours », « Réparée le 13/11
//      à 14 h 10 par Karim ») et mot du technicien, dans « Mes demandes », sur la fiche de sa demande et au-dessus du
//      signalement quand il flashe le QR d'une machine (« Vos dernières demandes sur cette machine »).
// Sécurité (ARCHITECTURE.md §22.5) : tout ce que lit le demandeur vient de demandes.csv (statut, mot_technicien,
// date_reparation, repare_par) ; il ne lit ni ordres_travail ni techniciens. L'écriture est faite par celui qui
// change l'OT (technicien ou responsable), dans le même geste, APRÈS l'écriture de l'OT : un échec (demande
// disparue, fichier verrouillé) ne défait jamais la transition, il est dit par un avertissement.
// Bases existantes : au passage au format 5, les demandes « Acceptée » ou « Regroupée » dont l'OT est en cours ou
// clôturé prennent le statut que suivreOt leur aurait donné (même règle, Formats.suiviDesDemandes et serveur.py, T526).
// Complète l'objet Demandes (chargé juste après demandes-regles.js).

Object.assign(Demandes, (() => {

  const { texte } = Demandes.interne;

  // Statuts d'une demande qui suivent son OT ; les autres (Nouvelle, Différée, Refusée) ne bougent jamais ici.
  const STATUTS_SUIVIS = ['Acceptée', 'Regroupée', 'En cours', 'Réparée'];
  const OT_EN_COURS = ['En cours', 'En attente'];
  const OT_REPARE = ['Clôturé techniquement', 'Clôturé administrativement'];
  const MOT_MAX = 300;
  const DERNIERES_NOMBRE = 3;
  const DERNIERES_JOURS = 90;

  // ===========================================================================================
  // 1. Le statut suit l'OT (règles pures, puis écriture)
  // ===========================================================================================

  /** Vrai si la demande est rattachée à cet OT et suit son cycle. */
  function rattachee(demande, otId) {
    return texte(demande.ot_id) === texte(otId) && STATUTS_SUIVIS.includes(texte(demande.statut));
  }

  /**
   * Statut que doit avoir une demande rattachée à l'OT (fonction pure) :
   *   OT En cours / En attente → « En cours » ; Clôturé techniquement ou administrativement → « Réparée » ;
   *   sinon (Créé, Préparé, Planifié, Annulé) : « Acceptée » ou « Regroupée » gardé tel quel, et depuis En cours
   *   ou Réparée : « Acceptée » si l'OT a été créé pour cette demande (di_id), « Regroupée » sinon.
   */
  function statutSelonOt(ot, demande) {
    if (OT_REPARE.includes(texte(ot.statut))) return 'Réparée';
    if (OT_EN_COURS.includes(texte(ot.statut))) return 'En cours';
    if (['Acceptée', 'Regroupée'].includes(texte(demande.statut))) return texte(demande.statut);
    return texte(ot.di_id) && texte(ot.di_id) === texte(demande.id) ? 'Acceptée' : 'Regroupée';
  }

  /** Mot pour l'opérateur : une ligne de texte, 300 caractères au plus. */
  function motPropre(mot) {
    return Array.from(texte(mot).replace(/\s+/g, ' ')).slice(0, MOT_MAX).join('').trim();
  }

  /**
   * Prénom du technicien de l'OT (jamais son nom ni son identifiant) ; sans technicien sur l'OT, celui du technicien
   * qui fait la clôture (profil technicien lié à une fiche) ; '' s'il n'est pas connu.
   */
  function prenomTechnicien(technicienId) {
    const profil = typeof App !== 'undefined' && App && App.profil;
    const repli = profil && profil.type === 'technicien' ? texte(profil.technicienId) : '';
    const id = texte(technicienId) || repli;
    const technicien = id ? Donnees.trouver('techniciens', id) : null;
    return technicien ? texte(technicien.prenom) : '';
  }

  /** Vrai si l'OT vient d'une demande (di_id) ou si une demande y est rattachée (regroupée). */
  function vientDUneDemande(ot) {
    return Boolean(ot) && (Boolean(texte(ot.di_id)) || Donnees.lignes('demandes').some((d) => rattachee(d, ot.id)));
  }

  /**
   * Après une transition de l'OT (Ordres.changerStatut, Ordres.clore) : chaque demande rattachée prend le statut
   * qui suit l'OT. statutAvant : celui de l'OT avant la transition ; mot : le mot pour l'opérateur (clôture).
   * Ne lève jamais : un échec est dit (toast d'avertissement, console) et la transition reste faite.
   * → nombre de demandes changées.
   */
  async function suivreOt(otId, statutAvant, mot) {
    try {
      const ot = Donnees.trouver('ordres_travail', otId);
      if (!ot) return 0;
      await Donnees.rechargerTable('demandes');
      if (!Donnees.lignes('demandes').some((d) => rattachee(d, otId))) return 0;
      const reparation = OT_REPARE.includes(texte(ot.statut)) && !OT_REPARE.includes(texte(statutAvant));
      const prenom = prenomTechnicien(ot.technicien_id);
      const leMot = motPropre(mot);
      return await Donnees.modifier('demandes', (lignes, outils) => {
        let changees = 0;
        lignes.filter((ligne) => rattachee(ligne, otId)).forEach((ligne) => {
          const avant = [ligne.statut, ligne.mot_technicien, ligne.date_reparation, ligne.repare_par].join('|');
          const cible = statutSelonOt(ot, ligne);
          if (cible === 'Réparée' && (reparation || texte(ligne.statut) !== 'Réparée')) {
            ligne.date_reparation = texte(ot.date_fin) || outils.maintenant();
            ligne.repare_par = prenom;
            if (reparation) ligne.mot_technicien = leMot;
          } else if (cible !== 'Réparée') {
            ligne.mot_technicien = '';
            ligne.date_reparation = '';
            ligne.repare_par = '';
          }
          ligne.statut = cible;
          if ([ligne.statut, ligne.mot_technicien, ligne.date_reparation, ligne.repare_par].join('|') !== avant) changees += 1;
        });
        return changees;
      }, { action: 'suit ' + otId + ' (' + texte(ot.statut) + ')' });
    } catch (erreur) {
      const message = I18n.t('demandes.retour.non_suivie', { otId, raisonErreur: App.raisonErreur(erreur) });
      try { UI.toast(message, 'attention'); } catch (ignoree) { /* pas d'écran (essais sans page) */ }
      console.warn('Prévo (demandes) : ' + message, erreur);
      return 0;
    }
  }

  // ===========================================================================================
  // 2. Mot pour l'opérateur : champ de la clôture
  // ===========================================================================================

  /** Bloc du champ « Un mot pour l'opérateur (facultatif) » (name="mot_operateur"), avec la dictée. */
  function blocMot() {
    const id = UI.identifiantUnique('ot-mot-operateur');
    return UI.element(UI.html`<div class="champ ot-mot-operateur" data-champ="mot_operateur">
      <label class="libelle" for="${id}">${I18n.t('demandes.retour.mot_libelle')}</label>
      <textarea id="${id}" name="mot_operateur" rows="2" maxlength="${MOT_MAX}" data-dictee aria-describedby="${id}-aide"></textarea>
      <p class="aide" id="${id}-aide">${I18n.t('demandes.retour.mot_aide')}</p></div>`);
  }

  /** Champs à ajouter à la fenêtre « Clore », après le compte rendu : [bloc] si l'OT vient d'une demande, sinon []. */
  function champsMotOperateur(ot) {
    return vientDUneDemande(ot) ? [blocMot()] : [];
  }

  /**
   * Avant la clôture technique (bouton de la fiche) : si l'OT vient d'une demande, une fenêtre propose le mot pour
   * l'opérateur. → { mot_operateur } (vide permis), {} sans demande, null si l'on renonce à clôturer.
   */
  async function demanderMotOperateur(ot) {
    if (!vientDUneDemande(ot)) return {};
    const contenu = UI.element(UI.html`<div class="form-colonne ot-fenetre-mot">
      <p>${I18n.t('demandes.retour.cloturer_intro')}</p></div>`);
    contenu.appendChild(blocMot());
    const choix = await UI.fenetre({
      titre: I18n.t('demandes.retour.cloturer_titre', { otId: ot.id }),
      contenu,
      boutons: [
        { libelle: I18n.t('commun.bouton.annuler'), valeur: null, classe: 'btn-fantome' },
        { libelle: I18n.t('ordres.cloture_techniquement.cloturer_techniquement'), valeur: 'cloturer', classe: 'btn-primaire', defaut: true },
      ],
    });
    if (choix !== 'cloturer') return null;
    return { mot_operateur: motPropre(UI.$('textarea', contenu).value) };
  }

  /** Fiche de l'OT (repères) : le mot laissé à l'opérateur, s'il y en a un. */
  function reperesRetour(ot) {
    const avecMot = Donnees.lignes('demandes').find((d) => rattachee(d, ot.id) && texte(d.mot_technicien));
    return avecMot ? UI.html`<dt>${I18n.t('demandes.retour.mot_pour_operateur')}</dt><dd class="ot-mot-operateur-lu">${avecMot.mot_technicien}</dd>` : '';
  }

  // ===========================================================================================
  // 3. Ce que lit l'opérateur
  // ===========================================================================================

  /** Statut en mots d'atelier (court) : Reçue, Acceptée, En cours, Réparée, Différée, Refusée. */
  function libelleAtelier(demande) {
    switch (texte(demande.statut)) {
      case 'Nouvelle': return I18n.t('demandes.retour.statut_recue');
      case 'Acceptée':
      case 'Regroupée': return I18n.t('demandes.retour.statut_acceptee');
      case 'En cours': return I18n.t('demandes.retour.statut_en_cours');
      case 'Réparée': return I18n.t('demandes.retour.statut_reparee');
      default: return Schema.libelleValeur('demandes', 'statut', demande.statut);
    }
  }

  /** Badge du statut : en mots d'atelier pour le demandeur, la valeur du schéma pour la maintenance. */
  function badgeStatut(demande) {
    return App.estDemandeur() ? UI.badgeStatut(demande.statut, null, libelleAtelier(demande))
      : UI.badgeValeur('demandes', 'statut', demande.statut);
  }

  /** « Réparée le 13/11 à 14 h 10 par Karim » (sans « par » si le prénom manque, sans date si elle manque). */
  function phraseReparee(demande) {
    const morceaux = /^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/.exec(texte(demande.date_reparation));
    const prenom = texte(demande.repare_par);
    if (!morceaux) return prenom ? I18n.t('demandes.retour.reparee_par', { prenom }) : I18n.t('demandes.retour.statut_reparee');
    const valeurs = { jour: morceaux[3] + '/' + morceaux[2], heures: morceaux[4] || '', minutes: morceaux[5] || '', prenom };
    if (!morceaux[4]) return prenom ? I18n.t('demandes.retour.reparee_jour_par', valeurs) : I18n.t('demandes.retour.reparee_jour', valeurs);
    return prenom ? I18n.t('demandes.retour.reparee_le_par', valeurs) : I18n.t('demandes.retour.reparee_le', valeurs);
  }

  /** Phrase de suivi pour l'opérateur (Acceptée, En cours, Réparée) ; '' pour les autres statuts. */
  function phraseSuivi(demande) {
    switch (texte(demande.statut)) {
      case 'Acceptée': return I18n.t('demandes.retour.suivi_acceptee');
      case 'En cours': return I18n.t('demandes.retour.suivi_en_cours');
      case 'Réparée': return phraseReparee(demande);
      default: return '';
    }
  }

  /** Retour lisible (phrase « Réparée le … » et mot du technicien), vide tant que la demande n'est pas réparée. */
  function retourHtml(demande) {
    if (texte(demande.statut) !== 'Réparée') return '';
    const mot = texte(demande.mot_technicien);
    return UI.html`<span class="di-retour"><span class="di-retour-phrase">${phraseReparee(demande)}</span>${mot
      ? UI.html`<span class="di-mot"><b>${I18n.t('demandes.retour.mot_du_technicien')}</b> ${mot}</span>` : ''}</span>`;
  }

  /** Cellule « statut » de la liste : badge, puis le retour d'une demande réparée. */
  function statutEtRetour(demande) {
    return UI.html`${badgeStatut(demande)}${retourHtml(demande)}`;
  }

  /** Vrai si la demande est « la sienne » : même règle que l'accueil du demandeur (nom du profil, casse ignorée). */
  function estALui(demande) {
    const nom = texte(App.profil && App.profil.nom).toLowerCase();
    return Boolean(nom) && texte(demande.demandeur).toLowerCase() === nom;
  }

  /** Date ISO (AAAA-MM-JJ) d'il y a n jours. */
  function ilYA(jours) {
    const date = new Date();
    date.setDate(date.getDate() - jours);
    return date.getFullYear() + '-' + String(date.getMonth() + 1).padStart(2, '0') + '-' + String(date.getDate()).padStart(2, '0');
  }

  /** Les 3 dernières demandes du demandeur sur cet équipement (90 jours au plus), les plus récentes d'abord. */
  function dernieresDemandes(equipementId) {
    const depuis = ilYA(DERNIERES_JOURS);
    return Donnees.lignes('demandes')
      .filter((d) => texte(d.equipement_id) === texte(equipementId) && estALui(d) && texte(d.date_heure).slice(0, 10) >= depuis)
      .sort((a, b) => texte(b.date_heure).localeCompare(texte(a.date_heure)) || texte(b.id).localeCompare(texte(a.id)))
      .slice(0, DERNIERES_NOMBRE);
  }

  // Le téléphone de l'opérateur peut avoir gardé la page ouverte (QR reflashé dans le même onglet) : à l'affichage
  // du bloc, les tables sont relues aussitôt (au plus une fois toutes les 5 s) au lieu d'attendre la surveillance
  // (20 s) ; une demande changée ailleurs réaffiche l'écran (App, événement « changement »).
  let derniereRelecture = 0;
  function relireBientot() {
    const maintenant = Date.now();
    if (maintenant - derniereRelecture < 5000 || typeof Donnees.rafraichir !== 'function') return;
    derniereRelecture = maintenant;
    Donnees.rafraichir().catch((erreur) => console.warn('Prévo (demandes) : relecture impossible.', erreur));
  }

  /**
   * « Vos dernières demandes sur cette machine » (demandeur seulement ; null s'il n'en a aucune, ou pour un autre
   * profil) : date, début du symptôme (deux lignes au plus), statut en mots d'atelier, phrase de suivi et mot du technicien.
   */
  function blocDernieresDemandes(equipementId) {
    if (!App.estDemandeur() || !texte(equipementId)) return null;
    relireBientot();
    const lignes = dernieresDemandes(equipementId);
    if (!lignes.length) return null;
    return UI.element(UI.html`<section class="carte di-dernieres" aria-labelledby="di-dernieres-titre">
      <h2 id="di-dernieres-titre">${I18n.t('demandes.retour.dernieres_titre')}</h2>
      <ul class="di-dernieres-liste">${lignes.map((d) => UI.html`<li><a href="#/di/${encodeURIComponent(d.id)}">
        <span class="di-dernieres-tete"><span class="di-dernieres-date">${UI.dateFr(d.date_heure)}</span>${badgeStatut(d)}</span>
        <span class="di-dernieres-symptome" title="${d.symptome}">${d.symptome}</span>
        ${phraseSuivi(d) && texte(d.statut) !== 'Réparée' ? UI.html`<span class="di-retour-phrase">${phraseSuivi(d)}</span>` : ''}
        ${retourHtml(d)}</a></li>`)}</ul></section>`);
  }

  /** Bloc « Suivi » de la fiche d'une demande réparée : le mot du technicien (la phrase « Réparée le … » est au-dessus). */
  function suiviRetour(demande) {
    const mot = texte(demande.statut) === 'Réparée' ? texte(demande.mot_technicien) : '';
    return mot ? UI.html`<dt>${I18n.t('demandes.retour.mot_du_technicien_titre')}</dt><dd class="di-mot-fiche">${mot}</dd>` : '';
  }

  return {
    STATUTS_SUIVIS, MOT_MAX,
    statutSelonOt, suivreOt, champsMotOperateur, demanderMotOperateur, reperesRetour,
    libelleAtelier, badgeStatut, phraseSuivi, phraseReparee, retourHtml, statutEtRetour, dernieresDemandes,
    blocDernieresDemandes, suiviRetour,
  };
})());
