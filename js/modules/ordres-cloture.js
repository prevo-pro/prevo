'use strict';
// Ordres — clôture d'un OT (T539, T553, lot 2 ergonomie) : la fenêtre de clôture unique (L20 : « Clôturer » du
// technicien et du responsable, « Clore » du responsable et du mode Solo, ARCHITECTURE.md §22.11, D132), ce que Prévo
// dit après une clôture (L22 : le technicien lit « Votre part est terminée. Le responsable validera. » ; en Solo, une
// seule clôture) et la clôture d'une visite préventive (L23).
// La fenêtre montre d'avance tout ce que la règle RG4 exige (étoile), la liste de ce qui manque en haut (tenue à jour
// pendant la saisie, Ordres.manquesCloture : la même règle que Ordres.verifierCloture) et son bouton dit ce qui
// manque au lieu de refuser après coup. Date de fin à « maintenant », temps passé proposé, « Autre » en tête des
// codes, compte rendu repris, case « remis en service en sécurité » ; pour une panne, « La machine était-elle
// arrêtée ? » (colonnes arret_production et duree_arret_h). Visite : compte rendu écrit d'office si tout est coché
// sans anomalie, temps proposé d'après la gamme, OT de réparation proposé sur anomalie, prochaine visite dite.
// Chargé juste après ordres-fiche.js ; les outils de la fiche (Ordres.interne) sont cherchés au moment de l'appel.
// Complète l'objet Ordres.

Object.assign(Ordres, (() => {

  const { transitionsPossibles } = Ordres;
  const { texte, nombre, estResponsable, estTechnicien, monTechnicienId, equipementDe, listeTechniciens, champOt,
    lignesDeLOt } = Ordres.interne;

  const enSolo = () => typeof App !== 'undefined' && typeof App.modeSolo === 'function' && App.modeSolo();

  // Champs de l'OT lus dans la fenêtre pour calculer ce qui manque (les mêmes que Ordres.clore écrit).
  const CHAMPS_FENETRE = ['date_fin', 'arret_production', 'duree_arret_h', 'symptome_code', 'cause_code', 'remede_code',
    'cause_precision', 'remede_precision', 'compte_rendu', 'astuce', 'remise_service'];
  const ECART_MAX_H = 12;               // au-delà, l'écart début → maintenant n'est pas un temps passé : rien n'est proposé

  // ===========================================================================================
  // 1. La fenêtre de clôture unique (L20) : « Clôturer » (clôture technique) et « Clore » (D132)
  // ===========================================================================================

  /** Bouton « Clore » : réglage actif, profil responsable, OT qui peut recevoir la clôture technique. */
  function boutonClore(ot) {
    return Ordres.clotureUneEtape() && transitionsPossibles(ot).includes('Clôturé techniquement')
      ? UI.html`<button type="button" class="btn btn-primaire" id="ot-clore">${UI.icone('valider')}${I18n.t('ordres.bouton_clore.clore')}</button>` : '';
  }

  /** Étoile sur un champ exigé (sans `required` : ce qui manque est dit par RG4, jamais par « Champ obligatoire »). */
  function marquerExige(bloc) {
    const etiquette = bloc.querySelector('label.case > span, label.libelle, legend');
    if (etiquette) etiquette.append(' ', UI.element(UI.html`<span class="requis" aria-hidden="true">*</span>`));
    const controle = bloc.querySelector('select, input, textarea');
    if (controle) controle.setAttribute('aria-required', 'true');
    return bloc;
  }

  /**
   * Temps passé proposé : { valeur (heures décimales, '' si rien), aide }. Un temps déjà saisi suffit (rien à
   * ajouter) ; sinon, pour une visite, le temps prévu de la gamme (L23) ; sinon l'écart début → maintenant arrondi
   * au quart d'heure (12 h au plus).
   */
  function tempsAProposer(ot, total) {
    if (total > 0) return { valeur: '', aide: I18n.t('ordres.champs_clore.deja_saisi', { total: UI.heures(total) }) };
    const visite = tempsPropose(ot);
    if (visite) return { valeur: visite, aide: I18n.t('ordres.cloture.temps_propose') };
    const debut = texte(ot.date_debut) ? new Date(texte(ot.date_debut).replace(' ', 'T')) : null;
    const ecart = debut && !Number.isNaN(debut.getTime()) ? (Date.now() - debut.getTime()) / 3600000 : 0;
    if (ecart > 0 && ecart <= ECART_MAX_H) {
      return { valeur: UI.dureeEnTexte(Math.max(0.25, Math.round(ecart * 4) / 4)), aide: I18n.t('ordres.cloture.temps_ecart') };
    }
    return { valeur: '', aide: I18n.t('ordres.champs_clore.moins_temps_passe_exige') };
  }

  /** Pour une panne (OT correctif) : « La machine était-elle arrêtée ? » Oui / Non, et la durée de l'arrêt si oui. */
  function questionArret(ot) {
    if (!Ordres.estCorrectif(ot)) return [];
    const coche = (valeur) => (ot.arret_production === valeur ? UI.brut(' checked') : '');
    const question = UI.element(UI.html`<fieldset class="ot-cloture-arret"><legend class="libelle">${I18n.t('ordres.cloture.machine_arretee')}</legend>
      <div class="ot-cloture-choix"><label class="case"><input type="radio" name="arret_production" value="1"${coche('1')}><span>${I18n.t('ordres.lecture.oui')}</span></label>
      <label class="case"><input type="radio" name="arret_production" value="0"${texte(ot.duree_arret_h) ? coche('0') : ''}><span>${I18n.t('ordres.lecture.non')}</span></label></div></fieldset>`);
    const duree = champOt('duree_arret_h', ot.duree_arret_h, { libelle: I18n.t('ordres.cloture.duree_arret') });
    const montrer = () => { duree.hidden = !UI.$('input[value="1"]', question).checked; };
    question.addEventListener('change', montrer);
    montrer();
    return [question, duree];
  }

  /** Technicien du temps passé : le sien pour un technicien (ou en Solo), sinon une liste (celui de l'OT d'avance). */
  function champTechnicien(ot) {
    const sien = (estTechnicien() && monTechnicienId()) || App.technicienSolo() || '';
    if (sien) return UI.element(UI.html`<input type="hidden" name="technicien_id" value="${sien}">`);
    const technicien = texte(ot.technicien_id);
    return champOt('technicien_id', technicien, { liste: listeTechniciens(technicien), libelle: I18n.t('ordres.champs_clore.technicien_temps_passe') });
  }

  /** Saisies facultatives, repliées pour garder la fenêtre courte : pièce sortie du magasin (Magasin.sortir), astuce. */
  function saisiesFacultatives(ot) {
    const { libelleArticle, aideAstuce } = Ordres.interne;
    const articles = Donnees.lignes('articles').filter((a) => texte(a.actif) !== '0')
      .map((a) => ({ valeur: a.id, libelle: I18n.t('ordres.options_articles.libelle_article_stock_stock_article', { libelleArticle: libelleArticle(a), stockArticle: UI.nombreFr(Donnees.stockArticle(a.id)) }) }));
    const bloc = UI.element(UI.html`<details class="ot-cloture-facultatif"${texte(ot.astuce) ? UI.brut(' open') : ''}>
      <summary>${I18n.t('ordres.cloture.facultatif')}</summary><div class="form-colonne"></div></details>`);
    UI.$('.form-colonne', bloc).append(
      UI.champ({ nom: 'article_id', type: 'ref', libelle: I18n.t('ordres.champs_clore.piece_sortie_magasin_facultatif') }, '', { liste: articles }),
      UI.champ({ nom: 'quantite', type: 'decimal', libelle: I18n.t('ordres.champs_clore.quantite_sortie') }, '1'),
      champOt('astuce', ot.astuce, { aide: aideAstuce() }));
    return bloc;
  }

  /**
   * Réservé à T554 (« Autoriser les clôtures incomplètes », « Dépannage provisoire ») : blocs ajoutés à la fenêtre,
   * juste après la case de sécurité ; leurs champs nommés sont lus avec les autres (UI.lireFormulaire).
   */
  function extensionsCloture(/* ot, mode */) {
    return [];
  }

  /** Réservé à T554 : vrai si la clôture peut se faire malgré des manques (réglage du responsable). */
  function clotureIncomplete(/* ot, manques */) {
    return false;
  }

  /** Champs de la fenêtre, dans l'ordre du travail ; les champs exigés par RG4 portent une étoile. */
  function champsCloture(ot, mode) {
    const total = lignesDeLOt('ot_temps', ot.id).reduce((somme, ligne) => somme + nombre(ligne.heures), 0);
    const temps = tempsAProposer(ot, total);
    const exiges = Ordres.codesExiges(ot);
    const fin = marquerExige(champOt('date_fin', texte(ot.date_fin) || Donnees.maintenant().slice(0, 16)));
    UI.$('input', fin).max = Donnees.maintenant().replace(' ', 'T');     // pas de date de fin dans le futur
    const heures = UI.champ({ nom: 'heures', type: 'duree', libelle: total > 0 ? I18n.t('ordres.champs_clore.temps_passe_ajouter_heures')
      : I18n.t('ordres.cloture.temps_passe') }, temps.valeur, { aide: temps.aide });
    const codes = Ordres.champsCodes(ot);       // T515 : symptôme, cause (sauf préventif), remède ; « Autre » en tête
    codes.forEach((bloc) => {
      const cle = bloc.dataset.code;
      if (cle && exiges[cle]) marquerExige(UI.$('.champ', bloc));
    });
    const remise = marquerExige(champOt('remise_service', ot.remise_service, {
      libelle: I18n.t('ordres.champs_clore.equipement_remis_service_securite'),
    }));
    if (texte((equipementDe(ot) || {}).habilitation_requise)) remise.appendChild(UI.element(UI.html`<p class="aide">${Ordres.rappelConsignation()}</p>`));
    return [
      UI.element(UI.html`<div class="ot-cloture-manques" aria-live="polite"></div>`),
      ...resumeVisite(ot),                                        // L23 : contrôles faits, anomalie
      fin,
      total > 0 ? heures : marquerExige(heures),
      champTechnicien(ot),
      ...Ordres.interne.rappelTempsRenforts(ot),                  // L16 : temps des renforts, sans bloquer
      ...questionArret(ot),                                       // P04 : le bilan compte les arrêts
      ...codes,
      marquerExige(champOt('compte_rendu', texte(ot.compte_rendu) || compteRenduDOffice(ot), {        // L23 : écrit d'office
        aide: I18n.t('ordres.champs_clore.ete_constate_cause_ete'),
      })),
      ...Demandes.champsMotOperateur(ot),                         // A4 : mot pour l'opérateur, si l'OT vient d'une demande
      remise,
      ...extensionsCloture(ot, mode),
      saisiesFacultatives(ot),
    ];
  }

  /** Saisies de la fenêtre prêtes à écrire : question de l'arrêt sans réponse → rien ; « Non » → pas de durée. */
  function saisiesFenetre(formulaire) {
    const valeurs = UI.lireFormulaire(formulaire);
    if (valeurs.arret_production === '') { delete valeurs.arret_production; delete valeurs.duree_arret_h; }
    if (valeurs.arret_production === '0') valeurs.duree_arret_h = '';
    return valeurs;
  }

  /** Ce qui manque encore (Ordres.manquesCloture) pour l'OT tel que la fenêtre l'écrirait : [{ champ, texte }]. */
  function manquesSaisis(ot, valeurs) {
    const saisies = Object.assign({}, valeurs, Ordres.codesSaisis(valeurs));
    const futur = Object.assign({}, ot);
    CHAMPS_FENETRE.forEach((nom) => { if (saisies[nom] !== undefined) futur[nom] = texte(saisies[nom]); });
    const heures = Donnees.nombre(valeurs.heures) || 0;
    const temps = lignesDeLOt('ot_temps', ot.id).concat(heures > 0 ? [{ heures: String(heures) }] : []);
    return Ordres.manquesCloture(futur, { temps }).map((manque) => (manque.champ === 'heures'
      ? { champ: 'heures', texte: I18n.t('ordres.cloture.manque_temps') } : manque));
  }

  /** Liste de ce qui manque (en haut de la fenêtre) et libellé du bouton, tenus à jour pendant la saisie. */
  function actualiser(ot, boite, bouton, libelle) {
    const manques = manquesSaisis(ot, saisiesFenetre(boite.closest('form')));
    boite.textContent = '';
    boite.appendChild(manques.length
      ? UI.bandeau('attention', UI.html`<b>${I18n.t('ordres.cloture.il_manque')}</b>
          <ul class="ot-manques">${manques.map((manque) => UI.html`<li data-champ="${manque.champ}">${manque.texte}</li>`)}</ul>`)
      : UI.bandeau('succes', I18n.t('ordres.cloture.rien_ne_manque')));
    if (bouton) {
      bouton.lastChild.textContent = manques.length && !clotureIncomplete(ot, manques)
        ? I18n.t('ordres.cloture.bouton_il_manque', { action: libelle, n: manques.length }) : libelle;
    }
    return manques;
  }

  /**
   * La fenêtre de clôture unique (L20). mode 'technique' : « Clôturer » (technicien, responsable : clôture technique,
   * Ordres.cloturerTechniquement) ; mode 'clore' : « Clore » (responsable, Solo : technique + administrative,
   * Ordres.clore). Les saisies des onglets sont enregistrées d'abord. Renvoie true si l'OT a été clôturé.
   */
  async function demanderCloture(ot, mode) {
    const { viderMessage, enregistrerFormulairesModifies, apresEnregistrement } = Ordres.interne;
    viderMessage();
    const sauvegarde = await enregistrerFormulairesModifies();
    if (!sauvegarde.ok) return false;
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const solo = enSolo();                       // L22 : en Solo, une seule clôture (ni « deux temps » ni « verrouiller »)
    const clore = mode === 'clore';
    const libelle = !clore ? I18n.t('ordres.cloture_techniquement.cloturer_techniquement')
      : solo ? I18n.t('ordres.bouton_clore.clore') : I18n.t('ordres.demander_clore.clore_verrouiller');
    const champs = champsCloture(actuel, mode);
    const boite = champs[0];
    const promesse = UI.fenetreAction({
      titre: clore ? I18n.t('ordres.demander_clore.clore_actuel_id', { actuelId: actuel.id }) : I18n.t('ordres.cloture.titre', { otId: actuel.id }),
      classe: 'ot-fenetre-clore', libelleValider: libelle,
      introduction: UI.html`<p>${!clore ? I18n.t('ordres.cloture.introduction')
        : solo ? I18n.t('ordres.cloture.solo_introduction') : I18n.t('ordres.demander_clore.cloture_technique_puis_administrative')}</p>`,
      champs,
      verifier: () => {
        const manques = actualiser(actuel, boite, null, libelle);
        return clotureIncomplete(actuel, manques) ? [] : manques.map((manque) => ({ nom: manque.champ, message: manque.texte }));
      },
      action: (valeurs, contenu) => {
        const saisies = saisiesFenetre(contenu.closest('form'));
        return clore ? Ordres.clore(actuel, saisies) : Ordres.cloturerTechniquement(actuel, saisies);
      },
    });
    const formulaire = boite.closest('form');                    // la fenêtre est ouverte (UI.fenetre, synchrone)
    const bouton = formulaire && formulaire.querySelector('.fenetre-actions .btn-primaire');
    if (formulaire) {
      const suivre = () => actualiser(actuel, boite, bouton, libelle);
      formulaire.addEventListener('input', suivre);
      formulaire.addEventListener('change', suivre);
      suivre();
    }
    const fait = await promesse;
    if (!fait) { if (sauvegarde.enregistres) await apresEnregistrement(); return false; }
    await apresEnregistrement();
    const avertissementGamme = Ordres.interne.lireAvertissementGamme(actuel.id);
    direApresTransition(actuel.id, clore ? 'Clôturé administrativement' : 'Clôturé techniquement', avertissementGamme,
      avertissementGamme ? [avertissementGamme] : [], clore);
    return true;
  }

  /** « Clore » (bouton #ot-clore, D132) : la fenêtre de clôture unique en mode 'clore'. */
  function demanderClore(ot) {
    return demanderCloture(ot, 'clore');
  }

  // ===========================================================================================
  // 2. Visite préventive (L23)
  // ===========================================================================================

  /** OT d'une visite préventive : issu d'une gamme, ou de type préventif. */
  function estVisite(ot) {
    return Boolean(ot) && (Boolean(texte(ot.gamme_id)) || /^préventif/.test(texte(ot.type)));
  }

  /** L23 : liste de contrôle toute cochée (une ligne au moins) et aucune anomalie constatée. */
  function visiteSansAnomalie(ot) {
    if (!estVisite(ot) || ot.anomalie_constatee === '1') return false;
    const operations = lignesDeLOt('ot_operations', ot.id);
    return operations.length > 0 && operations.every((operation) => operation.fait === '1');
  }

  /** L23 : compte rendu écrit d'office (langue de l'écran au moment de l'écriture) ; '' s'il est déjà écrit ou s'il faut l'écrire. */
  function compteRenduDOffice(ot) {
    return !texte(ot.compte_rendu) && visiteSansAnomalie(ot) ? I18n.t('ordres.cloture.visite_rien_a_signaler') : '';
  }

  /**
   * L23 : en tête de la fenêtre de clôture d'une visite, ce que dit la liste de contrôle : tout coché sans anomalie
   * (compte rendu rempli d'office, modifiable), anomalie constatée (compte rendu à écrire, OT de réparation proposé
   * après la clôture), ou contrôles en partie faits. Rien hors visite ou sans liste de contrôle.
   */
  function resumeVisite(ot) {
    if (!estVisite(ot)) return [];
    const operations = lignesDeLOt('ot_operations', ot.id);
    const faits = operations.filter((operation) => operation.fait === '1').length;
    const total = operations.length;
    let phrase = '';
    if (ot.anomalie_constatee === '1') phrase = I18n.t('ordres.cloture.visite_anomalie');
    else if (total && faits === total) phrase = I18n.t('ordres.cloture.visite_tout_coche', { faits, total });
    else if (total) phrase = I18n.t('ordres.cloture.visite_en_partie', { faits, total });
    if (!phrase) return [];
    const bloc = UI.element(UI.html`<p class="ot-cloture-visite"></p>`);
    bloc.textContent = phrase;
    return [bloc];
  }

  /** L23 : temps passé proposé pour une visite sans temps saisi : temps prévu de l'OT (recopié de la gamme), sinon de la gamme. */
  function tempsPropose(ot) {
    if (!estVisite(ot) || lignesDeLOt('ot_temps', ot.id).some((ligne) => nombre(ligne.heures) > 0)) return '';
    const gamme = texte(ot.gamme_id) ? Donnees.trouver('gammes', ot.gamme_id) : null;
    const prevu = nombre(ot.temps_prevu_h) || nombre(gamme && gamme.temps_prevu_h);
    return prevu > 0 && prevu <= 24 ? String(prevu) : '';
  }

  /** L23 : « Prochaine visite : le 14/12/2026. » quand la gamme de l'OT est périodique (déclencheur date), sinon ''. */
  function prochaineVisite(ot) {
    const gamme = texte(ot.gamme_id) ? Donnees.trouver('gammes', ot.gamme_id) : null;
    if (!gamme || gamme.declencheur !== 'date' || texte(gamme.actif) === '0' || !texte(gamme.prochaine_echeance)) return '';
    return I18n.t('ordres.cloture.prochaine_visite', { date: UI.dateFr(gamme.prochaine_echeance) });
  }

  /**
   * L23 : visite close avec une anomalie constatée et sans demande liée : l'OT de réparation est proposé. Le
   * responsable le crée (nouvel OT pré-rempli) ; le technicien le signale par une demande liée (le responsable décide).
   */
  function propositionReparation(ot) {
    if (!estVisite(ot) || ot.anomalie_constatee !== '1') return '';
    if (Donnees.lignes('demandes').some((demande) => demande.ot_origine_id === ot.id)) return '';
    const equipement = encodeURIComponent(texte(ot.equipement_id));
    const adresse = estResponsable()
      ? '#/ot/nouveau?equipement=' + equipement + '&type=' + encodeURIComponent('correctif différé')
        + '&titre=' + encodeURIComponent(I18n.t('ordres.cloture.titre_reparation', { otId: ot.id }))
        + '&travail=' + encodeURIComponent(texte(ot.compte_rendu))
      : '#/di/nouvelle?equipement=' + equipement + '&ot=' + encodeURIComponent(ot.id);
    return UI.html`<p>${I18n.t('ordres.cloture.anomalie_reparation')}</p>
      <p><a class="btn btn-secondaire" id="ot-reparation" href="${adresse}">${UI.icone('ajouter')}${estResponsable()
        ? I18n.t('ordres.cloture.creer_ot_reparation') : I18n.t('ordres.cloture.signaler_reparation')}</a></p>`;
  }

  // ===========================================================================================
  // 3. Après une transition : toast et message de la fiche (L22, L23)
  // ===========================================================================================

  /** Phrase dite après une transition : statut atteint, part du technicien terminée (L22), prochaine visite (L23). */
  function messageApresTransition(ot, cible, enUneFois) {
    return phrasesApresTransition(ot, cible, enUneFois).join(' ');
  }

  // Les phrases : la première dit le statut atteint, les suivantes (s'il y en a) ce qui reste à savoir.
  function phrasesApresTransition(ot, cible, enUneFois) {
    const cloture = enUneFois || cible === 'Clôturé techniquement';
    const morceaux = [enUneFois
      ? (enSolo() ? I18n.t('ordres.cloture.solo_clos', { otId: ot.id })
        : I18n.t('ordres.demander_clore.cloture_techniquement_administrativement', { actuelId: ot.id }))
      : ot.id + ' : ' + Schema.libelleValeur('ordres_travail', 'statut', cible) + '.'];
    if (!enUneFois && cible === 'Clôturé techniquement' && !estResponsable()) morceaux.push(I18n.t('ordres.cloture.part_terminee'));
    if (cloture) morceaux.push(prochaineVisite(ot));
    return morceaux.filter(Boolean);
  }

  /**
   * Toast et message au-dessus des onglets après une transition (fiche réaffichée) : l'avertissement de la gamme
   * remplace le succès (RG5) ; après une clôture, la phrase reste affichée, avec l'OT de réparation proposé (L23).
   */
  function direApresTransition(otId, cible, avertissementGamme, avertissements, enUneFois) {
    const ot = Donnees.trouver('ordres_travail', otId) || { id: otId };
    const phrases = phrasesApresTransition(ot, cible, enUneFois);
    UI.toast(avertissementGamme || phrases.join(' '), avertissementGamme ? 'attention' : 'succes');
    const cloture = enUneFois || cible === 'Clôturé techniquement';
    const reparation = cloture ? propositionReparation(ot) : '';
    if (avertissements.length || reparation) {
      const suite = !avertissementGamme && cloture && phrases.length > 1 ? phrases.join(' ') : '';
      Ordres.interne.afficherMessage('attention', UI.html`${avertissements.length ? UI.html`<p>${avertissements.join(' ')}</p>` : ''}${
        suite ? UI.html`<p>${suite}</p>` : ''}${reparation}`);
    } else if (cloture && phrases.length > 1) {
      Ordres.interne.afficherMessage('succes', phrases.join(' '));      // ce qui reste à savoir reste lisible après le toast
    }
  }

  // Outils prêtés aux fichiers du module (usage interne) : la fiche, l'onglet Compte rendu et l'onglet Exécution.
  Object.assign(Ordres.interne, {
    boutonClore, demanderClore, demanderCloture, direApresTransition, compteRenduDOffice, tempsPropose,
  });

  // Règles de L20 et L23 exposées pour les tests.
  return { visiteSansAnomalie, messageApresTransition, manquesSaisis };
})());
