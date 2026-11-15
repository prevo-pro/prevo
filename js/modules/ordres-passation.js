'use strict';
// Ordres — passation et renforts (lot 2 ergonomie, L16 ; ARCHITECTURE.md §14.2, « Passation et renforts »).
// Format 6 (ordres_travail) : renforts (identifiants de techniciens séparés par « , », le principal reste
// technicien_id), releve_mot, releve_par, releve_le, releve_motif (le dernier « Passer la main »).
//   « Passer la main » (fiche de l'OT, technicien principal) : pourquoi (motif), à qui (un collègue, ou « à qui est
//   disponible » : l'OT n'a plus de technicien et retourne dans « À prendre », L14), un mot de relève facultatif (champ
//   dicté : micro de dictee.js, réglage du responsable L24). Le statut ne change pas. Le mot s'affiche en tête de l'OT
//   avec le nom et l'heure, et sur les cartes de l'accueil (« Mes ordres de travail » du collègue, « À prendre », « En
//   attente dans l'équipe »). RG8 : celle de l'affectation (Ordres.controlerAffectation) pour le collègue choisi.
//   « Journée terminée » (accueil du technicien) : pour chaque OT ouvert à son nom, « Je le garde » (rien n'est écrit :
//   l'OT reste tel quel, « En cours » compris), « Je le passe à… » ou « À qui est disponible » (motif « fin de journée »).
//   « Ajouter un technicien » (fiche) : des renforts à côté du technicien principal ; l'OT apparaît chez chacun (accueil,
//   liste filtrée sur un technicien : Ordres.estTechnicienDeLOt) ; chacun saisit son temps (onglet Exécution) ; la
//   fenêtre de clôture rappelle, sans bloquer, les techniciens de l'OT sans temps saisi (rappelTempsRenforts).
// Droits : aucun nouveau. Tout technicien écrit déjà ordres_travail (serveur : PUT permis au rôle technicien, sans
// règle par OT) ; un renfort n'a que les droits de tout technicien. Hors mode Solo (un seul technicien).
// Chargé après ordres-prise.js ; ordres-fiche.js, ordres-cloture.js, ordres-liste.js et accueil.js l'appellent au moment
// de l'affichage. Complète l'objet Ordres.
Object.assign(Ordres, (() => {

  const { estOuvert, nomTechnicien, controlerAffectation, ecrireAvecTrace, monTechnicien } = Ordres;
  const { texte, apresEnregistrement, listeTechniciens } = Ordres.interne;

  const MOTIFS = ['fin de journée', 'compétence ou habilitation', 'pas le temps', 'autre'];
  const DISPONIBLE = '__disponible';
  const enSolo = () => typeof App !== 'undefined' && typeof App.modeSolo === 'function' && App.modeSolo();

  // ===========================================================================================
  // Règles pures
  // ===========================================================================================

  /** renforts (« TEC-0001,TEC-0003 ») → identifiants, sans vide ni doublon, dans l'ordre écrit. */
  function lireRenforts(valeur) {
    return [...new Set(texte(valeur).split(',').map((id) => id.trim()).filter(Boolean))];
  }

  /** Identifiants → valeur de la colonne renforts. */
  function ecrireRenforts(ids) {
    return lireRenforts((ids || []).join(',')).join(',');
  }

  /** « Passer la main » proposé à `moi` : OT ouvert à son nom (technicien principal). */
  function passationPossible(ot, moi) {
    return Boolean(ot) && Boolean(texte(moi)) && estOuvert(ot) && texte(ot.technicien_id) === texte(moi);
  }

  /** Mot de relève à montrer sur une carte de l'accueil : la main a été passée et celui qui l'a passée ne tient plus
   *  l'OT (repris à son nom, le mot n'est plus pour personne). */
  function releveAMontrer(ot) {
    return Boolean(ot) && Boolean(texte(ot.releve_par)) && Boolean(texte(ot.releve_le))
      && texte(ot.technicien_id) !== texte(ot.releve_par);
  }

  // ===========================================================================================
  // Écritures
  // ===========================================================================================

  function ligneOuverte(lignes, otId) {
    const ligne = lignes.find((l) => l.id === otId);
    if (!ligne) throw new Donnees.ErreurValidation(I18n.t('commun.message.ot_introuvable', { otId }));
    if (!estOuvert(ligne)) {
      throw new Donnees.ErreurValidation(I18n.t('ordres.prise.plus_ouvert', { otId, statut: Schema.libelleValeur('ordres_travail', 'statut', ligne.statut) }));
    }
    return ligne;
  }

  /**
   * « Passer la main » : l'OT de `de` (son technicien principal, relu frais : refus s'il a changé entre-temps) passe à
   * `a` (un collègue ; '' : à qui est disponible, sans technicien). motif : une valeur de releve_motif ; mot : facultatif.
   * RG8 pour le collègue (refus, ou dérogation du responsable : options). Le statut ne change pas ; le collègue sort des
   * renforts s'il y était. Rend l'identifiant du nouveau technicien ('' : à qui est disponible).
   */
  async function passerLaMain(otId, choix, options) {
    const de = texte(choix && choix.de);
    const a = texte(choix && choix.a);
    const motif = texte(choix && choix.motif);
    const action = a ? I18n.donnees('ordres.passation.journal_collegue', { technicienId: a })
      : I18n.donnees('ordres.passation.journal_disponible');
    const journal = { action };
    return ecrireAvecTrace((lignes) => {
      journal.action = action;
      journal.derogation = '';
      const ligne = ligneOuverte(lignes, otId);
      if (!de || texte(ligne.technicien_id) !== de) {
        throw new Donnees.ErreurValidation(I18n.t('ordres.passation.plus_a_vous', { otId }));
      }
      if (a === de) throw new Donnees.ErreurValidation(I18n.t('ordres.passation.meme_technicien'));
      if (!MOTIFS.includes(motif)) throw new Donnees.ErreurValidation(I18n.t('ordres.passation.choisir_motif'));
      if (a) {
        const marqueur = controlerAffectation(Object.assign({}, ligne, { technicien_id: a }), options);
        if (marqueur) Object.assign(journal, { action: action + ' ; ' + marqueur, derogation: marqueur });
      }
      Object.assign(ligne, {
        technicien_id: a,
        renforts: ecrireRenforts(lireRenforts(ligne.renforts).filter((id) => id !== a)),
        releve_mot: texte(choix.mot),
        releve_par: de,
        releve_le: Donnees.maintenant().slice(0, 16),
        releve_motif: motif,
      });
      return a;
    }, journal, otId);
  }

  // ===========================================================================================
  // Affichage : mot de relève, renforts
  // ===========================================================================================

  function prenom(id) {
    const technicien = texte(id) ? Donnees.trouver('techniciens', id) : null;
    return texte(technicien && technicien.prenom) || nomTechnicien(id) || texte(id);
  }

  const libelleMotif = (motif) => Schema.libelleValeur('ordres_travail', 'releve_motif', motif);

  /** En tête de la fiche : le dernier mot de relève, avec le nom, la date et l'heure, et le motif ; null sans relève. */
  function bandeauReleve(ot) {
    if (!texte(ot.releve_par) || !texte(ot.releve_le)) return null;
    const [date, heure] = UI.dateHeureFr(ot.releve_le).split(' ');
    const bloc = UI.bandeau('info', UI.html`<div class="ot-releve">
      <b>${I18n.t('ordres.passation.releve_titre', { nomTechnicien: prenom(ot.releve_par), date, heure: heure || '' })}</b>
      ${texte(ot.releve_motif) ? UI.html` <span class="ot-releve-motif">(${libelleMotif(ot.releve_motif)})</span>` : ''}
      ${texte(ot.releve_mot) ? UI.html`<p class="ot-releve-mot">${ot.releve_mot}</p>`
        : UI.html`<p class="muted">${I18n.t('ordres.passation.releve_sans_mot')}</p>`}</div>`);
    bloc.classList.add('ot-releve-bandeau');
    return bloc;
  }

  /** Ligne d'une carte de l'accueil : le mot de relève (ou qui a passé la main et pourquoi) ; '' sinon. */
  function releveCarteHtml(ot) {
    if (!releveAMontrer(ot)) return '';
    const qui = prenom(ot.releve_par);
    return texte(ot.releve_mot)
      ? UI.html`<p class="accueil-releve"><b>${I18n.t('ordres.passation.carte_mot', { nomTechnicien: qui })}</b> ${ot.releve_mot}</p>`
      : UI.html`<p class="accueil-releve">${I18n.t('ordres.passation.carte_passe', { nomTechnicien: qui, motif: libelleMotif(ot.releve_motif) })}</p>`;
  }

  /** Collègues proposés (fiches actives), sans `exclus`. */
  function collegues(exclus) {
    return listeTechniciens('').filter((option) => !exclus.includes(option.valeur));
  }

  function optionsHtml(options, vide) {
    return UI.html`<option value="">${vide}</option>${options.map((option) => UI.html`<option value="${option.valeur}">${option.libelle}</option>`)}`;
  }

  // --- Fenêtre « Passer la main » ------------------------------------------------------------

  function champsPassation(ot, moi) {
    const motifs = UI.element(UI.html`<fieldset class="ot-passation-motif" data-champ="releve_motif"><legend class="libelle">${I18n.t('ordres.passation.pourquoi')} <span class="requis" aria-hidden="true">*</span></legend>
      <div class="ot-cloture-choix">${MOTIFS.map((motif) => UI.html`<label class="case"><input type="radio" name="releve_motif" value="${motif}"><span>${libelleMotif(motif)}</span></label>`)}</div>
      <p class="erreur-champ" hidden></p></fieldset>`);
    const qui = UI.element(UI.html`<div class="champ" data-champ="a"><label class="libelle" for="ot-passation-a">${I18n.t('ordres.passation.a_qui')} <span class="requis" aria-hidden="true">*</span></label>
      <select id="ot-passation-a" name="a">${optionsHtml(collegues([moi]), I18n.t('ordres.passation.choisir'))}<option value="${DISPONIBLE}">${I18n.t('ordres.passation.a_qui_disponible')}</option></select>
      <p class="erreur-champ" hidden></p></div>`);
    const mot = UI.champ({ nom: 'releve_mot', type: 'texte_long' }, '', {
      libelle: I18n.t('ordres.passation.mot'), aide: I18n.t('ordres.passation.mot_aide') });
    return [motifs, qui, mot];
  }

  async function demanderPassation(ot) {
    const moi = monTechnicien();
    let passe = null;
    const fait = await UI.fenetreAction({
      titre: I18n.t('ordres.passation.titre', { otId: ot.id }), classe: 'ot-fenetre-passation',
      libelleValider: I18n.t('ordres.passation.passer_la_main'),
      introduction: UI.html`<p>${I18n.t('ordres.passation.introduction')}</p>`,
      champs: champsPassation(ot, moi),
      verifier: (valeurs, contenu) => {
        const erreurs = [];
        if (!UI.$('input[name=releve_motif]:checked', contenu)) erreurs.push({ nom: 'releve_motif', message: I18n.t('ordres.passation.choisir_motif') });
        if (!valeurs.a) erreurs.push({ nom: 'a', message: I18n.t('ordres.passation.choisir_qui') });
        return erreurs;
      },
      action: async (valeurs, contenu) => {
        const choix = { de: moi, a: valeurs.a === DISPONIBLE ? '' : valeurs.a, motif: UI.$('input[name=releve_motif]:checked', contenu).value, mot: valeurs.releve_mot };
        passe = await Ordres.avecDerogation((options) => passerLaMain(ot.id, choix, options));
      },
    });
    if (!fait) return;
    UI.toast(passe ? I18n.t('ordres.passation.fait_collegue', { otId: ot.id, nomTechnicien: prenom(passe) })
      : I18n.t('ordres.passation.fait_disponible', { otId: ot.id }), 'succes');
    await apresEnregistrement();
  }

  /** Fiche de l'OT (après la carte Actions rangée) : le mot de relève en tête, « Passer la main » et « Ajouter un
   *  technicien » dans la carte Actions, les clics. Rien d'autre en mode Solo que le mot (s'il y en a un). */
  function poserPassation(racine, ot) {
    const zoneEtat = UI.$('.ot-bandeau-etat', racine);
    const releve = bandeauReleve(ot);
    if (releve && zoneEtat) zoneEtat.prepend(releve);
    if (enSolo()) return;
    const actions = UI.$('.ot-actions > .actions', racine);
    if (actions) {
      if (passationPossible(ot, monTechnicien())) {
        actions.appendChild(UI.element(UI.html`<button type="button" class="btn btn-secondaire" id="ot-passer-main">${I18n.t('ordres.passation.passer_la_main')}</button>`));
      }
    }
    racine.addEventListener('click', (evenement) => {
      if (evenement.target.closest('#ot-passer-main')) demanderPassation(ot);
    });
  }

  Object.assign(Ordres.interne, { poserPassation });

  return {
    // règles pures
    lireRenforts, ecrireRenforts, passationPossible, releveAMontrer, MOTIFS_RELEVE: MOTIFS,
    // écritures
    passerLaMain,
    // accueils (accueil.js, ordres-prise.js : cherchés au moment de l'affichage)
    releveCarteHtml,
  };
})());
