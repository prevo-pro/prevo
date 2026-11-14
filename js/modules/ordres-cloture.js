'use strict';
// Ordres — clôture d'un OT (T539, lot 2 ergonomie) : la fenêtre « Clore » (clôture en une étape, ARCHITECTURE.md
// §22.11, D132 ; sortie de ordres-fiche.js) et ce que Prévo dit après une clôture (L22 : le technicien lit « Votre part
// est terminée. Le responsable validera. » ; en Solo, une seule clôture, sans « deux temps » ni « verrouiller »).
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
    UI.$('input', fin).max = Donnees.maintenant().replace(' ', 'T');     // pas de date de fin dans le futur
    const remise = champOt('remise_service', ot.remise_service, {
      libelle: I18n.t('ordres.champs_clore.equipement_remis_service_securite'),
    });
    if (texte((equipementDe(ot) || {}).habilitation_requise)) remise.appendChild(UI.element(UI.html`<p class="aide">${Ordres.rappelConsignation()}</p>`));
    return [
      fin,
      champOt('arret_production', ot.arret_production, { libelle: I18n.t('ordres.champs_clore.arret_production_pendant_intervention') }),
      champOt('duree_arret_h', ot.duree_arret_h),
      UI.champ({ nom: 'heures', type: 'duree', libelle: I18n.t('ordres.champs_clore.temps_passe_ajouter_heures') }, '',
        { aide: total > 0 ? I18n.t('ordres.champs_clore.deja_saisi', { total: UI.heures(total) }) : I18n.t('ordres.champs_clore.moins_temps_passe_exige') }),
      champOt('technicien_id', technicien, { liste: listeTechniciens(technicien), libelle: I18n.t('ordres.champs_clore.technicien_temps_passe') }),
      UI.champ({ nom: 'article_id', type: 'ref', libelle: I18n.t('ordres.champs_clore.piece_sortie_magasin_facultatif') }, '', { liste: articles }),
      UI.champ({ nom: 'quantite', type: 'decimal', libelle: I18n.t('ordres.champs_clore.quantite_sortie') }, '1'),
      ...Ordres.champsCodes(ot),                 // T515 : symptôme, cause (sauf préventif), remède, « Autre »
      champOt('compte_rendu', ot.compte_rendu, {
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
  // 2. Après une transition : toast et message de la fiche (L22)
  // ===========================================================================================

  /** Phrase dite après une transition : statut atteint, part du technicien terminée (L22). */
  function messageApresTransition(ot, cible, enUneFois) {
    return phrasesApresTransition(ot, cible, enUneFois).join(' ');
  }

  // Les phrases : la première dit le statut atteint, les suivantes (s'il y en a) ce qui reste à savoir.
  function phrasesApresTransition(ot, cible, enUneFois) {
    const morceaux = [enUneFois
      ? (enSolo() ? I18n.t('ordres.cloture.solo_clos', { otId: ot.id })
        : I18n.t('ordres.demander_clore.cloture_techniquement_administrativement', { actuelId: ot.id }))
      : ot.id + ' : ' + Schema.libelleValeur('ordres_travail', 'statut', cible) + '.'];
    if (!enUneFois && cible === 'Clôturé techniquement' && !estResponsable()) morceaux.push(I18n.t('ordres.cloture.part_terminee'));
    return morceaux.filter(Boolean);
  }

  /**
   * Toast et message au-dessus des onglets après une transition (fiche réaffichée) : l'avertissement de la gamme
   * remplace le succès (RG5) ; après une clôture, la phrase reste affichée.
   */
  function direApresTransition(otId, cible, avertissementGamme, avertissements, enUneFois) {
    const ot = Donnees.trouver('ordres_travail', otId) || { id: otId };
    const phrases = phrasesApresTransition(ot, cible, enUneFois);
    UI.toast(avertissementGamme || phrases.join(' '), avertissementGamme ? 'attention' : 'succes');
    const cloture = enUneFois || cible === 'Clôturé techniquement';
    if (avertissements.length) {
      Ordres.interne.afficherMessage('attention', avertissements.join(' '));
    } else if (cloture && phrases.length > 1) {
      Ordres.interne.afficherMessage('succes', phrases.join(' '));      // ce qui reste à savoir reste lisible après le toast
    }
  }

  // Outils prêtés aux fichiers du module (usage interne) : la fiche.
  Object.assign(Ordres.interne, { boutonClore, demanderClore, direApresTransition });

  // Phrase dite après une transition, exposée pour les tests.
  return { messageApresTransition };
})());
