'use strict';
// Parametres (3/4) — carte « Organisation : seul ou en équipe » de l'écran Paramètres (ARCHITECTURE.md §22.11 ; CDC
// D132 ; lot 1 ergonomie, B, T521). Le mode Solo est le profil Responsable avec le réglage mode_solo = 1 de
// parametres.csv, pas un quatrième profil (App.modeSolo(), App.technicienSolo() dans js/app.js ; flux sans la couche
// équipe : solo-flux.js).
//   En Solo : le technicien « moi », « Ma fiche » (taux horaire, habilitations : #/equipe/<id>), les accès (QR des
//   opérateurs, accès de la direction : #/equipe/acces, mode serveur) et « Passer en équipe » : mode_solo = 0, rien
//   n'est supprimé (les OT gardent leur technicien, le compte reste responsable, cloture_une_etape tel quel) ; une
//   fenêtre dit quoi faire ensuite (ajouter un technicien, lui créer un accès), avec les liens.
//   En équipe : « Revenir en Solo », possible seulement s'il ne reste qu'un technicien actif dans techniciens.csv ET, en
//   mode comptes, aucun autre compte technicien ou responsable actif (GET /api/acces/comptes ; le serveur refuse aussi
//   le passage de mode_solo à 1 dans ce cas, controle_d_ecriture de parametres) ; sinon un message nomme ce qui
//   l'empêche et où le régler. Aucun technicien actif : prénom, nom, métier → technicien « moi » créé par les écritures du
//   module Équipe (Equipe.creerTechnicien ; repris s'il existe déjà, actif, sous le même nom). Les OT ouverts sans
//   technicien ou au nom d'un technicien inactif passent au nom du technicien seul après confirmation (une ligne de
//   prise en charge chacun). Puis mode_solo = 1, solo_technicien_id et cloture_une_etape = 1.
// Les réglages (libellés, aides) sont déclarés dans la liste REGLAGES de parametres-reglages.js, que parametres.js
// passe à la carte par un relais (carteSolo, brancherSolo). Complète l'objet Parametres.

Object.assign(Parametres.interne, (() => {

  const ROLES_DE_LA_MAINTENANCE = ['technicien', 'responsable'];
  let reglages = [];                          // REGLAGES, reçus à l'affichage

  function reglage(cle) {
    return reglages.find((candidat) => candidat.cle === cle) || { libelle: cle, aide: '' };
  }

  const texte = (valeur) => String(valeur === undefined || valeur === null ? '' : valeur).trim();

  // Écrit des clés de parametres.csv (ligne créée si elle manque) en une seule écriture.
  function ecrireParametres(valeurs, action) {
    return Donnees.modifier('parametres', (lignes) => {
      Object.keys(valeurs).forEach((cle) => {
        const ligne = lignes.find((l) => l.cle === cle);
        if (ligne) ligne.valeur = valeurs[cle]; else lignes.push({ cle: cle, valeur: valeurs[cle] });
      });
    }, { action: action });
  }

  function nomTechnicien(technicien) {
    return [technicien.prenom, technicien.nom].map((partie) => texte(partie)).filter(Boolean).join(' ');
  }

  // ===========================================================================================
  // Règles du retour en Solo
  // ===========================================================================================

  function techniciensActifs() {
    return Donnees.lignes('techniciens').filter((t) => texte(t.actif) !== '0');
  }

  /** OT ouverts sans technicien ou au nom d'un technicien inactif (ou inconnu) : ils passeront au technicien seul. */
  function otsAReprendre(moiId) {
    const actifs = new Set(techniciensActifs().map((t) => t.id));
    return Donnees.lignes('ordres_travail').filter((ot) => Ordres.estOuvert(ot)
      && texte(ot.technicien_id) !== moiId && (!texte(ot.technicien_id) || !actifs.has(texte(ot.technicien_id))));
  }

  /** Autres comptes actifs de la maintenance (mode comptes) : [{ identifiant, nom, role }] ; [] sans comptes. */
  async function autresComptes() {
    if (App.mode !== 'serveur' || !App.comptesExiges() || typeof EquipeAcces === 'undefined') return [];
    const moi = texte(App.session && App.session.identifiant);
    const reponse = await EquipeAcces.api.comptes();
    return (reponse.comptes || []).filter((compte) => compte.actif && ROLES_DE_LA_MAINTENANCE.includes(compte.role)
      && texte(compte.identifiant) !== moi)
      .map((compte) => ({ identifiant: compte.identifiant, nom: nomTechnicien(compte) || compte.identifiant, role: compte.role }));
  }

  /** Ce qui empêche le retour en Solo (fragment UI.html), ou '' : plusieurs techniciens actifs, d'autres comptes. */
  async function obstacleAuSolo() {
    const actifs = techniciensActifs();
    if (actifs.length > 1) {
      return I18n.html('parametres.organisation.refus_techniciens', { n: actifs.length,
        liste: actifs.map((t) => nomTechnicien(t) || t.id).join(', '), lien: '#/equipe' });
    }
    const comptes = await autresComptes();
    if (comptes.length) {
      return I18n.html('parametres.organisation.refus_comptes', { n: comptes.length,
        liste: comptes.map((c) => c.nom + ' (' + I18n.t('equipe.role.' + c.role) + ')').join(', '), lien: '#/equipe/acces' });
    }
    return '';
  }

  // ===========================================================================================
  // Carte
  // ===========================================================================================

  /** Carte « Organisation : seul ou en équipe » (fragment UI.html) ; `listeReglages` : REGLAGES. */
  function carteSolo(listeReglages) {
    reglages = listeReglages || [];
    const actif = App.modeSolo();
    const technicienId = App.technicienSolo();
    const technicien = technicienId ? Donnees.trouver('techniciens', technicienId) : null;
    const t = (cle, valeurs) => I18n.t('parametres.organisation.' + cle, valeurs);
    return UI.html`<article class="carte" id="carte-solo">
      <div class="entete-carte"><h2>${t('titre')}</h2><span class="badge ${actif ? 'ok' : 'info'}" id="solo-etat">${actif ? t('etat_seul') : t('etat_equipe')}</span></div>
      ${actif ? UI.html`<p>${reglage('mode_solo').aide}</p>
        <dl class="valeurs">
          <dt>${reglage('solo_technicien_id').libelle}</dt>
          <dd id="solo-technicien">${technicien ? UI.html`${nomTechnicien(technicien) || technicien.id} (${technicien.id})` : I18n.t('parametres.carte_solo.aucun')}</dd>
        </dl>
        <ul class="organisation-liens">
          ${technicien ? UI.html`<li><a id="solo-ma-fiche" href="#/equipe/${encodeURIComponent(technicien.id)}">${t('ma_fiche')}</a></li>` : ''}
          ${App.mode === 'serveur' ? UI.html`<li><a id="solo-acces" href="#/equipe/acces">${t('acces')}</a></li>` : ''}
        </ul>
        <p class="note">${t('embauche')}</p>
        <div class="actions"><button type="button" class="btn btn-secondaire" id="btn-passer-equipe">${UI.icone('equipe')}${t('passer_equipe')}</button></div>`
    : UI.html`<p>${t('equipe_explication')}</p>
        <p class="note">${I18n.html('parametres.organisation.ensuite', { nouveau: '#/equipe/nouveau', acces: '#/equipe/acces' })}</p>
        <p class="erreur-champ" id="solo-refus" role="alert" hidden></p>
        <div class="actions"><button type="button" class="btn btn-secondaire" id="btn-passer-solo">${UI.icone('utilisateur')}${t('revenir_solo')}</button></div>`}
    </article>`;
  }

  // ===========================================================================================
  // Écritures
  // ===========================================================================================

  // Technicien actif de même prénom et nom (casse et accents ignorés) : repris plutôt que doublé.
  function technicienExistant(valeurs) {
    const cle = UI.normaliserRecherche(valeurs.nom + ' ' + valeurs.prenom);
    return techniciensActifs().find((t) => UI.normaliserRecherche(texte(t.nom) + ' ' + texte(t.prenom)) === cle) || null;
  }

  /** Aucun technicien actif : prénom, nom, métier → technicien « moi » (créé ou repris). Rend son id, '' si annulé. */
  async function demanderMoi() {
    let technicienId = '';
    const fait = await UI.fenetreAction({
      titre: I18n.t('parametres.organisation.revenir_solo'), libelleValider: I18n.t('commun.bouton.continuer'),
      introduction: UI.html`<p>${I18n.t('parametres.passer_en_solo.faites_maintenance_meme_prevo')}</p>`,
      champs: [
        UI.champ({ nom: 'prenom', type: 'texte', libelle: I18n.t('commun.champ.prenom') }, '', { obligatoire: true }),
        UI.champ({ nom: 'nom', type: 'texte', libelle: I18n.t('parametres.passer_en_solo.nom') }, '', { obligatoire: true }),
        UI.champ({ nom: 'metier', type: 'texte', libelle: I18n.t('parametres.passer_en_solo.metier_facultatif') }, ''),
      ],
      verifier: () => [],
      action: async (valeurs) => {
        const existant = technicienExistant(valeurs);
        technicienId = existant ? existant.id
          : await Equipe.creerTechnicien({ prenom: valeurs.prenom, nom: valeurs.nom, metier: valeurs.metier });
      },
    });
    return fait ? technicienId : '';
  }

  /** Les OT à reprendre passent au nom de moiId (une ligne de prise en charge chacun), en une écriture. */
  function reprendreOts(moiId, ids) {
    if (!ids.length) return Promise.resolve();
    return Donnees.modifier('ordres_travail', (lignes) => {
      lignes.forEach((ot) => {
        if (!ids.includes(ot.id) || !Ordres.estOuvert(ot) || texte(ot.technicien_id) === moiId) return;
        Ordres.interne.noterPrise(ot, moiId);
        ot.technicien_id = moiId;
      });
    }, { action: I18n.donnees('parametres.organisation.journal_reprise', { moiId, n: ids.length }) });
  }

  /** Confirmation qui nomme les OT repris ; vrai si accepté (ou rien à reprendre). */
  async function confirmerReprise(moiId, ots) {
    if (!ots.length) return true;
    const choix = await UI.fenetre({
      titre: I18n.t('parametres.organisation.revenir_solo'),
      contenu: UI.element(UI.html`<div id="solo-confirmation">
        <p>${I18n.t('parametres.organisation.ots_repris', { n: ots.length, nom: nomTechnicien(Donnees.trouver('techniciens', moiId) || {}) || moiId })}</p>
        <ul>${ots.slice(0, 10).map((ot) => UI.html`<li>${ot.id} — ${ot.titre}</li>`)}</ul>
        ${ots.length > 10 ? UI.html`<p class="note">${I18n.t('parametres.organisation.et_autres', { n: ots.length - 10 })}</p>` : ''}
      </div>`),
      boutons: [{ libelle: I18n.t('commun.bouton.annuler'), valeur: false, classe: 'btn-fantome' },
        { libelle: I18n.t('parametres.organisation.revenir_solo'), valeur: true, classe: 'btn-primaire', defaut: true }],
    });
    return choix === true;
  }

  function montrerRefus(contenu) {
    const zone = UI.$('#solo-refus');
    if (!zone) { UI.toast(String(contenu), 'attention'); return; }
    UI.remplir(zone, contenu);
    zone.hidden = !contenu;
  }

  async function revenirEnSolo() {
    montrerRefus('');
    const obstacle = await obstacleAuSolo();
    if (obstacle) { montrerRefus(obstacle); return; }
    const actifs = techniciensActifs();
    const moiId = actifs.length === 1 ? actifs[0].id : await demanderMoi();
    if (!moiId) return;
    const ots = otsAReprendre(moiId);
    if (!await confirmerReprise(moiId, ots)) return;
    await reprendreOts(moiId, ots.map((ot) => ot.id));
    await ecrireParametres({ mode_solo: '1', solo_technicien_id: moiId, cloture_une_etape: '1' }, I18n.donnees('parametres.passer_en_solo.passage_mode_solo'));   // journal (D156)
    App.marquerSaisie(false);
    UI.toast(I18n.t('parametres.passer_en_solo.mode_solo_active'), 'succes');
    await App.reafficher();
  }

  async function passerEnEquipe() {
    await ecrireParametres({ mode_solo: '0' }, I18n.donnees('parametres.quitter_solo.fin_mode_solo'));      // journal (D156)
    App.marquerSaisie(false);
    UI.toast(I18n.t('parametres.quitter_solo.mode_solo_quitte_rien'), 'succes');
    await App.reafficher();
    // Ce qu'il faut faire ensuite, avec les liens (la fenêtre se ferme quand on suit un lien).
    const contenu = UI.element(UI.html`<div id="solo-ensuite"><p>${I18n.t('parametres.organisation.equipe_explication')}</p>
      <ol><li><a href="#/equipe/nouveau">${I18n.t('parametres.organisation.ajouter_technicien')}</a></li>
        ${App.mode === 'serveur' ? UI.html`<li><a href="#/equipe/acces">${I18n.t('parametres.organisation.creer_acces')}</a></li>` : ''}</ol></div>`);
    UI.fenetre({
      titre: I18n.t('parametres.organisation.vous_etes_equipe'), contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.fermer'), valeur: null, classe: 'btn-secondaire', defaut: true }],
      surOuverture(dialogue, fermer) {
        contenu.addEventListener('click', (evenement) => { if (evenement.target.closest('a')) fermer(null); });
      },
    });
  }

  /**
   * T323 (Nicolas, 07/11) : mode Solo dont le technicien « moi » n'est plus reconnu (vidé par un import ZIP, fiche
   * supprimée) : Prévo demande au responsable qui est « moi » au lieu de deviner : une fiche de l'équipe, ou une fiche
   * à créer (prénom, nom). Appelé par js/app.js une fois l'application prête ; Annuler laisse la question pour la
   * prochaine ouverture. Rend vrai si « moi » a été posé.
   */
  async function demanderMoiSolo() {
    const actifs = techniciensActifs();
    const liste = UI.champ({ nom: 'technicien', type: 'choix', libelle: I18n.t('parametres.demander_moi_solo.ma_fiche'),
      valeurs: actifs.map((t) => t.id) }, '');          // l'option vide de la liste : « la créer »
    UI.$$('option', liste).forEach((option) => {
      const fiche = actifs.find((t) => t.id === option.value);
      option.textContent = fiche ? (nomTechnicien(fiche) || fiche.id) + ' (' + fiche.id + ')' : I18n.t('parametres.demander_moi_solo.pas_dans_la_liste');
    });
    const fait = await UI.fenetreAction({
      titre: I18n.t('parametres.demander_moi_solo.qui_est_moi'), libelleValider: I18n.t('parametres.demander_moi_solo.c_est_moi'),
      introduction: UI.html`<p id="solo-moi-question">${I18n.t('parametres.demander_moi_solo.prevo_ne_devine_pas')}</p>`,
      champs: [liste,
        UI.champ({ nom: 'prenom', type: 'texte', libelle: I18n.t('commun.champ.prenom') }, ''),
        UI.champ({ nom: 'nom', type: 'texte', libelle: I18n.t('parametres.passer_en_solo.nom') }, '')],
      verifier: (valeurs) => (valeurs.technicien || texte(valeurs.nom) ? []
        : [{ nom: 'nom', message: I18n.t('parametres.demander_moi_solo.choisir_ou_creer') }]),
      action: async (valeurs) => {
        let technicienId = valeurs.technicien;
        if (!technicienId) {
          const existant = technicienExistant(valeurs);
          technicienId = existant ? existant.id : await Equipe.creerTechnicien({ prenom: valeurs.prenom, nom: valeurs.nom });
        }
        await ecrireParametres({ solo_technicien_id: technicienId }, I18n.donnees('parametres.demander_moi_solo.moi_choisi'));   // journal (D156)
      },
    });
    if (!fait) return false;
    App.marquerSaisie(false);
    UI.toast(I18n.t('parametres.demander_moi_solo.moi_enregistre'), 'succes');
    await App.reafficher();
    return true;
  }

  /** Branche les boutons de la carte ; `pendant(bouton, contexte, action)` : outil de parametres.js. */
  function brancherSolo(conteneur, pendant) {
    const solo = UI.$('#btn-passer-solo', conteneur);
    if (solo) solo.addEventListener('click', () => pendant(solo, 'retour en Solo', revenirEnSolo));
    const equipe = UI.$('#btn-passer-equipe', conteneur);
    if (equipe) equipe.addEventListener('click', () => pendant(equipe, 'passage en équipe', passerEnEquipe));
  }

  return { carteSolo, brancherSolo, demanderMoiSolo, otsAReprendre };
})());
