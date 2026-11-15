'use strict';
// Ordres — « Je prends cet OT » et reprise de l'OT d'un collègue (lot 1 ergonomie, A3, T516 ; ARCHITECTURE.md §14.2,
// « Prises en charge »). Un technicien (compte technicien lié à sa fiche, profil Technicien d'un poste sans comptes, ou
// responsable en mode Solo : App.technicienSolo()) met à son nom un OT ouvert sans technicien (« Je prends cet OT »,
// fiche et liste) ou affecté à un collègue (« Reprendre cet OT à mon nom », fiche, avec confirmation). Chaque prise,
// reprise ou changement de technicien (préparation, planning) ajoute une ligne à ordres_travail.prises_en_charge
// (format 5 : « date_heure|technicien_id|technicien_precedent_id », le dernier vide pour une première prise) ; la
// ligne du journal (profil posé par le serveur) reste la trace d'autorité. RG8 (D191) : la règle de l'affectation,
// inchangée (Ordres.controlerAffectation ; la dérogation reste au responsable, Ordres.avecDerogation).
// Affichage : bloc « Prises en charge » de la fiche et du bon de travail ; sur l'accueil du technicien, les cartes
// « À prendre » (nombre dans le titre) et « En attente dans l'équipe » (lot 2, L14 : les OT des collègues mis en
// attente, avec le motif et, L16, le mot de relève ; hors mode Solo) et les reprises de ses OT (7 jours) ; sur celui du responsable, « Reprises
// récentes » et (L17) « Demandes prises par les techniciens ».
// Qui accepte une demande (lot 2, L17) : quand le réglage le permet (Demandes.techniciensAcceptent), les demandes
// « Nouvelle » sont aussi dans « À prendre », avec « Je prends » (Demandes.prendre : acceptée, OT créé à son nom, en
// un geste) ; même bouton sur la fiche de la demande (demandes-fiche.js, prendreDemandeParEcran).
// Carte Actions de la fiche (lot 2, L18) : un seul bouton mis en avant, celui de la prochaine étape utile pour la
// personne connectée (rangerActions) ; « Marquer préparé » et « Annuler » rangés sous « Plus d'options ». Sur un OT en
// attente ou en cours au nom d'un collègue, « Prendre la suite » : à mon nom (prendre, trace de prise) puis en cours.
// Sur téléphone, le bouton mis en avant est redit dans une barre fixe en bas de la fiche (poserBarrePrincipale).
// Chargé après ordres-habilitations.js ; les écrans des fichiers précédents l'appellent par Ordres.interne au moment
// de l'appel. Complète l'objet Ordres.

Object.assign(Ordres, (() => {

  const { estOuvert, nomTechnicien, controlerAffectation, ecrireAvecTrace } = Ordres;
  const { texte, estResponsable, estTechnicien, apresEnregistrement } = Ordres.interne;

  const STATUTS_SUITE = ['En attente', 'En cours'];   // L18 : « Prendre la suite » plutôt que « Reprendre à mon nom »
  const JOURS_REPRISES = 7;            // une reprise reste dite sur l'accueil pendant 7 jours
  const NOMBRE_A_PRENDRE = 5;          // OT montrés par la carte « À prendre »
  const RANG_PRIORITE = { P1: 1, P2: 2, P3: 3, P4: 4 };

  // ===========================================================================================
  // Règles pures
  // ===========================================================================================

  /** Lignes de prises_en_charge → [{ date, technicienId, precedentId }], dans l'ordre écrit (lignes illisibles ignorées). */
  function lirePrises(valeur) {
    return texte(valeur).split(/\r?\n/).map((ligne) => ligne.split('|').map((morceau) => morceau.trim()))
      .filter((morceaux) => morceaux.length >= 2 && morceaux[0] && morceaux[1])
      .map((morceaux) => ({ date: morceaux[0], technicienId: morceaux[1], precedentId: morceaux[2] || '' }));
  }

  /** Valeur de prises_en_charge avec une ligne de plus. */
  function ajouterPrise(valeur, date, technicienId, precedentId) {
    const ligne = [date, texte(technicienId), texte(precedentId)].join('|');
    const avant = texte(valeur).replace(/\s+$/, '');
    return avant ? avant + '\n' + ligne : ligne;
  }

  /** Le technicien du profil : sa fiche (technicien), « moi » en mode Solo (responsable), sinon la fiche liée au compte
   *  du responsable (L06, lot 2 : le responsable est aussi technicien), sinon ''. */
  function monTechnicien() {
    if (estTechnicien()) return texte(App.profil && App.profil.technicienId);
    return estResponsable() ? texte(App.technicienSolo()) || texte(App.profil && App.profil.technicienId) : '';
  }

  /** Geste proposé au technicien `moi` sur cet OT : 'prendre' (ouvert, sans technicien), 'reprendre' (ouvert, au nom
   *  d'un autre), sinon ''. */
  function priseProposee(ot, moi) {
    const id = texte(moi);
    if (!id || !ot || !estOuvert(ot)) return '';
    const actuel = texte(ot.technicien_id);
    if (!actuel) return 'prendre';
    return actuel === id ? '' : 'reprendre';
  }

  /** Date ISO (AAAA-MM-JJ) `jours` jours avant `dateIso`. */
  function joursAvant(dateIso, jours) {
    const date = new Date(texte(dateIso).slice(0, 10) + 'T12:00:00');
    date.setDate(date.getDate() - jours);
    const deux = (n) => String(n).padStart(2, '0');
    return date.getFullYear() + '-' + deux(date.getMonth() + 1) + '-' + deux(date.getDate());
  }

  /**
   * L16 : la ligne de prise d'un « Passer la main » vers un collègue (le précédent est celui qui a passé la main, à la
   * minute de la relève : releve_par, releve_le de l'OT). Ce n'est pas une reprise : ni « Vos OT repris » chez celui
   * qui a passé la main, ni « Reprises récentes » chez le responsable. Seule la dernière passation de l'OT est connue
   * (releve_* est réécrit à chaque passation).
   */
  function estPassation(ot, prise) {
    return !!(ot && prise && prise.precedentId && prise.precedentId === texte(ot.releve_par)
      && prise.date === texte(ot.releve_le).slice(0, 16));
  }

  /**
   * Reprises (lignes avec un précédent) datées de `depuis` (ISO) ou après, les plus récentes d'abord ; precedentId :
   * seulement celles qui ont repris un OT à ce technicien. → [{ ot, date, technicienId, precedentId }].
   */
  function reprisesRecentes(ordres, depuis, precedentId) {
    const resultat = [];
    ordres.forEach((ot) => lirePrises(ot.prises_en_charge).forEach((prise) => {
      if (!prise.precedentId || prise.date.slice(0, 10) < depuis) return;
      if (precedentId && prise.precedentId !== precedentId) return;
      if (prise.technicienId === prise.precedentId || estPassation(ot, prise)) return;
      resultat.push(Object.assign({ ot }, prise));
    }));
    return resultat.sort((a, b) => b.date.localeCompare(a.date) || b.ot.id.localeCompare(a.ot.id));
  }

  /** Ordre des OT d'une carte de l'accueil : priorité puis date prévue (puis n°). */
  function parPriorite(a, b) {
    return (RANG_PRIORITE[a.priorite] || 9) - (RANG_PRIORITE[b.priorite] || 9)
      || texte(a.date_prevue || '9999').localeCompare(texte(b.date_prevue || '9999')) || a.id.localeCompare(b.id);
  }

  /** OT ouverts sans technicien, priorité puis date prévue (puis n°). */
  function otsAPrendre(ordres) {
    return ordres.filter((ot) => estOuvert(ot) && !texte(ot.technicien_id)).sort(parPriorite);
  }

  /**
   * L17 : demandes acceptées par un technicien (« Je prends ») depuis `depuis` (ISO), les plus récentes d'abord : leur
   * OT porte une première prise sans précédent datée de sa création (Demandes.prendre l'écrit ainsi ; une acceptation
   * du responsable crée l'OT sans technicien). → [{ demande, ot, technicienId, date }].
   */
  function demandesPrisesParTechniciens(demandes, ordres, depuis) {
    const parId = new Map(ordres.map((ot) => [ot.id, ot]));
    const resultat = [];
    demandes.forEach((demande) => {
      const ot = texte(demande.ot_id) ? parId.get(texte(demande.ot_id)) : null;
      const premiere = ot ? lirePrises(ot.prises_en_charge)[0] : null;
      if (!premiere || premiere.precedentId || premiere.date !== texte(ot.date_creation).slice(0, 16)) return;
      if (texte(ot.di_id) !== texte(demande.id) || premiere.date.slice(0, 10) < depuis) return;
      resultat.push({ demande, ot, technicienId: premiere.technicienId, date: premiere.date });
    });
    return resultat.sort((a, b) => b.date.localeCompare(a.date) || b.ot.id.localeCompare(a.ot.id));
  }

  /** L14 : OT « En attente » au nom d'un collègue (un technicien autre que `moi`), priorité puis date prévue. */
  function otsEnAttenteEquipe(ordres, moi) {
    const id = texte(moi);
    return ordres.filter((ot) => texte(ot.statut) === 'En attente' && texte(ot.technicien_id) && texte(ot.technicien_id) !== id)
      .sort(parPriorite);
  }

  // ===========================================================================================
  // Écritures
  // ===========================================================================================

  /**
   * Ajoute à la ligne d'OT (copie de Donnees.modifier) la ligne de prise quand son technicien devient `nouveauId`
   * (préparation, planning, prise) ; à appeler AVANT d'écrire technicien_id. Rien si le technicien ne change pas ou
   * est retiré.
   */
  function noterPrise(ligne, nouveauId) {
    const nouveau = texte(nouveauId);
    const precedent = texte(ligne.technicien_id);
    if (!nouveau || nouveau === precedent) return;
    ligne.prises_en_charge = ajouterPrise(ligne.prises_en_charge, Donnees.maintenant().slice(0, 16), nouveau, precedent);
  }

  /**
   * Met l'OT au nom de technicienId (« Je prends » si precedentAttendu est vide, reprise sinon). Refus si l'OT n'est
   * plus ouvert ou si son technicien a changé entre-temps (deux techniciens qui prennent le même OT). RG8 : celle de
   * l'affectation (controlerAffectation, refus ou dérogation du responsable : options { passerOutreHabilitation,
   * motifDerogation }). Le statut ne change pas. Rend le technicien précédent ('' pour une première prise).
   */
  async function prendre(otId, technicienId, precedentAttendu, options) {
    const moi = texte(technicienId);
    const attendu = texte(precedentAttendu);
    const action = attendu ? I18n.donnees('ordres.prise.journal_reprise', { precedentId: attendu })
      : I18n.donnees('ordres.prise.journal_prise');
    const journal = { action };
    return ecrireAvecTrace((lignes) => {
      journal.action = action;                       // mutation rejouée en cas de conflit : action de départ
      journal.derogation = '';
      const ligne = lignes.find((l) => l.id === otId);
      if (!ligne) throw new Donnees.ErreurValidation(I18n.t('commun.message.ot_introuvable', { otId }));
      if (!moi) throw new Donnees.ErreurValidation(I18n.t('ordres.prise.sans_technicien'));
      if (!estOuvert(ligne)) {
        throw new Donnees.ErreurValidation(I18n.t('ordres.prise.plus_ouvert', { otId, statut: Schema.libelleValeur('ordres_travail', 'statut', ligne.statut) }));
      }
      if (texte(ligne.technicien_id) !== attendu) {
        throw new Donnees.ErreurValidation(I18n.t('ordres.prise.change_entre_temps', { otId, nomTechnicien: nomTechnicien(ligne.technicien_id) || I18n.t('ordres.cartes.non_affecte') }));
      }
      const prochaine = Object.assign({}, ligne, { technicien_id: moi });
      const marqueur = controlerAffectation(prochaine, options);
      if (marqueur) Object.assign(journal, { action: action + ' ; ' + marqueur, derogation: marqueur });
      noterPrise(ligne, moi);
      ligne.technicien_id = moi;
      return attendu;
    }, journal, otId);
  }

  // ===========================================================================================
  // Affichage
  // ===========================================================================================

  /** Prénom du technicien (sinon son nom complet, sinon l'identifiant). */
  function prenom(id) {
    const technicien = texte(id) ? Donnees.trouver('techniciens', id) : null;
    return texte(technicien && technicien.prenom) || nomTechnicien(id) || texte(id);
  }

  function phrasePrise(prise, ot) {
    if (estPassation(ot, prise)) {
      return I18n.t('ordres.prise.ligne_passation', { nomTechnicien: prenom(prise.technicienId), nomPrecedent: prenom(prise.precedentId) });
    }
    return prise.precedentId
      ? I18n.t('ordres.prise.ligne_reprise', { nomTechnicien: prenom(prise.technicienId), nomPrecedent: prenom(prise.precedentId) })
      : I18n.t('ordres.prise.ligne_prise', { nomTechnicien: prenom(prise.technicienId) });
  }

  /** Bloc « Prises en charge » de la fiche (carte Repères) : '' s'il n'y en a aucune. */
  function prisesEnChargeHtml(ot) {
    const prises = lirePrises(ot.prises_en_charge);
    if (!prises.length) return '';
    return UI.html`<h3 class="ot-sous-titre">${I18n.t('ordres.prise.titre_bloc')}</h3>
      <ul class="ot-prises">${prises.map((prise) => UI.html`<li><span class="sans-coupure">${UI.dateHeureFr(prise.date)}</span> — ${phrasePrise(prise, ot)}</li>`)}</ul>`;
  }

  /** Même bloc sur le bon de travail. */
  function prisesEnChargeBon(ot) {
    const prises = lirePrises(ot.prises_en_charge);
    if (!prises.length) return '';
    return UI.html`<section class="bt-prises"><h2>${I18n.t('ordres.prise.titre_bloc')}</h2>
      <ul>${prises.map((prise) => UI.html`<li>${UI.dateHeureFr(prise.date)} — ${phrasePrise(prise, ot)}</li>`)}</ul></section>`;
  }

  /** Geste de la fiche : celui de priseProposee, « suite » (L18) pour un OT en attente ou en cours d'un collègue. */
  function gesteFiche(ot, moi) {
    const sorte = priseProposee(ot, moi);
    return sorte === 'reprendre' && STATUTS_SUITE.includes(texte(ot.statut)) ? 'suite' : sorte;
  }

  /** L19 : la prise serait refusée (réglage « bloquante », habilitation électrique manquante, aucune dérogation) : le
   *  nom de ceux qui l'ont valide remplace le bouton (« Habilitation BR attendue. Peut le prendre : Marc Petit. ») ;
   *  '' sinon (le bouton reste). */
  function habilitesAuLieuDuBouton(otId) {
    const ot = Donnees.trouver('ordres_travail', otId);
    const moi = monTechnicien();
    const refuse = (id) => Ordres.interne.refusHabilitation(Object.assign({}, ot, { technicien_id: id }), id, ot.date_prevue);
    const refus = ot && moi ? refuse(moi) : null;
    if (!refus) return '';
    const liste = refus.manquantes.map((m) => m.intitule).join(', ');
    const noms = Donnees.lignes('techniciens').filter((t) => texte(t.actif) !== '0' && texte(t.id) !== moi && !refuse(texte(t.id)))
      .map((t) => nomTechnicien(t.id));
    return UI.html`<p class="ot-habilites">${noms.length ? I18n.t('ordres.prise.habilites', { n: noms.length, liste, noms: noms.join(', ') })
      : I18n.t('ordres.prise.personne_habilite', { liste })}</p>`;
  }

  function boutonPrise(sorte, otId) {
    if (!sorte) return '';
    const habilites = habilitesAuLieuDuBouton(otId);
    if (habilites) return habilites;
    const libelle = { prendre: 'ordres.prise.je_prends', suite: 'ordres.prise.prendre_suite', reprendre: 'ordres.prise.reprendre' }[sorte];
    return UI.html`<button type="button" class="btn ${sorte === 'reprendre' ? 'btn-secondaire' : 'btn-primaire'}" data-action="prendre-ot" data-sorte="${sorte}" data-ot="${otId}">${UI.icone('valider')}${I18n.t(libelle)}</button>`;
  }

  /** Bouton de la carte Actions de la fiche (« Je prends cet OT », « Prendre la suite » ou « Reprendre cet OT à mon
   *  nom »), ou ''. */
  function boutonsPrise(ot) {
    return boutonPrise(gesteFiche(ot, monTechnicien()), ot.id);
  }

  /**
   * Onglet Préparation en lecture seule : le technicien de l'OT en texte (plus de liste qui se déroule sans bouton
   * pour l'enregistrer ; la valeur reste lue par RG8 en direct, champ caché), et le bouton de prise juste après les champs (un bouton du fieldset désactivé ne marcherait pas).
   */
  function placerTechnicienLecture(formulaire, ot) {
    const nom = nomTechnicien(ot.technicien_id) || I18n.t('ordres.cartes.non_affecte');
    Ordres.interne.placerChamp(formulaire, 'technicien_id', UI.element(UI.html`<div class="champ ot-champ-lu ot-technicien-lecture">
      <span class="libelle">${I18n.t('commun.champ.technicien')}</span><p class="ot-valeur">${nom}</p>
      <input type="hidden" name="technicien_id" value="${texte(ot.technicien_id)}"></div>`));
    const bouton = boutonsPrise(ot);
    const fieldset = formulaire.querySelector('fieldset');
    if (bouton && fieldset) fieldset.after(UI.element(UI.html`<div class="actions ot-prise-preparation">${bouton}</div>`));
  }

  // --- Carte Actions de la fiche : le bouton de la prochaine étape mis en avant (L18) ----------

  // Gestes rangés sous « Plus d'options » (passages facultatifs ou rares).
  const CIBLES_REPLIEES = ['Préparé', 'Annulé'];

  /** Le bouton de la prochaine étape utile parmi ceux de la carte (zone .actions), ou null : prendre l'OT, le démarrer
   *  ou reprendre le travail, le clore, le clôturer, puis créer l'OT lié d'un OT verrouillé. */
  function boutonPrincipal(zone, ot) {
    const parCible = (cible) => 'button[data-cible="' + cible + '"]';
    const selecteurs = ['button[data-action="prendre-ot"][data-sorte="prendre"]', 'button[data-sorte="suite"]',
      ot.statut === 'Clôturé techniquement' ? '' : parCible('En cours'),                  // « Rouvrir » : jamais en avant
      '#ot-clore', parCible('Clôturé techniquement'), parCible('Clôturé administrativement'), '#ot-lie'];
    for (const selecteur of selecteurs) {
      const bouton = selecteur && zone.querySelector(':scope > ' + selecteur);
      if (bouton) return bouton;
    }
    return null;
  }

  /** Range la carte Actions : le bouton principal en tête (seul en bleu), les autres en second, « Marquer préparé »
   *  et « Annuler » sous « Plus d'options » (replié), avec « Reprendre le travail » quand « Prendre la suite » est là
   *  (il remettrait en cours au nom du collègue). Rend le bouton principal (ou null). */
  function rangerActions(racine, ot) {
    const zone = racine.querySelector('.ot-actions > .actions');
    if (!zone) return null;
    const principal = boutonPrincipal(zone, ot);
    UI.$$('button.btn-primaire', zone).forEach((bouton) => {
      if (bouton !== principal) bouton.classList.replace('btn-primaire', 'btn-secondaire');
    });
    if (principal) {
      principal.classList.add('btn-primaire', 'ot-bouton-principal');
      principal.classList.remove('btn-secondaire');
      zone.prepend(principal);
    }
    const cibles = CIBLES_REPLIEES.concat(zone.querySelector('[data-sorte="suite"]') ? ['En cours'] : []);
    const replies = UI.$$('button[data-action="transition"]', zone).filter((bouton) => cibles.includes(bouton.dataset.cible));
    if (replies.length) {
      const plus = UI.element(UI.html`<details class="ot-plus-options">
        <summary>${I18n.t('ordres.actions.plus_options')}</summary><div class="actions"></div></details>`);
      replies.forEach((bouton) => UI.$('.actions', plus).appendChild(bouton));
      zone.after(plus);
    }
    poserBarrePrincipale(racine, principal);
    return principal;
  }

  /** Barre fixe en bas de la fiche (téléphone seulement, css/modules/ordres.css) : une copie du bouton mis en avant,
   *  qui clique l'original (mêmes contrôles, même écriture). Cachée pendant une saisie (clavier ouvert). */
  function poserBarrePrincipale(racine, principal) {
    if (!principal) return;
    const copie = principal.cloneNode(true);
    copie.removeAttribute('id');
    copie.classList.remove('ot-bouton-principal');
    copie.dataset.action = 'barre-principale';              // ni transition ni prise : seul l'original agit
    const barre = UI.element(UI.html`<div class="ot-barre-principale sans-impression"></div>`);
    barre.appendChild(copie);
    copie.addEventListener('click', () => { if (!principal.disabled && document.contains(principal)) principal.click(); });
    racine.appendChild(barre);
  }

  /** Clics sur « Je prends » / « Reprendre » dans la fiche (carte Actions, onglet Préparation) ; carte Actions rangée. */
  function brancherPrise(racine, ot) {
    rangerActions(racine, ot);
    racine.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button[data-action="prendre-ot"]');
      if (bouton) demanderPrise(ot.id, bouton, false);
    });
  }

  /**
   * Prise ou reprise par l'écran : confirmation qui nomme le collègue pour une reprise ; RG8 comme l'affectation ;
   * puis la fiche réaffichée, « Démarrer » proposé (sur la liste : la fiche ouverte). « Prendre la suite » (L18) : la
   * reprise (trace dans prises_en_charge), puis, pour un OT en attente, le passage En cours (changerStatut, journal
   * habituel) ; la fiche s'ouvre sur Exécution.
   */
  async function demanderPrise(otId, bouton, depuisListe) {
    const actuel = Donnees.trouver('ordres_travail', otId);
    const moi = monTechnicien();
    const sorte = depuisListe ? priseProposee(actuel, moi) : gesteFiche(actuel, moi);
    if (!sorte) return;
    const precedent = texte(actuel.technicien_id);
    const suite = sorte === 'suite';
    if (sorte !== 'prendre' && !(await UI.confirmer(
      I18n.t(suite ? 'ordres.prise.confirmer_suite' : 'ordres.prise.confirmer_reprise', { nomTechnicien: prenom(precedent) }),
      { titre: I18n.t('ordres.prise.titre_reprise', { otId }), oui: I18n.t(suite ? 'ordres.prise.prendre_suite' : 'ordres.prise.reprendre_oui') }))) return;
    if (bouton) bouton.disabled = true;
    try {
      await Ordres.avecDerogation((options) => prendre(otId, moi, precedent, options));
      const apres = Donnees.trouver('ordres_travail', otId);
      if (suite && apres && apres.statut === 'En attente') await Ordres.changerStatut(otId, 'En attente', 'En cours', {});
    } catch (erreur) {
      App.signalerErreur(erreur, 'prise en charge d\'un OT');
      if (bouton && document.contains(bouton)) bouton.disabled = false;
      if (suite) await apresEnregistrement();          // la reprise a pu être écrite : la fiche le montre
      return;
    }
    const toast = { prendre: 'ordres.prise.prise_faite', suite: 'ordres.prise.suite_faite', reprendre: 'ordres.prise.reprise_faite' }[sorte];
    UI.toast(I18n.t(toast, { otId, nomTechnicien: prenom(precedent) }), 'succes');
    if (depuisListe) { App.naviguer('#/ot/' + encodeURIComponent(otId)); return; }
    if (suite) Ordres.interne.memoire.ongletParOt[otId] = 'execution';
    await apresEnregistrement();
    const demarrer = document.querySelector('.ot-actions button[data-action="transition"][data-cible="En cours"]');
    if (demarrer) demarrer.focus();
  }

  // --- Liste des OT : « Je prends » sur la ligne d'un OT non affecté -------------------------

  /** Cellule « Technicien » de la liste : le nom, ou « Je prends » pour un OT ouvert sans technicien. */
  function technicienOuPrendre(ot) {
    const nom = nomTechnicien(ot.technicien_id);
    if (nom) return nom;
    return priseProposee(ot, monTechnicien()) === 'prendre' ? boutonPrise('prendre', ot.id) : '';
  }

  /** Sous la carte (téléphone) d'un OT à prendre : le bouton « Je prends » (hors du lien de la carte). */
  function boutonPrendreCarte(ot) {
    if (priseProposee(ot, monTechnicien()) !== 'prendre') return '';
    return UI.html`<div class="actions ot-carte-prise">${boutonPrise('prendre', ot.id)}</div>`;
  }

  function brancherPriseListe(conteneur) {
    ['.ot-liste-tableau', '.ot-liste-cartes'].forEach((selecteur) => {
      const zone = conteneur.querySelector(selecteur);
      if (!zone) return;
      zone.addEventListener('click', (evenement) => {
        const bouton = evenement.target.closest('button[data-action="prendre-ot"]');
        if (!bouton) return;
        evenement.preventDefault();
        demanderPrise(bouton.dataset.ot, bouton, true);
      });
    });
  }

  // --- Accueils ------------------------------------------------------------------------------

  function libelleEquipementCourt(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? (equipement.repere || equipement.id) : texte(equipementId);
  }

  // L19 : l'habilitation attendue est dite sur la carte ; si la prise serait refusée, ceux qui l'ont, sous la carte.
  function ligneOtAccueil(ot) {
    const attendue = Ordres.interne.libelleExigences(ot);
    return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' ? 'accent-p1' : (ot.priorite === 'P2' ? 'accent-p2' : '')}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${libelleEquipementCourt(ot.equipement_id)}</span>${ot.date_prevue ? UI.html`<span>${UI.dateFr(ot.date_prevue)}</span>` : ''}</div>
      ${Ordres.releveCarteHtml(ot)}
      ${attendue ? UI.html`<div class="carte-meta ot-habilitation-attendue">${I18n.t('ordres.habilitation_exigee.attendue', { liste: attendue })}</div>` : ''}
    </a>${habilitesAuLieuDuBouton(ot.id)}</li>`;
  }

  /** L17 : une demande « Nouvelle » dans « À prendre » : la carte mène à la demande, « Je prends » en dessous. */
  function ligneDemandeAccueil(demande) {
    return UI.html`<li class="accueil-demande-a-prendre"><a href="#/di/${encodeURIComponent(demande.id)}" class="${demande.impact === 'sécurité' ? 'accent-p1' : ''}">
      <div class="carte-tete"><b>${demande.id}</b><span class="badge info">${I18n.t('ordres.prise.demande')}</span>${Accueil.interne.badgeImpact(demande.impact)}</div>
      <div class="carte-titre">${demande.symptome}</div>
      <div class="carte-meta"><span>${libelleEquipementCourt(demande.equipement_id)}</span><span>${demande.demandeur}</span><span>${UI.dateHeureFr(demande.date_heure)}</span></div>
    </a><div class="actions ot-carte-prise"><button type="button" class="btn btn-primaire" data-action="prendre-demande" data-di="${demande.id}">${UI.icone('valider')}${I18n.t('ordres.prise.je_prends_demande')}</button></div></li>`;
  }

  /** Accueil du technicien : carte « À prendre » (L17 : d'abord les demandes « Nouvelle » qu'il peut prendre, puis les
   *  OT ouverts sans technicien ; leur nombre dans le titre ; 5 de chaque au plus ; lien filtré). repere : marque
   *  data-aide-apres (téléphone, L14). */
  function carteAPrendre(ots, demandes, repere) {
    const nombre = ots.length + demandes.length;
    return UI.html`<article class="carte accueil-a-prendre" ${repere ? UI.brut('data-aide-apres') : ''}>
      <div class="entete-carte"><h2>${I18n.t('ordres.prise.a_prendre_n', { n: nombre })}</h2></div>
      ${nombre ? UI.html`<ul class="liste-cartes">${demandes.slice(0, NOMBRE_A_PRENDRE).map((demande) => ligneDemandeAccueil(demande))}${ots.slice(0, NOMBRE_A_PRENDRE).map((ot) => ligneOtAccueil(ot))}</ul>`
        : UI.html`<p class="muted">${I18n.t('ordres.prise.rien_a_prendre')}</p>`}
      ${ots.length ? UI.html`<p class="accueil-voir-tout"><a href="#/ot?technicien=__aucun">${I18n.t('ordres.prise.voir_non_affectes')}</a></p>` : ''}
    </article>`;
  }

  /**
   * L17 : « Je prends » sur une demande (accueil, fiche de la demande) : acceptée et OT créé au nom du technicien
   * (Demandes.prendre), puis la fiche de l'OT ouverte. Refus (prise ailleurs, réglage changé, RG8) : dit, écran relu.
   */
  async function prendreDemandeParEcran(diId, bouton) {
    if (bouton) bouton.disabled = true;
    try {
      const otId = await Demandes.prendre(diId, monTechnicien());
      UI.toast(I18n.t('ordres.prise.demande_prise', { diId, otId }), 'succes');
      App.naviguer('#/ot/' + encodeURIComponent(otId));
    } catch (erreur) {
      App.signalerErreur(erreur, 'prise de la demande ' + diId);
      if (bouton && document.contains(bouton)) bouton.disabled = false;
      await App.reafficher();
    }
  }

  /** Branche « Je prends » des demandes de la carte « À prendre » (accueil du technicien, après son affichage). */
  function brancherAccueilTechnicien(conteneur) {
    const carte = conteneur && conteneur.querySelector('.accueil-a-prendre');
    if (!carte) return;
    carte.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button[data-action="prendre-demande"]');
      if (!bouton || bouton.disabled) return;
      evenement.preventDefault();
      prendreDemandeParEcran(bouton.dataset.di, bouton);
    });
  }

  /** L14 : carte « En attente dans l'équipe » : les OT des collègues mis en attente, le collègue, le motif d'attente
   *  et le mot de relève (L16, ordres-passation.js, chargé après ce fichier : cherché à l'affichage) ; chaque ligne mène à la fiche, où « Prendre la
   *  suite » (L18) existe. Montrée hors Solo, même vide (une phrase courte, jamais « aucun OT ouvert »). */
  function carteEnAttenteEquipe(ots, repere) {
    const ligne = (ot) => UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' ? 'accent-p1' : (ot.priorite === 'P2' ? 'accent-p2' : '')}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}<span class="accueil-collegue">${prenom(ot.technicien_id)}</span></div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${libelleEquipementCourt(ot.equipement_id)}</span></div>
      ${texte(ot.motif_attente) ? UI.html`<p class="accueil-motif-attente"><b>${I18n.t('ordres.prise.motif_attente')}</b> ${ot.motif_attente}</p>` : ''}
      ${Ordres.releveCarteHtml(ot)}
    </a></li>`;
    return UI.html`<article class="carte accueil-en-attente-equipe" ${repere ? UI.brut('data-aide-apres') : ''}>
      <div class="entete-carte"><h2>${I18n.t('ordres.prise.en_attente_equipe_n', { n: ots.length })}</h2></div>
      ${ots.length ? UI.html`<ul class="liste-cartes">${ots.slice(0, NOMBRE_A_PRENDRE).map(ligne)}</ul>`
        : UI.html`<p class="muted">${I18n.t('ordres.prise.rien_en_attente_equipe')}</p>`}
      ${ots.length > NOMBRE_A_PRENDRE ? UI.html`<p class="accueil-voir-tout"><a href="#/ot">${I18n.t('ordres.prise.voir_tous_en_attente', { reste: ots.length - NOMBRE_A_PRENDRE })}</a></p>` : ''}
    </article>`;
  }

  function phraseReprise(reprise, pourLeCollegue) {
    const valeurs = { nomTechnicien: prenom(reprise.technicienId), nomPrecedent: prenom(reprise.precedentId),
      otId: reprise.ot.id, titre: texte(reprise.ot.titre), date: UI.dateFr(reprise.date), heure: reprise.date.slice(11, 16) };
    return pourLeCollegue ? I18n.t('ordres.prise.reprise_de_votre_ot', valeurs) : I18n.t('ordres.prise.reprise_par', valeurs);
  }

  function listeReprises(reprises, pourLeCollegue) {
    return UI.html`<ul class="ot-reprises">${reprises.map((reprise) => UI.html`<li>
      <a href="#/ot/${encodeURIComponent(reprise.ot.id)}">${phraseReprise(reprise, pourLeCollegue)}</a></li>`)}</ul>`;
  }

  /** Accueil du technicien : les reprises de SES OT par un collègue (7 jours) ; '' s'il n'y en a pas. */
  function repriseDeMesOt() {
    const moi = monTechnicien();
    if (!moi) return '';
    const reprises = reprisesRecentes(Donnees.lignes('ordres_travail'), joursAvant(Donnees.aujourdhui(), JOURS_REPRISES), moi);
    if (!reprises.length) return '';
    return UI.html`<article class="carte accueil-reprises" role="status">
      <div class="entete-carte"><h2>${I18n.t('ordres.prise.vos_ot_repris')}</h2></div>${listeReprises(reprises, true)}</article>`;
  }

  /** L17 : accueil du responsable, ligne discrète « Demandes prises par les techniciens » (7 jours, les 5 dernières) :
   *  ce qui a été accepté sans lui ; '' s'il n'y en a pas. */
  function prisesSansResponsable() {
    const prises = demandesPrisesParTechniciens(Donnees.lignes('demandes'), Donnees.lignes('ordres_travail'),
      joursAvant(Donnees.aujourdhui(), JOURS_REPRISES));
    if (!prises.length) return '';
    return UI.html`<article class="carte accueil-prises-techniciens">
      <div class="entete-carte"><h2>${I18n.t('ordres.prise.prises_par_techniciens')}</h2></div>
      <ul class="ot-reprises">${prises.slice(0, NOMBRE_A_PRENDRE).map((prise) => UI.html`<li>
        <a href="#/ot/${encodeURIComponent(prise.ot.id)}">${I18n.t('ordres.prise.prise_sans_vous', { diId: prise.demande.id,
          otId: prise.ot.id, nomTechnicien: prenom(prise.technicienId), titre: texte(prise.demande.symptome),
          date: UI.dateFr(prise.date), heure: prise.date.slice(11, 16) })}</a></li>`)}</ul></article>`;
  }

  /** Accueil du responsable : bloc court « Reprises récentes » (7 jours, les 5 dernières) ; '' s'il n'y en a pas. */
  function reprisesResponsable() {
    const reprises = reprisesRecentes(Donnees.lignes('ordres_travail'), joursAvant(Donnees.aujourdhui(), JOURS_REPRISES));
    if (!reprises.length) return '';
    return UI.html`<article class="carte accueil-reprises">
      <div class="entete-carte"><h2>${I18n.t('ordres.prise.reprises_recentes')}</h2><span class="badge info">${reprises.length}</span></div>
      ${listeReprises(reprises.slice(0, NOMBRE_A_PRENDRE), false)}</article>`;
  }

  /** Accueil du technicien (L14), juste après « Mes ordres de travail » : « À prendre » puis, hors mode Solo, « En
   *  attente dans l'équipe ». telephone : blocs marqués data-aide-apres (l'aide à l'écran vient après eux). Rend
   *  { html, nombreAPrendre } (le nombre est redit par « Mes ordres de travail » quand elle est vide). */
  function blocsAccueilTechnicien(telephone) {
    const ordres = Donnees.lignes('ordres_travail');
    const aPrendre = otsAPrendre(ordres);
    // L17 : les demandes « Nouvelle », pour un technicien lié à sa fiche, quand le réglage le permet.
    const demandes = estTechnicien() && monTechnicien() && typeof Demandes !== 'undefined' && Demandes.demandesAPrendre
      ? Demandes.demandesAPrendre(Donnees.lignes('demandes')) : [];
    const solo = typeof App !== 'undefined' && App.modeSolo && App.modeSolo();
    const html = UI.html`${carteAPrendre(aPrendre, demandes, telephone)}${solo ? '' : carteEnAttenteEquipe(otsEnAttenteEquipe(ordres, monTechnicien()), telephone)}`;
    return { html, nombreAPrendre: aPrendre.length + demandes.length };
  }

  Object.assign(Ordres.interne, {
    noterPrise, boutonsPrise, brancherPrise, rangerActions, placerTechnicienLecture, prisesEnChargeHtml, prisesEnChargeBon,
    technicienOuPrendre, boutonPrendreCarte, brancherPriseListe,
  });

  return {
    // règles pures (prises en charge, format 5)
    lirePrises, ajouterPrise, estPassation, priseProposee, reprisesRecentes, otsAPrendre, otsEnAttenteEquipe, demandesPrisesParTechniciens,
    joursAvant,
    // écriture
    prendre, monTechnicien,
    // accueils (accueil.js, accueil-bento.js : cherchés au moment de l'affichage)
    blocsAccueilTechnicien, brancherAccueilTechnicien, prendreDemandeParEcran, repriseDeMesOt, reprisesResponsable,
    prisesSansResponsable,
  };
})());
