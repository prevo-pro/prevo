"""Retour vers l'opérateur à l'écran (T517, A4 du lot 1 ergonomie). Navigateur, serveur sur une copie de la démo.

    py -X utf8 -m unittest discover -s tests -p "test_demandes_retour_ecrans.py" -v

Le technicien clôture techniquement l'OT d'une demande : la fenêtre propose « Un mot pour l'opérateur (facultatif) »
(champ marqué pour la dictée, 300 caractères) ; demandes.csv reçoit « Réparée », le mot, la date de fin et le prénom.
Puis le demandeur (même nom que la demande) : « Vos dernières demandes sur cette machine » sur la fiche de
l'équipement (route du QR) et au-dessus du formulaire Signaler, « Réparée le … par <prénom> » et le mot sur la fiche
de sa demande et dans « Mes demandes » ; le responsable : filtre « Réparées », mot sur la fiche de l'OT.
"""
import csv
import io
import unittest
from pathlib import Path

from commun import CasNavigateur, ServeurPrevo, attendre_pret, preregler_profil, scenarios_demo

SCENARIOS = scenarios_demo()
OT_EN_COURS = SCENARIOS["ot_en_cours_regroupe"]          # OT « En cours » venu d'une demande, avec des regroupées
MOT = "Courroie changée, vous pouvez redémarrer"


def lire_csv(chemin):
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    return [{cle: (valeur[1:] if valeur.startswith("'") else valeur) for cle, valeur in ligne.items()}
            for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")]


class TestRetourALEcran(CasNavigateur):

    def ouvrir(self, serveur, route):
        self.page.goto(serveur.url + "/" + route)
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def changer_profil(self, type_profil, nom="", technicien_id=""):
        self.page.evaluate("([t, n, tec]) => localStorage.setItem('prevo.profil', JSON.stringify({type: t, nom: n, technicienId: tec}))",
                           [type_profil, nom, technicien_id])
        self.page.reload()
        attendre_pret(self.page)
        self.page.wait_for_load_state("networkidle")

    def aller(self, route, selecteur):
        self.page.evaluate("(route) => { location.hash = route; }", route)
        self.page.wait_for_selector(selecteur)

    def texte(self, selecteur):
        return " ".join(self.page.inner_text(selecteur).split())

    def test_cloture_avec_mot_puis_ce_que_voit_l_operateur(self):
        with ServeurPrevo() as serveur:
            dossier = serveur.dossier
            ot = next(o for o in lire_csv(dossier / "ordres_travail.csv") if o["id"] == OT_EN_COURS)
            self.assertEqual(ot["statut"], "En cours")
            rattachees = [d for d in lire_csv(dossier / "demandes.csv") if d["ot_id"] == OT_EN_COURS]
            origine = next(d for d in rattachees if d["id"] == ot["di_id"])
            self.assertEqual(origine["statut"], "En cours")              # T525 : la démo suit déjà l'OT en cours
            technicien = next(t for t in lire_csv(dossier / "techniciens.csv") if t["id"] == ot["technicien_id"])
            codes = lire_csv(dossier / "codes_defaillance.csv")
            cause = next(c["code"] for c in codes if c["famille"] == "cause")
            remede = next(c["code"] for c in codes if c["famille"] == "remède")

            # 1. Le technicien de l'OT clôture : fenêtre du mot pour l'opérateur.
            preregler_profil(self.contexte, "technicien", "", ot["technicien_id"])
            self.ouvrir(serveur, "#/ot/" + OT_EN_COURS)
            self.page.evaluate("""async ([id, cause, remede]) => {
                const fin = Donnees.maintenant();
                await Ordres.interne.modifierOt(id, { date_fin: fin, cause_code: cause, remede_code: remede,
                  compte_rendu: 'Courroie usée remplacée, tension réglée.', remise_service: '1' }, 'essai T517');
                const ot = Donnees.trouver('ordres_travail', id);
                await Ordres.interne.modifierLieeAOt(id, 'ot_temps', (lignes, outils) => {
                  lignes.push({ id: outils.nouvelId(lignes), ot_id: id, technicien_id: ot.technicien_id,
                    date: fin.slice(0, 10), heures: '1' }); }, { action: 'temps essai' });
                await App.reafficher(); }""", [OT_EN_COURS, cause, remede])
            self.page.wait_for_selector("button[data-cible='Clôturé techniquement']")
            self.page.click("button[data-cible='Clôturé techniquement']")
            champ = self.page.wait_for_selector("dialog textarea[name='mot_operateur']")
            self.assertEqual(champ.get_attribute("maxlength"), "300")
            self.assertIsNotNone(champ.get_attribute("data-dictee"))
            self.assertIn("Il le lira en flashant le QR", self.page.inner_text("dialog"))
            champ.fill(MOT)
            self.page.click("dialog button.btn-primaire")
            self.page.wait_for_function("(id) => Donnees.trouver('ordres_travail', id).statut === 'Clôturé techniquement'",
                                        arg=OT_EN_COURS)
            # La demande suit juste après l'écriture de l'OT, dans le même geste.
            self.page.wait_for_function("(id) => (Donnees.trouver('demandes', id) || {}).statut === 'Réparée'",
                                        arg=origine["id"])
            self.page.wait_for_load_state("networkidle")
            ecrites = {d["id"]: d for d in lire_csv(dossier / "demandes.csv") if d["ot_id"] == OT_EN_COURS}
            self.assertEqual(set(ecrites), {d["id"] for d in rattachees})
            for demande in ecrites.values():
                self.assertEqual((demande["statut"], demande["mot_technicien"], demande["repare_par"]),
                                 ("Réparée", MOT, technicien["prenom"]))
                self.assertTrue(demande["date_reparation"])
            self.assertIn(MOT, self.texte(".ot-fiche"))                              # repères de l'OT

            # 2. Le demandeur : fiche de l'équipement (route du QR), Signaler, fiche et liste de ses demandes.
            self.changer_profil("demandeur", origine["demandeur"])
            self.aller("#/equipement/" + origine["equipement_id"], ".parc-signaler")
            bloc = self.page.wait_for_selector(".di-dernieres")
            texte_bloc = " ".join(bloc.inner_text().split())
            self.assertIn("Vos dernières demandes sur cette machine", texte_bloc)
            self.assertIn("Réparée le", texte_bloc)
            self.assertIn("par " + technicien["prenom"], texte_bloc)
            self.assertIn(MOT, texte_bloc)
            self.assertNotIn(technicien["nom"], texte_bloc)
            # Le bouton « Signaler un problème » reste le premier geste : avant le bloc.
            self.assertTrue(self.page.evaluate("""() => { const s = document.querySelector('.parc-signaler');
                const b = document.querySelector('.di-dernieres');
                return Boolean(s.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING); }"""))
            self.aller("#/di/nouvelle?equipement=" + origine["equipement_id"], ".di-formulaire")
            self.page.wait_for_selector(".di-dernieres-zone .di-dernieres")
            self.aller("#/di/" + origine["id"], ".di-suivi")
            suivi = self.texte(".di-suivi")
            self.assertIn("Réparée le", suivi)
            self.assertIn(MOT, suivi)
            self.assertNotIn("un ordre de travail a été créé", suivi)
            self.aller("#/di", ".di-compte")
            self.assertIn(MOT, self.texte("#contenu"))

            # 3. Le responsable : filtre « Réparées », mot sur la fiche de l'OT.
            self.changer_profil("responsable")
            self.aller("#/di?statut=R%C3%A9par%C3%A9e", ".di-compte")
            self.assertIn(origine["id"], self.texte(".di-zone-tableau"))
            self.aller("#/ot/" + OT_EN_COURS, ".ot-fiche")
            self.assertIn(MOT, self.texte(".ot-fiche"))


if __name__ == "__main__":
    unittest.main()
