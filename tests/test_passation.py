"""Tests de L16 (lot 2 ergonomie, T557) : passation et renforts (js/modules/ordres-passation.js, ARCHITECTURE.md §14.2
« Passation et renforts »).

Familles :
    regles   : renforts (lecture, écriture), techniciens de l'OT, « Passer la main » proposé, temps manquants, mot de
               relève à montrer ; filtre de la liste sur un technicien (renforts compris) ;
    parcours : en mode serveur sans comptes, Karim passe la main à Julien avec un mot (en tête de la fiche, sur
               l'accueil de Julien), puis Julien à « qui est disponible » (l'OT retourne dans « À prendre » avec son
               mot) ; RG8 refuse un collègue sans l'habilitation ; « Journée terminée » (garder, passer) ; renforts :
               ajout, l'OT chez le renfort, rappel des temps manquants à la clôture sans bloquer, retrait ;
    serveur  : aucun droit nouveau (PUT d'ordres_travail avec relève et renforts : technicien accepté comme avant,
               demandeur et direction 403).

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_passation.py" -v
"""
import time
import unittest

from commun import ServeurPrevo, demo_rg8_bloquante
import test_acces_roles as roles
from test_ordres_prise import CasPrise, ot_sur_disque, lire_csv, KARIM, JULIEN, THOMAS


class CasPassation(CasPrise):

    def attendre(self, serveur, ot_id, condition, delai_s=10):
        fin = time.time() + delai_s
        while True:
            ligne = ot_sur_disque(serveur.dossier, ot_id)
            if condition(ligne) or time.time() > fin:
                return ligne
            time.sleep(0.2)

    def fenetre(self):
        return "dialog.dialogue[open]"

    def valider_fenetre(self):
        self.page.click("dialog.dialogue[open] .fenetre-actions .btn-primaire")


class TestReglesPassation(CasPassation):

    def test_regles(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            evaluer = self.page.evaluate
            self.assertEqual(evaluer("Ordres.lireRenforts(' TEC-0001, ,TEC-0003,TEC-0001 ')"), ["TEC-0001", "TEC-0003"])
            self.assertEqual(evaluer("Ordres.ecrireRenforts(['TEC-0003', '', 'TEC-0003', 'TEC-0001'])"), "TEC-0003,TEC-0001")
            self.assertEqual(evaluer("Ordres.techniciensDeLOt({ technicien_id: 'TEC-0002', renforts: 'TEC-0001,TEC-0002' })"),
                             ["TEC-0002", "TEC-0001"])
            self.assertEqual(evaluer("Ordres.techniciensDeLOt({ technicien_id: '', renforts: 'TEC-0001' })"), ["TEC-0001"])
            self.assertTrue(evaluer("Ordres.estTechnicienDeLOt({ technicien_id: 'TEC-0002', renforts: 'TEC-0001' }, 'TEC-0001')"))
            self.assertFalse(evaluer("Ordres.estTechnicienDeLOt({ technicien_id: 'TEC-0002', renforts: 'TEC-0001' }, 'TEC-0004')"))
            self.assertFalse(evaluer("Ordres.estTechnicienDeLOt({ technicien_id: '', renforts: '' }, '')"))
            # « Passer la main » : OT ouvert, à mon nom (principal) seulement
            self.assertTrue(evaluer("Ordres.passationPossible({ statut: 'En cours', technicien_id: 'TEC-0002' }, 'TEC-0002')"))
            self.assertFalse(evaluer("Ordres.passationPossible({ statut: 'En cours', technicien_id: 'TEC-0001', renforts: 'TEC-0002' }, 'TEC-0002')"))
            self.assertFalse(evaluer("Ordres.passationPossible({ statut: 'Clôturé techniquement', technicien_id: 'TEC-0002' }, 'TEC-0002')"))
            self.assertFalse(evaluer("Ordres.passationPossible({ statut: 'Créé', technicien_id: '' }, '')"))
            # temps manquants : seulement pour un OT fait à plusieurs, sauf celui qui clôture
            self.assertEqual(evaluer("""Ordres.tempsManquants({ technicien_id: 'A', renforts: 'B,C' },
                [{ technicien_id: 'B', heures: '1.5' }, { technicien_id: 'C', heures: '0' }], 'A')"""), ["C"])
            self.assertEqual(evaluer("Ordres.tempsManquants({ technicien_id: 'A', renforts: '' }, [], 'B')"), [])
            self.assertEqual(evaluer("Ordres.tempsManquants({ technicien_id: 'A', renforts: 'B' }, [], '')"), ["A", "B"])
            # mot de relève sur une carte : main passée, et celui qui l'a passée ne tient plus l'OT
            self.assertTrue(evaluer("Ordres.releveAMontrer({ technicien_id: 'B', releve_par: 'A', releve_le: '2026-11-15 17:00' })"))
            self.assertTrue(evaluer("Ordres.releveAMontrer({ technicien_id: '', releve_par: 'A', releve_le: '2026-11-15 17:00' })"))
            self.assertFalse(evaluer("Ordres.releveAMontrer({ technicien_id: 'A', releve_par: 'A', releve_le: '2026-11-15 17:00' })"))
            self.assertFalse(evaluer("Ordres.releveAMontrer({ technicien_id: 'B', releve_par: '', releve_le: '' })"))
            # T567 : la ligne de prise d'une passation (précédent = releve_par, à la minute de releve_le) n'est pas
            # une reprise : ni « Vos OT repris » chez celui qui a passé la main, ni « Reprises récentes »
            ot_passe = ("{ id: 'OT-9', statut: 'En cours', technicien_id: 'B', releve_par: 'A', releve_le: '2026-11-15 17:00', "
                        "prises_en_charge: '2026-11-14 08:00|A|\\n2026-11-15 17:00|B|A' }")
            self.assertTrue(evaluer("Ordres.estPassation(%s, { date: '2026-11-15 17:00', technicienId: 'B', precedentId: 'A' })" % ot_passe))
            self.assertFalse(evaluer("Ordres.estPassation(%s, { date: '2026-11-14 08:00', technicienId: 'A', precedentId: '' })" % ot_passe))
            self.assertFalse(evaluer("Ordres.estPassation(%s, { date: '2026-11-15 17:05', technicienId: 'B', precedentId: 'A' })" % ot_passe))
            self.assertEqual(evaluer("Ordres.reprisesRecentes([%s], '2026-11-01', 'A').length" % ot_passe), 0)
            self.assertEqual(evaluer("Ordres.reprisesRecentes([%s], '2026-11-01').length" % ot_passe), 0)
            ot_repris = ot_passe.replace("releve_par: 'A'", "releve_par: ''")     # même ligne sans passation : reprise
            self.assertEqual(evaluer("Ordres.reprisesRecentes([%s], '2026-11-01', 'A').length" % ot_repris), 1)
            # liste filtrée sur un technicien : ses OT et ceux où il est en renfort
            ids = evaluer("""Ordres.filtrer([
                { id: 'A', statut: 'En cours', technicien_id: 'TEC-0001', renforts: '' },
                { id: 'B', statut: 'En cours', technicien_id: 'TEC-0002', renforts: 'TEC-0001' },
                { id: 'C', statut: 'En cours', technicien_id: 'TEC-0002', renforts: '' }],
                { etat: 'ouverts', technicien: 'TEC-0001' }).map((o) => o.id)""")
            self.assertEqual(ids, ["A", "B"])


class TestParcoursPassation(CasPassation):

    def test_passer_la_main_mot_en_tete_et_sur_l_accueil(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            ot = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Fuite L16", "technicien_id": KARIM,
                                "priorite": "P1", "date_prevue": "2026-01-02"})      # en tête de « À prendre » (5 OT)
            self.page.evaluate("id => Ordres.changerStatut(id, 'Créé', 'En cours', {})", ot)
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.aller_fiche(ot)
            self.page.click("#ot-passer-main")
            self.page.wait_for_selector(self.fenetre())
            # rien de choisi : la fenêtre le dit, rien n'est écrit
            self.valider_fenetre()
            self.page.wait_for_selector("dialog.dialogue[open] .erreur-champ:not([hidden])")
            self.assertEqual(ot_sur_disque(serveur.dossier, ot)["technicien_id"], KARIM)
            self.page.check("dialog.dialogue[open] input[name=releve_motif][value='pas le temps']")
            self.page.select_option("#ot-passation-a", JULIEN)
            self.assertEqual(self.page.locator("dialog.dialogue[open] textarea[name=releve_mot][data-dictee]").count(), 1)
            self.page.fill("dialog.dialogue[open] textarea[name=releve_mot]", "Joint changé, reste à resserrer la bride.")
            self.valider_fenetre()
            ligne = self.attendre(serveur, ot, lambda o: o["technicien_id"] == JULIEN)
            self.assertEqual((ligne["technicien_id"], ligne["statut"], ligne["releve_par"], ligne["releve_motif"]),
                             (JULIEN, "En cours", KARIM, "pas le temps"))
            self.assertEqual(ligne["releve_mot"], "Joint changé, reste à resserrer la bride.")
            self.assertRegex(ligne["releve_le"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
            # T567 : la passation ajoute sa ligne aux prises en charge (Julien, avant : Karim, à la minute de la relève)
            prises = [p.split("|") for p in ligne["prises_en_charge"].replace("\r", "").split("\n") if p.strip()]
            self.assertEqual(prises[-1], [ligne["releve_le"], JULIEN, KARIM])
            nombre_prises = len(prises)
            journal = [j for j in lire_csv(serveur.dossier, "journal.csv") if j["id_ligne"] == ot]
            self.assertTrue(any("main passée à " + JULIEN in j["action"] for j in journal), journal)
            # le mot en tête de la fiche, avec le nom et l'heure ; plus de « Passer la main » pour Karim
            self.page.wait_for_selector(".ot-releve-bandeau")
            tete = self.page.inner_text(".ot-releve-bandeau")
            self.assertIn("Mot de relève de Karim", tete)
            self.assertIn(ligne["releve_le"][11:16], tete)
            self.assertIn("resserrer la bride", tete)
            self.assertEqual(self.page.locator("#ot-passer-main").count(), 0)
            self.page.wait_for_selector(".ot-prises")
            self.assertIn("Karim a passé la main à Julien", self.page.inner_text(".ot-prises"))
            # celui qui a passé la main n'est pas « repris » sur son accueil
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.page.wait_for_selector(".accueil-mes-ordres, .accueil-a-prendre")
            self.assertEqual(self.page.locator(".accueil-reprises").count(), 0)

            # Julien : l'OT dans « Mes ordres de travail », avec le mot
            self.changer_profil(serveur, "#/accueil", "technicien", JULIEN, "Julien Moreau")
            self.page.wait_for_selector(".accueil-mes-ordres .accueil-releve")
            carte = self.page.inner_text(".accueil-mes-ordres li:has(a[href='#/ot/%s'])" % ot)
            self.assertIn("Mot de Karim", carte)
            self.assertIn("resserrer la bride", carte)
            # Julien la passe à qui est disponible : « À prendre », avec son mot (il n'en écrit pas : motif dit)
            self.aller_fiche(ot)
            self.page.click("#ot-passer-main")
            self.page.wait_for_selector(self.fenetre())
            self.page.check("dialog.dialogue[open] input[name=releve_motif][value='fin de journée']")
            self.page.select_option("#ot-passation-a", "__disponible")
            self.valider_fenetre()
            ligne = self.attendre(serveur, ot, lambda o: o["technicien_id"] == "")
            self.assertEqual((ligne["technicien_id"], ligne["releve_par"], ligne["releve_mot"]), ("", JULIEN, ""))
            # à qui est disponible : aucune ligne de prise (l'OT n'a plus de technicien)
            self.assertEqual(len([p for p in ligne["prises_en_charge"].split("\n") if p.strip()]), nombre_prises)
            self.changer_profil(serveur, "#/accueil", "technicien", THOMAS, "Thomas Garnier")
            self.page.wait_for_selector(".accueil-a-prendre")
            carte = self.page.inner_text(".accueil-a-prendre li:has(a[href='#/ot/%s'])" % ot)
            self.assertIn("Passé par Julien (fin de journée)", carte)

    def test_rg8_journee_terminee_et_attente_equipe(self):
        with ServeurPrevo(demo_rg8_bloquante()) as serveur:          # L19 (T556) : RG8 réglée « bloquante »
            self.ouvrir(serveur, "#/ot")
            exige = self.creer_ot({"equipement_id": "EQ-0012", "titre": "Armoire L16", "technicien_id": JULIEN,
                                   "date_prevue": "2026-10-21"})
            garde = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Garde L16", "technicien_id": KARIM})
            passe = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Passe L16", "technicien_id": KARIM})
            for ot in (garde, passe):
                self.page.evaluate("id => Ordres.changerStatut(id, 'Créé', 'En cours', {})", ot)
            self.changer_profil(serveur, "#/accueil", "technicien", JULIEN, "Julien Moreau")
            # RG8 : Thomas n'a plus l'habilitation BR (échue), la passation est refusée dans la fenêtre, rien d'écrit
            self.aller_fiche(exige)
            avant = ot_sur_disque(serveur.dossier, exige)
            self.page.click("#ot-passer-main")
            self.page.wait_for_selector(self.fenetre())
            self.page.check("dialog.dialogue[open] input[name=releve_motif][value='autre']")
            self.page.select_option("#ot-passation-a", THOMAS)
            self.valider_fenetre()
            self.page.wait_for_function("() => /BR/.test(document.querySelector('dialog.dialogue[open]').innerText)")
            self.assertEqual(ot_sur_disque(serveur.dossier, exige), avant)
            self.page.click("dialog.dialogue[open] .fenetre-actions .btn-fantome")

            # « Journée terminée » : chaque OT ouvert à son nom ; « Je le garde » d'office
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.page.click("button[data-action=journee-terminee]")
            self.page.wait_for_selector(self.fenetre())
            self.assertEqual(self.page.locator("fieldset[data-ot='%s']" % exige).count(), 0)      # pas à son nom
            for ot in (garde, passe):
                self.assertTrue(self.page.is_checked("fieldset[data-ot='%s'] input[value=garde]" % ot))
            bloc = "fieldset[data-ot='%s']" % passe
            self.page.check(bloc + " input[value=passe]")
            self.valider_fenetre()                                   # collègue non choisi : dit, rien d'écrit
            self.page.wait_for_function("id => /" + "Choisissez à qui passer" + "/.test(document.querySelector('dialog.dialogue[open]').innerText)", arg=passe)
            self.page.select_option(bloc + " select[data-role=a]", JULIEN)
            self.page.fill(bloc + " textarea[data-role=mot]", "Carter ouvert.")
            self.valider_fenetre()
            ligne = self.attendre(serveur, passe, lambda o: o["technicien_id"] == JULIEN)
            self.assertEqual((ligne["technicien_id"], ligne["releve_motif"], ligne["releve_mot"], ligne["statut"]),
                             (JULIEN, "fin de journée", "Carter ouvert.", "En cours"))
            gardee = ot_sur_disque(serveur.dossier, garde)
            self.assertEqual((gardee["technicien_id"], gardee["statut"], gardee["releve_le"]), (KARIM, "En cours", ""))

            # L14 : Julien met l'OT en attente ; Thomas le voit dans « En attente dans l'équipe » avec le mot
            self.page.evaluate("id => Ordres.changerStatut(id, 'En cours', 'En attente', { motif_attente: 'pièce' })", passe)
            self.changer_profil(serveur, "#/accueil", "technicien", THOMAS, "Thomas Garnier")
            self.page.wait_for_selector(".accueil-en-attente-equipe .accueil-releve")
            carte = self.page.inner_text(".accueil-en-attente-equipe li:has(a[href='#/ot/%s'])" % passe)
            self.assertIn("pièce", carte)
            self.assertIn("Carter ouvert.", carte)

    def test_renforts_accueil_cloture_et_retrait(self):
        with ServeurPrevo() as serveur:
            self.ouvrir(serveur, "#/ot")
            ot = self.creer_ot({"equipement_id": "EQ-0005", "titre": "Moteur L16", "technicien_id": KARIM})
            self.page.evaluate("id => Ordres.changerStatut(id, 'Créé', 'En cours', {})", ot)
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.aller_fiche(ot)
            self.page.click("#ot-ajouter-renfort")
            self.page.wait_for_selector(self.fenetre())
            self.assertIn("Karim Benali reste le technicien principal", self.page.inner_text(self.fenetre()))
            self.assertEqual(self.page.locator("#ot-renfort option[value='%s']" % KARIM).count(), 0)
            self.page.select_option("#ot-renfort", JULIEN)
            self.valider_fenetre()
            ligne = self.attendre(serveur, ot, lambda o: o["renforts"] == JULIEN)
            self.assertEqual((ligne["technicien_id"], ligne["renforts"]), (KARIM, JULIEN))
            self.page.wait_for_selector(".ot-renforts")
            self.assertIn("Julien", self.page.inner_text(".ot-renforts"))

            # Julien : l'OT chez lui, marqué « Renfort » ; il saisit son temps ; pas de « Passer la main » pour lui
            self.changer_profil(serveur, "#/accueil", "technicien", JULIEN, "Julien Moreau")
            self.page.wait_for_selector(".accueil-mes-ordres a[href='#/ot/%s']" % ot)
            self.assertIn("Renfort", self.page.inner_text(".accueil-mes-ordres li:has(a[href='#/ot/%s'])" % ot))
            self.aller_fiche(ot)
            self.assertEqual(self.page.locator("#ot-passer-main").count(), 0)
            self.assertEqual(self.page.locator("#ot-ajouter-renfort").count(), 1)

            # Thomas en second renfort (par Julien), sans temps : à la clôture par Karim, le rappel nomme Julien et
            # Thomas sans rien bloquer de plus que RG4
            self.page.evaluate("([id, t]) => Ordres.ajouterRenfort(id, t)", [ot, THOMAS])
            self.page.evaluate("""id => Donnees.modifier('ot_temps', (lignes, outils) => {
                lignes.push({ id: outils.nouvelId(lignes), ot_id: id, technicien_id: 'TEC-0001', date: Donnees.aujourdhui(), heures: '2' }); })""", ot)
            self.changer_profil(serveur, "#/accueil", "technicien", KARIM, "Karim Benali")
            self.aller_fiche(ot)
            self.page.click(".ot-actions button[data-cible='Clôturé techniquement']")
            self.page.wait_for_selector(".ot-cloture-temps-renforts")
            rappel = self.page.inner_text(".ot-cloture-temps-renforts")
            self.assertIn("Thomas", rappel)
            self.assertNotIn("Julien", rappel)
            self.assertNotIn("Karim", rappel)
            manques = self.page.inner_text(".ot-cloture-manques")
            self.assertNotIn("Thomas", manques)
            self.page.click("dialog.dialogue[open] .fenetre-actions .btn-fantome")

            # Retrait d'un renfort (confirmation) : Thomas n'est plus sur l'OT
            self.aller_fiche(ot)
            self.page.click("button[data-action=retirer-renfort][data-technicien='%s']" % THOMAS)
            self.page.wait_for_selector(self.fenetre())
            self.valider_fenetre()
            ligne = self.attendre(serveur, ot, lambda o: o["renforts"] == JULIEN)
            self.assertEqual(ligne["renforts"], JULIEN)


class TestDroitsServeurPassation(unittest.TestCase):
    """Aucun droit nouveau : un technicien écrit ordres_travail comme avant (pas de règle par OT au serveur), le
    demandeur et la Direction restent refusés, relève et renforts compris."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        roles.setUpModule()
        roles.lancer_serveur_comptes(cls)

    def test_put_releve_et_renforts(self):
        chemin = self.serveur.dossier / "ordres_travail.csv"
        disque = chemin.read_bytes()
        entete, lignes = roles.lire_tableau(disque)
        cible = next(l for l in lignes if l[entete.index("statut")] in ("En cours", "Créé", "Préparé"))
        for colonne, valeur in (("renforts", "TEC-0003"), ("releve_par", "TEC-0002"), ("releve_le", "2026-11-15 17:30"),
                                ("releve_motif", "fin de journée"), ("releve_mot", "Mot de relève d'essai")):
            cible[entete.index(colonne)] = valeur
        corps = roles.ecrire_tableau(entete, lignes)
        for role in ("demandeur", "direction"):
            with self.subTest(role=role):
                reponse = self.client.requete("PUT", "/api/csv/ordres_travail", corps, cookie=self.cookies[role],
                                              entetes={"X-Version-Attendue": roles.version_de(disque)})
                self.assertTrue(reponse.refus_de_role(), (reponse.statut, reponse.octets[:200]))
                self.assertEqual(chemin.read_bytes(), disque)
        recu = self.client.requete("GET", "/api/csv/ordres_travail", cookie=self.cookies["technicien"])
        reponse = self.client.requete("PUT", "/api/csv/ordres_travail", corps, cookie=self.cookies["technicien"],
                                      entetes={"X-Version-Attendue": recu.entetes["x-version"]})
        self.assertEqual(reponse.statut, 200, reponse.octets[:300])
        apres = {l[0]: l for l in roles.lire_tableau(chemin.read_bytes())[1]}
        self.assertEqual(apres[cible[0]][entete.index("renforts")], "TEC-0003")
        self.assertEqual(apres[cible[0]][entete.index("releve_motif")], "fin de journée")


if __name__ == "__main__":
    unittest.main()
