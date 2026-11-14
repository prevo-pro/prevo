'use strict';
// Import (4/7) — écriture et annulation (lot 5, ARCHITECTURE.md §18.7) : sauvegarde « avant-import »
// (instantané en démo), écriture par Donnees.modifier dans l'ordre des références, journal, retour
// arrière. Complète l'objet Import.
//
// API :
//   Import.importer(apercu, { nomFichier, recalculer }) → Promise<{ sauvegarde, tables, tablesTouchees,
//     nomFichier }> :
//     - recalculer() (facultatif) rend un aperçu recalculé sur les données fraîches : relu juste avant
//       d'écrire ; s'il diffère de celui que le responsable a validé (un autre poste a écrit entre-temps),
//       rien n'est écrit et Import.ErreurImport (perime: true, apercu: le nouveau) est levée ;
//     - sauvegarde = nom de la sauvegarde « avant-import » (modes serveur et dossier ; un échec arrête
//       tout, rien n'est écrit) ; en démo, instantané en mémoire des tables touchées ;
//     - tables = { nomTable: { crees, misAJour } } ; journal : chaque ligne écrite (« création —
//       import <fichier> »…) et une ligne de bilan par table (« import <fichier> : n créé(s), m mis à jour ») ;
//     - échec en cours d'écriture : l'erreur porte resultatPartiel (même forme), à passer à annuler.
//     recalculer doit reprendre les mêmes options que l'aperçu validé (même « maintenant »).
//     - heuresParJour (L30, facultatif) : heures de marche par jour données aux machines créées ou mises à jour par
//       l'import qui n'en ont pas (jamais à une autre machine ; jamais à la place d'une valeur du fichier ou de la base).
//   Import.annuler(resultat) → Promise<{ restaurees }> : rend les tables touchées dans leur état d'avant
//     l'import (restauration de la sauvegarde, avec la copie de sécurité habituelle ; en démo, l'instantané).
//   Import.ORDRE_ECRITURE : ordre des tables (les références avant ceux qui les citent ; garanties et contrats de
//     prestataires après les fournisseurs et les équipements, T487 ; réserves après les contrôles, T489).

Object.assign(Import, (() => {

  const ORDRE_ECRITURE = Object.freeze(['localisations', 'fournisseurs', 'techniciens', 'equipements', 'articles',
    'mouvements_stock', 'compteurs', 'controles_reglementaires', 'reserves_controle', 'garanties', 'contrats_prestataires', 'habilitations',
    'gammes', 'gamme_operations', 'codes_defaillance', 'ordres_travail', 'ot_temps']);

  // Instantanés de la démo (rien n'y est sauvegardé sur un disque) : resultat → { nomTable: octets }.
  const instantanes = new WeakMap();

  function texte(valeur) {
    return valeur === null || valeur === undefined ? '' : String(valeur).trim();
  }

  function ecrituresDe(apercu, nomTable) {
    const ecritures = apercu && apercu.ecritures ? apercu.ecritures[nomTable] : null;
    if (!ecritures) return null;
    const creer = ecritures.creer || [];
    const modifier = ecritures.modifier || [];
    const supprimer = ecritures.supprimer || [];          // T523 : codes de la liste de départ remplacés par l'import
    return creer.length || modifier.length ? { creer, modifier, supprimer } : null;
  }

  // Signature d'un aperçu : ce qui serait écrit (identifiants et champs), pour savoir s'il a changé.
  function signature(apercu) {
    return JSON.stringify(ORDRE_ECRITURE.map((nomTable) => {
      const ecritures = ecrituresDe(apercu, nomTable);
      if (!ecritures) return null;
      return [nomTable, ecritures.creer.map((ligne) => JSON.stringify(ligne)).sort(),
        ecritures.modifier.map((modification) => modification.id + ' ' + JSON.stringify(modification.changes)).sort(),
        ecritures.supprimer.slice().sort()];
    }));
  }

  function erreurPerime(nouveau) {
    const erreur = new Import.ErreurImport(I18n.t('import.erreur_perime.donnees_ont_change_autre'));
    erreur.perime = true;
    erreur.apercu = nouveau;
    return erreur;
  }

  async function importer(apercuValide, options) {
    const reglages = options || {};
    const nomFichier = texte(reglages.nomFichier) || 'fichier';
    let apercu = apercuValide;
    if (typeof reglages.recalculer === 'function') {
      try { await Donnees.rafraichir(); } catch (erreur) { /* l'écriture relira de toute façon les tables périmées */ }
      const frais = await reglages.recalculer();
      if (signature(frais) !== signature(apercuValide)) throw erreurPerime(frais);
      apercu = frais;
    }
    const tablesTouchees = ORDRE_ECRITURE.filter((nomTable) => ecrituresDe(apercu, nomTable));
    if (!tablesTouchees.length) throw new Import.ErreurImport(I18n.t('import.importer.rien_importer_aucune_ligne'));

    // 1. Sauvegarde juste avant (rien n'est écrit si elle échoue) ; instantané en démo.
    let sauvegarde = null;
    let instantane = null;
    if (App.mode === 'demo') {
      const tout = Donnees.instantane();
      instantane = {};
      tablesTouchees.forEach((nomTable) => { instantane[nomTable] = tout[nomTable]; });
    } else {
      try {
        sauvegarde = await App.adaptateur.sauvegarder('avant-import');
      } catch (erreur) {
        throw new Import.ErreurImport(I18n.t('import.importer.sauvegarde_impossible_raison', { raison: texte(erreur && erreur.message) }));
      }
      if (!sauvegarde) throw new Import.ErreurImport(I18n.t('import.importer.sauvegarde_impossible'));
    }

    // 2. Écriture table par table, dans l'ordre des références. Si une table échoue en cours de route,
    //    l'erreur porte resultatPartiel (tables déjà touchées, sauvegarde) : l'écran propose d'annuler.
    const tables = {};
    const resultat = { sauvegarde, tables, tablesTouchees: [], nomFichier };
    if (instantane) instantanes.set(resultat, instantane);
    try {
      for (const nomTable of tablesTouchees) {
        resultat.tablesTouchees.push(nomTable);
        await ecrireTable(nomTable, ecrituresDe(apercu, nomTable), nomFichier, tables,
          nomTable === 'equipements' ? completerHeures(reglages.heuresParJour) : null);
      }
    } catch (erreur) {
      if (erreur && typeof erreur === 'object') erreur.resultatPartiel = resultat;
      throw erreur;
    }
    return resultat;
  }

  // Une table : créations (identifiant déjà pris entre-temps → erreur, jamais de doublon) puis mises à
  // jour ; le journal note chaque ligne (« création — import <fichier> »…) puis le bilan de la table.
  /** L30 : complément d'une machine importée (heures de marche par jour si elle n'en a pas), ou null sans réponse. */
  function completerHeures(heures) {
    if (typeof heures !== 'number' || !Number.isFinite(heures)) return null;
    return (ligne) => { if (!texte(ligne.heures_fonct_jour)) ligne.heures_fonct_jour = String(heures); };
  }

  async function ecrireTable(nomTable, ecritures, nomFichier, tables, completer) {
    const bilan = { crees: 0, misAJour: 0 };
    await Donnees.modifier(nomTable, (lignes) => {
      bilan.crees = 0;                                     // la fonction peut être rejouée après un conflit
      bilan.misAJour = 0;
      delete bilan.remplaces;
      // T523 : codes de la liste de départ remplacés par ceux du fichier (aperçu relu juste avant : toujours non cités).
      ecritures.supprimer.forEach((id) => {
        const rang = lignes.findIndex((ligne) => ligne.id === id);
        if (rang >= 0) { lignes.splice(rang, 1); bilan.remplaces = (bilan.remplaces || 0) + 1; }
      });
      const parId = new Map(lignes.map((ligne) => [ligne.id, ligne]));
      ecritures.creer.forEach((nouvelle) => {
        if (parId.has(nouvelle.id)) {
          throw new Import.ErreurImport(I18n.t('import.ecrire_table.identifiant_vient_etre_pris', { nouvelleId: nouvelle.id }));
        }
        const copie = Object.assign({}, nouvelle);
        if (completer) completer(copie);
        lignes.push(copie);
        parId.set(copie.id, copie);
        bilan.crees += 1;
      });
      ecritures.modifier.forEach((modification) => {
        const ligne = parId.get(modification.id);
        if (!ligne) return;
        Object.assign(ligne, modification.changes);
        if (completer) completer(ligne);
        bilan.misAJour += 1;
      });
    }, { action: 'import ' + nomFichier });
    tables[nomTable] = bilan;
    await Donnees.journaliser(nomTable, '', 'import ' + nomFichier + ' : ' + bilan.crees + ' créé(s), '
      + bilan.misAJour + ' mis à jour' + (bilan.remplaces ? ', ' + bilan.remplaces + ' code(s) de départ remplacé(s)' : ''));
  }

  async function annuler(resultat) {
    if (!resultat || !resultat.tablesTouchees || !resultat.tablesTouchees.length) {
      throw new Import.ErreurImport(I18n.t('import.annuler.aucun_import_annuler'));
    }
    const tables = resultat.tablesTouchees.slice();
    const instantane = instantanes.get(resultat);
    if (instantane) {
      for (const nomTable of tables) {
        await App.adaptateur.enregistrer(nomTable, instantane[nomTable], Donnees.version(nomTable));
        await Donnees.rechargerTable(nomTable);
      }
      instantanes.delete(resultat);
    } else {
      if (!resultat.sauvegarde) throw new Import.ErreurImport(I18n.t('import.annuler.aucune_sauvegarde_import_rien'));
      await App.adaptateur.restaurer(resultat.sauvegarde, tables);
      await Donnees.chargerTout();
    }
    await Donnees.journaliser('parametres', '', 'import ' + resultat.nomFichier + ' annulé : '
      + tables.join(', ') + ' rendues dans leur état d\'avant');
    return { restaurees: tables };
  }

  return { ORDRE_ECRITURE, importer, annuler };
})());
