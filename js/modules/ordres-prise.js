'use strict';
// Ordres — « Je prends cet OT » et reprise de l'OT d'un collègue (lot 1 ergonomie, A3, T516 ; ARCHITECTURE.md §14.2,
// « Prises en charge »). Un technicien (compte technicien lié à sa fiche, profil Technicien d'un poste sans comptes, ou
// responsable en mode Solo : App.technicienSolo()) met à son nom un OT ouvert sans technicien (« Je prends cet OT »,
// fiche et liste) ou affecté à un collègue (« Reprendre cet OT à mon nom », fiche, avec confirmation). Chaque prise,
// reprise ou changement de technicien (préparation, planning) ajoute une ligne à ordres_travail.prises_en_charge
// (format 5 : « date_heure|technicien_id|technicien_precedent_id », le dernier vide pour une première prise) ; la
// ligne du journal (profil posé par le serveur) reste la trace d'autorité. RG8 (D191) : la règle de l'affectation,
// inchangée (Ordres.controlerAffectation ; la dérogation reste au responsable, Ordres.avecDerogation).
// Affichage : bloc « Prises en charge » de la fiche et du bon de travail ; sur l'accueil du technicien, la carte
// « À prendre » et les reprises de ses OT (7 jours) ; sur celui du responsable, « Reprises récentes ».
// Chargé après ordres-habilitations.js ; les écrans des fichiers précédents l'appellent par Ordres.interne au moment
// de l'appel. Complète l'objet Ordres.

Object.assign(Ordres, (() => {

  const { estOuvert, nomTechnicien, controlerAffectation, ecrireAvecTrace } = Ordres;
  const { texte, estResponsable, estTechnicien, apresEnregistrement } = Ordres.interne;

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
   * Reprises (lignes avec un précédent) datées de `depuis` (ISO) ou après, les plus récentes d'abord ; precedentId :
   * seulement celles qui ont repris un OT à ce technicien. → [{ ot, date, technicienId, precedentId }].
   */
  function reprisesRecentes(ordres, depuis, precedentId) {
    const resultat = [];
    ordres.forEach((ot) => lirePrises(ot.prises_en_charge).forEach((prise) => {
      if (!prise.precedentId || prise.date.slice(0, 10) < depuis) return;
      if (precedentId && prise.precedentId !== precedentId) return;
      if (prise.technicienId === prise.precedentId) return;
      resultat.push(Object.assign({ ot }, prise));
    }));
    return resultat.sort((a, b) => b.date.localeCompare(a.date) || b.ot.id.localeCompare(a.ot.id));
  }

  /** OT ouverts sans technicien, priorité puis date prévue (puis n°). */
  function otsAPrendre(ordres) {
    return ordres.filter((ot) => estOuvert(ot) && !texte(ot.technicien_id))
      .sort((a, b) => (RANG_PRIORITE[a.priorite] || 9) - (RANG_PRIORITE[b.priorite] || 9)
        || texte(a.date_prevue || '9999').localeCompare(texte(b.date_prevue || '9999')) || a.id.localeCompare(b.id));
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

  function phrasePrise(prise) {
    return prise.precedentId
      ? I18n.t('ordres.prise.ligne_reprise', { nomTechnicien: prenom(prise.technicienId), nomPrecedent: prenom(prise.precedentId) })
      : I18n.t('ordres.prise.ligne_prise', { nomTechnicien: prenom(prise.technicienId) });
  }

  /** Bloc « Prises en charge » de la fiche (carte Repères) : '' s'il n'y en a aucune. */
  function prisesEnChargeHtml(ot) {
    const prises = lirePrises(ot.prises_en_charge);
    if (!prises.length) return '';
    return UI.html`<h3 class="ot-sous-titre">${I18n.t('ordres.prise.titre_bloc')}</h3>
      <ul class="ot-prises">${prises.map((prise) => UI.html`<li><span class="sans-coupure">${UI.dateHeureFr(prise.date)}</span> — ${phrasePrise(prise)}</li>`)}</ul>`;
  }

  /** Même bloc sur le bon de travail. */
  function prisesEnChargeBon(ot) {
    const prises = lirePrises(ot.prises_en_charge);
    if (!prises.length) return '';
    return UI.html`<section class="bt-prises"><h2>${I18n.t('ordres.prise.titre_bloc')}</h2>
      <ul>${prises.map((prise) => UI.html`<li>${UI.dateHeureFr(prise.date)} — ${phrasePrise(prise)}</li>`)}</ul></section>`;
  }

  function boutonPrise(sorte, otId) {
    if (!sorte) return '';
    const libelle = sorte === 'prendre' ? I18n.t('ordres.prise.je_prends') : I18n.t('ordres.prise.reprendre');
    return UI.html`<button type="button" class="btn ${sorte === 'prendre' ? 'btn-primaire' : 'btn-secondaire'}" data-action="prendre-ot" data-ot="${otId}">${UI.icone('valider')}${libelle}</button>`;
  }

  /** Bouton de la carte Actions de la fiche (« Je prends cet OT » ou « Reprendre cet OT à mon nom »), ou ''. */
  function boutonsPrise(ot) {
    return boutonPrise(priseProposee(ot, monTechnicien()), ot.id);
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

  /** Clics sur « Je prends » / « Reprendre » dans la fiche (carte Actions, onglet Préparation). */
  function brancherPrise(racine, ot) {
    racine.addEventListener('click', (evenement) => {
      const bouton = evenement.target.closest('button[data-action="prendre-ot"]');
      if (bouton) demanderPrise(ot.id, bouton, false);
    });
  }

  /**
   * Prise ou reprise par l'écran : confirmation qui nomme le collègue pour une reprise ; RG8 comme l'affectation ;
   * puis la fiche réaffichée, « Démarrer » proposé (sur la liste : la fiche ouverte).
   */
  async function demanderPrise(otId, bouton, depuisListe) {
    const actuel = Donnees.trouver('ordres_travail', otId);
    const moi = monTechnicien();
    const sorte = priseProposee(actuel, moi);
    if (!sorte) return;
    const precedent = texte(actuel.technicien_id);
    if (sorte === 'reprendre' && !(await UI.confirmer(
      I18n.t('ordres.prise.confirmer_reprise', { nomTechnicien: prenom(precedent) }),
      { titre: I18n.t('ordres.prise.titre_reprise', { otId }), oui: I18n.t('ordres.prise.reprendre_oui') }))) return;
    if (bouton) bouton.disabled = true;
    try {
      await Ordres.avecDerogation((options) => prendre(otId, moi, precedent, options));
    } catch (erreur) {
      App.signalerErreur(erreur, 'prise en charge d\'un OT');
      if (bouton && document.contains(bouton)) bouton.disabled = false;
      return;
    }
    UI.toast(sorte === 'prendre' ? I18n.t('ordres.prise.prise_faite', { otId }) : I18n.t('ordres.prise.reprise_faite', { otId, nomTechnicien: prenom(precedent) }), 'succes');
    if (depuisListe) { App.naviguer('#/ot/' + encodeURIComponent(otId)); return; }
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

  function ligneOtAccueil(ot) {
    const equipement = Donnees.trouver('equipements', ot.equipement_id);
    return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' ? 'accent-p1' : (ot.priorite === 'P2' ? 'accent-p2' : '')}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${equipement ? (equipement.repere || equipement.id) : texte(ot.equipement_id)}</span>${ot.date_prevue ? UI.html`<span>${UI.dateFr(ot.date_prevue)}</span>` : ''}</div>
    </a></li>`;
  }

  /** Accueil du technicien : carte « À prendre » (nombre d'OT ouverts sans technicien, les 5 premiers, lien filtré). */
  function carteAPrendre() {
    const ots = otsAPrendre(Donnees.lignes('ordres_travail'));
    return UI.html`<article class="carte accueil-a-prendre">
      <div class="entete-carte"><h2>${I18n.t('ordres.prise.a_prendre')}</h2><span class="badge ${ots.length ? 'info' : 'neutre'}">${ots.length}</span></div>
      ${ots.length ? UI.html`<ul class="liste-cartes">${ots.slice(0, NOMBRE_A_PRENDRE).map(ligneOtAccueil)}</ul>`
        : UI.html`<p class="muted">${I18n.t('ordres.prise.rien_a_prendre')}</p>`}
      ${ots.length ? UI.html`<p class="accueil-voir-tout"><a href="#/ot?technicien=__aucun">${I18n.t('ordres.prise.voir_non_affectes')}</a></p>` : ''}
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

  /** Accueil du responsable : bloc court « Reprises récentes » (7 jours, les 5 dernières) ; '' s'il n'y en a pas. */
  function reprisesResponsable() {
    const reprises = reprisesRecentes(Donnees.lignes('ordres_travail'), joursAvant(Donnees.aujourdhui(), JOURS_REPRISES));
    if (!reprises.length) return '';
    return UI.html`<article class="carte accueil-reprises">
      <div class="entete-carte"><h2>${I18n.t('ordres.prise.reprises_recentes')}</h2><span class="badge info">${reprises.length}</span></div>
      ${listeReprises(reprises.slice(0, NOMBRE_A_PRENDRE), false)}</article>`;
  }

  /** Accueil du technicien, après ses habilitations (D199 : elles suivent ses OT) : la carte « À prendre ». Ses OT repris
   * par un collègue (repriseDeMesOt) viennent, eux, en tête de l'accueil, avant ses OT (T528). */
  function accueilTechnicien() {
    return carteAPrendre();
  }

  Object.assign(Ordres.interne, {
    noterPrise, boutonsPrise, brancherPrise, placerTechnicienLecture, prisesEnChargeHtml, prisesEnChargeBon,
    technicienOuPrendre, boutonPrendreCarte, brancherPriseListe,
  });

  return {
    // règles pures (prises en charge, format 5)
    lirePrises, ajouterPrise, priseProposee, reprisesRecentes, otsAPrendre, joursAvant,
    // écriture
    prendre, monTechnicien,
    // accueils (accueil.js, accueil-bento.js : cherchés au moment de l'affichage)
    accueilTechnicien, repriseDeMesOt, reprisesResponsable,
  };
})());
