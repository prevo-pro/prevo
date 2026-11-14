'use strict';
// PannesRecurrentes (lot 2 ergonomie, décision L29) : une machine qui tombe en panne à répétition.
//
// Une « panne » : une demande d'intervention (sauf refusée ou regroupée) ou un OT correctif (immédiat ou différé, sauf
// annulé). Une demande et l'OT qui la traite ne comptent qu'une fois : l'OT la représente (lien demandes.ot_id ou
// ordres_travail.di_id), daté du signalement de la demande ; une demande dont l'OT est annulé ne compte plus.
// Alerte : au moins `seuil` pannes (3 par défaut) sur la même machine en `jours` jours (30 par défaut), comptés jusqu'au
// jour de la panne regardée (aujourd'hui pour l'accueil) ; renforcée d'une mention quand au moins deux de ces pannes ont
// la même cause enregistrée (code cause de l'OT, ou sa précision « Autre », T515). Les deux seuils sont des réglages du
// responsable (parametres.csv, lus par le seul accesseur `reglages`).
//
// Ce n'est pas le calcul des suggestions de préventif (Suggestions, S1 et S2 : OT correctifs CLÔTURÉS avec une cause,
// sur 12 mois, par cause) ni celui des causes fréquentes (CausesFrequentes : par symptôme, sur l'historique entier) :
// ici on compte ce qui arrive maintenant, demandes ouvertes comprises, et la cause n'est qu'une mention.
//
// Montré : à l'accueil du responsable (tuile « Pannes récurrentes », accueil-bento.js), sur la demande qu'il traite
// (demandes-fiche.js) et sur l'OT correctif ouvert du technicien ou du responsable (ordres-fiche.js), avec les
// interventions précédentes en lien. Jamais au demandeur (il ne lit pas les OT, D126). Lecture seule.

const PannesRecurrentes = (() => {

  const REGLAGES = {
    seuil: { cle: 'pannes_recurrentes_seuil', defaut: 3, min: 2, max: 20 },
    jours: { cle: 'pannes_recurrentes_jours', defaut: 30, min: 7, max: 365 },
  };
  const TYPES_PANNES = ['correctif immédiat', 'correctif différé'];
  const DEMANDES_ECARTEES = ['Refusée', 'Regroupée'];
  const LIENS_MONTRES = 5;                 // interventions précédentes montrées dans le bandeau

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  /** Les deux réglages du responsable : { seuil, jours } (absent, illisible ou hors bornes → défaut). */
  function reglages() {
    const lire = (definition) => {
      const brut = texte(Donnees.parametre(definition.cle, ''));
      const valeur = Number(brut);
      return brut !== '' && Number.isInteger(valeur) && valeur >= definition.min && valeur <= definition.max ? valeur : definition.defaut;
    };
    return { seuil: lire(REGLAGES.seuil), jours: lire(REGLAGES.jours) };
  }

  function jourValide(valeur) {
    const jour = texte(valeur).replace('T', ' ').slice(0, 10);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(jour)) return '';
    const [annee, mois, quantieme] = jour.split('-').map(Number);
    const date = new Date(Date.UTC(annee, mois - 1, quantieme));
    return date.getUTCMonth() === mois - 1 && date.getUTCDate() === quantieme ? jour : '';
  }

  function ajouterJours(jour, nombre) {
    const [annee, mois, quantieme] = jour.split('-').map(Number);
    return new Date(Date.UTC(annee, mois - 1, quantieme) + nombre * 86400000).toISOString().slice(0, 10);
  }

  /** Cause enregistrée d'un OT : { cle, libelle } (code, ou « Autre : <précision> ») ou null. */
  function causeDe(ot) {
    if (!ot) return null;
    const code = texte(ot.cause_code);
    if (code) {
      const ligne = Donnees.lignes('codes_defaillance').find((c) => c.famille === 'cause' && texte(c.code) === code);
      return { cle: code, libelle: ligne && texte(ligne.libelle) ? texte(ligne.libelle) : code };
    }
    const precision = texte(ot.cause_precision);
    return precision ? { cle: 'autre:' + precision.toLowerCase(), libelle: I18n.t('commun.code.autre_precise', { texte: precision }) } : null;
  }

  /**
   * Pannes par machine : Map equipement_id → [{ id, lien, moment, jour, titre, ot, di, cause }], de la plus ancienne à
   * la plus récente. `id` : l'OT qui représente la panne, sinon la demande.
   */
  function pannesParEquipement() {
    const demandes = new Map(Donnees.lignes('demandes').map((di) => [di.id, di]));
    const ordres = Donnees.lignes('ordres_travail');
    const otDeLaDemande = new Map();
    ordres.forEach((ot) => { if (texte(ot.di_id)) otDeLaDemande.set(texte(ot.di_id), ot); });
    const parId = new Map(ordres.map((ot) => [ot.id, ot]));
    const resultat = new Map();
    const ajouter = (panne) => {
      if (!panne.jour) return;
      if (!resultat.has(panne.equipementId)) resultat.set(panne.equipementId, []);
      resultat.get(panne.equipementId).push(panne);
    };
    ordres.forEach((ot) => {
      if (!TYPES_PANNES.includes(texte(ot.type)) || texte(ot.statut) === 'Annulé') return;
      const di = texte(ot.di_id) ? demandes.get(texte(ot.di_id)) : null;
      const moment = texte(di && di.date_heure) || texte(ot.date_creation);
      ajouter({ id: ot.id, lien: '#/ot/' + encodeURIComponent(ot.id), equipementId: texte(ot.equipement_id), moment,
        jour: jourValide(moment), titre: texte(ot.titre), ot, di, cause: causeDe(ot) });
    });
    demandes.forEach((di) => {
      if (DEMANDES_ECARTEES.includes(texte(di.statut))) return;
      if ((texte(di.ot_id) && parId.has(texte(di.ot_id))) || otDeLaDemande.has(di.id)) return;     // l'OT la représente
      ajouter({ id: di.id, lien: '#/di/' + encodeURIComponent(di.id), equipementId: texte(di.equipement_id),
        moment: texte(di.date_heure), jour: jourValide(di.date_heure), titre: texte(di.symptome), ot: null, di, cause: null });
    });
    resultat.forEach((liste) => liste.sort((a, b) => a.moment.localeCompare(b.moment) || a.id.localeCompare(b.id)));
    return resultat;
  }

  /** Cause la plus répétée d'une série (au moins 2 fois) : { libelle, nombre } ou null. */
  function memeCause(pannes) {
    const comptes = new Map();
    pannes.forEach((p) => {
      if (!p.cause) return;
      const element = comptes.get(p.cause.cle) || { libelle: p.cause.libelle, nombre: 0 };
      element.nombre += 1;
      comptes.set(p.cause.cle, element);
    });
    let meilleure = null;
    comptes.forEach((element) => { if (element.nombre >= 2 && (!meilleure || element.nombre > meilleure.nombre)) meilleure = element; });
    return meilleure;
  }

  /** Alerte d'une machine au jour `fin` (inclus) : { equipementId, pannes, nombre, memeCause, reglages } ou null. */
  function alerteDe(equipementId, pannes, fin, regles) {
    const debut = ajouterJours(fin, -(regles.jours - 1));
    const serie = (pannes || []).filter((p) => p.jour >= debut && p.jour <= fin);
    if (serie.length < regles.seuil) return null;
    return { equipementId, pannes: serie, nombre: serie.length, memeCause: memeCause(serie), reglages: regles };
  }

  /** Machines en alerte aujourd'hui (accueil) : les plus de pannes d'abord, puis la panne la plus récente. */
  function machinesEnAlerte(jour) {
    const regles = reglages();
    const fin = jour || Donnees.aujourdhui();
    const alertes = [];
    pannesParEquipement().forEach((pannes, equipementId) => {
      const alerte = alerteDe(equipementId, pannes, fin, regles);
      if (alerte) alertes.push(alerte);
    });
    return alertes.sort((a, b) => b.nombre - a.nombre
      || b.pannes[b.pannes.length - 1].moment.localeCompare(a.pannes[a.pannes.length - 1].moment)
      || a.equipementId.localeCompare(b.equipementId));
  }

  /** Alerte vue depuis une panne (identifiant d'OT ou de demande) : comptée jusqu'à son jour ; null sinon. */
  function alertePour(equipementId, ids) {
    const pannes = pannesParEquipement().get(texte(equipementId)) || [];
    const courante = pannes.find((p) => ids.includes(p.id));
    if (!courante) return null;
    const alerte = alerteDe(texte(equipementId), pannes.filter((p) => p.moment <= courante.moment || p === courante), courante.jour, reglages());
    return alerte ? Object.assign(alerte, { courante }) : null;
  }

  function repere(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    return equipement ? texte(equipement.repere) || equipementId : equipementId;
  }

  /** Bandeau « Pannes à répétition » (élément DOM), interventions précédentes en lien, la plus récente d'abord. */
  function bandeau(alerte) {
    const precedentes = alerte.pannes.filter((p) => p !== alerte.courante).reverse();
    const montrees = precedentes.slice(0, LIENS_MONTRES);
    const bloc = UI.bandeau('attention', UI.html`
      <p><b>${I18n.t('causes.pannes_recurrentes.titre', { n: alerte.nombre, repere: repere(alerte.equipementId), jours: alerte.reglages.jours })}</b></p>
      ${alerte.memeCause ? UI.html`<p class="pannes-recurrentes-cause"><b>${I18n.t('causes.pannes_recurrentes.meme_cause', { n: alerte.memeCause.nombre, cause: alerte.memeCause.libelle })}</b></p>` : ''}
      <p>${I18n.t('causes.pannes_recurrentes.precedentes')}</p>
      <ul class="pannes-recurrentes-liste">${montrees.map((p) => UI.html`<li><a href="${p.lien}">${p.id}</a>
        <span>${UI.dateFr(p.jour)}</span> <span>${p.titre}</span>${p.cause ? UI.html` <span class="muted">${I18n.t('causes.pannes_recurrentes.cause', { cause: p.cause.libelle })}</span>` : ''}</li>`)}</ul>
      <p><a class="pannes-recurrentes-historique" href="#/equipement/${encodeURIComponent(alerte.equipementId)}">${I18n.t('causes.pannes_recurrentes.historique_machine')}</a></p>`);
    bloc.classList.add('pannes-recurrentes');
    return bloc;
  }

  /** Bandeau sur la demande que le responsable traite (demandes-fiche.js) : posé dans `zone`, ou rien. */
  function poserSurDemande(zone, demande) {
    if (!zone || !demande) return;
    const alerte = alertePour(demande.equipement_id, [demande.id, texte(demande.ot_id)].filter(Boolean));
    if (alerte) zone.appendChild(bandeau(alerte));
  }

  /** Bandeau sur un OT correctif ouvert (technicien, responsable ; ordres-fiche.js) : posé dans `zone`, ou rien. */
  function poserSurOt(zone, ot) {
    if (!zone || !ot || App.estDemandeur() || !TYPES_PANNES.includes(texte(ot.type)) || !Ordres.estOuvert(ot)) return;
    const alerte = alertePour(ot.equipement_id, [ot.id]);
    if (alerte) zone.appendChild(bandeau(alerte));
  }

  return { REGLAGES, reglages, pannesParEquipement, machinesEnAlerte, alertePour, poserSurDemande, poserSurOt, repere };
})();
