'use strict';
// SoloAccueil — accueil du mode Solo (lot 1 ergonomie, B, T521 ; ARCHITECTURE.md §22.11, §19), inspiré de la 1.2.1 :
// ce qui attend le technicien seul aujourd'hui, et deux gros boutons. Rien sur l'équipe (ni « À prendre », ni
// « Reprises récentes », ni planning). Appelé par accueil.js (Accueil.afficher) quand App.modeSolo() ; les demandes des
// opérateurs sont d'abord converties en OT à son nom (Solo.convertirDemandes, solo-flux.js).
//   En-tête : « Bonjour », la date ; « Nouvel OT » et « Signaler un problème » (#accueil-solo, boutons de 48 px et plus) ;
//   « Exporter en ZIP ». Puis les avertissements habituels (mise à jour, contrôle de la base, copie externe, Tailscale,
//   parc vide) et, dans l'ordre :
//     1. « Pannes déclarées » (#solo-pannes) : « Nouvelle panne déclarée par <nom> : <machine> », lien vers l'OT, tant
//        que l'OT n'est pas démarré ;
//     2. « En cours ou en attente » (#solo-en-cours), avec le motif de l'attente ;
//     3. « Visites préventives de la semaine » (#solo-preventif) : préventifs à faire au plus tard dimanche, et (L27) les
//        visites du calendrier dues d'ici là dont l'OT n'est pas encore créé (lien vers la gamme) ;
//     4. « À faire » (#solo-a-faire) : les autres OT pas encore démarrés ;
//     puis « Fini ces 7 derniers jours : N », le bilan du mois (tuile de Rapport, lien vers Indicateurs › Bilan) et la
//     carte « Connecter un téléphone ».
// Dépendances : App, UI, Donnees, Accueil (accueil.js, accueil-bento.js), Ordres, Solo. Charte : css/modules/solo.css.

const SoloAccueil = (() => {

  const RANG_PRIORITE = { P1: 1, P2: 2, P3: 3, P4: 4 };
  const NOMBRE_LIGNES = 8;
  const JOURS_FINIS = 7;

  const texte = (valeur) => String(valeur === undefined || valeur === null ? '' : valeur).trim();

  function trier(ordres) {
    return ordres.slice().sort((a, b) => (RANG_PRIORITE[a.priorite] || 9) - (RANG_PRIORITE[b.priorite] || 9)
      || texte(a.date_prevue || '9999').localeCompare(texte(b.date_prevue || '9999')) || a.id.localeCompare(b.id));
  }

  /** Date ISO `jours` jours avant `dateIso`. */
  function joursAvant(dateIso, jours) {
    const [annee, mois, jour] = dateIso.split('-').map(Number);
    const date = new Date(Date.UTC(annee, mois - 1, jour));
    date.setUTCDate(date.getUTCDate() - jours);
    return date.toISOString().slice(0, 10);
  }

  /**
   * Ce qui attend le technicien seul (règle pure sur les lignes) → { pannes: [{ di, ot }], enCours, preventifs, visites,
   * aFaire, finis } ; pannes : demandes acceptées dont l'OT n'est pas démarré (Créé, Préparé, Planifié), les plus récentes
   * d'abord ; un OT n'apparaît que dans une liste. visites (L27) : visites du calendrier dues d'ici dimanche sans OT
   * (éléments de Preventif.visitesDeLaSemaine ; [] sans le module).
   */
  function repartir(demandes, ordres, aujourdhui) {
    const parId = new Map(ordres.map((ot) => [ot.id, ot]));
    const pannes = demandes.filter((di) => texte(di.statut) === 'Acceptée' && parId.has(texte(di.ot_id))
        && Solo.etatSimple(parId.get(texte(di.ot_id))) === 'a_faire')
      .sort((a, b) => texte(b.date_heure).localeCompare(texte(a.date_heure)))
      .map((di) => ({ di, ot: parId.get(texte(di.ot_id)) }));
    const dejaDits = new Set(pannes.map((panne) => panne.ot.id));
    const dimanche = Accueil.dimancheDe(aujourdhui);
    const ouverts = ordres.filter((ot) => Ordres.estOuvert(ot) && !dejaDits.has(ot.id));
    const enCours = trier(ouverts.filter((ot) => Solo.etatSimple(ot) === 'en_cours'));
    const aFaireTous = ouverts.filter((ot) => Solo.etatSimple(ot) === 'a_faire');
    const preventifs = trier(aFaireTous.filter((ot) => Accueil.preventifDeLaSemaine(ot, dimanche)));
    const idsPreventifs = new Set(preventifs.map((ot) => ot.id));
    // Les préventifs des semaines suivantes ne sont pas « à faire aujourd'hui » : ils restent dans la liste des OT.
    const aFaire = trier(aFaireTous.filter((ot) => !idsPreventifs.has(ot.id) && texte(ot.origine) !== 'préventif'));
    const depuis = joursAvant(aujourdhui, JOURS_FINIS);
    const finis = ordres.filter((ot) => Solo.etatSimple(ot) === 'fini'
      && texte(ot.date_cloture_tech || ot.date_cloture_admin).slice(0, 10) >= depuis).length;
    const visites = typeof Preventif !== 'undefined' && typeof Preventif.visitesDeLaSemaine === 'function'
      ? Preventif.visitesDeLaSemaine(aujourdhui).filter((visite) => !visite.otId && visite.gammeId) : [];
    return { pannes, enCours, preventifs, visites, aFaire, finis };
  }

  // ===========================================================================================
  // Morceaux
  // ===========================================================================================

  function ligneOt(ot, detail) {
    return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' || ot.priorite === 'P2' ? 'accent-' + ot.priorite.toLowerCase() : ''}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${detail || ''}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${Solo.libelleMachine(ot.equipement_id)}</span>${ot.date_prevue ? UI.html`<span>${I18n.t('accueil.solo.prevu', { date: UI.dateFr(ot.date_prevue) })}</span>` : ''}</div>
    </a></li>`;
  }

  /** Visite du calendrier sans OT (L27) : lien vers la gamme ; l'OT sera créé le jour venu. */
  function ligneVisite(visite) {
    const gamme = Donnees.trouver('gammes', visite.gammeId);
    return UI.html`<li class="solo-visite"><a href="#/preventif/gamme/${encodeURIComponent(visite.gammeId)}">
      <div class="carte-tete"><b>${visite.gammeId}</b><span class="badge neutre">${I18n.t('accueil.solo.visite_sans_ot')}</span></div>
      <div class="carte-titre">${texte(gamme && gamme.libelle) || visite.gammeId}</div>
      <div class="carte-meta"><span>${Solo.libelleMachine(visite.equipementId)}</span><span>${I18n.t('accueil.solo.prevu', { date: UI.dateFr(visite.date) })}</span></div>
    </a></li>`;
  }

  /** Carte des visites préventives (L27) : OT de la semaine et visites sans OT, par date ; au-delà de 8, lien vers le calendrier. */
  function listePreventifs(ordres, visites) {
    const lignes = ordres.map((ot) => ({ date: texte(ot.date_prevue).slice(0, 10), rang: 0, html: () => ligneOt(ot) }))
      .concat(visites.map((visite) => ({ date: visite.date, rang: 1, html: () => ligneVisite(visite) })))
      .sort((a, b) => a.date.localeCompare(b.date) || a.rang - b.rang);
    const montrees = lignes.slice(0, NOMBRE_LIGNES);
    return UI.html`<ul class="liste-cartes">${montrees.map((ligne) => ligne.html())}</ul>
      ${lignes.length > montrees.length ? UI.html`<p class="accueil-voir-tout"><a href="#/preventif?onglet=calendrier">${I18n.t('accueil.solo.voir_les_autres', { n: lignes.length - montrees.length })}</a></p>` : ''}`;
  }

  function badgeEtat(ot) {
    if (ot.statut === 'En attente') {
      return UI.html`<span class="badge attention">${I18n.t('accueil.solo.en_attente_motif', { motif: texte(ot.motif_attente) || I18n.t('ordres.bandeau_etat.motif_non_renseigne') })}</span>`;
    }
    return UI.html`<span class="badge info">${I18n.t('ordres.solo.etat_en_cours')}</span>`;
  }

  function carte(id, titre, nombre, contenu, vide) {
    return UI.html`<article class="carte solo-carte" id="${id}">
      <div class="entete-carte"><h2>${titre}</h2><span class="badge ${nombre > 0 ? 'info' : 'neutre'}">${nombre}</span></div>
      ${nombre ? contenu : UI.html`<p class="muted solo-vide">${vide}</p>`}
    </article>`;
  }

  function listeOt(ordres, detail) {
    const montres = ordres.slice(0, NOMBRE_LIGNES);
    return UI.html`<ul class="liste-cartes">${montres.map((ot) => ligneOt(ot, detail ? detail(ot) : ''))}</ul>
      ${ordres.length > montres.length ? UI.html`<p class="accueil-voir-tout"><a href="#/ot">${I18n.t('accueil.solo.voir_les_autres', { n: ordres.length - montres.length })}</a></p>` : ''}`;
  }

  function cartePannes(pannes) {
    const lignes = pannes.slice(0, NOMBRE_LIGNES).map(({ di, ot }) => UI.html`<li class="solo-panne">
      <a href="#/ot/${encodeURIComponent(ot.id)}">
        <div class="carte-tete"><b>${I18n.t('accueil.solo.nouvelle_panne', { nom: texte(di.demandeur) || '—', machine: Solo.libelleMachine(di.equipement_id) })}</b>${Accueil.interne.badgeImpact(di.impact)}</div>
        <div class="carte-titre">${di.symptome}</div>
        <div class="carte-meta"><span>${ot.id}</span><span>${UI.dateHeureFr(di.date_heure)}</span></div>
      </a></li>`);
    return carte('solo-pannes', I18n.t('accueil.solo.pannes_declarees'), pannes.length,
      UI.html`<ul class="liste-cartes">${lignes}</ul>`, I18n.t('accueil.solo.aucune_panne'));
  }

  // « Pannes récurrentes » (T546, reste de L29) : même calcul que la tuile du bento (PannesRecurrentes.machinesEnAlerte,
  // seuils de Paramètres) ; carte quand une machine est en alerte, sinon une seule ligne discrète.
  function carteRecurrentes(aujourdhui) {
    if (typeof PannesRecurrentes === 'undefined') return '';
    const alertes = PannesRecurrentes.machinesEnAlerte(aujourdhui);
    const { seuil, jours } = PannesRecurrentes.reglages();
    if (!alertes.length) {
      return UI.html`<p class="note solo-recurrentes-calme" id="solo-recurrentes"><b>${I18n.t('accueil.tuile_recurrentes.titre')}</b> · ${I18n.t('accueil.tuile_recurrentes.aucune', { seuil, jours })}</p>`;
    }
    const lignes = alertes.slice(0, NOMBRE_LIGNES).map((a) => UI.html`<li class="solo-recurrente">
      <a href="#/equipement/${encodeURIComponent(a.equipementId)}" id="solo-recurrente-${a.equipementId}">
        <div class="carte-titre"><b>${I18n.t('accueil.tuile_recurrentes.machine', { repere: PannesRecurrentes.repere(a.equipementId), n: a.nombre, jours })}</b></div>
        <div class="carte-meta">${a.memeCause ? UI.html`<span class="rouge">${I18n.t('accueil.tuile_recurrentes.meme_cause', { n: a.memeCause.nombre, cause: a.memeCause.libelle })}</span>`
          : UI.html`<span>${I18n.t('accueil.tuile_recurrentes.causes_differentes')}</span>`}</div>
      </a></li>`);
    return carte('solo-recurrentes', I18n.t('accueil.tuile_recurrentes.titre'), alertes.length, UI.html`<ul class="liste-cartes">${lignes}</ul>
      ${alertes.length > NOMBRE_LIGNES ? UI.html`<p class="muted">${I18n.t('accueil.tuile_recurrentes.et_autres', { n: alertes.length - NOMBRE_LIGNES })}</p>` : ''}`, '');
  }

  function entete(aujourdhui) {
    return UI.html`<div class="entete-page solo-entete"><div class="solo-salut">
        <h1>${I18n.t('accueil.entete.bonjour')}</h1><p class="bento-date">${Accueil.dateEnLettres(aujourdhui, true)}</p>
      </div>
      <div class="actions">
        ${App.mode === 'demo' ? UI.html`<span class="bento-demo" id="accueil-demo">${UI.icone('alerte')}${I18n.t('accueil.entete.demo_rien_enregistre')}</span>` : ''}
        <button type="button" class="btn btn-fantome" id="btn-export-accueil">${UI.icone('export')}${I18n.t('accueil.entete.exporter_zip')}</button>
      </div></div>
      <div class="solo-actions" id="accueil-solo">
        <a class="btn btn-primaire btn-gros" id="accueil-nouvel-ot" href="#/ot/nouveau">${UI.icone('ajouter')}<span>${I18n.t('accueil.actions_solo.nouvel_ot')}</span></a>
        <a class="btn btn-secondaire btn-gros" id="accueil-signaler" href="#/di/nouvelle">${UI.icone('alerte')}<span>${I18n.t('accueil.actions_solo.signaler_probleme')}</span></a>
      </div>`;
  }

  // ===========================================================================================
  // Écran
  // ===========================================================================================

  /** Remplit #contenu avec l'accueil du Solo ; `connexion` : carte « Connecter un téléphone » ou '' (accueil.js). */
  async function afficher(conteneur, connexion) {
    try {
      await Solo.convertirDemandes();
    } catch (erreur) {
      console.warn('Prévo (Solo) : demandes non converties à l\'accueil.', erreur);
    }
    if (!/^#\/accueil/.test(location.hash)) return;
    const aujourdhui = Donnees.aujourdhui();
    const r = repartir(Donnees.lignes('demandes'), Donnees.lignes('ordres_travail'), aujourdhui);
    const { alerteControle, carteBaseVide } = Accueil.interne;
    UI.remplir(conteneur, UI.html`<div class="solo-accueil accueil-instruments" id="solo-accueil">${entete(aujourdhui)}
      <div id="maj-zone"></div>${alerteControle()}<div id="copie-externe-zone"></div><div id="tailscale-zone"></div>${carteBaseVide()}
      ${cartePannes(r.pannes)}
      ${carteRecurrentes(aujourdhui)}
      ${carte('solo-en-cours', I18n.t('accueil.solo.en_cours'), r.enCours.length, listeOt(r.enCours, badgeEtat), I18n.t('accueil.solo.rien_en_cours'))}
      ${carte('solo-preventif', I18n.t('accueil.solo.preventif_semaine'), r.preventifs.length + r.visites.length, listePreventifs(r.preventifs, r.visites),
    I18n.t('accueil.solo.aucun_preventif', { date: UI.dateFr(Accueil.dimancheDe(aujourdhui)) }))}
      ${carte('solo-a-faire', I18n.t('accueil.solo.a_faire'), r.aFaire.length, listeOt(r.aFaire), I18n.t('accueil.solo.rien_a_faire'))}
      <p class="accueil-voir-tout solo-finis" id="solo-finis"><a href="#/ot?etat=clotures">${I18n.t('accueil.solo.finis', { n: r.finis })}</a>
        · <a href="#/ot">${I18n.t('accueil.solo.tous_les_ot')}</a> · <a href="#/indicateurs?onglet=rapports" id="solo-bilan">${I18n.t('accueil.solo.bilan')}</a></p>
      <div id="solo-rapport"></div>
    </div>${connexion}`);
    const tuileRapport = typeof Rapport !== 'undefined' && typeof Rapport.tuileAccueil === 'function' ? Rapport.tuileAccueil() : null;
    if (tuileRapport) conteneur.querySelector('#solo-rapport').appendChild(tuileRapport);
    conteneur.querySelector('#btn-export-accueil').addEventListener('click', () => App.exporterZip());
    if (typeof MiseAJour !== 'undefined') MiseAJour.afficherSiPossible();
    Accueil.afficherEtatServeur(conteneur);
    App.definirTitreMobile(I18n.t('accueil.entete.bonjour'), Accueil.dateEnLettres(aujourdhui, false));
  }

  // Aide à l'écran de l'accueil en Solo (variante « solo », lue par aide-ecrans.js) : AideEcransTextes est produit par un
  // outil et ne se retouche pas ; la variante est ajoutée ici, au chargement.
  if (typeof AideEcransTextes !== 'undefined' && AideEcransTextes.accueil && AideEcransTextes.accueil.profils) {
    AideEcransTextes.accueil.profils.solo = {
      get texte() { return I18n.t('accueil.solo.aide_texte'); },
      get essayez() { return I18n.t('accueil.solo.aide_essayez'); },
    };
  }

  return { afficher, repartir };
})();
