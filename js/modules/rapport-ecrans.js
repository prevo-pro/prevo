'use strict';
// Rapport (2/2) — figer un rapport mensuel (document HTML daté, jamais écrasé : « Recalculer » crée
// une révision), onglet « Rapports mensuels » de l'écran Indicateurs, tuile de l'accueil qui
// propose de figer le mois écoulé (ARCHITECTURE.md §15.10 ; CDC du lot 3, D43 à D45).
//   4. Figer : écriture du document, liste rapports_mensuels (parametres.csv), journal
//   5. Onglet « Rapports mensuels » : figer un mois, ouvrir, imprimer, recalculer, télécharger (démo)
//   6. Tuile de l'accueil (responsable, T90) : « Figer » ou « Plus tard » ; rien n'est écrit sans clic
//   7. Bilan du mois : ce qui manque et où le renseigner, activité du mois (T519 ; fonctions pures pour Rapport.donnees)
// T519 (lot 1 ergonomie, A6) : « Voir le bilan » affiche le mois en cours (chiffres provisoires) et le premier mois
// d'utilisation, sans rien enregistrer ; seul un mois terminé se fige (figer refuse le mois en cours).
// Complète l'objet Rapport créé par rapport-contenu.js.

Object.assign(Rapport, (() => {

  const { enLangueDuRapport, texte, nomDemande, libelleMois, decalerMois, lienCourriel, estCouvert, debutHistorique, repere } = Rapport.interne;
  const ESSAIS_DE_NOM = 50;
  const CLE_PLUS_TARD = 'prevo.rapport.plusTard';     // sessionStorage : mois reporté à plus tard
  // Appliqué au nom demandé (nomDemande de rapport-contenu.js : préfixe d'horodatage du serveur retiré, audit F4).
  const MOTIF_NOM = /^rapport-mensuel-(\d{4}-\d{2})(?:-r(\d+))?\.html$/;

  /** « de septembre 2026 », « d'octobre 2026 », « d'août 2026 » (élision devant une voyelle). */
  function deMois(mois) {
    const libelle = libelleMois(mois);
    // Les deux formes sont dans le dictionnaire (« for September 2026 » en anglais, T289).
    return I18n.t(/^[aeiouyàâéèêîôû]/i.test(libelle) ? 'rapport.de_mois.elision' : 'rapport.de_mois.de', { mois: libelle });
  }

  // ===========================================================================================
  // 4. Figer
  // ===========================================================================================

  /** 'rapport-mensuel-2026-09.html', puis '…-r2.html', '…-r3.html'… */
  function nomFichier(mois, revision) {
    return Rapport.PREFIXE_FICHIER + mois + (revision > 1 ? '-r' + revision : '') + '.html';
  }

  /** Le stockage refuse le nom parce qu'un document le porte déjà (jamais d'écrasement). */
  function estNomPris(erreur) {
    return erreur instanceof Donnees.ErreurStockage && /existe déjà|porte déjà ce nom/.test(erreur.message);
  }

  /**
   * Fige le rapport d'un mois 'AAAA-MM' → { nom, rapport }. Le document est écrit par l'adaptateur
   * de stockage (donnees/documents/ en modes serveur et dossier, mémoire en démo) sous un nom libre :
   * le premier de la série qui n'est ni dans rapports_mensuels ni déjà sur le disque. Puis le nom
   * est ajouté à rapports_mensuels (une écriture de parametres.csv, journalisée).
   */
  async function figer(mois, options) {
    if (!/^\d{4}-\d{2}$/.test(texte(mois))) throw new Donnees.ErreurValidation(I18n.t('rapport.figer.mois_invalide', { mois }));
    const reglages = options || {};
    // Un bilan provisoire n'est jamais figé (T519) : seul un mois terminé l'est.
    if (mois >= (texte(reglages.aujourdhui).slice(0, 10) || Donnees.aujourdhui()).slice(0, 7)) {
      throw new Donnees.ErreurValidation(I18n.t('rapport.figer.mois_pas_termine', { mois: libelleMois(mois) }));
    }
    // Langue du rapport (D160) : choisie au moment de figer, sinon celle de l'installation ; son dictionnaire est chargé au besoin.
    const langue = reglages.langue || '';
    if (langue) await I18n.chargerLangue(langue);
    const rapport = Rapport.donnees(mois, reglages.aujourdhui, reglages.maintenant, langue);
    const page = await Rapport.html(mois, { donnees: rapport, commentaire: reglages.commentaire, langue });
    const dejaFiges = Rapport.rapportsFiges().map(nomDemande);
    let revision = 1;
    while (dejaFiges.includes(nomFichier(mois, revision))) revision += 1;
    let nom = null;
    for (let essai = 0; essai < ESSAIS_DE_NOM && !nom; essai += 1) {
      try {
        nom = await App.adaptateur.ecrireDocument(nomFichier(mois, revision + essai), new Blob([page], { type: 'text/html;charset=utf-8' }));
      } catch (erreur) {
        if (!estNomPris(erreur)) throw erreur;
      }
    }
    if (!nom) throw new Donnees.ErreurStockage(I18n.t('rapport.figer.aucun_nom_libre_rapport', { deMois: deMois(mois) }));
    await Donnees.modifier('parametres', (lignes) => {
      let ligne = lignes.find((candidate) => candidate.cle === 'rapports_mensuels');
      if (!ligne) { ligne = { cle: 'rapports_mensuels', valeur: '' }; lignes.push(ligne); }
      const liste = texte(ligne.valeur).split(',').map(texte).filter(Boolean);
      if (!liste.includes(nom)) liste.push(nom);
      ligne.valeur = liste.join(',');
    }, { action: 'rapport mensuel figé : ' + nom });
    return { nom, rapport };
  }

  // ===========================================================================================
  // 5. Onglet « Rapports mensuels »
  // ===========================================================================================

  /** Mois que l'on peut figer : les 24 derniers mois couverts par l'historique, du plus récent. */
  function moisProposables() {
    const courant = Donnees.aujourdhui().slice(0, 7);
    const liste = [];
    for (let rang = 1; rang <= 24; rang += 1) {
      const mois = decalerMois(courant, -rang);
      if (estCouvert(mois)) liste.push(mois);
    }
    return liste;
  }

  /** Mois dont on peut voir le bilan sans l'enregistrer : le mois en cours (T519), puis (L30) chaque mois passé qui a des
   *  données — un OT créé, démarré ou terminé, un temps passé, une demande —, du plus récent au plus ancien. */
  function moisApercu() {
    const courant = Donnees.aujourdhui().slice(0, 7);
    const mois = new Set();
    const noter = (valeur) => { const m = texte(valeur).slice(0, 7); if (/^\d{4}-\d{2}$/.test(m) && m < courant) mois.add(m); };
    Donnees.lignes('ordres_travail').forEach((ot) => { noter(ot.date_creation); noter(ot.date_debut); noter(ot.date_fin); });
    Donnees.lignes('ot_temps').forEach((ligne) => noter(ligne.date));
    Donnees.lignes('demandes').forEach((demande) => noter(demande.date_heure));
    return [courant].concat(Array.from(mois).sort().reverse());
  }

  /** Libellé d'un mois de « Voir le bilan » : en cours, premier mois d'utilisation (commencé avant le 1er OT), ou le mois. */
  function libelleApercu(mois, courant) {
    if (mois === courant) return I18n.t('rapport.apercu.mois_en_cours', { mois: libelleMois(mois) });
    return mois === debutHistorique().slice(0, 7) && !estCouvert(mois) ? I18n.t('rapport.apercu.premier_mois', { mois: libelleMois(mois) }) : libelleMois(mois);
  }

  /** Bilan d'un mois affiché dans un nouvel onglet, isolé (Donnees.documentAffichable), sans rien enregistrer. */
  async function voirBilan(mois, options) {
    const page = await Rapport.html(mois, options || { apercu: true });
    const affichable = await Donnees.documentAffichable('bilan-' + mois + '.html', new Blob([page], { type: 'text/html;charset=utf-8' }));
    const adresse = URL.createObjectURL(affichable);
    window.open(adresse, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(adresse), 60000);
    return page;
  }

  function lignesDesRapports() {
    return Rapport.rapportsFiges().map((nom) => Object.assign({ nom }, (() => {
      const morceaux = MOTIF_NOM.exec(nomDemande(nom));
      return morceaux ? { mois: morceaux[1], revision: Number(morceaux[2] || 1) } : { mois: '', revision: 1 };
    })())).reverse();
  }

  /** Ouvre le document dans un nouvel onglet (rouvrable sans Prévo). */
  async function ouvrir(nom) {
    const adresse = await App.adaptateur.urlDocument(nom);
    if (!adresse) throw new Donnees.ErreurStockage(I18n.t('rapport.ouvrir.rapport_introuvable_documents', { nom }));
    window.open(adresse, '_blank', 'noopener');
  }

  /** Imprime le document : il est affiché dans un cadre isolé (aucun script n'y tourne), puis imprimé. */
  async function imprimer(nom) {
    const blob = await App.adaptateur.lireDocument(nom);
    if (!blob) throw new Donnees.ErreurStockage(I18n.t('rapport.ouvrir.rapport_introuvable_documents', { nom }));
    const cadre = document.createElement('iframe');
    cadre.setAttribute('sandbox', 'allow-same-origin allow-modals');
    cadre.className = 'rapport-cadre-impression';
    cadre.title = I18n.t('rapport.imprimer.impression_rapport', { nom });
    cadre.srcdoc = await blob.text();
    cadre.addEventListener('load', () => {
      cadre.contentWindow.print();
      setTimeout(() => cadre.remove(), 1000);
    }, { once: true });
    document.body.appendChild(cadre);
  }

  async function telecharger(nom) {
    const blob = await App.adaptateur.lireDocument(nom);
    if (!blob) throw new Donnees.ErreurStockage(I18n.t('rapport.telecharger.rapport_introuvable', { nom }));
    UI.telecharger(nom, blob);
  }

  /**
   * Direction (T520, A7) : le bilan d'un mois calculé à la demande et ouvert dans un nouvel onglet, sans rien écrire
   * (ni document ni rapports_mensuels : figer reste au responsable).
   */
  function carteBilan(proposables) {
    return UI.html`<article class="carte rapports-bilan">
      <div class="entete-carte"><h2>${I18n.t('rapport.bilan.titre')}</h2></div>
      <p class="note">${I18n.t('rapport.bilan.explication')}</p>
      ${proposables.length ? UI.html`<div class="rapports-bilan-formulaire">
        <div class="champ"><label class="libelle" for="rapports-bilan-mois">${I18n.t('rapport.onglet.mois')}</label>
          <select id="rapports-bilan-mois" data-hors-saisie>${proposables.map((mois) => UI.html`<option value="${mois}">${libelleMois(mois)}</option>`)}</select></div>
        <button type="button" class="btn btn-primaire" data-action="voir-bilan">${I18n.t('rapport.bilan.voir')}</button>
      </div>` : UI.html`<p>${I18n.t('rapport.onglet.aucun_mois_complet_historique')}</p>`}
    </article>`;
  }

  function messageFige(resultat) {
    return UI.html`${I18n.html('rapport.message_fige.rapport_fige', { mois: deMois(resultat.rapport.mois), nom: resultat.nom, adresse: lienCourriel(resultat.rapport) })}`;
  }

  function afficherOnglet(conteneur) {
    const proposables = moisProposables();
    const rapports = lignesDesRapports();
    const demo = App.mode === 'demo';
    const direction = App.estDirection();        // T520 : lecture seule — bilan d'un mois sans le figer, rapports figés
    const apercu = moisApercu();
    const courant = Donnees.aujourdhui().slice(0, 7);
    UI.remplir(conteneur, UI.html`<div class="rapports">
      <div id="rapports-message"></div>
      <article class="carte rapports-apercu">
        <div class="entete-carte"><h2>${I18n.t('rapport.apercu.titre')}</h2></div>
        <p class="note">${I18n.t('rapport.apercu.note')}</p>
        <form class="rapports-apercu-formulaire" data-hors-saisie>
          <div class="champ"><label class="libelle" for="rapports-apercu-mois">${I18n.t('rapport.onglet.mois')}</label>
            <select id="rapports-apercu-mois">${apercu.map((mois) => UI.html`<option value="${mois}">${libelleApercu(mois, courant)}</option>`)}</select></div>
          <button type="submit" class="btn btn-secondaire">${I18n.t('rapport.apercu.voir_bilan')}</button>
        </form>
      </article>
      ${direction ? carteBilan(proposables) : UI.html`<article class="carte rapports-figer">
        <div class="entete-carte"><h2>${I18n.t('rapport.onglet.figer_rapport_mensuel')}</h2></div>
        <p class="note">${I18n.t('rapport.onglet.page_4_direction_disponibilite')}</p>
        ${proposables.length ? UI.html`<form class="rapports-formulaire" data-hors-saisie>
          <div class="champ"><label class="libelle" for="rapports-mois">${I18n.t('rapport.onglet.mois')}</label>
            <select id="rapports-mois">${proposables.map((mois) => UI.html`<option value="${mois}">${libelleMois(mois)}</option>`)}</select></div>
          <div class="champ"><label class="libelle" for="rapports-langue">${I18n.t('rapport.onglet.langue_du_rapport')}</label>
            <select id="rapports-langue">${I18n.langues.map((langue) => UI.html`<option value="${langue.code}" ${langue.code === I18n.installation ? 'selected' : ''}>${langue.nom}</option>`)}</select></div>
          <div class="champ large"><label class="libelle" for="rapports-commentaire">${I18n.t('rapport.onglet.commentaire_mois_facultatif')}</label>
            <textarea id="rapports-commentaire" rows="4" maxlength="4000" data-dictee></textarea></div>
          <p class="note large rapports-enregistrer-explication">${I18n.t('rapport.onglet.enregistrer_explication')}</p>
          <button type="submit" class="btn btn-primaire">${I18n.t('rapport.onglet.figer_rapport')}</button>
        </form>` : UI.html`<p>${I18n.t('rapport.onglet.aucun_mois_complet_historique')}</p>`}
      </article>`}
      <article class="carte rapports-liste">
        <div class="entete-carte"><h2>${I18n.t('rapport.onglet.rapports_figes')}</h2><span class="badge ${rapports.length ? 'info' : 'neutre'}">${rapports.length}</span></div>
        ${rapports.length ? UI.html`<div class="table-defile"><table class="table">
          <thead><tr><th scope="col">${I18n.t('rapport.onglet.mois')}</th><th scope="col">${I18n.t('rapport.onglet.fichier')}</th><th scope="col">${I18n.t('rapport.onglet.actions')}</th></tr></thead>
          <tbody>${rapports.map((ligne) => UI.html`<tr data-nom="${ligne.nom}">
            <td>${ligne.mois ? libelleMois(ligne.mois) : '—'}${ligne.revision > 1 ? UI.html` <span class="badge neutre">${I18n.t('rapport.onglet.revision_revision', { revision: ligne.revision })}</span>` : ''}</td>
            <td><code>${ligne.nom}</code></td>
            <td class="actions">
              <button type="button" class="btn btn-secondaire" data-action="ouvrir" data-nom="${ligne.nom}">${I18n.t('rapport.onglet.ouvrir')}</button>
              <button type="button" class="btn btn-secondaire" data-action="imprimer" data-nom="${ligne.nom}">${I18n.t('commun.bouton.imprimer')}</button>
              ${ligne.mois && !direction ? UI.html`<button type="button" class="btn btn-fantome" data-action="recalculer" data-mois="${ligne.mois}">${I18n.t('rapport.onglet.recalculer')}</button>` : ''}
              ${demo || direction ? UI.html`<button type="button" class="btn btn-fantome" data-action="telecharger" data-nom="${ligne.nom}">${I18n.t('rapport.onglet.telecharger')}</button>` : ''}
            </td></tr>`)}</tbody></table></div>`
          : UI.vide(I18n.t('rapport.onglet.aucun_rapport_fige'), direction ? I18n.t('rapport.bilan.aucun_rapport_fige_direction')
            : I18n.t('rapport.onglet.figez_mois_ecoule_garder'), 'indicateurs')}
      </article></div>`);
    const racine = conteneur.querySelector('.rapports');
    const message = (type, contenu) => UI.remplir(racine.querySelector('#rapports-message'), UI.bandeau(type, contenu));
    const formulaireApercu = racine.querySelector('.rapports-apercu-formulaire');
    formulaireApercu.addEventListener('submit', async (evenement) => {
      evenement.preventDefault();
      const bouton = formulaireApercu.querySelector('button[type=submit]');
      bouton.disabled = true;
      try { await voirBilan(formulaireApercu.querySelector('#rapports-apercu-mois').value); } catch (erreur) { App.signalerErreur(erreur, 'bilan du mois'); }
      finally { bouton.disabled = false; }
    });
    const formulaire = racine.querySelector('.rapports-formulaire');
    if (formulaire) {
      const zoneCommentaire = formulaire.querySelector('#rapports-commentaire');
      brancherCommentaireIa(formulaire, zoneCommentaire);
      formulaire.addEventListener('submit', async (evenement) => {
        evenement.preventDefault();
        const commentaire = { texte: zoneCommentaire.value.trim(), aideIa: Boolean(zoneCommentaire.dataset.iaModele) };
        const mois = formulaire.querySelector('#rapports-mois').value;
        const ecart = commentaire.texte ? ecartDeMois(zoneCommentaire, mois) : '';
        if (ecart) { message('important', ecart); return; }            // rien n'est figé
        await executer(formulaire.querySelector('button[type=submit]'), async () => {
          const resultat = await figer(mois, { commentaire, langue: formulaire.querySelector('#rapports-langue').value });
          if (commentaire.texte && commentaire.aideIa) {
            try {
              await Ia.tracerUtilisation('parametres', 'rapports_mensuels', I18n.donnees('rapport.onglet.commentaire_rapport', { resultatNom: resultat.nom }), zoneCommentaire.dataset.iaModele);
            } catch (erreur) {                                            // le rapport est figé : on le dit quand même
              console.warn('Prévo (rapport) : trace de la proposition IA non écrite (' + (erreur && erreur.message) + ').', erreur);
            }
          }
          return resultat;
        }, conteneur, message);
      });
    }
    racine.addEventListener('click', async (evenement) => {
      const bouton = evenement.target.closest && evenement.target.closest('button[data-action]');
      if (!bouton || bouton.closest('form')) return;
      const actions = {
        ouvrir: () => ouvrir(bouton.dataset.nom), imprimer: () => imprimer(bouton.dataset.nom),
        telecharger: () => telecharger(bouton.dataset.nom),
        'voir-bilan': () => voirBilan(racine.querySelector('#rapports-bilan-mois').value, {}),
      };
      if (bouton.dataset.action === 'recalculer') {
        const choixLangue = racine.querySelector('#rapports-langue');       // recalculer : dans la langue proposée au formulaire
        await executer(bouton, () => figer(bouton.dataset.mois, choixLangue ? { langue: choixLangue.value } : {}), conteneur, message);
      } else if (actions[bouton.dataset.action]) {
        try { await actions[bouton.dataset.action](); } catch (erreur) { App.signalerErreur(erreur, 'rapport ' + bouton.dataset.nom); }
      }
    });
  }

  /**
   * Lot 4 (§17.5, D71) : « Proposer un commentaire » (bouton absent sans IA). L'IA écrit avec des jetons
   * remplacés par les chiffres du rapport ; un chiffre écrit en clair fait refuser la proposition. Le
   * commentaire reste modifiable ; rien n'est figé sans « Figer le rapport ».
   */
  function brancherCommentaireIa(formulaire, zoneCommentaire) {
    const choixMois = formulaire.querySelector('#rapports-mois');
    const note = UI.element(UI.html`<p class="erreur-champ rapports-ecart-mois" role="alert" hidden></p>`);
    zoneCommentaire.closest('.champ').appendChild(note);
    // Commentaire proposé pour un autre mois que celui choisi : ses chiffres sont faux pour ce mois (D71).
    const avertirMois = () => {
      const ecart = ecartDeMois(zoneCommentaire, choixMois.value);
      note.hidden = !ecart;
      note.textContent = ecart || '';
    };
    choixMois.addEventListener('change', avertirMois);
    zoneCommentaire.addEventListener('input', () => {
      if (!zoneCommentaire.value.trim()) { delete zoneCommentaire.dataset.iaModele; delete zoneCommentaire.dataset.iaMois; }
      avertirMois();
    });
    const zone = Ia.emplacement(I18n.t('rapport.brancher_commentaire_ia.proposer_commentaire'), () => {
      const mois = formulaire.querySelector('#rapports-mois').value;
      const langue = formulaire.querySelector('#rapports-langue').value;
      const remplir = (resultat, reponse, retoucher) => {
        zoneCommentaire.value = resultat.texte;
        zoneCommentaire.dataset.iaModele = reponse.modele;
        zoneCommentaire.dataset.iaMois = mois;           // ses chiffres sont ceux de ce mois-là
        avertirMois();
        if (retoucher) zoneCommentaire.focus();
      };
      // Le commentaire est imprimé dans le rapport figé : les données envoyées à l'IA sont dans la langue du rapport (D160).
      // Et la demande dit d'écrire dans cette langue (`langue`, D159), même si l'écran est dans une autre.
      I18n.chargerLangue(langue).then(() => {
        const rapport = Rapport.donnees(mois, undefined, undefined, langue);
        Ia.ouvrirEncadre({ apres: zone, fonction: 'commentaireRapport', langue,
          donnees: enLangueDuRapport(langue, () => ({ mois: libelleMois(mois), jetons: Rapport.jetonsCommentaire(rapport), points: rapport.faits.concat(rapport.decisions).map(sansChiffres) })),
          utiliser: (resultat, reponse) => remplir(resultat, reponse, false), modifier: (resultat, reponse) => remplir(resultat, reponse, true) });
      }).catch((erreur) => App.signalerErreur(erreur, 'commentaire du rapport'));
    });
    zoneCommentaire.closest('.champ').insertAdjacentElement('afterend', zone);
  }

  /** Message si le commentaire vient de l'IA pour un autre mois que `mois` ; '' sinon. */
  function ecartDeMois(zoneCommentaire, mois) {
    const iaMois = zoneCommentaire.dataset.iaModele ? zoneCommentaire.dataset.iaMois : '';
    if (!iaMois || iaMois === mois) return '';
    return I18n.t('rapport.ecart_de_mois.commentaire_ete_propose_ia', { moisIa: libelleMois(iaMois), moisRapport: libelleMois(mois) });
  }

  /** Point du rapport envoyé à l'IA sans chiffre ni montant (§17.3 : aucun coût ; D71 : l'IA n'écrit aucun chiffre). */
  function sansChiffres(point) {
    // Montants dans la devise réglée (T304) : son symbole et son code s'ajoutent à « € ».
    const unites = ['€', UI.symboleDevise(), UI.devise()].map((u) => u.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    const chiffres = new RegExp('\\d[\\d\\s\\u00a0\\u202f.,]*(?:\\s?(?:' + unites + '|%|h\\b|j\\b))?', 'g');
    return texte(point).replace(chiffres, I18n.t('rapport.sans_chiffres.texte') + ' ').replace(/\s+/g, ' ').trim();
  }

  /** Fige (ou recalcule) puis réaffiche l'onglet avec le message de réussite. */
  async function executer(bouton, action, conteneur, message) {
    bouton.disabled = true;
    try {
      const resultat = await action();
      UI.toast(I18n.t('rapport.executer.rapport_fige', { resultatNom: resultat.nom }), 'succes');
      afficherOnglet(conteneur);
      UI.remplir(conteneur.querySelector('#rapports-message'), UI.bandeau('succes', messageFige(resultat)));
    } catch (erreur) {
      if (erreur instanceof Donnees.ErreurValidation) message('important', erreur.message);
      else App.signalerErreur(erreur, 'rapport mensuel');
    } finally {
      if (document.contains(bouton)) bouton.disabled = false;
    }
  }

  // ===========================================================================================
  // 6. Tuile de l'accueil (responsable)
  // ===========================================================================================

  function moisReporte() {
    try { return sessionStorage.getItem(CLE_PLUS_TARD) || ''; } catch (erreur) { return ''; }
  }

  /**
   * Tuile « Rapport de <mois> — pas encore figé » de l'accueil du responsable (élément DOM, T90 ; mise
   * en page : css/modules/accueil.css) ou null : responsable seulement, mois proposé par
   * Rapport.moisAProposer, sauf s'il a été reporté (« Plus tard ») pendant cette ouverture de Prévo.
   * Rien n'est écrit sans clic sur « Figer ». « Plus tard » retire la tuile : la ligne des compteurs
   * s'étend (la grille ne la réserve que si elle est là).
   */
  function tuileAccueil() {
    if (!App.estResponsable()) return null;
    const mois = Rapport.moisAProposer(Donnees.aujourdhui());
    if (!mois || moisReporte() === mois) return null;
    const bloc = UI.element(UI.html`<section class="bento-tuile bento-rapport" id="bandeau-rapport" aria-labelledby="bento-rapport-titre">
      <div class="bento-rapport-texte">
        <h2 id="bento-rapport-titre">${I18n.t('rapport.tuile_accueil.rapport_de_mois', { deMois: deMois(mois) })}</h2>
        <p>${I18n.t('rapport.tuile_accueil.pas_encore_fige_page')}</p>
      </div>
      <div class="bento-rapport-actions">
        <button type="button" class="btn btn-primaire" data-action="figer-rapport"><span>${I18n.html('rapport.tuile_accueil.figer_rapport')}</span></button>
        <button type="button" class="btn btn-fantome" data-action="rapport-plus-tard">${I18n.t('rapport.tuile_accueil.plus_tard')}</button>
      </div>
    </section>`);
    bloc.querySelector('[data-action="figer-rapport"]').addEventListener('click', async (evenement) => {
      const bouton = evenement.currentTarget;
      bouton.disabled = true;
      try {
        const resultat = await figer(mois);
        UI.toast(I18n.t('rapport.executer.rapport_fige', { resultatNom: resultat.nom }), 'succes');
        await App.reafficher();
      } catch (erreur) {
        bouton.disabled = false;
        App.signalerErreur(erreur, 'rapport mensuel');
      }
    });
    bloc.querySelector('[data-action="rapport-plus-tard"]').addEventListener('click', () => {
      try { sessionStorage.setItem(CLE_PLUS_TARD, mois); } catch (erreur) { /* stockage refusé : la tuile part quand même */ }
      bloc.remove();
    });
    return bloc;
  }

  // ===========================================================================================
  // 7. Bilan du mois : ce qui manque, et où le renseigner ; activité du mois (T519, lot 1 ergonomie, A6). Fonctions
  //    PURES appelées par Rapport.donnees (rapport-contenu.js, par Rapport.interne). Un réglage absent n'est jamais
  //    remplacé par une valeur (D35) : il est nommé, avec l'écran où le saisir ; ce qui se calcule sans lui est affiché.
  // ===========================================================================================

  /** Nombre de noms ou de repères cités au plus par ligne (une page A4). */
  const NOMS_CITES = 4;
  /** Machines citées au plus dans l'activité du mois (une page A4). */
  const MACHINES_CITEES = 3;

  function citer(elements, libeller) {
    const noms = elements.slice(0, NOMS_CITES).map(libeller).join(', ');
    return elements.length > NOMS_CITES ? I18n.t('rapport.manque.et_autres', { liste: noms, n: elements.length - NOMS_CITES }) : noms;
  }

  function nomTechnicien(element) {
    const technicien = element.technicien;
    return technicien ? [texte(technicien.prenom), texte(technicien.nom)].filter(Boolean).join(' ') || technicien.id : element.technicienId;
  }

  function nomArticle(element) {
    return element.article ? texte(element.article.reference) || texte(element.article.designation) || element.articleId : element.articleId;
  }

  const enHeures = (valeur) => UI.heures(valeur);                    // L21 : « 1 h 15 », à la minute

  /** « 2,5 h sans taux horaire, 1 pièce sans prix » ('' si le coût est complet). */
  function manqueCout(manques) {
    const morceaux = [];
    const heures = manques.techniciens.reduce((somme, element) => somme + element.heures, 0);
    if (heures) morceaux.push(I18n.t('rapport.manque.heures_sans_taux', { duree: enHeures(heures) }));
    if (manques.articles.length) morceaux.push(I18n.t('rapport.manque.pieces_sans_prix', { n: manques.articles.length }));
    return morceaux.join(', ');
  }

  /** Lignes « ce qui manque » du coût de maintenance : main-d'œuvre sans taux horaire, pièces sans prix. */
  function manquesDuCout(manques) {
    const lignes = [];
    if (manques.techniciens.length) {
      lignes.push({ libelle: I18n.t('rapport.manque.main_oeuvre_non_chiffree'), ou: I18n.t('rapport.ou.taux_horaire'),
        raison: I18n.t('rapport.manque.taux_horaire_non_renseigne', { n: manques.techniciens.length,
          liste: citer(manques.techniciens, (element) => nomTechnicien(element) + ' (' + enHeures(element.heures) + ')') }) });
    }
    if (manques.articles.length) {
      lignes.push({ libelle: I18n.t('rapport.manque.pieces_non_chiffrees'), ou: I18n.t('rapport.ou.prix_unitaire'),
        raison: I18n.t('rapport.manque.prix_non_renseigne', { n: manques.articles.length,
          liste: citer(manques.articles, (element) => nomArticle(element) + ' (' + UI.nombreFr(element.quantite) + ')') }) });
    }
    return lignes;
  }

  /**
   * Tuiles « disponibilité » et « coût » quand un réglage manque : la disponibilité dit « à compléter » et ce qui manque
   * (aucune machine n'a ses heures par jour) ; le coût sans aucun taux ni prix n'est jamais un « 0 € » (« non chiffré »),
   * un coût partiel garde son montant avec « Partiel : … » et n'est comparé qu'entre deux mois complets.
   * `references` : { precedent, annee } → true (mois couvert, coût complet), false (couvert, incomplet), null (non couvert).
   */
  function completerTuiles(tuiles, global, manques, references, libellePrecedent, libelleAnnee) {
    tuiles.forEach((tuile) => {
      if (tuile.cle === 'disponibilite' && global.tempsRequis.valeur === null && global.tempsRequis.exclus.length) {
        Object.assign(tuile, { texteValeur: I18n.t('rapport.manque.a_completer'), raison: I18n.t('rapport.manque.disponibilite_heures'),
          precision: I18n.t('rapport.manque.disponibilite_heures'), ou: I18n.t('rapport.ou.heures_fonctionnement') });
      }
      if (tuile.cle !== 'cout') return;
      // L30 : les heures-homme du mois (OT clôturés, ceux du coût) toujours dites, que le coût soit chiffré ou non.
      tuile.heuresHomme = I18n.t('rapport.manque.heures_homme', { duree: enHeures(global.cout.heures || 0) });
      ['precedent', 'annee'].filter((cle) => references[cle] !== null && (!manques.complet || !references[cle])).forEach((cle) => {
        const libelleReference = cle === 'precedent' ? libellePrecedent : libelleAnnee;
        tuile.tendance[cle] = { sens: null, texte: I18n.t('rapport.comparer.non_comparable_cout_incomplet', { libelleReference }) };
      });
      if (manques.complet || tuile.valeur === null) return;
      const manque = manqueCout(manques);
      tuile.partiel = true;
      if (tuile.valeur === 0) {
        Object.assign(tuile, { valeur: null, texteValeur: I18n.t('rapport.cout_arret.non_chiffre'), raison: manque, precision: manque });
      } else tuile.precision = I18n.t('rapport.cout_arret.partiel', { manque });
    });
  }

  /** Activité du mois (Indicateurs.activite) et arrêts saisis (toutes les pannes du mois, sans réglage) ; L30 : OT en
   *  retard au jour du bilan et délai de prise en charge par priorité, calculés comme au tableau de bord (global). */
  function activiteDuMois(periode, global, jour) {
    const activite = Indicateurs.activite(periode);
    return Object.assign(activite, {
      retard: { n: global.otEnRetard.valeur || 0, jour },
      delais: Object.keys(global.delais).filter((priorite) => global.delais[priorite].effectif && global.delais[priorite].mediane !== null)
        .map((priorite) => ({ priorite, mediane: global.delais[priorite].mediane, n: global.delais[priorite].effectif })),
      arret: { heures: global.dureeArret.valeur, pannes: global.dureeArret.effectif, sansDuree: global.dureeArret.exclus.length },
      parMachine: activite.parMachine.map((element) => Object.assign({ repere: repere(element.equipementId) }, element)),
    });
  }

  /** Phrases de l'activité du mois (page et courriel), puis (L30) les OT en retard et le délai de prise en charge. */
  function phrasesActivite(activite) {
    return phrasesInterventions(activite).concat(activite.retard ? [
      I18n.t('rapport.activite.ot_retard', { n: activite.retard.n, jour: UI.dateFr(activite.retard.jour) }),
      activite.delais.length ? I18n.t('rapport.activite.delai_prise_en_charge', { liste: activite.delais.map((element) =>
        I18n.t('rapport.activite.delai_priorite', { priorite: element.priorite, duree: enHeures(element.mediane), n: element.n })).join(', ') })
        : I18n.t('rapport.activite.delai_aucun')] : []);
  }

  function phrasesInterventions(activite) {
    if (!activite.correctifs && !activite.clotures && !activite.heures.total && !activite.ouverts) return [I18n.t('rapport.activite.aucune')];
    const phrases = [
      I18n.t('rapport.activite.correctifs', { n: activite.correctifs, avecArret: activite.correctifsAvecArret }),
      I18n.t('rapport.activite.clotures', { n: activite.clotures, preventifs: activite.cloturesPreventifs })
        + (activite.ouverts ? I18n.t('rapport.activite.ouverts', { n: activite.ouverts }) : ''),
      I18n.t('rapport.activite.heures', { total: enHeures(activite.heures.total), correctif: enHeures(activite.heures.correctif), preventif: enHeures(activite.heures.preventif) }),
    ];
    if (activite.arret.pannes || activite.arret.sansDuree) {
      phrases.push(I18n.t('rapport.activite.arrets', { n: activite.arret.pannes, duree: enHeures(activite.arret.heures || 0) })
        + (activite.arret.sansDuree ? I18n.t('rapport.activite.arrets_sans_duree', { n: activite.arret.sansDuree }) : ''));
    }
    if (activite.parMachine.length) {
      phrases.push(I18n.t('rapport.activite.par_machine', { liste: citer(activite.parMachine.slice(0, MACHINES_CITEES),
        (element) => I18n.t('rapport.activite.machine', { repere: element.repere, n: element.n })) + (activite.parMachine.length > MACHINES_CITEES
        ? I18n.t('rapport.activite.autres_machines', { n: activite.parMachine.length - MACHINES_CITEES }) : '') }));
    }
    return phrases;
  }

  Object.assign(Rapport.interne, { completerTuiles, manquesDuCout, activiteDuMois, phrasesActivite });

  return { figer, afficherOnglet, tuileAccueil, voirBilan };
})());
