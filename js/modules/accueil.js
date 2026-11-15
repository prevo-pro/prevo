'use strict';
// Accueil (1/2) : écran d'arrivée (#/accueil), adapté au profil (brief §9 E1, ARCHITECTURE.md §10 et §14.6).
// Ce fichier : calculs des compteurs, accueils du technicien et du demandeur, carte de connexion,
// affichage ; l'accueil du responsable (« bento », T90) est dans accueil-bento.js, qui complète Accueil.
//
//   Responsable : tuile de synthèse, « À traiter en premier », compteurs (DI à traiter, OT en retard,
//                 P1 ouverts, préventifs de la semaine), rapport du mois écoulé, 5 DI à traiter et 5 OT
//                 en retard, tuiles « à surveiller » (articles à commander ; contrôles sous 30 jours et
//                 habilitations à renouveler, lot 3 ; suggestions de préventif, lot 3 bis, §16.6 ; garanties
//                 et contrats, 2.2), une alerte si « Contrôle de la base » signale des erreurs (accueil-bento.js).
//   Technicien  : gros bouton « Signaler », les trois indicateurs des contrôles et de l'équipe (contrôles
//                 sous 30 jours, habilitations à renouveler, réserves en retard depuis la 2.2), puis (lot 2, L14)
//                 « Mes ordres de travail » (tous ses OT ouverts en une liste, pannes d'abord, préventifs
//                 marqués), « À prendre » et « En attente dans l'équipe » (ordres-prise.js) ; sur téléphone,
//                 ces trois blocs passent au-dessus de l'aide à l'écran et des compteurs ; enfin « Mes
//                 habilitations » (2.2, D199 : les siennes seulement, type, échéance, statut, sans
//                 justificatif ; carte d'equipe-habilitations.js).
//   Demandeur   : gros bouton « Signaler un problème » et ses 5 dernières demandes (statut,
//                 motif de refus).
//   Tous, en mode serveur et sauf sur téléphone (D31) : carte « Connecter un téléphone » (QR code
//   de l'adresse réseau du PC) — sur le téléphone, on est déjà connecté.
//
// Définitions des compteurs (ARCHITECTURE.md §10 et §14.6) :
//   DI à traiter             = demande au statut « Nouvelle » ;
//   OT en retard             = statut ni clôturé ni annulé ET date prévue avant aujourd'hui ;
//   P1 ouvert                = priorité P1 ET statut ni clôturé ni annulé ;
//   Préventif de la semaine  = OT d'origine « préventif », ni clôturé ni annulé, date prévue au
//                              plus tard le dimanche de la semaine en cours (retards compris) ;
//   Article à commander      = Magasin.aCommander() (article actif, stock ≤ point de commande) ;
//   Contrôle sous 30 jours   = Controles.sous30Jours() (équipement suivi, prochaine date inconnue
//                              ou dans les 30 jours, retards compris ; lot 3, §15.9) ;
//   Habilitation à renouveler = Equipe.aRenouveler() (technicien actif, habilitation qui compte
//                              échue ou à échéance dans les 60 jours ; lot 3, §15.9) ;
//   Réserve en retard        = Controles.reservesEnRetard() (réserve ouverte d'un contrôle d'équipement
//                              suivi, échéance de levée passée ; sans échéance saisie, 30 jours après le
//                              contrôle, D187 ; 2.2, CS170). Les observations reprises de la 2.1 n'ont pas
//                              d'échéance saisie : presque toutes le sont au premier lancement, d'où le détail
//                              « échéance par défaut passée (30 jours après le contrôle) ».
//   Échéances des garanties  = Garanties.aEcheance() (2.2, CS173 ; responsable seulement) : garanties qui se
//   et des contrats            terminent dans le délai d'alerte (réglage alerte_echeances_jours, 60 jours par
//                              défaut, D187), contrats en alerte (« à décider » avant la date limite de
//                              résiliation, reconduction tacite ; « se termine bientôt » avant la fin, sans
//                              reconduction tacite : jamais « à décider », T463) et contrats aux dates à mettre
//                              à jour. Module Garanties absent (pages de test) : null.

const Accueil = (() => {

  const STATUTS_OT_FERMES = ['Clôturé techniquement', 'Clôturé administrativement', 'Annulé'];
  const NOMBRE_LIGNES = 5;             // lignes montrées dans les listes du responsable et du demandeur
  const NOMBRE_OT_TECHNICIEN = 15;     // un technicien voit tous ses OT ouverts, jusqu'à ce nombre
  const MILLISECONDES_PAR_JOUR = 24 * 60 * 60 * 1000;
  const ORIGINE_PREVENTIF = 'préventif';
  const LIEN_RESERVES_EN_RETARD = '#/controles?filtre=reserves-en-retard';

  // Adresses du serveur lues une première fois puis gardées (évite un aller-retour à chaque affichage).
  let adressesEnMemoire = null;
  let porteOuverte = false;       // lot 7 : le serveur a sa porte d'entrée (deux écouteurs, hors de « ce PC »)
  let cePcSeulement = false;      // recette du lot 7 : portée « ce PC », aucun téléphone ne joint Prévo

  // ===========================================================================================
  // 1. Calculs (fonctions pures sur les lignes des tables, exposées pour les tests)
  // ===========================================================================================

  function otOuvert(ot) {
    return !STATUTS_OT_FERMES.includes(ot.statut);
  }

  function otEnRetard(ot, aujourdhui) {
    return otOuvert(ot) && ot.date_prevue !== '' && ot.date_prevue < aujourdhui;
  }

  function p1Ouvert(ot) {
    return ot.priorite === 'P1' && otOuvert(ot);
  }

  /** Dimanche de la semaine (du lundi au dimanche) d'une date ISO : '2026-10-20' (mardi) → '2026-10-25'. */
  function dimancheDe(dateIso) {
    const [annee, mois, jour] = dateIso.split('-').map(Number);
    const date = new Date(Date.UTC(annee, mois - 1, jour));        // en UTC : pas de piège d'heure d'été
    date.setUTCDate(date.getUTCDate() + (7 - date.getUTCDay()) % 7);  // getUTCDay() : 0 = dimanche
    return date.toISOString().slice(0, 10);
  }

  /** OT préventif ouvert à faire au plus tard le `dimanche` donné (retards compris). */
  function preventifDeLaSemaine(ot, dimanche) {
    const prevue = String(ot.date_prevue || '').slice(0, 10);
    return ot.origine === ORIGINE_PREVENTIF && otOuvert(ot) && prevue !== '' && prevue <= dimanche;
  }

  /**
   * Visites préventives de la semaine (L27) : celles du calendrier (Preventif.visitesDeLaSemaine, chargé après ce
   * fichier) ; sans le module (pages de test), les OT préventifs de la semaine. [{ gammeId, equipementId, date, otId }]
   */
  function visitesPreventivesSemaine(aujourdhui, ordres, dimanche) {
    if (typeof Preventif !== 'undefined' && typeof Preventif.visitesDeLaSemaine === 'function') return Preventif.visitesDeLaSemaine(aujourdhui);
    return ordres.filter((ot) => preventifDeLaSemaine(ot, dimanche))
      .map((ot) => ({ gammeId: ot.gamme_id || '', equipementId: ot.equipement_id, date: String(ot.date_prevue).slice(0, 10), otId: ot.id }));
  }

  /**
   * Les listes qui donnent les compteurs de l'accueil :
   * { diATraiter, otEnRetard, p1Ouverts, preventifsSemaine } (lignes de demandes et d'OT), visitesPreventivesSemaine
   * (visites dues d'ici dimanche d'après le calendrier du préventif, L27),
   * articlesACommander (éléments de Magasin.aCommander() : { article, stock, pointCommande, … }),
   * controlesSous30j, habilitationsARenouveler et reservesEnRetard (éléments de
   * Controles.reservesEnRetard() : { reserve, controle, etat }, l'échéance la plus ancienne d'abord),
   * echeances (Garanties.aEcheance() : { garanties, contrats, aMettreAJour }, lignes ; null sans le module).
   */
  function calculerCompteurs() {
    const aujourdhui = Donnees.aujourdhui();
    const dimanche = dimancheDe(aujourdhui);
    const ordres = Donnees.lignes('ordres_travail');
    return {
      diATraiter: Donnees.lignes('demandes').filter((di) => di.statut === 'Nouvelle'),
      otEnRetard: ordres.filter((ot) => otEnRetard(ot, aujourdhui)),
      p1Ouverts: ordres.filter(p1Ouvert),
      preventifsSemaine: ordres.filter((ot) => preventifDeLaSemaine(ot, dimanche)),
      // L27 : visites préventives dues d'ici dimanche d'après le calendrier du préventif (OT créé ou non).
      visitesPreventivesSemaine: visitesPreventivesSemaine(aujourdhui, ordres, dimanche),
      articlesACommander: Magasin.aCommander(),
      // Lot 3 (§15.9) : les règles des contrôles et de l'équipe, appelées au moment du calcul
      // (leurs fichiers sont chargés après celui-ci).
      controlesSous30j: Controles.sous30Jours(aujourdhui),
      habilitationsARenouveler: Equipe.aRenouveler(aujourdhui),
      // 2.2 (CS170) : réserves des contrôles dont l'échéance de levée est passée (controles-reserves.js).
      reservesEnRetard: Controles.reservesEnRetard(aujourdhui),
      // 2.2 (CS173) : garanties et contrats à échéance (garanties-regles.js, chargé après ce fichier ; absent des
      // pages de test qui ne chargent pas tous les modules).
      echeances: typeof Garanties !== 'undefined' ? Garanties.aEcheance(aujourdhui) : null,
    };
  }

  /**
   * Détail des réserves en retard (éléments de Controles.reservesEnRetard), sous leur nombre : aucune → « aucune
   * échéance de levée passée » ; toutes à l'échéance saisie → « échéance de levée passée » ; toutes à l'échéance
   * par défaut (réserves reprises de la 2.1 ou saisies sans échéance, D187) → « échéance par défaut passée
   * (30 jours après le contrôle) » ; sinon « dont n à l'échéance par défaut (30 jours après le contrôle) ».
   */
  function detailReservesEnRetard(reserves) {
    const parDefaut = reserves.filter((element) => element.etat.parDefaut).length;
    const jours = Controles.interne.DELAI_LEVEE_PAR_DEFAUT_JOURS;
    if (!reserves.length) return I18n.t('accueil.detail_reserves_en_retard.aucune_echeance_passee');
    if (!parDefaut) return I18n.t('accueil.detail_reserves_en_retard.echeance_passee');
    if (parDefaut === reserves.length) return I18n.t('accueil.detail_reserves_en_retard.echeance_par_defaut_passee', { jours });
    return I18n.t('accueil.detail_reserves_en_retard.dont_echeance_par_defaut', { n: parDefaut, jours });
  }

  /** Nombre de jours entre deux dates ISO (AAAA-MM-JJ) : combien de jours après `debut` tombe `fin`. */
  function joursEntre(debut, fin) {
    const [anneeD, moisD, jourD] = debut.split('-').map(Number);
    const [anneeF, moisF, jourF] = fin.split('-').map(Number);
    return Math.round((Date.UTC(anneeF, moisF - 1, jourF) - Date.UTC(anneeD, moisD - 1, jourD)) / MILLISECONDES_PAR_JOUR);
  }

  function pluriel(nombre, singulier, plurielTexte) {
    return nombre + ' ' + (nombre > 1 ? (plurielTexte || singulier + 's') : singulier);
  }

  // « EQ-0005 » → « PO-02 — Pompe d'alimentation » (repli : l'identifiant brut).
  function libelleEquipement(equipementId) {
    const equipement = Donnees.trouver('equipements', equipementId);
    if (!equipement) return equipementId || '—';
    return equipement.repere + (equipement.designation ? ' — ' + equipement.designation : '');
  }

  // ===========================================================================================
  // 2. Petits morceaux d'écran
  // ===========================================================================================

  // Impact d'une demande : couleur de la charte ET libellé.
  function badgeImpact(impact) {
    const tons = { 'sécurité': 'ko', 'arrêt': 'attention', 'dégradé': 'info', 'gêne': 'neutre' };
    return UI.html`<span class="badge ${tons[impact] || 'neutre'}">${Schema.libelleValeur('demandes', 'impact', impact) || '—'}</span>`;
  }

  function carteDemande(di, avecMotif) {
    const motif = avecMotif && di.motif_decision && (di.statut === 'Refusée' || di.statut === 'Différée')
      ? UI.html`<p class="accueil-motif"><b>${di.statut === 'Refusée' ? I18n.t('accueil.carte_demande.motif_refus') : I18n.t('accueil.carte_demande.motif_report')} :</b> ${di.motif_decision}</p>`
      : '';
    return UI.html`<li><a href="#/di/${encodeURIComponent(di.id)}" class="${di.impact === 'sécurité' ? 'accent-p1' : ''}">
      <div class="carte-tete"><b>${di.id}</b>${avecMotif ? Demandes.badgeStatut(di) : badgeImpact(di.impact)}</div>
      <div class="carte-titre">${di.symptome}</div>
      <div class="carte-meta"><span>${libelleEquipement(di.equipement_id)}</span>${avecMotif ? '' : UI.html`<span>${di.demandeur}</span>`}<span>${UI.dateHeureFr(di.date_heure)}</span></div>
      ${motif}${avecMotif ? Demandes.retourHtml(di) : ''}
    </a></li>`;
  }

  function carteOrdre(ot, aujourdhui, etiquette) {
    const enRetard = otEnRetard(ot, aujourdhui);
    const retard = enRetard ? UI.html`<span class="accueil-retard">${I18n.t('accueil.carte_ordre.retard_jours', { n: joursEntre(ot.date_prevue, aujourdhui) })}</span>` : '';
    const prevu = ot.date_prevue ? UI.html`<span>${I18n.t('accueil.carte_ordre.prevu_date_prevue', { date_prevue: UI.dateFr(ot.date_prevue) })}</span>` : UI.html`<span>${I18n.t('accueil.carte_ordre.pas_date_prevue')}</span>`;
    return UI.html`<li><a href="#/ot/${encodeURIComponent(ot.id)}" class="${ot.priorite === 'P1' ? 'accent-p1' : (ot.priorite === 'P2' ? 'accent-p2' : '')}">
      <div class="carte-tete"><b>${ot.id}</b>${UI.badgePriorite(ot.priorite)}${UI.badgeValeur('ordres_travail', 'statut', ot.statut)}${etiquette || ''}</div>
      <div class="carte-titre">${ot.titre}</div>
      <div class="carte-meta"><span>${libelleEquipement(ot.equipement_id)}</span>${prevu}${retard}</div>
      ${typeof Ordres !== 'undefined' && Ordres.releveCarteHtml ? Ordres.releveCarteHtml(ot) : ''}
    </a></li>`;
  }

  // Une carte « titre + liste de cartes + lien vers la liste complète ».
  function carteListe(titre, nombreTotal, elements, lien, libelleLien, videTitre, videTexte, videIcone) {
    const reste = nombreTotal - elements.length;
    return UI.html`<article class="carte">
      <div class="entete-carte"><h2>${titre}</h2><span class="badge ${nombreTotal > 0 ? 'info' : 'neutre'}">${nombreTotal}</span></div>
      ${elements.length
        ? UI.html`<ul class="liste-cartes">${elements}</ul>`
        : UI.vide(videTitre, videTexte, videIcone)}
      ${lien ? UI.html`<p class="accueil-voir-tout"><a href="${lien}">${reste > 0 ? I18n.t('accueil.carte_liste.libelle_lien_reste_plus', { libelleLien, reste }) : libelleLien}</a></p>` : ''}
    </article>`;
  }

  function indicateur(lien, classe, libelle, chiffre, complement) {
    return UI.html`<a href="${lien}" class="${classe}">
      <div class="lib">${libelle}</div><div class="chiffre">${chiffre}</div><div class="comp">${complement}</div>
    </a>`;
  }

  // Lot 3 (§15.9) : contrôles réglementaires sous 30 jours et habilitations à renouveler ; 2.2 (CS170) :
  // réserves en retard. La couleur du trait suit l'état (rouge : un contrôle ou une réserve en retard ;
  // ambre : une habilitation échue), toujours avec le texte qui le dit.
  function indicateursConformite(compteurs, aujourdhui) {
    const reserves = compteurs.reservesEnRetard;
    const controlesEnRetard = compteurs.controlesSous30j
      .filter((controle) => Controles.etat(controle, aujourdhui).statut === 'en retard').length;
    const habilitationsEchues = compteurs.habilitationsARenouveler
      .filter((element) => element.etat.statut === 'échue').length;
    return UI.html`${indicateur('#/controles?filtre=30j', controlesEnRetard ? 'rouge' : '', I18n.t('accueil.indicateurs_conformite.controles_sous_30'),
      compteurs.controlesSous30j.length, controlesEnRetard ? I18n.t('accueil.indicateurs_conformite.dont_retard', { controlesEnRetard }) : I18n.t('accueil.indicateurs_conformite.controles_reglementaires'))}
      ${indicateur('#/equipe?filtre=a-renouveler', habilitationsEchues ? 'ambre' : '', I18n.t('accueil.indicateurs_conformite.habilitations_renouveler'),
      compteurs.habilitationsARenouveler.length,
      habilitationsEchues ? I18n.t('accueil.indicateurs_conformite.dont_echues', { n: habilitationsEchues }) : I18n.t('accueil.indicateurs_conformite.60_jours'))}
      ${indicateur(LIEN_RESERVES_EN_RETARD, reserves.length ? 'rouge' : '', I18n.t('accueil.indicateurs_conformite.reserves_en_retard'),
      reserves.length, detailReservesEnRetard(reserves))}`;
  }

  // Alerte du responsable : « Contrôle de la base » a trouvé des erreurs.
  function alerteControle() {
    const erreurs = Donnees.problemes().filter((p) => p.gravite === 'erreur').length;
    if (erreurs === 0) return '';
    // UI.bandeau rend un élément DOM : on le convertit en fragment sûr pour l'insérer dans un gabarit.
    return UI.brut(UI.bandeau('important', UI.html`${I18n.html('accueil.alerte_controle.erreurs_corriger', { n: erreurs })}`).outerHTML);
  }

  // Base sans équipement (responsable) : invitation à reprendre les listes existantes (lot 5, §18.9).
  function carteBaseVide() {
    if (Donnees.lignes('equipements').length) return '';
    return UI.html`<article class="carte" id="carte-import-accueil">
      <div class="entete-carte"><h2>${I18n.t('accueil.carte_base_vide.parc_vide')}</h2></div>
      <p>${I18n.t('accueil.carte_base_vide.reprenez_listes_existantes_equipements')}</p>
      <div class="actions"><a class="btn btn-primaire" id="lien-import-accueil" href="#/import">${UI.icone('document')}${I18n.t('accueil.carte_base_vide.importer_donnees')}</a></div>
    </article>`;
  }

  // ===========================================================================================
  // 3. Connexion d'un téléphone (mode serveur)
  // ===========================================================================================

  async function lireAdressesReseau() {
    if (adressesEnMemoire) return adressesEnMemoire;
    let adresses = [];
    try {
      const informations = await App.adaptateur.info();
      adresses = (informations && informations.adressesReseau) || [];
      adressesEnMemoire = adresses;
      // Lot 7 (§22.6) : hors de « ce PC », l'adresse est celle de la porte d'entrée, qui conduit le téléphone à
      // l'application en https après « Faites confiance au PC atelier » (une fois par téléphone).
      porteOuverte = Boolean(informations && informations.porte);
      cePcSeulement = Boolean(informations && informations.cePcSeulement);
    } catch (erreur) {
      console.warn('Prévo : adresses réseau du serveur inconnues (' + (erreur && erreur.message) + ').', erreur);
    }
    return adresses;
  }

  // P12 : tant qu'aucun téléphone ne s'est jamais connecté, la carte « Connecter un téléphone » est en haut de l'accueil
  // du responsable. Ce que le serveur sait déjà (rien de nouveau) : un appareil enrôlé (GET /api/acces/invitations) ou une
  // connexion depuis une autre adresse que ce PC (journal des connexions, GET /api/acces/journal). Une fois vu, c'est
  // vu pour la session de la page ; sinon relu au plus toutes les 30 s ; une réponse illisible vaut « pas encore ».
  const ADRESSES_DE_CE_PC = ['127.0.0.1', '::1', 'localhost'];
  const RELECTURE_TELEPHONE_MS = 30000;
  let telephoneDejaVu = false;
  let telephoneLuLe = 0;

  async function lireAcces(chemin, texte) {
    const reponse = await fetch(chemin, { method: 'GET', headers: { 'X-Prevo': '1' }, cache: 'no-store', credentials: 'same-origin' });
    if (!reponse.ok) throw new Error(String(reponse.status));
    return texte ? reponse.text() : reponse.json();
  }

  async function telephoneDejaConnecte() {
    if (telephoneDejaVu) return true;
    if (Date.now() - telephoneLuLe < RELECTURE_TELEPHONE_MS) return false;
    telephoneLuLe = Date.now();
    try {
      const acces = await lireAcces('/api/acces/invitations', false);
      if ((acces.appareils || []).length > 0) telephoneDejaVu = true;
    } catch (erreur) { /* lecture impossible : la carte reste en haut */ }
    if (!telephoneDejaVu) {
      try {
        const lignes = (await lireAcces('/api/acces/journal', true)).replace(/^\ufeff/, '').split(/\r?\n/).slice(1);
        telephoneDejaVu = lignes.some((ligne) => {
          const [, , adresse, , resultat] = ligne.split(';');
          return resultat === 'connexion' && adresse && !ADRESSES_DE_CE_PC.includes(adresse.trim());
        });
      } catch (erreur) { /* idem */ }
    }
    return telephoneDejaVu;
  }

  function carteConnexion(adresses) {
    // Recette du lot 7 : en portée « ce PC », Prévo n'écoute que sur ce PC : pas de QR qu'aucun téléphone n'ouvrirait.
    if (cePcSeulement) {
      return UI.html`<article class="carte" id="carte-connexion">
        <div class="entete-carte"><h2>${I18n.t('accueil.carte_connexion.connecter_telephone')}</h2></div>
        <div class="encadre info" id="connexion-ce-pc">
          ${I18n.html('accueil.carte_connexion.prevo_joignable_pc_instant')}
        </div>
      </article>`;
    }
    if (adresses.length === 0) {
      return UI.html`<article class="carte" id="carte-connexion">
        <div class="entete-carte"><h2>${I18n.t('accueil.carte_connexion.connecter_telephone')}</h2></div>
        <div class="encadre attention">
          ${I18n.html('accueil.carte_connexion.aucune_adresse_reseau_detectee')}
        </div>
        <p class="note">${I18n.t('accueil.carte_connexion.attendant_prevo_reste_utilisable')}</p>
      </article>`;
    }
    const autres = adresses.slice(1);
    return UI.html`<article class="carte" id="carte-connexion">
      <div class="entete-carte"><h2>${I18n.t('accueil.carte_connexion.connecter_telephone')}</h2></div>
      <div class="accueil-connexion">
        <div class="qr" id="qr-connexion">${UI.qrSvg(adresses[0], 176)}</div>
        <div class="accueil-connexion-texte">
          <p>${I18n.t('accueil.carte_connexion.scannez_qr_code_appareil')}</p>
          <p>${I18n.html('accueil.carte_connexion.saisissez_adresse', { adresse: adresses[0] })}</p>
          ${autres.length ? UI.html`<details class="note autres-adresses" id="autres-adresses"><summary>${I18n.t('accueil.carte_connexion.autres_adresses_pc')}</summary>
            <ul>${autres.map((adresse) => UI.html`<li>${adresse}</li>`)}</ul></details>` : ''}
          <ul class="accueil-rappels">
            <li>${I18n.html('accueil.carte_connexion.telephone_doit_etre_meme')}</li>
            <li>${I18n.html('accueil.carte_connexion.premier_lancement_windows_demande')}</li>
            ${porteOuverte ? UI.html`<li>${I18n.html('accueil.carte_connexion.premiere_fois_telephone_affiche')}</li>` : ''}
          </ul>
        </div>
      </div>
    </article>`;
  }

  // ===========================================================================================
  // 4. Accueils du technicien et du demandeur (celui du responsable : accueil-bento.js)
  // ===========================================================================================

  // Carte du technicien (lot 2, L14) : « Mes ordres de travail », tous ses OT ouverts en une liste, les pannes d'abord
  // puis les préventifs (marqués d'une étiquette), chaque groupe dans l'ordre reçu (priorité puis date prévue). Plus de
  // sous-titre « Autres » (lu comme « les OT des autres »). Vide : ce qui attend dans « À prendre » est dit.
  function carteOrdresTechnicien(mesOrdres, aujourdhui, nombreAPrendre) {
    const estPreventif = (ot) => ot.origine === ORIGINE_PREVENTIF;
    const ordonnes = mesOrdres.filter((ot) => !estPreventif(ot)).concat(mesOrdres.filter(estPreventif));
    const montres = ordonnes.slice(0, NOMBRE_OT_TECHNICIEN);
    const reste = ordonnes.length - montres.length;
    const etiquette = (ot) => (estPreventif(ot)
      ? UI.html`<span class="badge violet accueil-etiquette-preventif">${Schema.libelleValeur('ordres_travail', 'origine', ot.origine)}</span>` : '');
    return UI.html`<article class="carte accueil-mes-ordres">
      <div class="entete-carte"><h2>${I18n.t('accueil.carte_ordres_technicien.mes_ordres_travail', { n: mesOrdres.length })}</h2></div>
      ${montres.length
        ? UI.html`<ul class="liste-cartes">${montres.map((ot) => carteOrdre(ot, aujourdhui, etiquette(ot)))}</ul>`
        : UI.html`<p class="muted accueil-mes-ordres-vide">${nombreAPrendre > 0
          ? I18n.t('accueil.carte_ordres_technicien.aucun_a_votre_nom_a_prendre', { n: nombreAPrendre })
          : I18n.t('accueil.carte_ordres_technicien.aucun_a_votre_nom')}</p>`}
      ${montres.length ? UI.html`<p class="accueil-voir-tout"><a href="#/ot">${reste > 0 ? I18n.t('accueil.carte_ordres_technicien.voir_tous_ordres_travail', { reste }) : I18n.t('accueil.carte_ordres_technicien.voir_tous_ordres_travail_2')}</a></p>` : ''}
    </article>`;
  }

  // D199 (T480) : SES habilitations, celles du technicien du profil (en mode serveur avec comptes : du compte connecté,
  // App.profil vient de la session), jamais un justificatif (D196). Carte d'equipe-habilitations.js, chargé après ce
  // fichier : cherchée au moment de l'affichage (absente des pages de test qui ne chargent pas ce fichier).
  function carteMesHabilitations(aujourdhui) {
    if (typeof Equipe === 'undefined' || typeof Equipe.carteMesHabilitations !== 'function') return '';
    return Equipe.carteMesHabilitations(App.profil.technicienId, aujourdhui);
  }

  function accueilTechnicien() {
    const aujourdhui = Donnees.aujourdhui();
    const identifiant = App.profil.technicienId;
    const rangPriorite = { P1: 1, P2: 2, P3: 3, P4: 4 };
    const mesOrdres = Donnees.lignes('ordres_travail')
      .filter((ot) => ot.technicien_id === identifiant && otOuvert(ot))
      .sort((a, b) => (rangPriorite[a.priorite] || 9) - (rangPriorite[b.priorite] || 9)
        || (a.date_prevue || '9999').localeCompare(b.date_prevue || '9999'));
    const compteurs = calculerCompteurs();
    // L14 : « Mes ordres de travail », « À prendre », « En attente dans l'équipe » (ordres-prise.js, chargé après ce
    // fichier) ; sur téléphone, au-dessus de l'aide à l'écran (repère data-aide-apres, aide-ecrans.js) et des compteurs.
    const telephone = UI.estTelephone();
    const equipe = typeof Ordres !== 'undefined' && Ordres.blocsAccueilTechnicien
      ? Ordres.blocsAccueilTechnicien(telephone) : { html: '', nombreAPrendre: 0 };
    const blocs = UI.html`${typeof Ordres !== 'undefined' && Ordres.repriseDeMesOt ? Ordres.repriseDeMesOt() : ''}
      ${carteOrdresTechnicien(mesOrdres, aujourdhui, equipe.nombreAPrendre)}${equipe.html}`;
    return UI.html`
      <div class="entete-page"><div>
        <h1>${I18n.t('accueil.accueil_technicien.accueil')}</h1>
        <p>${I18n.t('accueil.accueil_technicien.bonjour_voici_ordres_travail', { profilNom: App.profil.nom })}</p>
      </div></div>
      ${telephone ? blocs : ''}
      <div class="pile-gros accueil-signaler">
        <a href="#/di/nouvelle" class="btn btn-primaire btn-gros">${UI.icone('ajouter')}<span>${I18n.html('accueil.accueil_technicien.signaler_probleme_creer_demande')}</span></a>
      </div>
      <div class="instruments accueil-instruments accueil-instruments-technicien">${indicateursConformite(compteurs, aujourdhui)}</div>
      ${telephone ? '' : blocs}
      ${carteMesHabilitations(aujourdhui)}`;
  }

  function accueilDemandeur() {
    const nom = App.profil.nom.trim().toLowerCase();
    const mesDemandes = Donnees.lignes('demandes')
      .filter((di) => di.demandeur.trim().toLowerCase() === nom)
      .sort((a, b) => b.date_heure.localeCompare(a.date_heure));
    return UI.html`
      <div class="entete-page"><div>
        <h1>${I18n.t('accueil.accueil_technicien.accueil')}</h1>
        <p>${I18n.t('accueil.accueil_demandeur.bonjour_equipement_fonctionne_pas', { profilNom: App.profil.nom })}</p>
      </div></div>
      <div class="pile-gros accueil-signaler">
        <a href="#/di/nouvelle" class="btn btn-primaire btn-gros">${UI.icone('ajouter')}<span>${I18n.html('accueil.accueil_technicien.signaler_probleme_creer_demande')}</span></a>
      </div>
      ${carteListe(I18n.t('accueil.accueil_demandeur.mes_dernieres_demandes'), mesDemandes.length,
        mesDemandes.slice(0, NOMBRE_LIGNES).map((di) => carteDemande(di, true)),
        '#/di', I18n.t('accueil.accueil_demandeur.voir_toutes_mes_demandes'),
        I18n.t('accueil.accueil_demandeur.aucune_demande_moment'), I18n.t('accueil.accueil_demandeur.demandes_creez_apparaitront_ici'), 'demandes')}`;
  }

  /**
   * Direction (T520, A7) : lecture seule — quatre portes (tableau de bord, bilan du mois, parc et historique, ordres
   * de travail) ; aucun bouton d'écriture, ni la carte « Connecter un téléphone ».
   */
  function accueilDirection() {
    const porte = (lien, icone, titre, detail) => UI.html`<a href="${lien}" class="btn btn-secondaire btn-gros">${UI.icone(icone)}<span>${titre}<small>${detail}</small></span></a>`;
    const nom = App.profil.nom.trim();
    return UI.html`
      <div class="entete-page"><div>
        <h1>${I18n.t('accueil.accueil_technicien.accueil')}</h1>
        <p>${nom ? I18n.t('accueil.accueil_direction.bonjour_nom', { profilNom: nom }) : I18n.t('accueil.accueil_direction.bonjour')}</p>
      </div></div>
      ${typeof Indicateurs !== 'undefined' && Indicateurs.teteDuMois ? Indicateurs.teteDuMois() : ''}
      <p class="note">${I18n.t('accueil.accueil_direction.lecture_seule')}</p>
      <div class="pile-gros accueil-direction">
        ${porte('#/indicateurs', 'indicateurs', I18n.t('accueil.accueil_direction.tableau_de_bord'), I18n.t('accueil.accueil_direction.tableau_de_bord_detail'))}
        ${porte('#/indicateurs?onglet=rapports', 'imprimer', I18n.t('accueil.accueil_direction.bilan'), I18n.t('accueil.accueil_direction.bilan_detail'))}
        ${porte('#/parc', 'parc', I18n.t('accueil.accueil_direction.parc'), I18n.t('accueil.accueil_direction.parc_detail'))}
        ${porte('#/ot', 'ordres', I18n.t('accueil.accueil_direction.ordres'), I18n.t('accueil.accueil_direction.ordres_detail'))}
      </div>`;
  }

  // ===========================================================================================
  // 5. Écran
  // ===========================================================================================

  async function afficher(conteneur) {
    if (App.estDirection()) { UI.remplir(conteneur, accueilDirection()); return; }
    // Carte « Connecter un téléphone » : en mode serveur, sauf sur un téléphone (D31 : il est déjà
    // connecté, et le QR ne se scanne pas sur son propre écran). On lit l'adresse réseau AVANT
    // d'écrire l'écran (un seul remplissage).
    const avecConnexion = App.mode === 'serveur' && !UI.estTelephone();
    const adresses = avecConnexion ? await lireAdressesReseau() : null;
    // Si l'utilisateur est parti ailleurs pendant l'attente, on n'écrase pas son nouvel écran.
    if (!/^#\/accueil/.test(location.hash)) return;

    const connexion = adresses === null ? '' : carteConnexion(adresses);
    // L05 (lot 2) : carte « Ajouter des utilisateurs » (equipe-utilisateurs.js), avant celle du téléphone, partout où
    // celle-ci est posée (responsable, Solo, technicien).
    const finAccueil = UI.html`${typeof EquipeUtilisateurs !== 'undefined' ? EquipeUtilisateurs.carteAccueil() : ''}${connexion}`;
    // Responsable : accueil « bento » (accueil-bento.js, chargé après ce fichier : appelé au moment de
    // l'affichage), avec la tuile du rapport du mois écoulé (lot 3, §15.9).
    // T521 : accueil du mode Solo (solo-accueil.js, chargé après ce fichier).
    if (typeof SoloAccueil !== 'undefined' && App.modeSolo()) { await SoloAccueil.afficher(conteneur, finAccueil); return; }
    if (App.estResponsable()) {
      // P12 : en haut tant qu'aucun téléphone ne s'est connecté (seulement quand la carte montre une adresse et un QR,
      // et que les comptes sont exigés : sans eux, le serveur ne tient ni journal ni liste d'appareils).
      const enHaut = Boolean(connexion) && !cePcSeulement && adresses.length > 0 && App.comptesExiges()
        && !(await telephoneDejaConnecte());
      if (!/^#\/accueil/.test(location.hash)) return;
      Accueil.afficherResponsable(conteneur, finAccueil, enHaut);
      return;
    }
    const contenu = App.estTechnicien() ? accueilTechnicien() : accueilDemandeur();
    UI.remplir(conteneur, UI.html`${contenu}${finAccueil}`);
    // L17 : « Je prends » des demandes de la carte « À prendre » (ordres-prise.js).
    if (App.estTechnicien() && typeof Ordres !== 'undefined' && Ordres.brancherAccueilTechnicien) Ordres.brancherAccueilTechnicien(conteneur);
  }

  // App est chargé après les modules : l'écran est enregistré une fois la page lue.
  document.addEventListener('DOMContentLoaded', () => {
    App.ecran({
      id: 'accueil', route: /^#\/accueil$/, get titre() { return I18n.t('accueil.accueil_technicien.accueil'); },
      menu: { get libelle() { return I18n.t('accueil.accueil_technicien.accueil'); }, icone: 'accueil', ordre: 10 },
      profils: ['demandeur', 'technicien', 'responsable', 'direction'],
      // Les compteurs viennent de demandes et ordres_travail ; l'alerte de contrôle peut venir de
      // n'importe quelle table (sauf le journal, qui change à chaque action).
      tables: Schema.nomsTables().filter((nomTable) => nomTable !== 'journal'),
      afficher,
    });
  });

  return {
    afficher, calculerCompteurs, otEnRetard, p1Ouvert, dimancheDe, preventifDeLaSemaine,
    // Pour accueil-bento.js seulement (pas une API : aucun autre module ni test ne s'en sert).
    interne: { otOuvert, joursEntre, pluriel, libelleEquipement, badgeImpact, alerteControle, carteBaseVide,
      detailReservesEnRetard, NOMBRE_LIGNES, ORIGINE_PREVENTIF, LIEN_RESERVES_EN_RETARD },
  };
})();
