'use strict';
// InstallationEtapes : les formulaires des huit étapes de l'assistant d'installation (installation-ecrans.js,
// ARCHITECTURE.md §22.10 ; D131, D132 ; CS130) — champs, « Régler autrement » (réglages fins avec l'aide
// d'AccesTextes.options), lecture des valeurs et messages. Chaque formulaire reçoit le contexte « c » de l'écran :
// c.etat (GET etat), c.brouillon(), c.situation(), c.etatEtape(cle), c.blocTextes(choix), c.aideOption(cle).
// Les réglages que l'API n'écrit pas (durées de session, IA, quota) sont montrés avec leur aide et renvoyés à
// Paramètres › Accès et installation. Migration depuis 1.2 (T171) : les CSV présents sont annoncés dès l'étape 1 et
// gardés ; sans CSV au départ (brouillon.base_presente faux), l'étape 8 demande par quoi commencer (vide ou démo) et
// la langue de Prévo (langue_defaut de la base neuve, celle de l'écran « base vide » ou, sans elle, d'après le
// navigateur : langueDeDepart, UI.langueDuNavigateur, T296 ;
// appliquée à la fin, quand Prévo s'ouvre sur la base créée) et la dictée vocale (L24 : oui / non, dictee_autorisee ;
// cochée d'après l'écran « base vide » ou, en Solo, « oui » : dicteeDeDepart ; sans réponse, « non » sauf en Solo) ;
// dossier conseillé C:\Prevo proposé à l'étape 8 tant que le brouillon n'a pas deplacement_refuse (« Rester ici »).
// Dépendances : UI, AccesTextes. Chargé avant installation-ecrans.js.

const InstallationEtapes = (() => {

  const LONGUEUR_MIN_MOT_DE_PASSE = 12;        // règles du serveur (§22.3)
  const LONGUEUR_MAX_MOT_DE_PASSE = 256;
  const LONGUEUR_SOLIDE = 20;
  const LIEN_TAILSCALE = 'https://tailscale.com/download';
  // Libellés d'une portée et d'un démarrage (valeurs de prevo.config.json) : accesseurs, lus à l'affichage (aussi par
  // Paramètres › Accès et installation, InstallationEtapes.LIBELLES_PORTEE[valeur]).
  const LIBELLES_PORTEE = Object.freeze({
    get 'ce-pc'() { return I18n.t('installation.libelles_portee.seulement_pc'); },
    get atelier() { return I18n.t('installation.libelles_portee.wi_fi_atelier'); },
    get dehors() { return I18n.t('installation.libelles_portee.aussi_hors_atelier'); },
  });
  const LIBELLES_DEMARRAGE = Object.freeze({
    get systeme() { return I18n.t('installation.libelles_demarrage.pc_sans_fenetre'); },
    get session() { return I18n.t('installation.libelles_demarrage.ouverture_session'); },
    get aucun() { return I18n.t('installation.libelles_demarrage.main_raccourci'); },
  });

  // ===========================================================================================
  // 1. Petits blocs : champ d'un réglage, réglage lu, bouton radio
  // ===========================================================================================

  // attributs : fragment UI.brut('min="1" max="65535"') ; exemple : texte du placeholder (facultatif).
  function champReglage(c, cle, libelle, type, valeur, attributs, exemple) {
    const lue = valeur === null || valeur === undefined ? '' : valeur;
    return UI.html`<div class="champ">
      <label class="libelle" for="inst-${cle}">${libelle}</label>
      ${exemple ? UI.html`<input type="${type}" id="inst-${cle}" name="${cle}" value="${lue}" ${UI.brut(attributs || '')} placeholder="${exemple}">`
    : UI.html`<input type="${type}" id="inst-${cle}" name="${cle}" value="${lue}" ${UI.brut(attributs || '')}>`}
      <p class="aide">${c.aideOption(cle)}</p>
    </div>`;
  }

  // Réglage que l'assistant ne peut pas écrire (l'API n'a pas d'étape pour lui) : montré avec son aide et sa valeur.
  function reglageLu(c, cle) {
    const valeur = c.brouillon()[cle];
    const texte = Array.isArray(valeur) ? valeur.join(', ') : (valeur === true ? I18n.t('installation.reglage_lu.oui') : valeur === false ? I18n.t('installation.reglage_lu.non') : String(valeur === undefined ? '' : valeur));
    return UI.html`<div class="installation-reglage-lu"><b>${cle}</b> : ${texte || '—'}<p class="aide">${c.aideOption(cle)}</p></div>`;
  }

  const notePlusTard = () => I18n.t('installation.note_plus_tard.reglages_changent_apres_installation');

  // L24 (T549) : la réponse « Dictée vocale » donnée sur l'écran « base vide » avant « Installer Prévo » est gardée
  // pour cet onglet (sessionStorage) et cochée à l'étape 8 ; sans elle, Solo : « oui » (la personne qui installe est
  // celle qui dicte), équipe : rien de coché (sans réponse, non autorisée).
  const CLE_DICTEE_DE_DEPART = 'prevo.installation.dictee';

  /** Note la réponse de l'écran « base vide » (« 1 », « 0 », ou rien : oubliée). Sans sessionStorage, rien. */
  function noterDicteeDeDepart(valeur) {
    try {
      if (valeur === '0' || valeur === '1') window.sessionStorage.setItem(CLE_DICTEE_DE_DEPART, valeur);
      else window.sessionStorage.removeItem(CLE_DICTEE_DE_DEPART);
    } catch (erreur) { /* sans mémoire d'onglet : l'étape 8 repose la question */ }
  }

  // L01 (T549) : la langue de Prévo choisie sur l'écran « base vide » suit de même (sessionStorage de l'onglet) ; sans
  // elle, ou si elle n'est pas déclarée, la langue du navigateur (T296).
  const CLE_LANGUE_DE_DEPART = 'prevo.installation.langue';

  /** Note la langue choisie sur l'écran « base vide » (un code déclaré ; autre chose : oubliée). Sans sessionStorage, rien. */
  function noterLangueDeDepart(code) {
    try {
      if (I18n.langues.some((declaree) => declaree.code === code)) window.sessionStorage.setItem(CLE_LANGUE_DE_DEPART, code);
      else window.sessionStorage.removeItem(CLE_LANGUE_DE_DEPART);
    } catch (erreur) { /* sans mémoire d'onglet : la langue du navigateur */ }
  }

  /** Langue proposée à l'étape 8 : celle notée au départ si elle est déclarée, sinon celle du navigateur. */
  function langueDeDepart() {
    let notee = null;
    try { notee = window.sessionStorage.getItem(CLE_LANGUE_DE_DEPART); } catch (erreur) { notee = null; }
    return I18n.langues.some((declaree) => declaree.code === notee) ? notee : UI.langueDuNavigateur();
  }

  /** Réponse à cocher à l'étape 8 : celle notée au départ, sinon « 1 » en Solo (solo vrai), sinon '' (rien de coché). */
  function dicteeDeDepart(solo) {
    let notee = null;
    try { notee = window.sessionStorage.getItem(CLE_DICTEE_DE_DEPART); } catch (erreur) { notee = null; }
    if (notee === '0' || notee === '1') return notee;
    return solo ? '1' : '';
  }

  function choixRadio(nom, valeur, coche, titre, detail) {
    return UI.html`<label class="installation-choix">
      <input type="radio" name="${nom}" value="${valeur}" ${UI.brut(coche ? 'checked' : '')}>
      <span><b>${titre}</b>${detail ? UI.html`<small>${detail}</small>` : ''}</span>
    </label>`;
  }

  // ===========================================================================================
  // 2. Formulaires des étapes : { champs, autrement, lire(section) → corps ou { probleme }, message (rien coché),
  //    passer (l'étape est faite : « Continuer » avance sans appel), propresBoutons (Tailscale), reussite(donnees) →
  //    toast, echec(donnees) → message qui garde l'étape ouverte, apres(section) (mots de passe vidés) }
  // ===========================================================================================

  function caseACocher(nom, coche, titre, detail) {
    return UI.html`<label class="installation-choix">
      <input type="checkbox" name="${nom}" value="1" ${UI.brut(coche ? 'checked' : '')}>
      <span><b>${titre}</b>${detail ? UI.html`<small>${detail}</small>` : ''}</span>
    </label>`;
  }

  // T521 (lot 1 ergonomie, B) : deux questions sur la même étape. « Qui fait la maintenance ? » règle le mode (Solo ou
  // équipe) et rien d'autre ; puis « Qui d'autre ouvre Prévo ? », qui règle le réseau et les comptes : en Solo, trois
  // cases facultatives (rien de coché : ce PC seulement, sans compte) ; en équipe, les deux choix d'avant. Le groupe
  // montré suit le premier choix (CSS :has, installation.css) ; l'API reçoit toujours « situation » (seul, equipe,
  // informaticien), et « autres » en Solo.
  function formulaireSituation(c) {
    const choisie = c.situation();
    // Reprise d'un brouillon Solo : les cases cochées alors (un brouillon d'avant T521 : « mon téléphone » si la portée
    // dépasse ce PC).
    const autres = choisie === 'seul' ? Object.assign({ telephone: c.brouillon().portee !== 'ce-pc' }, c.brouillon().solo_autres || {}) : {};
    const nombre = Number(c.etat.nombre_csv) || 0;
    // Migration depuis 1.2 (D131, T171) : des CSV sont là → dit dès la première étape ; ils ne sont jamais touchés.
    // T521 : seulement s'ils ont des lignes (une base que cette version vient de créer vide n'est pas « Prévo 1.2 »).
    const anterieures = c.etat.donnees_anterieures === undefined ? c.etat.csv_presents : c.etat.donnees_anterieures;
    const migration = anterieures ? UI.html`<div class="alerte" id="inst-migration"><div class="alerte-texte">
        ${c.etat.derniere_modification
    ? I18n.html('installation.migration.donnees_la_date', { n: nombre, date: UI.dateHeureFr(c.etat.derniere_modification) })
    : I18n.html('installation.migration.donnees_la', { n: nombre })}</div></div>` : '';
    const t = (cle) => I18n.t('installation.formulaire_situation.' + cle);
    const forme = choisie === 'informaticien' ? 'informaticien' : 'equipe';
    return {
      champs: UI.html`${migration}<div class="installation-situation">
        <div class="installation-choix-liste" id="inst-qui-maintenance">
          ${choixRadio('situation', 'seul', choisie === 'seul', t('seul'), t('seul_aide'))}
          ${choixRadio('situation', 'equipe', choisie === 'equipe' || choisie === 'informaticien', t('equipe'), t('equipe_aide'))}
        </div>
        <fieldset class="installation-autres installation-autres-seul" id="inst-autres-seul">
          <legend>${t('qui_d_autre')}</legend>
          <p class="aide">${t('rien_coche')}</p>
          <div class="installation-choix-liste">
            ${caseACocher('autre_telephone', autres.telephone, t('mon_telephone'), t('mon_telephone_aide'))}
            ${caseACocher('autre_operateurs', autres.operateurs, t('operateurs'), t('operateurs_aide'))}
            ${caseACocher('autre_direction', autres.direction, t('direction'), t('direction_aide'))}
          </div>
        </fieldset>
        <fieldset class="installation-autres installation-autres-equipe" id="inst-autres-equipe">
          <legend>${t('qui_d_autre')}</legend>
          <div class="installation-choix-liste">
            ${choixRadio('forme_equipe', 'equipe', forme === 'equipe', AccesTextes.situations.equipe, t('plusieurs_personnes_telephones_comptes'))}
            ${choixRadio('forme_equipe', 'informaticien', forme === 'informaticien', AccesTextes.situations.informaticien, t('toutes_options_page_rien'))}
          </div>
        </fieldset>
      </div>`,
      autrement: UI.html`<p class="note">${I18n.html('installation.formulaire_situation.tout_assistant_regle_ecrit')}</p>`,
      lire(section) {
        const coche = UI.$('input[name="situation"]:checked', section);
        if (!coche) return null;
        if (coche.value === 'seul') {
          const autre = (nom) => UI.$('input[name="autre_' + nom + '"]', section).checked;
          return { situation: 'seul', autres: { telephone: autre('telephone'), operateurs: autre('operateurs'), direction: autre('direction') } };
        }
        const formeCochee = UI.$('input[name="forme_equipe"]:checked', section);
        return { situation: formeCochee && formeCochee.value === 'informaticien' ? 'informaticien' : coche.value };
      },
      message: I18n.t('installation.formulaire_situation.choisissez_qui_maintenance'),
    };
  }

  // Lot 2 ergonomie (T536, L11) : « Y a-t-il du Wi-Fi dans l'atelier ? », près du choix de la portée (facultatif). « Non »
  // montre les deux solutions (CSS :has, installation.css) : un poste de déclaration relié par câble, ou une borne Wi-Fi
  // réservée à Prévo. La réponse (wifi_atelier : oui, non) est écrite à « terminer » dans parametres.csv
  // (atelier_sans_wifi), que l'écran Étiquettes lit ; elle se change ensuite dans Paramètres.
  function questionWifi(reponse) {
    const t = (cle) => I18n.t('installation.formulaire_portee.' + cle);
    return UI.html`<fieldset class="installation-wifi" id="inst-wifi">
        <legend>${t('wifi_question')}</legend>
        <p class="aide">${t('wifi_aide')}</p>
        <div class="installation-choix-liste">
          ${choixRadio('wifi_atelier', 'oui', reponse === 'oui', t('wifi_oui'), '')}
          ${choixRadio('wifi_atelier', 'non', reponse === 'non', t('wifi_non'), '')}
        </div>
        <div class="encadre attention installation-sans-wifi" id="inst-sans-wifi" role="note">
          <p><b>${t('sans_wifi_titre')}</b></p>
          <p>${t('sans_wifi_solutions')}</p>
          <ul><li>${I18n.html('installation.formulaire_portee.sans_wifi_poste')}</li>
            <li>${I18n.html('installation.formulaire_portee.sans_wifi_borne')}</li></ul>
          <p>${t('sans_wifi_portee')}</p>
        </div>
      </fieldset>`;
  }

  function formulairePortee(c) {
    const b = c.brouillon();
    const details = { 'ce-pc': I18n.t('installation.formulaire_portee.ni_compte_ni_https'),
      atelier: I18n.t('installation.formulaire_portee.postes_telephones_entreprise_compte'),
      dehors: I18n.t('installation.formulaire_portee.telephone_deplacement_maison_reseau') };
    return {
      champs: UI.html`${questionWifi(b.wifi_atelier)}<p class="aide">${c.aideOption('portee')}</p>
        <div class="installation-choix-liste">${Object.keys(LIBELLES_PORTEE).map((cle) =>
          choixRadio('portee', cle, cle === b.portee, LIBELLES_PORTEE[cle], details[cle]))}</div>`,
      autrement: UI.html`<div class="form-colonne">
        ${champReglage(c, 'port_http', I18n.t('installation.formulaire_portee.port_http_application_pc'), 'number', b.port_http, UI.brut('min="1" max="65535"'))}
        ${champReglage(c, 'port_https', I18n.t('installation.formulaire_portee.port_https_application_reseau'), 'number', b.port_https, UI.brut('min="1" max="65535"'))}
        ${champReglage(c, 'noms', I18n.t('installation.formulaire_portee.noms_acceptes_separes_virgules'), 'text', (b.noms || []).join(', '), UI.brut('autocomplete="off" spellcheck="false"'))}
      </div>`,
      lire(section) {
        const coche = UI.$('input[name="portee"]:checked', section);
        if (!coche) return null;
        const wifi = UI.$('input[name="wifi_atelier"]:checked', section);
        return { portee: coche.value, port_http: Number(UI.$('#inst-port_http', section).value),
          port_https: Number(UI.$('#inst-port_https', section).value), noms: nomsSaisis(section),
          wifi_atelier: wifi ? wifi.value : '' };
      },
      message: I18n.t('installation.formulaire_portee.choisissez_ou_prevo_doit'),
    };
  }

  // Noms acceptés saisis dans une section (virgules, points-virgules ou espaces) ; le serveur les met en minuscules.
  function nomsSaisis(section) {
    const champ = UI.$('#inst-noms', section);
    return champ ? champ.value.split(/[\s,;]+/).map((n) => n.trim()).filter(Boolean) : [];
  }

  function indicationForce(valeur) {
    const longueur = valeur.length;
    if (!longueur) return '';
    if (longueur < LONGUEUR_MIN_MOT_DE_PASSE) return I18n.t('installation.indication_force.trop_court', { n: longueur, minimum: LONGUEUR_MIN_MOT_DE_PASSE });
    if (longueur < LONGUEUR_SOLIDE) return I18n.t('installation.indication_force.correct', { n: longueur });
    return I18n.t('installation.indication_force.solide', { n: longueur });
  }

  // T520 (A7) : accès facultatif de la direction (lecture seule : tableau de bord, bilan, historique), créé avec le
  // compte du responsable ; son mot de passe provisoire est montré une fois par l'écran (installation-ecrans.js).
  function blocDirection(c) {
    return UI.html`<fieldset class="installation-direction">
      <legend>${I18n.t('installation.direction.titre')}</legend>
      <p class="note">${I18n.t(c.situation() === 'seul' ? 'installation.direction.explication_solo' : 'installation.direction.explication')}</p>
      <div class="form-colonne">
        <div class="champ"><label class="libelle" for="inst-direction-prenom">${I18n.t('commun.champ.prenom')}</label>
          <input type="text" id="inst-direction-prenom" name="direction_prenom" autocomplete="off" maxlength="80"></div>
        <div class="champ"><label class="libelle" for="inst-direction-nom">${I18n.t('installation.formulaire_compte.nom')}</label>
          <input type="text" id="inst-direction-nom" name="direction_nom" autocomplete="off" maxlength="80"></div>
      </div>
    </fieldset>`;
  }

  /** { prenom, nom } de l'accès de la direction, null s'il est laissé vide, { probleme } sans prénom. */
  function lireDirection(section) {
    const prenom = UI.$('#inst-direction-prenom', section);
    if (!prenom) return null;
    const valeurs = { prenom: prenom.value.trim(), nom: UI.$('#inst-direction-nom', section).value.trim() };
    if (!valeurs.prenom && !valeurs.nom) return null;
    if (!valeurs.prenom) return { probleme: I18n.t('installation.direction.prenom_obligatoire') };
    return valeurs;
  }

  // T521 : en Solo, l'accès de la direction n'est proposé que si « La direction lit le tableau de bord et le bilan » a
  // été coché à l'étape 1 ; en équipe, toujours (facultatif, T520).
  function directionProposee(c) {
    return c.situation() !== 'seul' || Boolean((c.brouillon().solo_autres || {}).direction);
  }

  function formulaireCompte(c) {
    const b = c.brouillon();
    const sansMotDePasse = b.portee === 'ce-pc';            // Solo sur ce PC : le technicien « moi », sans compte
    const existant = Boolean(c.etat.responsable_existe) || c.etatEtape('compte') === 'fait';
    return {
      champs: UI.html`
        ${existant ? UI.html`<div class="alerte"><div class="alerte-texte">${I18n.html('installation.formulaire_compte.compte_responsable_existe_deja')}</div></div>` : ''}
        ${sansMotDePasse ? UI.html`<p class="note">${I18n.t('installation.formulaire_compte.pc_seulement_nom_cree')}</p>` : ''}
        ${sansMotDePasse || existant ? '' : UI.html`<p class="note">${I18n.t('installation.formulaire_compte.responsable_aussi_technicien')}</p>`}
        <div class="form-colonne">
          <div class="champ"><label class="libelle" for="inst-prenom">${I18n.t('commun.champ.prenom')} <span class="requis" aria-hidden="true">*</span></label>
            <input type="text" id="inst-prenom" name="prenom" autocomplete="given-name" maxlength="80"></div>
          <div class="champ"><label class="libelle" for="inst-nom">${I18n.t('installation.formulaire_compte.nom')}</label>
            <input type="text" id="inst-nom" name="nom" autocomplete="family-name" maxlength="80"></div>
          ${sansMotDePasse || existant ? '' : UI.html`<div class="alerte info installation-identifiant" id="inst-identifiant" role="status" aria-live="polite" hidden></div>`}
          ${sansMotDePasse ? '' : UI.html`
          <p class="note">${I18n.t('installation.formulaire_compte.12_caracteres_moins_256')}</p>
          <div class="champ"><label class="libelle" for="inst-mot-de-passe">${I18n.t('installation.formulaire_compte.mot_passe')}</label>
            <input type="password" id="inst-mot-de-passe" name="mot_de_passe" autocomplete="new-password" minlength="12" maxlength="256" aria-describedby="inst-force">
            <p class="aide" id="inst-force" aria-live="polite"></p></div>
          <div class="champ"><label class="libelle" for="inst-confirmation">${I18n.t('installation.formulaire_compte.confirmation')}</label>
            <input type="password" id="inst-confirmation" name="confirmation" autocomplete="new-password" maxlength="256"></div>`}
        </div>
        ${sansMotDePasse || existant || !directionProposee(c) ? '' : blocDirection(c)}`,
      autrement: UI.html`<p class="note">${notePlusTard()}</p>${['session_heures', 'session_longue_jours', 'invitation_heures', 'demandeurs_avec_compte'].map((cle) => reglageLu(c, cle))}`,
      passer: existant,
      lire(section) {
        const prenom = UI.$('#inst-prenom', section).value.trim();
        if (!prenom) return { probleme: I18n.t('installation.formulaire_compte.prenom_obligatoire') };
        const corps = { prenom: prenom, nom: UI.$('#inst-nom', section).value.trim() };
        if (sansMotDePasse) return corps;
        const motDePasse = UI.$('#inst-mot-de-passe', section).value;
        if (motDePasse.length < LONGUEUR_MIN_MOT_DE_PASSE) {
          return { probleme: I18n.t('installation.mot_de_passe.trop_court', { n: LONGUEUR_MIN_MOT_DE_PASSE, longueur: motDePasse.length }) };
        }
        if (motDePasse.length > LONGUEUR_MAX_MOT_DE_PASSE) return { probleme: I18n.t('installation.mot_de_passe.trop_long', { n: LONGUEUR_MAX_MOT_DE_PASSE }) };
        if (motDePasse !== UI.$('#inst-confirmation', section).value) return { probleme: I18n.t('installation.formulaire_compte.confirmation_correspond_pas_mot') };
        const direction = lireDirection(section);
        if (direction && direction.probleme) return direction;
        return Object.assign(corps, { mot_de_passe: motDePasse }, direction ? { direction } : {});
      },
      // Les mots de passe ne restent jamais dans la page : vidés à chaque réponse.
      apres(section) {
        UI.$$('input[type="password"]', section).forEach((champ) => { champ.value = ''; });
        const force = UI.$('#inst-force', section);
        if (force) force.textContent = '';
      },
    };
  }

  function formulaireCertificat(c) {
    const b = c.brouillon();
    const informaticien = c.situation() === 'informaticien';
    const dehors = b.portee === 'dehors';
    const tailscale = c.etat.tailscale || {};
    let choisi = b.certificat_auto ? 'automatique' : b.certificat ? 'fichiers' : b.mandataire ? (dehors ? 'reseau_prive' : 'mandataire') : '';
    if (!choisi) choisi = informaticien ? 'mandataire' : (c.situation() === 'seul' && dehors && tailscale.present ? 'reseau_prive' : 'automatique');
    const principal = [
      choixRadio('mode', 'automatique', choisi === 'automatique', I18n.t('installation.formulaire_certificat.automatique_recommande'),
        c.etat.mkcert_present ? I18n.t('installation.formulaire_certificat.prevo_fabrique_certificat_atelier')
          : I18n.t('installation.formulaire_certificat.mkcert_introuvable_outils_tiers')),
      dehors ? choixRadio('mode', 'reseau_prive', choisi === 'reseau_prive', I18n.t('installation.formulaire_certificat.reseau_prive_tailscale'),
        tailscale.present ? I18n.t('installation.formulaire_certificat.certificat_reconnu_partout_rien')
          : I18n.t('installation.formulaire_certificat.tailscale_pas_detecte_pc')) : '',
    ];
    const avances = [
      choixRadio('mode', 'fichiers', choisi === 'fichiers', I18n.t('installation.formulaire_certificat.ai_mon_certificat_deux'), I18n.t('installation.formulaire_certificat.fourni_pki_entreprise')),
      choixRadio('mode', 'mandataire', choisi === 'mandataire', I18n.t('installation.formulaire_certificat.derriere_mon_mandataire_inverse'), I18n.t('installation.formulaire_certificat.iis_nginx_caddy_tailscale')),
    ];
    const fichiers = UI.html`<div class="form-colonne">
      ${champReglage(c, 'certificat', I18n.t('installation.formulaire_certificat.certificat_fichier_pem'), 'text', b.certificat, UI.brut('autocomplete="off" spellcheck="false"'))}
      ${champReglage(c, 'cle', I18n.t('installation.formulaire_certificat.cle_privee_fichier_pem'), 'text', b.cle, UI.brut('autocomplete="off" spellcheck="false"'))}
      ${champReglage(c, 'noms', I18n.t('installation.formulaire_certificat.noms_acceptes_mandataire_nom'), 'text', (b.noms || []).join(', '), UI.brut('autocomplete="off" spellcheck="false"'))}
    </div>`;
    return {
      champs: UI.html`<div class="installation-choix-liste">${principal}${informaticien ? avances : ''}</div>${informaticien ? fichiers : ''}`,
      autrement: informaticien ? UI.html`<p class="note">${c.aideOption('certificat_auto')} ${c.aideOption('mandataire')}</p>`
        : UI.html`<div class="installation-choix-liste">${avances}</div>${fichiers}`,
      lire(section) {
        const coche = UI.$('input[name="mode"]:checked', section);
        if (!coche) return null;
        const corps = { mode: coche.value };
        const noms = nomsSaisis(section);
        if (corps.mode === 'fichiers') Object.assign(corps, { certificat: UI.$('#inst-certificat', section).value.trim(), cle: UI.$('#inst-cle', section).value.trim() });
        if (corps.mode === 'mandataire' && noms.length) corps.noms = noms;
        return corps;
      },
      message: I18n.t('installation.formulaire_certificat.choisissez_comment_prevo_obtient'),
      attente(corps) {   // T527 : la fabrication du certificat prend quelques secondes, dites à côté du bouton.
        return corps.mode === 'automatique' ? I18n.t('installation.formulaire_certificat.fabrication_en_cours') : '';
      },
      reussite(donnees) {
        const noms = (donnees.noms_certificat || []).join(', ');
        // L07 (lot 2) : « étiquettes à réimprimer » seulement si le parc a déjà des machines (GET etat : parc_present).
        if (donnees.mode === 'automatique') {
          return I18n.t(c.etat.parc_present ? 'installation.formulaire_certificat.certificat_pret_etiquettes_qr'
            : 'installation.formulaire_certificat.certificat_pret', { noms });
        }
        return '';
      },
    };
  }

  function formulaireTailscale(c) {
    const t = c.etat.tailscale || {};
    const b = c.brouillon();
    const nomPc = t.nom || I18n.t('installation.formulaire_tailscale.nom_inconnu');
    let ligne = I18n.t('installation.formulaire_tailscale.tailscale_installe_mais_pas');
    if (!t.present) ligne = t.raison ? I18n.t('installation.formulaire_tailscale.tailscale_pas_detecte_pc_raison', { raison: StockageServeur.texte(t, 'raison') }) : I18n.t('installation.formulaire_tailscale.tailscale_pas_detecte_pc');
    else if (t.connecte) ligne = I18n.t('installation.formulaire_tailscale.tailscale_installe_connecte_pc', { nomPc });
    const port = b.port_http || 8080;
    return {
      champs: UI.html`
        <p class="installation-tailscale-etat" id="inst-tailscale-etat">${ligne}</p>
        <p class="note">${I18n.t('installation.formulaire_tailscale.tailscale_demande_compte_google')}</p>
        ${t.present ? '' : UI.html`<p><a class="btn btn-secondaire" id="inst-tailscale-telecharger" href="${LIEN_TAILSCALE}" target="_blank" rel="noopener">${I18n.t('installation.formulaire_tailscale.telecharger_tailscale_site_officiel')}</a></p>`}
        <div class="actions installation-actions-etape">
          <button type="button" class="btn btn-primaire" id="inst-tailscale-appliquer">${I18n.t('installation.formulaire_tailscale.ai_installe_tailscale_je')}</button>
          <button type="button" class="btn btn-fantome" id="inst-tailscale-plus-tard">${I18n.t('installation.formulaire_tailscale.plus_tard')}</button>
        </div>
        <div id="inst-tailscale-resultat" class="installation-resultat" hidden></div>`,
      autrement: UI.html`<p class="note">${I18n.html('installation.formulaire_tailscale.prevo_lancera_fois_tailscale', { port })}</p>${reglageLu(c, 'noms')}`,
      propresBoutons: true,                                   // « J'ai installé… » et « Plus tard » font les appels
      passer: c.etatEtape('tailscale') === 'fait',              // déjà appliqué : « Continuer » avance sans appel
    };
  }

  function formulaireDemarrage(c) {
    const b = c.brouillon();
    const windows = c.etat.systeme === 'windows';
    const details = { systeme: windows ? I18n.t('installation.formulaire_demarrage.tache_planifiee_pare_feu') : I18n.t('installation.formulaire_demarrage.tache_planifiee'),
      session: I18n.t('installation.formulaire_demarrage.demarre_quand_ouvrez_session'), aucun: I18n.t('installation.formulaire_demarrage.lancez_prevo_raccourci_fenetre') };
    return {
      champs: UI.html`<div class="installation-choix-liste">${Object.keys(LIBELLES_DEMARRAGE).map((cle) =>
          choixRadio('demarrage', cle, cle === (b.demarrage || 'aucun'), LIBELLES_DEMARRAGE[cle], details[cle]))}</div>
        <label class="case installation-case"><input type="checkbox" id="inst-veille" ${UI.brut(b.veille_desactivee ? 'checked' : '')}>
          <span>${I18n.t('installation.formulaire_demarrage.empecher_veille_pc_quand')}</span></label>
        <p class="aide">${c.aideOption('veille_desactivee')}</p>
        ${windows ? UI.html`<p class="note" id="inst-demarrage-uac">${I18n.html('installation.formulaire_demarrage.seule_invite_administrateur_windows')}</p>` : ''}
        <div id="inst-demarrage-resultat" class="installation-resultat" hidden></div>`,
      autrement: UI.html`<p class="note">${I18n.t('installation.formulaire_demarrage.scripts_sont_ecrits_dossier', { aideOption: c.aideOption('demarrage') })}</p>`,
      lire(section) {
        const coche = UI.$('input[name="demarrage"]:checked', section);
        return coche ? { demarrage: coche.value, veille_desactivee: UI.$('#inst-veille', section).checked } : null;
      },
      message: I18n.t('installation.formulaire_demarrage.choisissez_comment_prevo_demarre'),
      reussite(donnees) {
        const commandes = (donnees.commandes || []).join(' ; ');
        if (donnees.commandes && donnees.commandes.length) return I18n.t('installation.formulaire_demarrage.lancer_main_serveur', { commandes });
        if (donnees.lance && !donnees.lance.ok) return null;
        return '';
      },
      echec(donnees) {
        if (!donnees.lance || donnees.lance.ok) return '';
        const raison = StockageServeur.texte(donnees.lance, 'message') || I18n.t('installation.formulaire_demarrage.code', { code: donnees.lance.code });
        return I18n.t('installation.formulaire_demarrage.invite_administrateur_ete_refusee', { raison });
        return '';
      },
    };
  }

  function formulaireSauvegardes(c) {
    const b = c.brouillon();
    return {
      champs: UI.html`<p class="note">${I18n.t('installation.formulaire_sauvegardes.sauvegarde_jour_deja_faite')}</p>
        <div class="form-colonne">${champReglage(c, 'copie_sauvegardes', I18n.t('installation.formulaire_sauvegardes.dossier_copie_cle_usb'), 'text', b.copie_sauvegardes, UI.brut('autocomplete="off" spellcheck="false"'),
          I18n.t('installation.formulaire_sauvegardes.exemple_dossier'))}</div>
        <div class="actions installation-actions-etape"><button type="button" class="btn btn-fantome" id="inst-sauvegardes-plus-tard">${I18n.t('installation.formulaire_tailscale.plus_tard')}</button></div>`,
      autrement: UI.html`<p class="note">${notePlusTard()}</p>${reglageLu(c, 'quota_documents_mo')}`,
      lire(section) {
        const dossier = UI.$('#inst-copie_sauvegardes', section).value.trim();
        return dossier ? { dossier: dossier } : { probleme: I18n.t('installation.formulaire_sauvegardes.indiquez_dossier_choisissez_plus') };
      },
    };
  }

  function formulaireRecapitulatif(c) {
    const b = c.brouillon();
    const lignes = [
      [I18n.t('installation.formulaire_recapitulatif.utilise'), AccesTextes.situations[c.situation()] || c.situation()],
      [I18n.t('installation.formulaire_recapitulatif.depuis_ou'), LIBELLES_PORTEE[b.portee] || b.portee],
      [I18n.t('installation.formulaire_recapitulatif.comptes'), b.comptes ? I18n.t('installation.formulaire_recapitulatif.connexion_obligatoire_compte_responsable') : I18n.t('installation.formulaire_recapitulatif.aucun_prevo_joignable_pc')],
      // L03 (lot 2) : l'identifiant du responsable, rappelé (celui qui servira à la connexion après « Terminer »).
      ...(b.comptes && c.etat.responsable_identifiant ? [[I18n.t('installation.formulaire_recapitulatif.identifiant'), UI.html`<b id="inst-recap-identifiant">${c.etat.responsable_identifiant}</b>`]] : []),
      [I18n.t('installation.formulaire_recapitulatif.certificat'), b.portee === 'ce-pc' ? I18n.t('installation.formulaire_recapitulatif.sans_objet_http_pc') : b.certificat_auto ? I18n.t('installation.formulaire_recapitulatif.automatique_mkcert') : b.certificat ? I18n.t('installation.formulaire_recapitulatif.fichiers_pem') : b.mandataire ? I18n.t('installation.formulaire_recapitulatif.derriere_mandataire_tailscale_celui') : I18n.t('installation.formulaire_recapitulatif.regler')],
      [I18n.t('installation.formulaire_recapitulatif.demarrage'), LIBELLES_DEMARRAGE[b.demarrage] || b.demarrage],
      [I18n.t('installation.formulaire_recapitulatif.veille'), b.veille_desactivee ? I18n.t('installation.formulaire_recapitulatif.empechee_secteur') : I18n.t('installation.formulaire_recapitulatif.inchangee')],
      [I18n.t('installation.formulaire_recapitulatif.copie_sauvegardes'), b.copie_sauvegardes || I18n.t('installation.formulaire_tailscale.plus_tard')],
    ];
    const deplacer = c.etatEtape('deplacer') === 'a_faire' && !b.deplacement_refuse;
    // Sans CSV au départ de l'assistant (T171) : par quoi commencer ; avec (migration 1.2) : rien à demander, tout est gardé.
    const choixBase = b.base_presente === false;
    const dictee = dicteeDeDepart(Boolean(b.mode_solo) || c.situation() === 'seul');
    return {
      champs: UI.html`
        <dl class="installation-recap">${lignes.map(([titre, valeur]) => UI.html`<div><dt>${titre}</dt><dd>${valeur}</dd></div>`)}</dl>
        ${choixBase ? UI.html`<div class="carte installation-dossier" id="inst-base">
          <h3>${I18n.t('installation.formulaire_recapitulatif.quoi_commencer')}</h3>
          <div class="installation-choix-liste">
            ${choixRadio('base', 'vide', true, I18n.t('installation.formulaire_recapitulatif.commencer_vide'), I18n.t('installation.formulaire_recapitulatif.equipements_demandes_ot_rien'))}
            ${choixRadio('base', 'demo', false, I18n.t('installation.formulaire_recapitulatif.commencer_donnees_demonstration'), I18n.t('installation.formulaire_recapitulatif.atelier_fictif_equipements_ot'))}
          </div>
          <div class="champ installation-langue">
            <label class="libelle" for="inst-langue_defaut">${I18n.t('installation.formulaire_recapitulatif.langue_prevo')}</label>
            <select id="inst-langue_defaut" name="langue_defaut">${UI.optionsLangues(langueDeDepart())}</select>
            <p class="aide">${I18n.t('installation.formulaire_recapitulatif.langue_prevo_aide')}</p>
          </div>
          <div class="champ installation-dictee" id="inst-dictee">
            <h3>${I18n.t('installation.formulaire_recapitulatif.dictee_titre')}</h3>
            <p>${I18n.t('installation.formulaire_recapitulatif.dictee_voix')}</p>
            <div class="installation-choix-liste">
              ${choixRadio('dictee', '1', dictee === '1', I18n.t('installation.formulaire_recapitulatif.dictee_oui'), I18n.t('installation.formulaire_recapitulatif.dictee_oui_detail'))}
              ${choixRadio('dictee', '0', dictee === '0', I18n.t('installation.formulaire_recapitulatif.dictee_non'), I18n.t('installation.formulaire_recapitulatif.dictee_non_detail'))}
            </div>
            <p class="aide">${I18n.t('installation.formulaire_recapitulatif.dictee_aide')}</p>
          </div>
        </div>` : ''}
        ${deplacer ? UI.html`<div class="carte installation-dossier" id="inst-dossier">
          <h3>${I18n.t('installation.formulaire_recapitulatif.dossier_prevo')}</h3>
          <p>${I18n.html('installation.formulaire_recapitulatif.prevo_tourne_dossier_conseille', { dossier: c.etat.dossier, dossier_conseille: c.etat.dossier_conseille })}</p>
          <p>${I18n.t('installation.formulaire_recapitulatif.deplacer_prevo_copie_chaque', { dossier_conseille: c.etat.dossier_conseille })}</p>
          <div class="actions">
            <button type="button" class="btn btn-secondaire" id="inst-deplacer">${I18n.t('installation.formulaire_recapitulatif.deplacer_prevo_recommande', { dossier_conseille: c.etat.dossier_conseille })}</button>
            <button type="button" class="btn btn-fantome" id="inst-dossier-garder">${I18n.t('installation.formulaire_recapitulatif.rester_ici')}</button>
          </div>
          <p class="erreur-champ" id="inst-deplacer-erreur" role="alert" hidden></p>
        </div>` : ''}
        <div id="inst-fiche"><p class="chargement" role="status">${I18n.t('installation.formulaire_recapitulatif.lecture_fiche_acces')}</p></div>`,
      autrement: UI.html`${c.blocTextes('ia')}<p class="note">${notePlusTard()}</p>${['ia_fournisseur', 'ia_url', 'ia_en_ligne'].map((cle) => reglageLu(c, cle))}`,
      // Corps de « terminer » : la base de départ et sa langue (langue_defaut, T296) quand elles ont été demandées,
      // rien sinon (base présente : sa langue ne change pas).
      lire(section) {
        const coche = UI.$('input[name="base"]:checked', section);
        const langue = UI.$('#inst-langue_defaut', section);
        if (!coche) return {};
        const dictee = UI.$('input[name="dictee"]:checked', section);      // L24 : sans réponse, rien n'est envoyé (non autorisée)
        const corps = langue ? { base: coche.value, langue_defaut: langue.value } : { base: coche.value };
        if (dictee) corps.dictee_autorisee = dictee.value;
        return corps;
      },
    };
  }

  const FORMULAIRES = { situation: formulaireSituation, portee: formulairePortee, compte: formulaireCompte, certificat: formulaireCertificat,
    tailscale: formulaireTailscale, demarrage: formulaireDemarrage, sauvegardes: formulaireSauvegardes, recapitulatif: formulaireRecapitulatif };

  /** Formulaire d'une étape : { champs, autrement, lire(section), message, passer, propresBoutons, reussite, echec, apres }. */
  function formulaire(cle, contexte) {
    return FORMULAIRES[cle](contexte);
  }

  return { formulaire, indicationForce, noterDicteeDeDepart, dicteeDeDepart, noterLangueDeDepart, langueDeDepart, LIBELLES_PORTEE, LIBELLES_DEMARRAGE };
})();
