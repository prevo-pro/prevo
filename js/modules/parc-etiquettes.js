'use strict';
// Parc (4/5) — étiquettes QR par lot : sélection d'équipements, planches A4 de 24 ou 8 étiquettes,
// adresse encodée dans les QR (ARCHITECTURE.md §15.6 ; brief §9 E7).
// Complète l'objet Parc. L'écran #/parc/etiquettes est enregistré par parc-fiche.js (dernier
// fichier du module, seul à écouter DOMContentLoaded).
//
// Offert :
//   Parc.FORMATS_ETIQUETTES                      les deux formats de planche (24 ou 8 étiquettes)
//   Parc.equipementsPourEtiquettes({ localisationId, criticite, ids })   équipements à étiqueter
//   Parc.planchesEtiquettes(equipements, format, { haut, gauche })        HTML des planches A4
//   Parc.afficherEtiquettes(conteneur, parametres)                        écran #/parc/etiquettes
//   Parc.porteeAdresse(adresse)       'ce-pc' | 'locale' | 'tailscale' | 'exterieur' | '' (pas une adresse http)
//   Parc.estLocaleOuPrivee(adresse)   vrai pour 'ce-pc' et 'locale' (lot 1 ergonomie, T518)
//   Parc.adresseDesQr()               début de l'adresse mise dans les QR (mode serveur), '' sinon
//   Parc.consigneEtiquette(adresse, wifi)   ligne imprimée au-dessus du QR ('' si l'adresse est joignable de partout)
//   Parc.avertissementReseau(adresse, { lienPortee, lienEtiquettes })   encadré « le QR ne s'ouvrira pas en 4G »
//   Parc.atelierSansWifi()            vrai si l'atelier n'a pas de Wi-Fi (parametres.csv : atelier_sans_wifi = 1 ; T536)
//
// Impression : chaque planche est une page A4 dessinée en millimètres (positions absolues). La
// feuille css/modules/etiquettes.css lui donne une page nommée « etiquettes » sans marge
// (@page etiquettes { size: A4; margin: 0 }) : le bon de travail garde ses marges de 12 mm.

Object.assign(Parc, (() => {

  // Outils de parc-regles.js.
  const { estActif, comparerCodes, comparerLibelles, parRepere, identifiantsDescendants, badgeCriticite } = Parc.interne;
  const { cheminLocalisation } = Parc;

  /** Les deux formats de planche A4 (dimensions d'une étiquette en mm). */
  const FORMATS_ETIQUETTES = {
    '24': { colonnes: 3, lignes: 8, largeurMm: 70, hauteurMm: 37 },
    '8': { colonnes: 2, lignes: 4, largeurMm: 105, hauteurMm: 74 },
  };
  const FORMAT_DEFAUT = '24';
  const SEUIL_CONSIGNE_LONGUE = 60;                   // consigne plus longue (nom de Wi-Fi long) : police réduite pour tenir en deux lignes (L10)
  const A4 = { largeurMm: 210, hauteurMm: 297 };
  const DECALAGE_MAX_MM = 10;                         // décalage d'impression accepté : -10 à +10 mm
  const CLE_MEMOIRE = 'prevo.etiquettes';            // localStorage : { format, haut, gauche }
  const CLE_ADRESSE_QR = 'adresse_qr';                // parametres.csv (§15.1)
  const CLE_WIFI = 'wifi_nom';                        // parametres.csv : nom du Wi-Fi écrit sur l'étiquette (T518)
  const CLE_SANS_WIFI = 'atelier_sans_wifi';          // parametres.csv : 1 = l'atelier n'a pas de Wi-Fi (T536, L11)
  const TAILLE_QR_PX = 160;                           // taille du dessin ; l'impression la fixe en mm (CSS)

  // ===========================================================================================
  // 9. Étiquettes QR par lot : sélection et planches (règles)
  // ===========================================================================================

  /** Vrai si l'équipement mérite une étiquette : actif et pas au rebut. */
  function estEtiquetable(equipement) {
    return estActif(equipement) && equipement.statut !== 'rebut';
  }

  /**
   * Équipements à étiqueter, triés par repère : actifs hors rebut, de la localisation ET de ses
   * sous-localisations (si `localisationId`), de la criticité demandée (si `criticite`), parmi les
   * identifiants donnés (si `ids` est une liste non vide).
   */
  function equipementsPourEtiquettes(criteres) {
    const { localisationId = '', criticite = '', ids = [] } = criteres || {};
    let zone = null;
    if (localisationId) {
      zone = identifiantsDescendants('localisations', localisationId);
      zone.add(localisationId);
    }
    const choisis = Array.isArray(ids) && ids.length ? new Set(ids) : null;
    return Donnees.lignes('equipements')
      .filter((e) => estEtiquetable(e)
        && (!zone || zone.has(e.localisation_id))
        && (!criticite || e.criticite === criticite)
        && (!choisis || choisis.has(e.id)))
      .sort((a, b) => parRepere(a, b) || comparerCodes(a.id, b.id));
  }

  // Millimètres écrits pour le CSS : point décimal, deux décimales au plus (« 12.5 »).
  function mm(valeur) {
    return String(Math.round(valeur * 100) / 100);
  }

  // Décalage lu sans surprise : un nombre entre -10 et +10 mm, 0 sinon.
  function decalageMm(valeur) {
    const nombre = Donnees.nombre(valeur);
    if (nombre === null) return 0;
    return Math.min(DECALAGE_MAX_MM, Math.max(-DECALAGE_MAX_MM, nombre));
  }

  // QR d'une étiquette : l'adresse de la fiche (App.urlFicheEquipement). Repère seul si impossible.
  function qrEtiquette(equipement) {
    try {
      return UI.qrSvg(App.urlFicheEquipement(equipement.id), TAILLE_QR_PX);
    } catch (erreur) {
      console.warn('Prévo : QR de l\'étiquette ' + equipement.id + ' impossible (' + (erreur && erreur.message) + ').', erreur);
      return UI.html`<span class="etiquette-sans-qr">${I18n.t('parc.qr_etiquette.qr_indisponible')}</span>`;
    }
  }

  // ===========================================================================================
  // 9 bis. Adresse des QR joignable ou non hors de l'atelier (lot 1 ergonomie, T518, thème qr-4g)
  // ===========================================================================================

  /**
   * Portée de l'adresse d'un QR, d'après son nom d'hôte : 'ce-pc' (127.0.0.0/8, 0.0.0.0, localhost, ::1 : aucun
   * téléphone), 'locale' (10/8, 172.16/12, 192.168/16, 169.254/16, nom sans point ou en .local/.lan/.home, IPv6
   * fe80::/10 et fc00::/7 : le Wi-Fi de l'atelier seulement), 'tailscale' (100.64.0.0/10, *.ts.net : les appareils du
   * réseau privé seulement), 'exterieur' (joignable de partout, autant qu'on sache), '' (pas une adresse http(s),
   * « GMAO:<id> » des modes dossier et démo par exemple).
   */
  function porteeAdresse(adresse) {
    let hote = '';
    try {
      const url = new URL(String(adresse || '').trim());
      if (url.protocol !== 'http:' && url.protocol !== 'https:') return '';
      hote = url.hostname.toLowerCase().replace(/^\[|\]$/g, '').replace(/\.$/, '');
    } catch (erreur) {
      return '';
    }
    if (!hote) return '';
    if (hote === 'localhost' || hote.endsWith('.localhost')) return 'ce-pc';
    const ipv4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(hote);
    if (ipv4) {
      const a = Number(ipv4[1]);
      const b = Number(ipv4[2]);
      if (a === 127 || a === 0) return 'ce-pc';
      if (a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254)) return 'locale';
      if (a === 100 && b >= 64 && b <= 127) return 'tailscale';
      return 'exterieur';
    }
    if (hote.includes(':')) {                         // IPv6 (le navigateur l'écrit en minuscules, groupes abrégés)
      if (hote === '::1') return 'ce-pc';
      if (/^fe[89ab][0-9a-f]:/.test(hote) || /^f[cd][0-9a-f]{2}:/.test(hote)) return 'locale';
      return 'exterieur';
    }
    if (hote === 'ts.net' || hote.endsWith('.ts.net')) return 'tailscale';
    if (!hote.includes('.') || /\.(local|lan|home)$/.test(hote)) return 'locale';
    return 'exterieur';
  }

  /** Vrai si l'adresse n'est joignable que de ce PC ou du réseau de l'atelier. */
  function estLocaleOuPrivee(adresse) {
    const portee = porteeAdresse(adresse);
    return portee === 'ce-pc' || portee === 'locale';
  }

  /**
   * Ligne imprimée sous le QR : « Connectez-vous au Wi-Fi de l'usine… » pour une adresse 'locale' (avec le nom du
   * Wi-Fi s'il est donné), « Ouvrez l'application Tailscale… » pour 'tailscale' ; '' sinon (joignable de partout,
   * ou 'ce-pc' : aucun téléphone ne l'ouvrira, la consigne serait fausse ; l'écran le dit).
   */
  function consigneEtiquette(adresse, wifi) {
    const portee = porteeAdresse(adresse);
    const nom = String(wifi || '').trim();
    if (portee === 'locale') return nom ? I18n.t('parc.etiquette.consigne_wifi_nomme', { wifi: nom }) : I18n.t('parc.etiquette.consigne_wifi');
    if (portee === 'tailscale') return I18n.t('parc.etiquette.consigne_tailscale');
    return '';
  }

  /**
   * Encadré pour le responsable quand le QR ne s'ouvrira pas partout : la conséquence (page d'erreur du navigateur
   * en 4G) et les solutions ; '' quand l'adresse est joignable de l'extérieur ou n'est pas une adresse http(s).
   * `lienPortee` : lien vers Paramètres › Accès et installation (portée) ; `lienEtiquettes` : lien vers l'écran
   * Étiquettes (réimprimer, nom du Wi-Fi).
   */
  function avertissementReseau(adresse, options) {
    const portee = porteeAdresse(adresse);
    if (portee !== 'ce-pc' && portee !== 'locale' && portee !== 'tailscale') return '';
    const { lienPortee = false, lienEtiquettes = false } = options || {};
    const textes = {
      'ce-pc': ['parc.avertissement_reseau.ce_pc_titre', 'parc.avertissement_reseau.ce_pc_consequence',
        'parc.avertissement_reseau.ce_pc_solution_1', 'parc.avertissement_reseau.ce_pc_solution_2'],
      locale: ['parc.avertissement_reseau.locale_titre', 'parc.avertissement_reseau.locale_consequence',
        'parc.avertissement_reseau.locale_solution_1', 'parc.avertissement_reseau.locale_solution_2'],
      tailscale: ['parc.avertissement_reseau.tailscale_titre', 'parc.avertissement_reseau.tailscale_consequence',
        'parc.avertissement_reseau.tailscale_solution_1', 'parc.avertissement_reseau.tailscale_solution_2'],
    }[portee];
    const liens = [
      lienPortee ? UI.html`<a href="#/parametres">${I18n.t('parc.avertissement_reseau.lien_portee')}</a>` : '',
      lienEtiquettes ? UI.html`<a href="#/parc/etiquettes">${I18n.t('parc.avertissement_reseau.lien_etiquettes')}</a>` : '',
    ].filter(Boolean);
    return UI.html`<div class="encadre attention avertissement-reseau" data-portee="${portee}" role="note">${UI.icone('alerte')}
      <div>
        <p><b>${I18n.t(textes[0])}</b></p>
        <p>${I18n.html(textes[1], { adresse })}</p>
        <p>${I18n.t('parc.avertissement_reseau.solutions')}</p>
        <ul>
          <li>${I18n.t(textes[2])}</li>
          <li>${I18n.t(textes[3])}</li>
        </ul>
        ${liens.length ? UI.html`<p class="avertissement-reseau-liens">${liens}</p>` : ''}
      </div>
    </div>`;
  }

  // Une étiquette, placée en mm dans sa planche : QR, repère en gros, désignation, entreprise ; la consigne réseau
  // (T518) EN HAUT au-dessus du QR (L10), sur toute la largeur, quand il y en a une.
  function etiquetteHtml(equipement, position, gabarit, entreprise, consigne) {
    const boite = { left: mm(position.gaucheMm), top: mm(position.hautMm), width: mm(gabarit.largeurMm), height: mm(gabarit.hauteurMm) };
    const style = Object.keys(boite).map((propriete) => propriete + ': ' + boite[propriete] + 'mm').join('; ');
    return UI.html`<div class="etiquette${consigne ? ' avec-consigne' : ''}" data-equipement="${equipement.id}" style="${style}">
      <div class="etiquette-qr">${qrEtiquette(equipement)}</div>
      <div class="etiquette-texte">
        <b class="etiquette-repere">${equipement.repere || equipement.id}</b>
        <span class="etiquette-designation">${equipement.designation}</span>
        ${entreprise ? UI.html`<span class="etiquette-entreprise">${entreprise}</span>` : ''}
      </div>
      ${consigne ? UI.html`<span class="etiquette-consigne ${consigne.length > SEUIL_CONSIGNE_LONGUE ? 'consigne-longue' : 'consigne-courte'}">${consigne}</span>` : ''}
    </div>`;
  }

  /**
   * HTML des planches A4 (une <section class="planche-etiquettes"> par page) : étiquettes rangées
   * de gauche à droite puis de haut en bas, la grille centrée sur la feuille, puis décalée de
   * `decalage.haut` et `decalage.gauche` mm (réglage de l'imprimante). Format : '24' ou '8'.
   */
  function planchesEtiquettes(equipements, format, decalage) {
    const cle = String(format || FORMAT_DEFAUT);
    const gabarit = FORMATS_ETIQUETTES[cle];
    if (!gabarit) throw new Error(I18n.t('parc.planches_etiquettes.format_etiquettes_inconnu_24', { format }));
    const haut = decalageMm(decalage && decalage.haut);
    const gauche = decalageMm(decalage && decalage.gauche);
    const parPlanche = gabarit.colonnes * gabarit.lignes;
    const margeHaut = (A4.hauteurMm - gabarit.lignes * gabarit.hauteurMm) / 2;
    const margeGauche = (A4.largeurMm - gabarit.colonnes * gabarit.largeurMm) / 2;
    const entreprise = Donnees.parametre('entreprise_nom', '');
    const consigne = consigneEtiquette(App.urlFicheEquipement('X'), Donnees.parametre(CLE_WIFI, ''));
    const liste = equipements || [];
    const total = Math.ceil(liste.length / parPlanche);
    const planches = [];
    for (let numero = 0; numero < total; numero += 1) {
      const etiquettes = liste.slice(numero * parPlanche, (numero + 1) * parPlanche).map((equipement, rang) => {
        const position = {
          gaucheMm: margeGauche + gauche + (rang % gabarit.colonnes) * gabarit.largeurMm,
          hautMm: margeHaut + haut + Math.floor(rang / gabarit.colonnes) * gabarit.hauteurMm,
        };
        return etiquetteHtml(equipement, position, gabarit, entreprise, consigne);
      });
      planches.push(UI.html`<section class="planche-etiquettes format-${cle}" aria-label="${I18n.t('parc.planches_etiquettes.planche_v1_total', { numero: numero + 1, total })}">${etiquettes}</section>`);
    }
    return UI.html`${planches}`;
  }

  // ===========================================================================================
  // 10. Écran #/parc/etiquettes : sélection, adresse, format, décalage, aperçu, impression
  // ===========================================================================================

  // Réglages du poste (localStorage) : format et décalage. Valeur illisible → réglages par défaut.
  function lireReglages() {
    let lus = {};
    try {
      lus = JSON.parse(localStorage.getItem(CLE_MEMOIRE) || '{}') || {};
    } catch (erreur) {
      lus = {};
    }
    return {
      format: FORMATS_ETIQUETTES[lus.format] ? String(lus.format) : FORMAT_DEFAUT,
      haut: decalageMm(lus.haut),
      gauche: decalageMm(lus.gauche),
    };
  }

  function memoriserReglages(reglages) {
    try {
      localStorage.setItem(CLE_MEMOIRE, JSON.stringify({ format: reglages.format, haut: reglages.haut, gauche: reglages.gauche }));
    } catch (erreur) {
      console.warn('Prévo : réglages des étiquettes non mémorisés (' + (erreur && erreur.message) + ').', erreur);
    }
  }

  // Sélection de l'écran, gardée d'un affichage à l'autre tant que l'adresse ne change pas (un
  // changement sur un autre poste réaffiche l'écran sans perdre les cases décochées).
  let selection = null;

  function selectionPour(requete) {
    const texte = requete.toString();
    if (!selection || selection.requete !== texte) {
      selection = {
        requete: texte,
        localisationId: requete.get('localisation') || '',
        criticite: requete.get('criticite') || '',
        ids: (requete.get('ids') || '').split(',').map((id) => id.trim()).filter(Boolean),
        decoches: new Set(),
      };
    }
    return selection;
  }

  // Début de l'adresse mise dans les QR (« http://192.168.1.10:8080/ ») : App.urlFicheEquipement
  // la calcule (adresse_qr, sinon première adresse détectée) ; on retire la fin propre à la fiche.
  /** Vrai quand le responsable a dit que l'atelier n'a pas de Wi-Fi (assistant ou Paramètres ; T536, L11). */
  function atelierSansWifi() {
    return String(Donnees.parametre(CLE_SANS_WIFI, '0') || '').trim() === '1';
  }

  function adresseDeBase() {
    const exemple = App.urlFicheEquipement('X');
    const fin = '#/equipement/X';
    return exemple.endsWith(fin) ? exemple.slice(0, -fin.length) : exemple;
  }

  /** Début de l'adresse mise dans les QR en mode serveur (« http://192.168.1.10:8080/ »), '' dans les autres modes. */
  function adresseDesQr() {
    return App.mode === 'serveur' ? adresseDeBase() : '';
  }

  function memeAdresse(a, b) {
    return String(a || '').replace(/\/+$/, '') === String(b || '').replace(/\/+$/, '');
  }

  // Adresses proposées : celles du PC, plus l'adresse choisie avant si elle n'y est plus.
  function adressesProposees() {
    const adresses = App.adressesReseau();
    const choisie = String(Donnees.parametre(CLE_ADRESSE_QR, '') || '').trim();
    if (/^https?:\/\/\S+$/i.test(choisie) && !adresses.some((a) => memeAdresse(a, choisie))) adresses.push(choisie);
    return adresses;
  }

  async function enregistrerAdresse(adresse) {
    await Donnees.modifier('parametres', (lignes) => {
      if (!/^https?:\/\/\S+$/i.test(adresse)) {
        throw new Donnees.ErreurValidation(I18n.t('parc.enregistrer_adresse.adresse_invalide_doit_commencer', { adresse }));
      }
      const ligne = lignes.find((l) => l.cle === CLE_ADRESSE_QR);
      if (ligne) ligne.valeur = adresse; else lignes.push({ cle: CLE_ADRESSE_QR, valeur: adresse });
    }, { action: 'adresse des QR des étiquettes : ' + adresse });
  }

  // Nom du Wi-Fi écrit sur l'étiquette (T518) : vide = « le Wi-Fi de l'usine » sans nom.
  async function enregistrerWifi(nom) {
    const valeur = String(nom || '').trim().replace(/\s+/g, ' ');
    await Donnees.modifier('parametres', (lignes) => {
      const ligne = lignes.find((l) => l.cle === CLE_WIFI);
      if (ligne) ligne.valeur = valeur; else lignes.push({ cle: CLE_WIFI, valeur });
    }, { action: 'nom du Wi-Fi des étiquettes : ' + (valeur || '(aucun)') });
    return valeur;
  }

  // Champ « Nom du Wi-Fi » (mode serveur, adresse du réseau de l'atelier) : écrit sur chaque étiquette.
  function champWifi() {
    return UI.html`<div class="form-ligne etiquettes-wifi">
        <label for="etiquettes-wifi">${I18n.t('parc.carte_adresse.nom_wifi')}
          <input type="text" id="etiquettes-wifi" maxlength="40" autocomplete="off" value="${Donnees.parametre(CLE_WIFI, '')}"
            placeholder="${I18n.t('parc.carte_adresse.nom_wifi_exemple')}"></label>
        <button type="button" class="btn btn-secondaire" id="etiquettes-wifi-enregistrer">${UI.icone('valider')}${I18n.t('commun.bouton.enregistrer')}</button>
      </div>
      <p class="aide">${I18n.t('parc.carte_adresse.nom_wifi_aide')}</p>`;
  }

  // Carte « Adresse des QR » : en mode serveur, l'adresse encodée, l'avertissement et le choix ;
  // en dossier et en démo, ce que contient le QR.
  function carteAdresse() {
    if (App.mode !== 'serveur') {
      return UI.html`<section class="carte etiquettes-adresse" aria-labelledby="etiquettes-titre-adresse">
        <h2 id="etiquettes-titre-adresse">${UI.icone('qr')} ${I18n.t('parc.carte_adresse.contenu_qr')}</h2>
        <p>${I18n.html('parc.carte_adresse.qr_contient_gmao_id')}</p>
      </section>`;
    }
    const base = adresseDeBase();
    const adresses = adressesProposees();
    const choix = adresses.length > 1 ? UI.html`<div class="form-ligne etiquettes-choix-adresse">
        <label for="etiquettes-adresse">${I18n.t('parc.carte_adresse.adresse_pc_mettre_qr')}
          <select id="etiquettes-adresse">${adresses.map((adresse) => UI.html`<option value="${adresse}" ${memeAdresse(adresse, base) ? UI.brut('selected') : ''}>${adresse}</option>`)}</select>
        </label>
        <button type="button" class="btn btn-secondaire" id="etiquettes-adresse-enregistrer">${UI.icone('valider')}${I18n.t('parc.carte_adresse.utiliser_adresse')}</button>
      </div>` : '';
    return UI.html`<section class="carte etiquettes-adresse" aria-labelledby="etiquettes-titre-adresse">
      <h2 id="etiquettes-titre-adresse">${UI.icone('qr')} ${I18n.t('parc.carte_adresse.adresse_encodee_qr')}</h2>
      <p>${I18n.html('parc.carte_adresse.chaque_qr_ouvre_fiche', { base })}</p>
      <div class="encadre attention etiquettes-avertissement">${UI.icone('alerte')}
        ${I18n.t('parc.carte_adresse.si_adresse_ip_port')}</div>
      ${adresses.length ? '' : UI.html`<p class="note">${I18n.t('parc.carte_adresse.aucune_adresse_reseau_ete')}</p>`}
      ${App.cePcSeulement && App.cePcSeulement() ? UI.html`<div class="encadre info" id="etiquettes-ce-pc">${UI.icone('alerte')}
        ${I18n.t('parc.carte_adresse.prevo_joignable_pc_instant')}</div>` : ''}
      <div id="etiquettes-avertissement-reseau" tabindex="-1">${avertissementReseau(base, { lienPortee: true })}</div>
      ${choix}
      ${porteeAdresse(base) === 'locale' ? champWifi() : ''}
    </section>`;
  }

  // Options « Tout le parc », puis chaque localisation par son chemin (« Site › Atelier › Ligne »).
  function optionsLocalisations(valeur) {
    const localisations = Donnees.lignes('localisations')
      .map((l) => ({ id: l.id, chemin: cheminLocalisation(l.id) }))
      .sort((a, b) => comparerLibelles(a.chemin, b.chemin));
    return UI.html`<option value="">${I18n.t('parc.options_localisations.tout_parc')}</option>${localisations.map((l) => UI.html`<option value="${l.id}" ${l.id === valeur ? UI.brut('selected') : ''}>${l.chemin}</option>`)}`;
  }

  function optionsCriticite(valeur) {
    const choix = [['', I18n.t('parc.options_criticite.toutes')], ['A', I18n.t('parc.options_criticite.tres_critique')], ['B', I18n.t('parc.options_criticite.b_critique')], ['C', I18n.t('parc.options_criticite.peu_critique')]];
    return UI.html`${choix.map(([code, libelle]) => UI.html`<option value="${code}" ${code === valeur ? UI.brut('selected') : ''}>${libelle}</option>`)}`;
  }

  function optionsFormat(valeur) {
    return UI.html`${Object.keys(FORMATS_ETIQUETTES).sort((a, b) => Number(b) - Number(a)).map((cle) => {
      const g = FORMATS_ETIQUETTES[cle];
      return UI.html`<option value="${cle}" ${cle === valeur ? UI.brut('selected') : ''}>${I18n.t('parc.options_format.planche_mm', { cle, colonnes: g.colonnes, lignes: g.lignes, largeurMm: g.largeurMm, hauteurMm: g.hauteurMm })}</option>`;
    })}`;
  }

  // Liste à cocher des équipements retenus par les filtres.
  function listeEquipementsHtml(equipements, decoches) {
    if (!equipements.length) {
      return UI.html`<p class="muted etiquettes-vide">${I18n.t('parc.liste_equipements.aucun_equipement_actif_correspond')}</p>`;
    }
    return UI.html`${equipements.map((e) => UI.html`<label class="case etiquettes-case">
      <input type="checkbox" value="${e.id}" ${decoches.has(e.id) ? '' : UI.brut('checked')}>
      <span class="etiquettes-case-texte"><b>${e.repere || e.id}</b> <span>${e.designation}</span>
        <small>${e.localisation_id ? cheminLocalisation(e.localisation_id) : I18n.t('parc.liste_equipements.sans_localisation')}</small></span>
      ${badgeCriticite(e.criticite)}
    </label>`)}`;
  }

  // Rappel en tête de l'aperçu (à l'écran seulement : seul #impression est imprimé) : la consigne mise sur chaque
  // étiquette, ou « aucun téléphone » pour une adresse de ce PC, et le bouton qui mène à l'avertissement.
  function rappelConsigne() {
    const base = adresseDesQr();
    const portee = porteeAdresse(base);
    if (portee !== 'locale' && portee !== 'tailscale' && portee !== 'ce-pc') return '';
    const texte = portee === 'ce-pc' ? I18n.t('parc.etiquettes.rappel_aucun_telephone')
      : I18n.t('parc.etiquettes.rappel_consigne', { consigne: consigneEtiquette(base, Donnees.parametre(CLE_WIFI, '')) });
    return UI.html`<p class="encadre info etiquettes-rappel-consigne" id="etiquettes-rappel-consigne">${UI.icone('alerte')}
      <span>${texte} <button type="button" class="btn btn-fantome" id="etiquettes-voir-avertissement">${I18n.t('parc.etiquettes.voir_avertissement')}</button></span></p>`;
  }

  function afficherEtiquettes(conteneur, parametres) {
    const etat = selectionPour(parametres.requete);
    const reglages = lireReglages();
    // data-hors-saisie : ces réglages ne sont pas une saisie à protéger (l'état est gardé ici).
    UI.remplir(conteneur, UI.html`
      <div class="parc etiquettes" data-hors-saisie>
        <div class="entete-page">
          <div>
            <div class="fil"><a href="#/parc">${I18n.t('parc.etiquettes.parc')}</a></div>
            <h1>${I18n.t('parc.etiquettes.etiquettes_qr')}</h1>
            <p>${I18n.t('parc.etiquettes.choisissez_equipements_format_planche')}</p>
          </div>
        </div>
        ${carteAdresse()}
        <div class="grille etiquettes-grille">
          <section class="carte c5 etiquettes-selection" aria-labelledby="etiquettes-titre-selection">
            <h2 id="etiquettes-titre-selection">${I18n.t('parc.etiquettes.equipements')}</h2>
            <div class="form-ligne">
              <label for="etiquettes-localisation">${I18n.t('parc.etiquettes.localisation_sous_localisations')}
                <select id="etiquettes-localisation">${optionsLocalisations(etat.localisationId)}</select></label>
              <label for="etiquettes-criticite">${I18n.t('commun.champ.criticite')}
                <select id="etiquettes-criticite">${optionsCriticite(etat.criticite)}</select></label>
            </div>
            ${etat.ids.length ? UI.html`<p class="note">${I18n.html('parc.etiquettes.selection_limitee_lien', { n: etat.ids.length })}</p>` : ''}
            <div class="actions">
              <button type="button" class="btn btn-fantome" id="etiquettes-tout-cocher">${I18n.t('parc.etiquettes.tout_cocher')}</button>
              <button type="button" class="btn btn-fantome" id="etiquettes-tout-decocher">${I18n.t('parc.etiquettes.tout_decocher')}</button>
            </div>
            <fieldset class="etiquettes-liste" id="etiquettes-liste">
              <legend class="visuellement-cache">${I18n.t('parc.etiquettes.equipements_etiqueter')}</legend>
            </fieldset>
          </section>
          <div class="c7 etiquettes-droite">
            <section class="carte etiquettes-reglages" aria-labelledby="etiquettes-titre-format">
              <h2 id="etiquettes-titre-format">${I18n.t('parc.etiquettes.format_impression')}</h2>
              <div class="form-ligne">
                <label for="etiquettes-format">${I18n.t('parc.etiquettes.planche_4')}
                  <select id="etiquettes-format">${optionsFormat(reglages.format)}</select></label>
              </div>
              <div class="form-ligne etiquettes-decalages">
                <label for="etiquettes-decalage-haut">${I18n.t('parc.etiquettes.decalage_vers_bas_mm')}
                  <input type="number" id="etiquettes-decalage-haut" min="-${DECALAGE_MAX_MM}" max="${DECALAGE_MAX_MM}" step="0.5" inputmode="decimal" value="${reglages.haut}"></label>
                <label for="etiquettes-decalage-gauche">${I18n.t('parc.etiquettes.decalage_vers_droite_mm')}
                  <input type="number" id="etiquettes-decalage-gauche" min="-${DECALAGE_MAX_MM}" max="${DECALAGE_MAX_MM}" step="0.5" inputmode="decimal" value="${reglages.gauche}"></label>
              </div>
              <p class="aide">${I18n.t('parc.etiquettes.si_impression_tombe_cote')}</p>
              <p class="etiquettes-resume" id="etiquettes-resume" role="status" aria-live="polite"></p>
              <div class="actions">
                <button type="button" class="btn btn-primaire" id="etiquettes-imprimer">${UI.icone('imprimer')}${I18n.t('commun.bouton.imprimer')}</button>
              </div>
            </section>
            <section class="carte etiquettes-apercu-carte" aria-labelledby="etiquettes-titre-apercu">
              <h2 id="etiquettes-titre-apercu">${I18n.t('parc.etiquettes.apercu')}</h2>
              ${rappelConsigne()}
              <div class="etiquettes-apercu" id="etiquettes-apercu"></div>
            </section>
          </div>
        </div>
      </div>`);
    brancherEcran(conteneur, etat, reglages);
  }

  // Événements de l'écran : filtres, cases, format, décalage, adresse, impression.
  function brancherEcran(conteneur, etat, reglages) {
    const zoneListe = UI.$('#etiquettes-liste', conteneur);
    const zoneApercu = UI.$('#etiquettes-apercu', conteneur);
    const resume = UI.$('#etiquettes-resume', conteneur);
    const boutonImprimer = UI.$('#etiquettes-imprimer', conteneur);
    let retenus = [];                                  // équipements des filtres (cochés ou non)

    const equipementsCoches = () => retenus.filter((e) => !etat.decoches.has(e.id));

    function dessinerApercu() {
      const choisis = equipementsCoches();
      const gabarit = FORMATS_ETIQUETTES[reglages.format];
      const planches = Math.ceil(choisis.length / (gabarit.colonnes * gabarit.lignes));
      resume.textContent = choisis.length
        ? I18n.t('parc.etiquettes.resume_apercu', { etiquettes: I18n.t('parc.etiquettes.n_etiquettes', { n: choisis.length }),
          planches: I18n.t('parc.etiquettes.n_planches', { n: planches }), format: reglages.format })
        : I18n.t('parc.brancher_ecran.aucune_etiquette_cochez_moins');
      boutonImprimer.disabled = choisis.length === 0;
      UI.remplir(zoneApercu, choisis.length
        ? planchesEtiquettes(choisis, reglages.format, reglages)
        : UI.vide(I18n.t('parc.brancher_ecran.rien_imprimer'), I18n.t('parc.brancher_ecran.cochez_equipements_voir_etiquettes'), 'qr'));
    }

    function dessinerListe() {
      retenus = equipementsPourEtiquettes({ localisationId: etat.localisationId, criticite: etat.criticite, ids: etat.ids });
      UI.remplir(zoneListe, UI.html`<legend class="visuellement-cache">${I18n.t('parc.etiquettes.equipements_etiqueter')}</legend>${listeEquipementsHtml(retenus, etat.decoches)}`);
      dessinerApercu();
    }

    UI.$('#etiquettes-localisation', conteneur).addEventListener('change', (evenement) => {
      etat.localisationId = evenement.target.value;
      dessinerListe();
    });
    UI.$('#etiquettes-criticite', conteneur).addEventListener('change', (evenement) => {
      etat.criticite = evenement.target.value;
      dessinerListe();
    });
    zoneListe.addEventListener('change', (evenement) => {
      const caseACocher = evenement.target;
      if (caseACocher.type !== 'checkbox') return;
      if (caseACocher.checked) etat.decoches.delete(caseACocher.value); else etat.decoches.add(caseACocher.value);
      dessinerApercu();
    });
    UI.$('#etiquettes-tout-cocher', conteneur).addEventListener('click', () => {
      retenus.forEach((e) => etat.decoches.delete(e.id));
      dessinerListe();
    });
    UI.$('#etiquettes-tout-decocher', conteneur).addEventListener('click', () => {
      retenus.forEach((e) => etat.decoches.add(e.id));
      dessinerListe();
    });

    UI.$('#etiquettes-format', conteneur).addEventListener('change', (evenement) => {
      reglages.format = FORMATS_ETIQUETTES[evenement.target.value] ? evenement.target.value : FORMAT_DEFAUT;
      memoriserReglages(reglages);
      dessinerApercu();
    });
    [['#etiquettes-decalage-haut', 'haut'], ['#etiquettes-decalage-gauche', 'gauche']].forEach(([selecteur, cle]) => {
      const champ = UI.$(selecteur, conteneur);
      // Pendant la frappe : pris en compte dès que c'est un nombre ; en sortie du champ : valeur
      // ramenée entre -10 et +10 mm et réécrite.
      champ.addEventListener('input', () => {
        if (Donnees.nombre(champ.value) === null && champ.value !== '') return;
        reglages[cle] = decalageMm(champ.value);
        memoriserReglages(reglages);
        dessinerApercu();
      });
      champ.addEventListener('change', () => {
        reglages[cle] = decalageMm(champ.value);
        champ.value = String(reglages[cle]);
        memoriserReglages(reglages);
        dessinerApercu();
      });
    });

    const boutonAdresse = UI.$('#etiquettes-adresse-enregistrer', conteneur);
    if (boutonAdresse) {
      boutonAdresse.addEventListener('click', async () => {
        const adresse = UI.$('#etiquettes-adresse', conteneur).value;
        boutonAdresse.disabled = true;
        try {
          await enregistrerAdresse(adresse);
          UI.toast(I18n.t('parc.brancher_ecran.qr_contiendront_desormais', { adresse }), 'succes');
          await App.reafficher();
        } catch (erreur) {
          App.signalerErreur(erreur, 'adresse des QR');
          boutonAdresse.disabled = false;
        }
      });
    }

    const voirAvertissement = UI.$('#etiquettes-voir-avertissement', conteneur);
    if (voirAvertissement) {
      voirAvertissement.addEventListener('click', () => {
        const cible = UI.$('#etiquettes-avertissement-reseau', conteneur);
        if (!cible) return;
        cible.scrollIntoView({ block: 'center' });
        cible.focus({ preventScroll: true });
      });
    }
    const boutonWifi = UI.$('#etiquettes-wifi-enregistrer', conteneur);
    if (boutonWifi) {
      boutonWifi.addEventListener('click', async () => {
        boutonWifi.disabled = true;
        try {
          const nom = await enregistrerWifi(UI.$('#etiquettes-wifi', conteneur).value);
          UI.toast(nom ? I18n.t('parc.brancher_ecran.wifi_enregistre', { wifi: nom }) : I18n.t('parc.brancher_ecran.wifi_efface'), 'succes');
          await App.reafficher();
        } catch (erreur) {
          App.signalerErreur(erreur, 'nom du Wi-Fi des étiquettes');
          boutonWifi.disabled = false;
        }
      });
    }

    boutonImprimer.addEventListener('click', () => imprimer(equipementsCoches(), reglages));
    dessinerListe();
  }

  /** Remplit #impression avec les planches puis lance l'impression ; vidé après impression. */
  function imprimer(equipements, reglages) {
    const zone = document.getElementById('impression');
    if (!zone || !equipements.length) return;
    UI.remplir(zone, planchesEtiquettes(equipements, reglages.format, reglages));
    window.addEventListener('afterprint', () => { zone.textContent = ''; }, { once: true });
    window.print();
  }

  return {
    FORMATS_ETIQUETTES,
    equipementsPourEtiquettes,
    planchesEtiquettes,
    afficherEtiquettes,
    porteeAdresse,
    estLocaleOuPrivee,
    adresseDesQr,
    consigneEtiquette,
    avertissementReseau,
    atelierSansWifi,
  };
})());
