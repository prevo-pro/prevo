'use strict';
// EquipeUtilisateurs — « Ajouter des utilisateurs » (L05, lot 2 ergonomie ; ARCHITECTURE.md §22.3) : écran
// #/equipe/utilisateurs, carte de l'accueil (carteAccueil, appelée par accueil.js) et bouton de l'écran Équipe.
//   Opérateurs : le QR d'une invitation d'appareil (POST /api/acces/invitations, durée de la configuration), montré
//     par le responsable ou par un technicien (seul droit nouveau du technicien, tenu par le serveur).
//   Techniciens : le responsable seul saisit prénom, nom et métier ; Prévo crée la fiche et le compte ensemble
//     (POST /api/acces/comptes {nouvelle_fiche, metier, qr}) et montre un QR de premier accès : la personne le flashe
//     et choisit son mot de passe (connexion-ecrans.js, #/premier-acces/<jeton>), sans mot de passe provisoire.
//     En Solo : un lien vers « Passer en équipe » (Paramètres › Organisation).
//   Direction (le patron, lecture seule) : le responsable seul, par QR, sans fiche.
// Le QR et son lien sont montrés une seule fois, jamais mémorisés. Sans comptes (portée « ce PC ») : un lien vers
// Paramètres › Accès et installation. Dépendances : App, UI, Donnees, EquipeAcces (api, lienInvitation).

const EquipeUtilisateurs = (() => {

  const LIEN_ACCES = '#/parametres?rubrique=acces';
  const LIEN_ORGANISATION = '#/parametres?rubrique=solo';
  const texte = (valeur) => String(valeur === undefined || valeur === null ? '' : valeur).trim();

  /** « 2026-10-26T10:05:00 » → « 26/10/2026 10:05 ». */
  function dateHeure(valeur) {
    const trouve = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(texte(valeur));
    return trouve ? trouve[3] + '/' + trouve[2] + '/' + trouve[1] + ' ' + trouve[4] + ':' + trouve[5] : texte(valeur);
  }

  /** Comptes exigés sur ce serveur : seuls cas où des utilisateurs s'ajoutent. */
  const avecComptes = () => App.mode === 'serveur' && Boolean(App.comptesExiges && App.comptesExiges());

  // ===========================================================================================
  // 1. Fenêtre du QR (invitation d'un appareil, premier accès d'un compte) : montrée une seule fois
  // ===========================================================================================

  /** QR et lien dans une fenêtre ; ids de la fenêtre d'invitation d'Équipe › Accès gardés (acces-invitation-…). */
  function montrerQr(titre, phrase, chemin, note) {
    const lien = EquipeAcces.lienInvitation(chemin);
    const contenu = UI.element(UI.html`<div class="form-colonne acces-invitation">
      <p>${phrase}</p>
      <div class="acces-qr"><div class="acces-qr-image" id="acces-invitation-qr"></div>
        <div class="acces-lien champ"><label for="acces-invitation-lien">${I18n.t('equipe.montrer_invitation.lien_invitation')}</label>
          <input type="text" id="acces-invitation-lien" readonly value="${lien}" spellcheck="false"></div></div>
      <p class="note">${note || I18n.t('equipe.montrer_invitation.qr_montre_fois_fermez')}</p>
    </div>`);
    UI.remplir(UI.$('#acces-invitation-qr', contenu), UI.qrSvg(lien, 220));
    return UI.fenetre({ titre: titre, classe: 'equipe-fenetre', contenu: contenu,
      boutons: [{ libelle: I18n.t('commun.bouton.fermer'), valeur: null, classe: 'btn-primaire', defaut: true }] });
  }

  /** Invitation d'appareil créée (Équipe › Accès ou un opérateur ici) : son QR. */
  function montrerInvitation(resultat) {
    const invitation = resultat.invitation || {};
    const phrase = invitation.poste ? I18n.t('equipe.poste_declaration.invitation_texte', { dateHeure: dateHeure(invitation.expire_le) })
      : I18n.html('equipe.montrer_invitation.telephone_scanne_qr_ouvre', { dateHeure: dateHeure(invitation.expire_le) });
    return montrerQr(I18n.t('equipe.montrer_invitation.invitation_invitation_id', { invitationId: texte(invitation.id) }),
      phrase, resultat.chemin);
  }

  /** QR de premier accès d'un compte (créé ici, ou « QR » d'Équipe › Accès). */
  function montrerPremierAcces(resultat) {
    const compte = resultat.compte || {};
    return montrerQr(I18n.t('equipe.utilisateurs.qr_titre', { prenom: texte(compte.prenom) }),
      I18n.html('equipe.utilisateurs.qr_texte', { prenom: texte(compte.prenom), identifiant: texte(compte.identifiant),
        dateHeure: dateHeure(resultat.expire_le) }),
      resultat.chemin, I18n.t('equipe.utilisateurs.qr_note'));
  }

  // ===========================================================================================
  // 2. Actions
  // ===========================================================================================

  async function pendant(bouton, contexte, action) {
    if (bouton.disabled) return;
    bouton.disabled = true;
    try { await action(); } catch (erreur) { App.signalerErreur(erreur, contexte); } finally { bouton.disabled = false; }
  }

  function inviterOperateur(bouton) {
    // Sans « heures » : la durée réglée pour les invitations (invitation_heures).
    return pendant(bouton, 'invitation',async () => montrerInvitation(await EquipeAcces.api.creerInvitation()));
  }

  const champ = (nom, libelle, options) => UI.champ(Object.assign({ nom: nom, type: 'texte', libelle: libelle }, options || {}), '',
    { attributs: { maxlength: '60' } });

  /** Technicien (avec sa fiche) ou Direction : fenêtre prénom, nom (et métier), puis le QR. */
  async function ajouterParQr(role) {
    const technicien = role === 'technicien';
    const autre = UI.champ({ nom: 'autre_personne', type: 'booleen', libelle: I18n.t('equipe.champs_compte.autre_personne') }, '0');
    autre.hidden = true;
    let resultat = null;
    const fait = await UI.fenetreAction({
      titre: technicien ? I18n.t('equipe.utilisateurs.ajouter_technicien') : I18n.t('equipe.utilisateurs.ajouter_direction'),
      introduction: technicien ? I18n.t('equipe.utilisateurs.technicien_intro') : I18n.t('equipe.utilisateurs.direction_intro'),
      champs: [champ('prenom', I18n.t('commun.champ.prenom'), { obligatoire: true }), champ('nom', I18n.t('equipe.champs_compte.nom'))]
        .concat(technicien ? [champ('metier', I18n.t('equipe.utilisateurs.metier'))] : [], [autre]),
      libelleValider: I18n.t('equipe.utilisateurs.creer_qr'),
      verifier: (valeurs) => (texte(valeurs.prenom) ? [] : [{ nom: 'prenom', message: I18n.t('equipe.verifier_compte.prenom_obligatoire') }]),
      action: async (valeurs, contenu) => {
        const corps = { prenom: texte(valeurs.prenom), nom: texte(valeurs.nom), role: role, qr: true,
          autre_personne: valeurs.autre_personne === '1' };
        if (technicien) Object.assign(corps, { nouvelle_fiche: true, metier: texte(valeurs.metier) });
        try {
          resultat = await EquipeAcces.api.creerCompte(corps);
        } catch (erreur) {
          if (!erreur || erreur.code !== 'comptes.meme_personne') throw erreur;
          UI.$('[data-champ="autre_personne"]', contenu).hidden = false;
          throw new Donnees.ErreurValidation(erreur.message);
        }
      },
    });
    if (!fait || !resultat) return;
    App.marquerSaisie(false);
    if (technicien) await Donnees.rechargerTable('techniciens').catch(() => {});      // la fiche écrite par le serveur
    await montrerPremierAcces(resultat);
  }

  // ===========================================================================================
  // 3. Écran et carte de l'accueil
  // ===========================================================================================

  function lienAcces() {
    return I18n.html('equipe.utilisateurs.sans_comptes', { lien: LIEN_ACCES });
  }

  function carte(id, titre, phrase, bouton) {
    return UI.html`<section class="carte acces-carte" id="${id}"><div class="entete-carte"><h2>${titre}</h2></div>
      <p>${phrase}</p>${bouton ? UI.html`<div class="actions">${bouton}</div>` : ''}</section>`;
  }

  const bouton = (id, icone, libelle) => UI.html`<button type="button" class="btn btn-primaire" id="${id}">${UI.icone(icone)}${libelle}</button>`;

  function afficher(conteneur) {
    App.definirTitre(I18n.t('equipe.utilisateurs.titre'));
    const responsable = App.estResponsable();
    let corps;
    if (!avecComptes()) {
      corps = UI.bandeau('info', lienAcces());
    } else {
      const techniciens = !responsable ? ''
        : App.modeSolo() ? carte('utilisateurs-techniciens', I18n.t('equipe.utilisateurs.techniciens'),
          I18n.html('equipe.utilisateurs.solo_technicien', { lien: LIEN_ORGANISATION }))
          : carte('utilisateurs-techniciens', I18n.t('equipe.utilisateurs.techniciens'), I18n.t('equipe.utilisateurs.techniciens_phrase'),
            bouton('utilisateurs-ajouter-technicien', 'ajouter', I18n.t('equipe.utilisateurs.ajouter_technicien')));
      corps = UI.html`${carte('utilisateurs-operateurs', I18n.t('equipe.utilisateurs.operateurs'), I18n.t('equipe.utilisateurs.operateurs_phrase'),
        bouton('utilisateurs-inviter-operateur', 'qr', I18n.t('equipe.utilisateurs.montrer_qr_operateur')))}
        ${techniciens}
        ${responsable ? carte('utilisateurs-direction', I18n.t('equipe.utilisateurs.direction'), I18n.t('equipe.utilisateurs.direction_phrase'),
    bouton('utilisateurs-ajouter-direction', 'ajouter', I18n.t('equipe.utilisateurs.ajouter_direction'))) : ''}`;
    }
    UI.remplir(conteneur, UI.html`<div class="equipe equipe-utilisateurs">
      <div class="entete-page"><div><div class="fil">${I18n.html('equipe.utilisateurs.fil')}</div>
        <h1>${I18n.t('equipe.utilisateurs.titre')}</h1><p>${I18n.t('equipe.utilisateurs.sous_titre')}</p></div></div>
      <div class="form-colonne">${corps}</div></div>`);
    const brancher = (id, action) => { const b = UI.$('#' + id, conteneur); if (b) b.addEventListener('click', () => action(b)); };
    brancher('utilisateurs-inviter-operateur', inviterOperateur);
    brancher('utilisateurs-ajouter-technicien', () => ajouterParQr('technicien'));
    brancher('utilisateurs-ajouter-direction', () => ajouterParQr('direction'));
  }

  /** Carte « Ajouter des utilisateurs » de l'accueil (responsable, en Solo aussi ; technicien avec comptes) ; '' sinon. */
  function carteAccueil() {
    // Sans comptes, le réglage se fait sur le PC serveur seulement : rien à proposer sur un téléphone.
    if (App.mode !== 'serveur' || (!avecComptes() && UI.estTelephone())) return '';
    const responsable = App.estResponsable();
    if (!responsable && !(App.estTechnicien() && avecComptes())) return '';
    const phrase = !avecComptes() ? lienAcces()
      : !responsable ? I18n.t('equipe.utilisateurs.carte_technicien')
        : App.modeSolo() ? I18n.t('equipe.utilisateurs.carte_solo') : I18n.t('equipe.utilisateurs.carte_responsable');
    const lien = avecComptes() ? UI.html`<div class="actions"><a class="btn btn-secondaire" id="lien-ajouter-utilisateurs" href="#/equipe/utilisateurs">${UI.icone(responsable ? 'equipe' : 'qr')}${responsable ? I18n.t('equipe.utilisateurs.titre') : I18n.t('equipe.utilisateurs.montrer_qr_operateur')}</a></div>` : '';
    return UI.html`<article class="carte" id="carte-ajouter-utilisateurs">
      <div class="entete-carte"><h2>${I18n.t('equipe.utilisateurs.titre')}</h2></div><p>${phrase}</p>${lien}</article>`;
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'equipe-utilisateurs', route: /^#\/equipe\/utilisateurs$/, parent: 'equipe',
      get titre() { return I18n.t('equipe.utilisateurs.titre'); },
      profils: ['responsable', 'technicien'],
      tables: [],
      afficher: afficher,
    });
  });

  return { carteAccueil, montrerInvitation, montrerPremierAcces };
})();
