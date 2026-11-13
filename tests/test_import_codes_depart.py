"""Import de ses propres codes de défaillance sur une base qui a la liste de départ (lot 1 ergonomie, A2 ; T515 puis
T523) : un code importé dont le libellé est déjà pris dans sa famille par un code de la LISTE DE DÉPART
(js/catalogue/codes-depart.js) qu'aucune fiche ne cite prend sa place (le code de départ est retiré, celui du fichier
créé avec son identifiant à lui) ; code de départ cité par un OT, ou homonyme qui n'est pas de départ : refus du
formulaire, comme avant. L'aperçu le dit sur la ligne et en une phrase ; l'écriture retire le code de départ, le bilan
et le journal le comptent.

Page : index.html en file://, démo (codes de la démo, qui ne sont pas des codes de départ) complétée en mémoire de deux
codes de départ dont le libellé n'est pas dans la démo ; le second est cité par un OT.

Lancer depuis la racine du projet :
    py -m unittest discover -s tests -p "test_import_codes_depart.py" -v
"""
import unittest

from test_import_controles import MAINTENANT, CasControles

# Deux codes de départ absents de la démo (même famille et même libellé) ajoutés à la base ; un OT cite le second.
PREPARER_JS = """async () => {
  const meme = (a, b) => UI.normaliserRecherche(a) === UI.normaliserRecherche(b);
  const demo = Donnees.lignes('codes_defaillance');
  const libres = CodesDeDepart.lignes('fr').filter((d) => !demo.some((c) => c.famille === d.famille && (meme(c.libelle, d.libelle) || c.code === d.code)));
  const [libre, cite] = [libres[0], libres.find((d) => d.famille === 'cause')];
  const ajoutes = [];
  await Donnees.modifier('codes_defaillance', (lignes, outils) => {
    [libre, cite].forEach((d) => { const ligne = Object.assign({ id: outils.nouvelId(lignes) }, d); lignes.push(ligne); ajoutes.push(ligne); });
  }, { action: 'codes de départ (essai)' });
  const ot = Donnees.lignes('ordres_travail')[0];
  await Donnees.modifier('ordres_travail', (lignes) => { lignes.find((l) => l.id === ot.id).cause_code = cite.code; }, { action: 'essai' });
  return { libre: ajoutes[0], cite: ajoutes[1], otId: ot.id, citeParOt: Parametres.codeCite(ajoutes[1]), libreCite: Parametres.codeCite(ajoutes[0]) };
}"""
IMPORTER_JS = """async ([entetes, grille, maintenant]) => {
  const correspondance = entetes.map((champ, colonne) => ({ colonne, entete: champ, champ, statut: 'sure', raison: '' }));
  const calculer = () => Import.preparer('codes', grille, correspondance, { maintenant, mettreAJour: true });
  const resultat = await Import.importer(calculer(), { nomFichier: 'codes.csv', recalculer: calculer });
  const journal = Donnees.lignes('journal').map((l) => l.action);
  return { tables: resultat.tables, codes: Donnees.lignes('codes_defaillance').map((c) => [c.id, c.famille, c.code, c.libelle]),
           bilan: journal.filter((a) => a.startsWith('import codes.csv : ')) };
}"""


class TestCodesDeDepartRemplaces(CasControles):

    def test_homonyme_de_depart_non_cite_remplace_cite_ou_hors_depart_refuse(self):
        base = self.page.evaluate(PREPARER_JS)
        libre, cite = base["libre"], base["cite"]
        self.assertEqual((base["libreCite"], base["citeParOt"]), (False, True))
        self.assertEqual(self.fiche("codes_defaillance", "CD-0024")["libelle"], "Corrosion")       # code de la démo
        grille = [
            [libre["famille"], "U01", libre["libelle"]],      # 2 : homonyme d'un code de départ que rien ne cite → le remplace
            [cite["famille"], "U02", cite["libelle"]],        # 3 : homonyme d'un code de départ cité par un OT → refus
            ["cause", "U03", "Corrosion"],                    # 4 : homonyme d'un code qui n'est pas de départ → refus
            ["remède", "U04", "Essai sans homonyme"],         # 5 : passe, rien à remplacer
        ]
        apercu = self.apercu("codes", ["famille", "code", "libelle"], grille)
        self.verifier_actions(apercu, {2: "creer", 3: "refusee", 4: "refusee", 5: "creer"})
        remplace = "Prend la place du code de départ %s « %s », que rien ne cite." % (libre["code"], libre["libelle"])
        self.assertIn(remplace, self.ligne(apercu, 2)["raisons"])
        self.assertNotIn(remplace, self.ligne(apercu, 5)["raisons"])
        self.verifier_refus(self.ligne(apercu, 3), self.formulaire("codes", {"famille": cite["famille"], "code": "U02", "libelle": cite["libelle"]}))
        self.verifier_refus(self.ligne(apercu, 4), self.formulaire("codes", {"famille": "cause", "code": "U03", "libelle": "Corrosion"}))
        ecritures = apercu["ecritures"]["codes_defaillance"]
        self.assertEqual([c["code"] for c in ecritures["creer"]], ["U01", "U04"])
        self.assertEqual(ecritures["supprimer"], [libre["id"]])
        self.assertNotIn(libre["id"], [c["id"] for c in ecritures["creer"]])                   # son identifiant à lui
        self.assertEqual(self.page.evaluate("() => I18n.t('import.codes_depart.remplaces', { n: 1 })"),
                         "1 code de la liste de départ remplacé par le vôtre (même libellé).")

        avant = self.page.evaluate("() => Donnees.lignes('codes_defaillance').length")
        fait = self.page.evaluate(IMPORTER_JS, [["famille", "code", "libelle"], grille, MAINTENANT])
        self.assertEqual(fait["tables"]["codes_defaillance"], {"crees": 2, "misAJour": 0, "remplaces": 1})
        self.assertEqual(len(fait["codes"]), avant + 2 - 1)
        ids = {c[0]: c for c in fait["codes"]}
        self.assertNotIn(libre["id"], ids)                                                       # code de départ retiré
        self.assertEqual(ids[cite["id"]][2:], [cite["code"], cite["libelle"]])                    # cité : gardé
        self.assertEqual(ids["CD-0024"][2:], ["C13", "Corrosion"])                                # hors départ : gardé
        self.assertEqual(sorted(c[2] for c in fait["codes"] if c[2].startswith("U")), ["U01", "U04"])
        self.assertIn("import codes.csv : 2 créé(s), 0 mis à jour, 1 code(s) de départ remplacé(s)", fait["bilan"])

    def test_sans_code_de_depart_rien_ne_change(self):
        # Démo seule (aucun code de départ) : l'homonyme est refusé, rien n'est à retirer.
        apercu = self.apercu("codes", ["famille", "code", "libelle"], [["remède", "U05", "Réglage"]])
        self.verifier_actions(apercu, {2: "refusee"})
        self.assertNotIn("supprimer", apercu["ecritures"]["codes_defaillance"])


if __name__ == "__main__":
    unittest.main()
