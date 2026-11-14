'use strict';
// Ordres — clôture d'un OT (T539, lot 2 ergonomie) : la fenêtre « Clore » (clôture en une étape, ARCHITECTURE.md
// §22.11, D132 ; sortie de ordres-fiche.js), ce que Prévo dit après une clôture (L22 : le technicien lit « Votre part
// est terminée. Le responsable validera. » ; en Solo, une seule clôture, sans « deux temps » ni « verrouiller ») et la
// clôture d'une visite préventive (L23) : liste de contrôle toute cochée sans anomalie → compte rendu écrit d'office
// (« Visite faite, rien à signaler », dans la langue de l'écran, modifiable) ; anomalie constatée → compte rendu à
// écrire et OT de réparation proposé ; temps passé proposé d'après le temps prévu de la gamme ; prochaine visite dite.
// Chargé juste après ordres-fiche.js ; les outils de la fiche (Ordres.interne) sont cherchés au moment de l'appel.
// Complète l'objet Ordres.

Object.assign(Ordres, (() => {

  const { transitionsPossibles } = Ordres;
  const { texte, nombre, estResponsable, equipementDe, listeTechniciens, champOt, lignesDeLOt } = Ordres.interne;

  const enSolo = () => typeof App !== 'undefined' && typeof App.modeSolo === 'function' && App.modeSolo();

  // ===========================================================================================
  // 1. Clôture en une étape (ARCHITECTURE.md §22.11, D132) : « Clore », réglage cloture_une_etape
  // ===========================================================================================

  /** Bouton « Clore » : réglage actif, profil responsable, OT qui peut recevoir la clôture technique. */
  function boutonClore(ot) {
    return Ordres.clotureUneEtape() && transitionsPossibles(ot).includes('Clôturé techniquement')
      ? UI.html`<button type="button" class="btn btn-primaire" id="ot-clore">${UI.icone('valider')}${I18n.t('ordres.bouton_clore.clore')}</button>` : '';
  }

  // Champs de la fenêtre « Clore » : ceux des onglets Exécution et Compte rendu (mêmes libellés et
  // aides), le temps passé et une pièce sortie du magasin (facultative, Magasin.sortir).
  function champsClore(ot) {
    const { libelleArticle, aideAstuce } = Ordres.interne;
    const total = lignesDeLOt('ot_temps', ot.id).reduce((somme, ligne) => somme + nombre(ligne.heures), 0);
    const technicien = App.technicienSolo() || ot.technicien_id || '';
    const articles = Donnees.lignes('articles').filter((a) => texte(a.actif) !== '0')
      .map((a) => ({ valeur: a.id, libelle: I18n.t('ordres.options_articles.libelle_article_stock_stock_article', { libelleArticle: libelleArticle(a), stockArticle: UI.nombreFr(Donnees.stockArticle(a.id)) }) }));
    const fin = champOt('date_fin', texte(ot.date_fin) || Donnees.maintenant().slice(0, 16));
    const propose = tempsPropose(ot);                                    // L23 : d'après le temps prévu de la gamme
    UI.$('input', fin).max = Donnees.maintenant().replace(' ', 'T');     // pas de date de fin dans le futur
    const remise = champOt('remise_service', ot.remise_service, {
      libelle: I18n.t('ordres.champs_clore.equipement_remis_service_securite'),
    });
    if (texte((equipementDe(ot) || {}).habilitation_requise)) remise.appendChild(UI.element(UI.html`<p class="aide">${Ordres.rappelConsignation()}</p>`));
    return [
      fin,
      champOt('arret_production', ot.arret_production, { libelle: I18n.t('ordres.champs_clore.arret_production_pendant_intervention') }),
      champOt('duree_arret_h', ot.duree_arret_h),
      UI.champ({ nom: 'heures', type: 'duree', libelle: I18n.t('ordres.champs_clore.temps_passe_ajouter_heures') }, propose,
        { aide: total > 0 ? I18n.t('ordres.champs_clore.deja_saisi', { total: UI.heures(total) })
          : propose ? I18n.t('ordres.cloture.temps_propose') : I18n.t('ordres.champs_clore.moins_temps_passe_exige') }),
      champOt('technicien_id', technicien, { liste: listeTechniciens(technicien), libelle: I18n.t('ordres.champs_clore.technicien_temps_passe') }),
      UI.champ({ nom: 'article_id', type: 'ref', libelle: I18n.t('ordres.champs_clore.piece_sortie_magasin_facultatif') }, '', { liste: articles }),
      UI.champ({ nom: 'quantite', type: 'decimal', libelle: I18n.t('ordres.champs_clore.quantite_sortie') }, '1'),
      ...Ordres.champsCodes(ot),                 // T515 : symptôme, cause (sauf préventif), remède, « Autre »
      champOt('compte_rendu', texte(ot.compte_rendu) || compteRenduDOffice(ot), {        // L23 : écrit d'office, modifiable
        aide: I18n.t('ordres.champs_clore.ete_constate_cause_ete'),
      }),
      ...Demandes.champsMotOperateur(ot),                         // A4 : mot pour l'opérateur, si l'OT vient d'une demande
      champOt('astuce', ot.astuce, { aide: aideAstuce() }),
      remise,
    ];
  }

  /** « Clore » : saisies de la fiche enregistrées, puis une seule fenêtre → Ordres.clore (technique + administrative). */
  async function demanderClore(ot) {
    const { viderMessage, enregistrerFormulairesModifies, apresEnregistrement } = Ordres.interne;
    viderMessage();
    const sauvegarde = await enregistrerFormulairesModifies();
    if (!sauvegarde.ok) return;
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const solo = enSolo();                       // L22 : en Solo, une seule clôture (ni « deux temps » ni « verrouiller »)
    const fait = await UI.fenetreAction({
      titre: I18n.t('ordres.demander_clore.clore_actuel_id', { actuelId: actuel.id }), classe: 'ot-fenetre-clore',
      libelleValider: solo ? I18n.t('ordres.bouton_clore.clore') : I18n.t('ordres.demander_clore.clore_verrouiller'),
      introduction: UI.html`<p>${solo ? I18n.t('ordres.cloture.solo_introduction') : I18n.t('ordres.demander_clore.cloture_technique_puis_administrative')}</p>`,
      champs: champsClore(actuel),
      verifier: () => [],
      action: (valeurs, contenu) => Ordres.clore(actuel, UI.lireFormulaire(contenu.closest('form'))),
    });
    if (!fait) { if (sauvegarde.enregistres) await apresEnregistrement(); return; }
    await apresEnregistrement();
    const avertissementGamme = Ordres.interne.lireAvertissementGamme(actuel.id);
    direApresTransition(actuel.id, 'Clôturé administrativement', avertissementGamme, avertissementGamme ? [avertissementGamme] : [], true);
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

  /** L23 : temps passé proposé pour une visite sans temps saisi : temps prévu de l'OT (recopié de la gamme), sinon de la gamme. */
  function tempsPropose(ot) {
    if (!estVisite(ot) || lignesDeLOt('ot_temps', ot.id).some((ligne) => nombre(ligne.heures) > 0)) return '';
    const gamme = texte(ot.gamme_id) ? Donnees.trouver('gammes', ot.gamme_id) : null;
    const prevu = nombre(ot.temps_prevu_h) || nombre(gamme && gamme.temps_prevu_h);
    return prevu > 0 && prevu <= 24 ? String(prevu) : '';
  }

  /**
   * L23 : avant la clôture technique (bouton de la fiche) : le temps proposé dans l'onglet Exécution et laissé tel quel
   * est ajouté (comme « Ajouter le temps ») ; le compte rendu d'une visite sans anomalie est écrit d'office.
   */
  async function preparerCloture(ot) {
    const formulaire = document.getElementById('form-temps');
    const saisie = formulaire && formulaire.querySelector('[name="heures"]');
    if (saisie && formulaire.dataset.tempsPropose && saisie.value === formulaire.dataset.tempsPropose && tempsPropose(ot)) {
      formulaire.dataset.modifie = '1';
      if (!(await Ordres.interne.enregistrerFormulairesModifies()).ok) return ot;
    }
    const actuel = Donnees.trouver('ordres_travail', ot.id) || ot;
    const compteRendu = compteRenduDOffice(actuel);
    if (!compteRendu) return actuel;
    try {
      await Ordres.interne.modifierOt(ot.id, { compte_rendu: compteRendu }, I18n.donnees('ordres.cloture.journal_compte_rendu_d_office'));
    } catch (erreur) {
      App.signalerErreur(erreur);
    }
    return Donnees.trouver('ordres_travail', ot.id) || actuel;
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
    boutonClore, demanderClore, preparerCloture, direApresTransition, compteRenduDOffice, tempsPropose,
  });

  // Règles de L23 exposées pour les tests.
  return { visiteSansAnomalie, messageApresTransition };
})());
