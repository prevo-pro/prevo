'use strict';
// Ordres (T515, correction A2 du lot 1 ergonomie) — codes cause et remède de la clôture (ARCHITECTURE.md §10, RG4 ;
// §15.11). Complète l'objet Ordres créé par ordres-regles.js ; appelé par les autres fichiers ordres-*.js par des
// appels courts (Ordres.manquesDesCodes, Ordres.champCode, Ordres.champsCodes, Ordres.codesSaisis…) :
//   1. Règle de la clôture : cause et remède exigés sur un OT correctif (ou d'amélioration) tant que la famille a des
//      codes (RG4 du brief §8 : « code cause, code remède ») ; jamais sur un OT préventif ou réglementaire ; « renseigné » = un code OU une
//      précision non vide (« Autre (préciser) », colonnes cause_precision et remede_precision du format 5).
//   2. Champs de la clôture (onglet Compte rendu et fenêtre « Clore ») : liste des codes + « Autre (préciser) » (pas un
//      code de la table : enregistré code vide + texte de la précision), champ libre court avec dictée ; liste vide :
//      message non bloquant qui dit où créer les codes (lien et liste de départ pour le responsable).
//   3. Liste de départ (js/catalogue/codes-depart.js) : « Ajouter la liste de départ » n'ajoute que les codes absents.

Object.assign(Ordres, (() => {

  // Valeur de l'entrée « Autre (préciser) » des listes : jamais écrite dans un fichier (codesSaisis la retire).
  const AUTRE = '*autre*';
  const TYPES_PREVENTIFS = ['préventif systématique', 'préventif conditionnel', 'réglementaire'];
  const FAMILLES = {
    cause: { famille: 'cause', champ: 'cause_code', precision: 'cause_precision' },
    remede: { famille: 'remède', champ: 'remede_code', precision: 'remede_precision' },
  };
  const CHAMPS_CODES = ['symptome_code', 'cause_code', 'remede_code', 'cause_precision', 'remede_precision'];
  const PRECISION_MAX = 120;

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  // ===========================================================================================
  // 1. Règle de la clôture
  // ===========================================================================================

  /** Vrai pour un OT préventif (systématique, conditionnel) ou réglementaire : la cause n'y est jamais exigée. */
  function estPreventif(ot) {
    return TYPES_PREVENTIFS.includes(texte(ot && ot.type));
  }

  /** Vrai si la famille (« symptôme », « cause », « remède ») n'a aucun code dans codes_defaillance. */
  function familleVide(famille) {
    return !Donnees.lignes('codes_defaillance').some((c) => texte(c.famille) === famille && texte(c.code));
  }

  /** Vrai si l'OT a un code ou une précision (« Autre ») pour `cle` (« cause » ou « remede »). */
  function codeRenseigne(ot, cle) {
    const definition = FAMILLES[cle];
    return Boolean(texte(ot && ot[definition.champ]) || texte(ot && ot[definition.precision]));
  }

  /** { cause, remede } : vrai si la clôture exige ce code (correctif, famille non vide). */
  function codesExiges(ot) {
    if (estPreventif(ot)) return { cause: false, remede: false };
    return { cause: !familleVide('cause'), remede: !familleVide('remède') };
  }

  /** Manques de RG4 pour les codes (phrases, dans l'ordre cause puis remède) ; lu par Ordres.verifierCloture. */
  function manquesDesCodes(ot) {
    const exiges = codesExiges(ot);
    const manques = [];
    if (exiges.cause && !codeRenseigne(ot, 'cause')) manques.push(I18n.t('ordres.verifier_cloture.code_cause'));
    if (exiges.remede && !codeRenseigne(ot, 'remede')) manques.push(I18n.t('ordres.verifier_cloture.code_remede'));
    return manques;
  }

  /** Vrai si le champ cause est montré : pas sur un préventif, sauf anomalie constatée ou cause déjà renseignée. */
  function causeDemandee(ot) {
    return !estPreventif(ot) || texte(ot && ot.anomalie_constatee) === '1' || codeRenseigne(ot, 'cause');
  }

  /** « Autre : <texte> » pour une précision, '' sans précision (affichages de la cause et du remède). */
  function libelleAutre(precision) {
    const propre = texte(precision);
    return propre ? I18n.t('commun.code.autre_precise', { texte: propre }) : '';
  }

  /**
   * Champs des codes lus d'un formulaire, prêts à écrire : seulement ceux présents dans `valeurs` (un champ caché,
   * comme la cause d'un préventif, ne change rien) ; « Autre (préciser) » devient un code vide.
   */
  function codesSaisis(valeurs) {
    const saisis = {};
    CHAMPS_CODES.forEach((nom) => {
      if (valeurs && valeurs[nom] !== undefined) saisis[nom] = valeurs[nom] === AUTRE ? '' : texte(valeurs[nom]);
    });
    return saisis;
  }

  // ===========================================================================================
  // 2. Champs de la clôture
  // ===========================================================================================

  /** Message non bloquant d'une famille vide (et, pour le responsable, le lien et la liste de départ). */
  function noteFamilleVide(cle, surAjout) {
    const note = UI.element(UI.html`<p class="aide ot-codes-vides">${cle === 'cause' ? I18n.t('ordres.codes.aucun_code_cause') : I18n.t('ordres.codes.aucun_code_remede')}</p>`);
    if (!Ordres.interne.estResponsable()) return note;
    note.appendChild(UI.element(UI.html` <a href="#/parametres">${I18n.t('ordres.codes.ouvrir_parametres')}</a>`));
    const bouton = boutonListeDeDepart(surAjout);
    bouton.classList.add('ot-codes-depart');
    note.appendChild(bouton);
    return note;
  }

  /**
   * Champ d'un code de la clôture (cle : « cause » ou « remede ») : la liste des codes de la famille plus
   * « Autre (préciser) », et le champ de la précision (montré seulement pour « Autre »). Un OT sans code mais avec une
   * précision rouvre sur « Autre (préciser) » et son texte. Rend un bloc vide quand la cause n'est pas demandée.
   */
  function champCode(ot, cle) {
    const definition = FAMILLES[cle];
    const bloc = UI.element(UI.html`<div class="ot-code" data-code="${cle}"></div>`);
    if (cle === 'cause' && !causeDemandee(ot)) return bloc;
    const precision = texte(ot[definition.precision]);
    const valeur = texte(ot[definition.champ]) || (precision ? AUTRE : '');
    const liste = Ordres.interne.listeCodes(definition.famille)
      .concat([{ valeur: AUTRE, libelle: I18n.t('commun.code.autre_preciser') }]);
    const exige = codesExiges(ot)[cle];
    const choix = Ordres.interne.champOt(definition.champ, valeur, { liste,
      aide: estPreventif(ot) ? I18n.t('ordres.codes.facultatif_preventif') : '' });
    const saisie = Ordres.interne.champOt(definition.precision, precision, {
      libelle: cle === 'cause' ? I18n.t('ordres.codes.preciser_cause') : I18n.t('ordres.codes.preciser_remede'), attributs: { maxlength: String(PRECISION_MAX), 'data-dictee': '' } });
    bloc.append(choix, saisie);
    if (familleVide(definition.famille)) {
      bloc.appendChild(noteFamilleVide(cle, () => {
        const nouveau = champCode(Object.assign({}, ot, Ordres.codesSaisis(UI.lireFormulaire(bloc.closest('form') || bloc))), cle);
        bloc.replaceWith(nouveau);
      }));
    }
    const select = UI.$('select', choix);
    const champPrecision = UI.$('input', saisie);
    const montrer = () => { saisie.hidden = select.value !== AUTRE; };
    select.addEventListener('change', () => {
      if (select.value !== AUTRE && champPrecision.value) champPrecision.value = '';
      montrer();
      if (select.value === AUTRE) champPrecision.focus();
    });
    montrer();
    bloc.dataset.exige = exige ? '1' : '0';
    return bloc;
  }

  /** Champs des codes de la fenêtre « Clore » (symptôme, cause si demandée, remède). */
  function champsCodes(ot) {
    const symptome = Ordres.interne.champOt('symptome_code', ot.symptome_code, { liste: Ordres.interne.listeCodes('symptôme') });
    return [symptome, champCode(ot, 'cause'), champCode(ot, 'remede')].filter((bloc) => bloc.childElementCount);
  }

  // ===========================================================================================
  // 3. Liste de départ (js/catalogue/codes-depart.js)
  // ===========================================================================================

  /**
   * Lignes de la liste de départ absentes de `lignes` (ni le même code, ni le même libellé dans la famille), dans la
   * langue `langue` : [{ famille, code, libelle }].
   */
  function codesDeDepartAbsents(lignes, langue) {
    if (typeof CodesDeDepart === 'undefined') return [];
    const codes = new Set(lignes.map((l) => texte(l.code).toUpperCase()));
    const libelles = new Set(lignes.map((l) => texte(l.famille) + '|' + UI.normaliserRecherche(texte(l.libelle))));
    return CodesDeDepart.lignes(langue).filter((c) => !codes.has(c.code)
      && !libelles.has(c.famille + '|' + UI.normaliserRecherche(c.libelle)));
  }

  /** Ajoute les codes de départ absents (rien d'existant n'est modifié). Rend le nombre de codes ajoutés. */
  async function ajouterListeDeDepart() {
    let ajoutes = 0;
    return Donnees.modifier('codes_defaillance', (lignes, outils) => {
      codesDeDepartAbsents(lignes, I18n.installation).forEach((c) => {
        lignes.push({ id: outils.nouvelId(lignes), famille: c.famille, code: c.code, libelle: c.libelle });
        ajoutes += 1;
      });
      return ajoutes;
    }, { get action() { return I18n.donnees('ordres.codes.journal_liste_depart', { nombre: ajoutes }); } });
  }

  /** Bouton « Ajouter la liste de départ » (responsable) ; `surAjout()` après l'écriture réussie. */
  function boutonListeDeDepart(surAjout) {
    const bouton = UI.element(UI.html`<button type="button" class="btn btn-secondaire">${UI.icone('ajouter')}${I18n.t('ordres.codes.ajouter_liste_depart')}</button>`);
    bouton.addEventListener('click', async () => {
      if (bouton.disabled) return;
      bouton.disabled = true;
      try {
        const nombre = await ajouterListeDeDepart();
        UI.toast(I18n.t('ordres.codes.liste_depart_ajoutee', { nombre }), 'succes');
        if (surAjout) surAjout(nombre);
      } catch (erreur) {
        App.signalerErreur(erreur, 'ajout de la liste de départ des codes');
      } finally {
        bouton.disabled = false;
      }
    });
    return bouton;
  }

  /** Vrai si au moins une famille (symptôme, cause, remède) n'a aucun code : la liste de départ est proposée. */
  function listeDeDepartUtile() {
    return ['symptôme', 'cause', 'remède'].some(familleVide);
  }

  return {
    // codes de la clôture (T515, ARCHITECTURE.md §10, §15.11)
    CODE_AUTRE: AUTRE, TYPES_PREVENTIFS: Object.freeze(TYPES_PREVENTIFS.slice()),
    estPreventif, familleVide, codeRenseigne, codesExiges, manquesDesCodes, causeDemandee, libelleAutre, codesSaisis,
    champCode, champsCodes, codesDeDepartAbsents, ajouterListeDeDepart, boutonListeDeDepart, listeDeDepartUtile,
  };
})());
