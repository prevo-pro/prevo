'use strict';
// InstallationFiche : la fiche d'accès imprimable de l'assistant d'installation (étape 8 et route #/installation/fiche ;
// ARCHITECTURE.md §22.10 ; D131 ; CS130), mise en page d'après GET /api/installation/fiche : adresses de la porte,
// QR « ouvrir Prévo » (UI.qrSvg sur l'adresse de la porte) ; quand l'autorité locale existe, ce même QR sert aussi à
// « faire confiance au PC atelier » (la porte guide le téléphone : un seul QR, T527), adresse Tailscale et du mandataire, comment arrêter et
// relancer, où sont les données, mot de passe oublié. « Imprimer » copie la fiche dans #impression (seul imprimé,
// règle de css/style.css) puis window.print() ; à l'impression : fond blanc, encre noire, aucun bouton, QR
// lisibles (css/modules/installation.css, @media print). Après l'installation, la fiche reste consultable dans la
// coque sur #/installation/fiche (responsable, mode serveur ; le serveur ne la sert qu'au PC serveur : message sinon).
// Dépendances : UI ; App (route dans la coque). Un seul écouteur DOMContentLoaded pour le module « installation ».

const InstallationFiche = (() => {

  const TAILLE_QR_PX = 160;
  const DELAI_NETTOYAGE_IMPRESSION_MS = 2000;   // #impression vidé après l'impression (afterprint, ou ce délai)

  /** Première adresse par laquelle les autres appareils ouvrent Prévo (la porte), sinon ce PC. */
  function adressePrincipale(fiche) {
    return (fiche.adresses && fiche.adresses[0]) || fiche.adresse_tailscale
      || (fiche.adresses_mandataire && fiche.adresses_mandataire[0]) || fiche.adresse_locale || '';
  }

  function qr(texte, libelle, id) {
    let dessin;
    try {
      dessin = UI.qrSvg(texte, TAILLE_QR_PX);
    } catch (erreur) {
      dessin = UI.html`<p class="aide">${(erreur && erreur.message) || I18n.t('installation.qr.qr_indisponible')}</p>`;
    }
    return UI.html`<figure class="fiche-qr" id="${id}">${dessin}<figcaption><b>${libelle}</b><span class="fiche-adresse">${texte}</span></figcaption></figure>`;
  }

  // Lot 1 ergonomie (T518) : adresse principale du réseau de l'atelier ou Tailscale → l'avertissement « en 4G, le QR
  // donne une page d'erreur » (Parc.avertissementReseau) ; rien pour « ce PC » (la fiche le dit déjà) ni hors de la coque.
  function avertissementReseau(adresse) {
    if (typeof Parc === 'undefined' || !Parc.avertissementReseau || Parc.porteeAdresse(adresse) === 'ce-pc') return '';
    return Parc.avertissementReseau(adresse, { lienPortee: true, lienEtiquettes: true });
  }

  // L04 (lot 2) : une seule adresse pour les téléphones (la première : la carte qui porte la connexion du PC, choisie
  // par le serveur), les autres repliées sous « Autres adresses de ce PC ».
  function autresAdresses(autres) {
    if (!autres.length) return '';
    return UI.html`<details class="note autres-adresses" id="fiche-autres-adresses"><summary>${I18n.t('installation.rendre.autres_adresses_pc')}</summary>
      <ul>${autres.map((adresse) => UI.html`<li class="fiche-adresse">${adresse}</li>`)}</ul></details>`;
  }

  function texteDemarrage(fiche) {
    const lanceur = fiche.lanceur || 'Lancer_GMAO.bat';
    if (fiche.demarrage === 'systeme') {
      return I18n.t('installation.texte_demarrage.prevo_demarre_pc_sans', { lanceur });
    }
    if (fiche.demarrage === 'session') {
      return I18n.t('installation.texte_demarrage.prevo_demarre_quand_ouvrez', { lanceur });
    }
    return I18n.t('installation.texte_demarrage.prevo_lance_main_double', { lanceur });
  }

  function texteMotDePasse(fiche) {
    if (!fiche.comptes) {
      return UI.html`<p>${I18n.t('installation.texte_mot_de_passe.aucun_mot_passe_prevo')}</p>`;
    }
    const reinitialisation = fiche.reinitialisation || {};
    const commande = reinitialisation.commande || I18n.t('installation.mot_de_passe.commande_reinitialiser');
    const responsables = fiche.responsables || [];
    const solo = fiche.situation === 'seul' || App.modeSolo();
    return UI.html`<p>${reinitialisation.script
      ? I18n.html('installation.mot_de_passe.perdu_script', { script: reinitialisation.script, commande })
      : I18n.html('installation.mot_de_passe.perdu', { commande })}</p>
      ${responsables.length ? UI.html`<p>${solo   // T546 (L33) : en Solo, pas d'entrée Équipe au menu : lien vers « Accès : QR des opérateurs » (Paramètres)
        ? I18n.html('installation.mot_de_passe.responsables_solo', { n: responsables.length, responsables: responsables.join(', '), lien: '#/equipe/acces' })
        : I18n.html('installation.mot_de_passe.responsables', { n: responsables.length, responsables: responsables.join(', ') })}</p>` : ''}`;
  }

  /** Élément de la fiche d'accès (données de GET /api/installation/fiche). L02 (lot 2) : tant que l'installation n'est
   *  pas terminée hors de « ce PC » (telephones_apres_terminer), ni adresse ni QR pour les téléphones — Prévo n'écoute
   *  encore que ce PC (D122) — mais la phrase qui dit quand ils pourront se connecter. */
  function rendre(fiche) {
    const principale = adressePrincipale(fiche);
    const reseau = (fiche.adresses || []).concat(fiche.adresses_mandataire || []);
    // T527 : « faire confiance au PC atelier » a la même adresse (la porte) : un seul QR qui dit les deux usages.
    const confiance = Boolean(fiche.autorite_presente && fiche.adresse_confiance);
    return UI.element(UI.html`<div class="fiche-acces">
      <div class="fiche-entete">
        <div><h2>${I18n.t('installation.rendre.fiche_acces_prevo')}</h2><p class="aide">${I18n.t('installation.rendre.imprimer_garder_pres_pc')}</p></div>
        <button type="button" class="btn btn-secondaire sans-impression" id="fiche-imprimer">${UI.icone('imprimer')}<span>${I18n.t('commun.bouton.imprimer')}</span></button>
      </div>
      <section class="fiche-bloc">
        <h3>${I18n.t('installation.rendre.ouvrir_prevo')}</h3>
        <p>${I18n.html('installation.rendre.sur_ce_pc', { adresse: fiche.adresse_locale || '' })}</p>
        ${reseau.length ? UI.html`<p>${I18n.t('installation.rendre.depuis_postes_telephones_atelier')}</p>
          <ul><li class="fiche-adresse" id="fiche-adresse-principale">${reseau[0]}</li></ul>
          ${autresAdresses(reseau.slice(1))}` : ''}
        ${fiche.adresse_tailscale ? UI.html`<p>${I18n.html('installation.rendre.hors_atelier_tailscale_application', { adresse_tailscale: fiche.adresse_tailscale })}</p>` : ''}
        ${fiche.portee === 'ce-pc' ? UI.html`<p>${I18n.t('installation.rendre.prevo_joignable_pc_aucune')}</p>` : ''}
        ${fiche.telephones_apres_terminer ? UI.html`<div class="encadre info" id="fiche-telephones-apres-terminer">
          <p>${I18n.t('installation.rendre.telephones_apres_terminer')}</p></div>` : UI.html`<div class="fiche-qrs">
          ${qr(principale, confiance ? I18n.t('installation.rendre.ouvrir_prevo_et_confiance') : I18n.t('installation.rendre.ouvrir_prevo'), 'fiche-qr-ouvrir')}
        </div>
        ${confiance ? UI.html`<p class="aide">${I18n.t('installation.rendre.meme_qr_confiance')}</p>` : ''}
        ${avertissementReseau(principale)}`}
      </section>
      <section class="fiche-bloc">
        <h3>${I18n.t('installation.rendre.arreter_relancer')}</h3>
        <p>${texteDemarrage(fiche)}</p>
      </section>
      <section class="fiche-bloc">
        <h3>${I18n.t('installation.rendre.ou_sont_donnees')}</h3>
        <p>${I18n.html('installation.rendre.prevo_fichiers_csv_documents', { dossier: fiche.dossier || '', dossierDonnees: fiche.dossier_donnees || '' })}</p>
        <p>${fiche.copie_sauvegardes ? UI.html`${I18n.html('installation.rendre.copie_externe_chaque_nuit', { copie_sauvegardes: fiche.copie_sauvegardes })}`
          : I18n.t('installation.rendre.aucune_copie_externe_regler')}</p>
      </section>
      <section class="fiche-bloc">
        <h3>${I18n.t('installation.rendre.mot_passe_oublie')}</h3>
        ${texteMotDePasse(fiche)}
      </section>
    </div>`);
  }

  // Impression : la fiche seule, copiée dans #impression (enfant direct de body, seul imprimé quand il est rempli).
  function preparerImpression(element) {
    const zone = UI.$('#impression');
    UI.remplir(zone, element.cloneNode(true));
    return zone;
  }

  function terminerImpression() {
    const zone = UI.$('#impression');
    if (zone) zone.textContent = '';
  }

  function imprimer(element) {
    preparerImpression(element);
    window.addEventListener('afterprint', terminerImpression, { once: true });
    setTimeout(terminerImpression, DELAI_NETTOYAGE_IMPRESSION_MS);
    window.print();
  }

  /** Branche « Imprimer » sur une fiche rendue (rendre), puis la rend. */
  function brancher(element) {
    const bouton = UI.$('#fiche-imprimer', element);
    if (bouton) bouton.addEventListener('click', () => imprimer(element));
    return element;
  }

  async function lire() {
    let reponse;
    try {
      reponse = await fetch('/api/installation/fiche', { cache: 'no-store', credentials: 'same-origin' });
    } catch (erreur) {
      throw new Error(I18n.t('installation.lire.serveur_prevo_repond_pas'));
    }
    const donnees = await reponse.json().catch(() => null);
    if (!reponse.ok) {
      throw new Error(reponse.status === 404 ? I18n.t('installation.lire.fiche_acces_consulte_pc')
        : (donnees && StockageServeur.texte(donnees, 'erreur')) || I18n.t('commun.message.serveur_a_repondu', { status: reponse.status }));
    }
    return donnees;
  }

  // Dans la coque, après l'installation : #/installation et #/installation/fiche montrent la fiche (responsable).
  async function afficherDansLaCoque(conteneur) {
    UI.remplir(conteneur, UI.html`<div class="entete-page"><h1>${I18n.t('installation.dans_la_coque.fiche_acces')}</h1></div>`);
    if (App.mode !== 'serveur') {
      conteneur.appendChild(UI.element(UI.vide(I18n.t('installation.dans_la_coque.pas_serveur'), I18n.t('installation.dans_la_coque.fiche_acces_decrit_serveur'))));
      return;
    }
    let fiche;
    try {
      fiche = await lire();
    } catch (erreur) {
      conteneur.appendChild(UI.bandeau('attention', (erreur && erreur.message) || String(erreur)));
      return;
    }
    conteneur.appendChild(brancher(rendre(fiche)));
    conteneur.appendChild(UI.element(UI.html`<p class="note">${I18n.t('installation.dans_la_coque.reglages_acces_refont_parametres')}</p>`));
  }

  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'installation-fiche', route: /^#\/installation(\/fiche)?$/,
      get titre() { return I18n.t('installation.dans_la_coque.fiche_acces'); },
      profils: ['responsable'],
      afficher(conteneur) { return afficherDansLaCoque(conteneur); },
    });
  });

  return { rendre: (fiche) => brancher(rendre(fiche)), imprimer, preparerImpression, terminerImpression, adressePrincipale, lire };
})();
