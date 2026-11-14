"""Lot 1 ergonomie, T518 (thème « qr-4g » de l'étude d'ergonomie) : le QR flashé hors du Wi-Fi de l'atelier donne une
page d'erreur du navigateur, sans un mot de Prévo. Prévo ne peut pas l'empêcher (limite du réseau) ; il le dit :

    regles      Parc.porteeAdresse et Parc.estLocaleOuPrivee (127.0.0.0/8, localhost, ::1 → « ce-pc » ; 10/8,
                172.16/12, 192.168/16, 169.254/16, noms sans point, .local/.lan/.home, fe80::/10, fc00::/7 → « locale » ;
                100.64.0.0/10, *.ts.net → « tailscale » ; le reste → « exterieur » ; « GMAO:<id> » → '') et
                Parc.consigneEtiquette (la ligne imprimée au-dessus du QR, avec ou sans nom de Wi-Fi) ;
    etiquettes  adresse du réseau de l'atelier : chaque étiquette porte la consigne « Connectez-vous au Wi-Fi de
                l'usine… », au-dessus du QR et du repère, sans les rogner, dans l'aperçu et à l'impression, formats 24 et 8 ;
                l'avertissement (conséquence en 4G, deux solutions, lien vers la portée) et le rappel en tête de
                l'aperçu ; le nom du Wi-Fi enregistré (parametres.csv, wifi_nom) passe dans la consigne ;
    tailscale   adresse Tailscale : consigne « Ouvrez l'application Tailscale… » et l'avertissement qui va avec ;
    exterieur   adresse joignable de partout : ni consigne, ni avertissement, ni champ du Wi-Fi ;
    acces       Paramètres › Accès et installation (PC serveur, responsable) : l'avertissement suit l'adresse des QR.

Lancer depuis la racine du projet :
    py -X utf8 -m unittest discover -s tests -p "test_etiquettes_reseau.py" -v
"""
import csv
import io
import json
import re
import unittest

import test_parametres_acces as acces
from commun import ServeurPrevo, attendre_pret, preregler_profil
from test_etiquettes import CasEtiquettes, DECODER_QR_JS, ESPION_IMPRESSION_JS

CONSIGNE_WIFI = "Connectez-vous au Wi-Fi de l'usine pour déclarer une panne"
CONSIGNE_TAILSCALE = "Ouvrez l'application Tailscale sur ce téléphone pour déclarer une panne"
CONSIGNE_WIFI_NOMMEE = "Connectez-vous au Wi-Fi «\u00a0Atelier-Prod\u00a0» pour déclarer une panne"
CONSEQUENCE_4G = "en 4G par exemple"

# Portées attendues de Parc.porteeAdresse.
CAS_PORTEE = {
    "http://127.0.0.1:8080/": "ce-pc", "http://127.8.9.10/": "ce-pc", "http://localhost:8080/": "ce-pc",
    "http://LOCALHOST/": "ce-pc", "http://[::1]:8080/": "ce-pc", "http://0.0.0.0:8080/": "ce-pc",
    "http://10.0.0.5:8080/": "locale", "http://10.255.255.255/": "locale",
    "http://172.16.0.1/": "locale", "http://172.31.255.254:8443/": "locale",
    "http://172.15.0.1/": "exterieur", "http://172.32.0.1/": "exterieur",
    "http://192.168.1.10:8080/": "locale", "https://192.168.50.10:8443/": "locale",
    "http://192.169.1.1/": "exterieur", "http://169.254.10.20/": "locale",
    "http://atelier-pc:8080/": "locale", "http://atelier-pc.local:8080/": "locale", "http://gmao.lan/": "locale",
    "http://pc-maintenance.home/": "locale", "http://ATELIER-PC.LOCAL./": "locale",
    "http://[fe80::1]:8080/": "locale", "http://[febf::1]/": "locale", "http://[fec0::1]/": "exterieur",
    "http://[fd12:3456::1]/": "locale", "http://[fc00::1]/": "locale", "http://[2001:db8::1]/": "exterieur",
    "http://100.64.0.1/": "tailscale", "http://100.101.102.103:8080/": "tailscale", "http://100.127.255.254/": "tailscale",
    "http://100.63.0.1/": "exterieur", "http://100.128.0.1/": "exterieur",
    "https://pc-atelier.tail1234.ts.net/": "tailscale",
    "https://gmao.exemple.fr/": "exterieur", "http://8.8.8.8/": "exterieur", "https://prevo.local.exemple.fr/": "exterieur",
    "GMAO:EQ-0001": "", "": "", "pas une adresse": "", "ftp://192.168.1.10/": "",
}

# Pour chaque étiquette d'une zone : la consigne (texte, lignes non coupées), et les rectangles du QR, du repère, du
# bloc de texte et de la consigne, relatifs à l'étiquette.
MESURER_CONSIGNES_JS = """(selecteur) => Array.from(document.querySelectorAll(selecteur + ' .etiquette')).map((e) => {
  const r = e.getBoundingClientRect();
  const rect = (el) => { if (!el) return null; const b = el.getBoundingClientRect();
    return { haut: b.top - r.top, bas: b.bottom - r.top, gauche: b.left - r.left, droite: b.right - r.left, largeur: b.width }; };
  const consigne = e.querySelector('.etiquette-consigne');
  return { id: e.dataset.equipement, grand: !!e.closest('.format-8'), hauteur: r.height, largeur: r.width,
    consigne: consigne ? consigne.textContent.trim() : null,
    pt: consigne ? parseFloat(getComputedStyle(consigne).fontSize) * 0.75 : 0,
    coupee: consigne ? consigne.scrollHeight > consigne.clientHeight + 1 : false,
    qr: rect(e.querySelector('svg.qr-svg')), repere: rect(e.querySelector('.etiquette-repere')),
    texte: rect(e.querySelector('.etiquette-texte')), zone: rect(consigne) };
})"""


def lire_parametres(dossier):
    texte = (dossier / "parametres.csv").read_bytes().decode("utf-8-sig")
    return {l["cle"]: l["valeur"] for l in csv.DictReader(io.StringIO(texte), delimiter=";")}


class CasReseau(CasEtiquettes):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serveur = ServeurPrevo()
        cls.serveur.demarrer()
        cls.addClassCleanup(cls.serveur.arreter)

    def ouvrir(self, adresses, serveur=None, route="#/parc/etiquettes"):
        """L'application, /api/info remplacé par « adresses » (gabarits avec %d pour le port)."""
        serveur = serveur or self.serveur
        corps = json.dumps({"port": serveur.port, "adresse_locale": "http://localhost:%d/" % serveur.port,
                            "adresses_reseau": [a % serveur.port if "%d" in a else a for a in adresses]})
        self.page.route(re.compile(r".*/api/info$"),
                        lambda route_: route_.fulfill(status=200, content_type="application/json; charset=utf-8", body=corps))
        preregler_profil(self.contexte, "responsable")
        self.page.goto(serveur.url + "/")
        attendre_pret(self.page)
        self.aller(route)
        return self.page

    def choisir_format(self, format_):
        self.page.select_option("#etiquettes-format", format_)
        self.page.wait_for_function("(f) => document.querySelector('#etiquettes-apercu .planche-etiquettes.format-' + f) !== null",
                                    arg=format_)

    def verifier_consignes(self, selecteur, attendue):
        """Chaque étiquette de la zone porte « attendue », entière, AU-DESSUS du QR et du texte, dans l'étiquette."""
        mesures = self.page.evaluate(MESURER_CONSIGNES_JS, selecteur)
        self.assertTrue(mesures, "aucune étiquette dans " + selecteur)
        for m in mesures:
            with self.subTest(zone=selecteur, equipement=m["id"]):
                self.assertEqual(m["consigne"], attendue)
                self.assertFalse(m["coupee"], "consigne coupée : %r" % m)
                # En gros (L10) : au moins 8 pt sur la planche de 24, 14 pt sur celle de 8.
                if len(m["consigne"]) <= 60: self.assertGreaterEqual(m["pt"], 13.9 if m["grand"] else 7.9, "consigne trop petite : %r" % m)
                z, qr, repere, texte = m["zone"], m["qr"], m["repere"], m["texte"]
                self.assertLessEqual(z["bas"], qr["haut"] + 0.5, "consigne sur le QR : %r" % m)
                self.assertLessEqual(z["bas"], repere["haut"] + 0.5, "consigne sur le repère : %r" % m)
                self.assertLessEqual(z["bas"], texte["haut"] + 0.5, "consigne sur la désignation : %r" % m)
                for boite in (z, qr, repere):
                    self.assertGreaterEqual(boite["haut"], -0.5, m)
                    self.assertLessEqual(boite["bas"], m["hauteur"] + 0.5, m)
                    self.assertGreaterEqual(boite["gauche"], -0.5, m)
                    self.assertLessEqual(boite["droite"], m["largeur"] + 0.5, m)
        return mesures


class TestPorteeEtConsigne(CasReseau):

    def test_regles_portee_de_chaque_adresse_et_ligne_imprimee(self):
        page = self.ouvrir(["http://192.168.50.10:%d/"], route="#/parc")
        lues = page.evaluate("(cas) => Object.fromEntries(cas.map((a) => [a, Parc.porteeAdresse(a)]))", list(CAS_PORTEE))
        self.assertEqual(lues, CAS_PORTEE)
        locales = page.evaluate("(cas) => cas.filter((a) => Parc.estLocaleOuPrivee(a))", list(CAS_PORTEE))
        self.assertEqual(sorted(locales), sorted(a for a, p in CAS_PORTEE.items() if p in ("ce-pc", "locale")))
        consignes = page.evaluate("""() => [
            Parc.consigneEtiquette('http://192.168.1.10:8080/', ''),
            Parc.consigneEtiquette('http://192.168.1.10:8080/', '  Atelier-Prod  '),
            Parc.consigneEtiquette('https://pc.tail1234.ts.net/', 'Atelier-Prod'),
            Parc.consigneEtiquette('https://gmao.exemple.fr/', 'Atelier-Prod'),
            Parc.consigneEtiquette('http://localhost:8080/', ''),
            Parc.consigneEtiquette('GMAO:EQ-0001', '')]""")
        self.assertEqual(consignes, [CONSIGNE_WIFI, CONSIGNE_WIFI_NOMMEE, CONSIGNE_TAILSCALE, "", "", ""])
        self.assertEqual(page.evaluate("Parc.avertissementReseau('https://gmao.exemple.fr/', {})"), "")
        self.assertEqual(page.evaluate("Parc.avertissementReseau('GMAO:EQ-0001', {})"), "")


class TestEtiquettesAtelier(CasReseau):

    def test_consigne_sur_chaque_etiquette_apercu_et_impression_formats_24_et_8_puis_nom_du_wifi(self):
        with ServeurPrevo() as serveur:
            page = self.ouvrir(["http://192.168.50.10:%d/"], serveur)
            page.evaluate(ESPION_IMPRESSION_JS)
            # Avertissement : conséquence en 4G, deux solutions, lien vers la portée ; rappel en tête de l'aperçu.
            avertissement = page.locator("#etiquettes-avertissement-reseau .avertissement-reseau[data-portee='locale']")
            self.assertEqual(avertissement.count(), 1)
            texte = avertissement.inner_text()
            self.assertIn(CONSEQUENCE_4G, texte)
            self.assertIn("page d'erreur de son navigateur, pas Prévo", texte)
            self.assertIn("Aussi hors de l'atelier", texte)
            self.assertIn("Tailscale", texte)
            self.assertIn("réimprimer les étiquettes", texte)
            self.assertEqual(avertissement.locator("a[href='#/parametres']").count(), 1)
            rappel = page.inner_text("#etiquettes-rappel-consigne")
            self.assertIn(CONSIGNE_WIFI, rappel)
            page.click("#etiquettes-voir-avertissement")
            page.wait_for_function("document.activeElement && document.activeElement.id === 'etiquettes-avertissement-reseau'")
            # Le rappel est hors des planches : rien de plus n'est imprimé que les étiquettes.
            self.assertEqual(page.locator("#etiquettes-apercu #etiquettes-rappel-consigne").count(), 0)

            for format_ in ("24", "8"):
                with self.subTest(format=format_):
                    self.choisir_format(format_)
                    self.verifier_consignes("#etiquettes-apercu", CONSIGNE_WIFI)
                    # Le QR reste lisible : il mène toujours à la fiche.
                    lues = page.evaluate(DECODER_QR_JS, "#etiquettes-apercu")
                    self.assertTrue(all(l["qr"] and l["qr"].startswith("http://192.168.50.10:%d/#/equipement/" % serveur.port)
                                        for l in lues), lues[:3])
                    # Impression : mêmes étiquettes dans #impression, consigne comprise.
                    page.click("#etiquettes-imprimer")
                    page.emulate_media(media="print")
                    self.verifier_consignes("#impression", CONSIGNE_WIFI)
                    page.evaluate("() => { document.getElementById('impression').textContent = ''; }")
                    page.emulate_media(media="screen")

            # Nom du Wi-Fi : enregistré dans parametres.csv (wifi_nom), repris par la consigne et le rappel.
            page.fill("#etiquettes-wifi", "  Atelier-Prod ")
            page.click("#etiquettes-wifi-enregistrer")
            attendue = CONSIGNE_WIFI_NOMMEE
            page.wait_for_function("(t) => { const c = document.querySelector('#etiquettes-apercu .etiquette-consigne'); return c && c.textContent.trim() === t; }",
                                   arg=attendue)
            self.assertEqual(lire_parametres(serveur.dossier).get("wifi_nom"), "Atelier-Prod")
            self.assertIn(attendue, page.inner_text("#etiquettes-rappel-consigne"))
            self.assertEqual(page.input_value("#etiquettes-wifi"), "Atelier-Prod")
            for format_ in ("24", "8"):
                with self.subTest(format=format_, wifi=True):
                    self.choisir_format(format_)
                    self.verifier_consignes("#etiquettes-apercu", attendue)
            # Un nom très long ne rogne rien : la consigne tient en deux lignes au plus (coupée par « … » sinon).
            page.fill("#etiquettes-wifi", "Atelier-Production-Batiment-B-Etage-2")
            page.click("#etiquettes-wifi-enregistrer")
            page.wait_for_function("() => (document.querySelector('#etiquettes-apercu .etiquette-consigne') || {}).textContent.includes('Etage-2')")
            for format_ in ("24", "8"):
                with self.subTest(format=format_, wifi="long"):
                    self.choisir_format(format_)
                    mesures = page.evaluate(MESURER_CONSIGNES_JS, "#etiquettes-apercu")
                    for m in mesures:
                        self.assertFalse(m["coupee"], m)
                        self.assertLessEqual(m["zone"]["bas"], m["qr"]["haut"] + 0.5, m)
            # Effacé : retour à « le Wi-Fi de l'usine ».
            page.fill("#etiquettes-wifi", "")
            page.click("#etiquettes-wifi-enregistrer")
            page.wait_for_function("(t) => (document.querySelector('#etiquettes-apercu .etiquette-consigne') || {}).textContent === t",
                                   arg=CONSIGNE_WIFI)
            self.assertEqual(lire_parametres(serveur.dossier).get("wifi_nom"), "")


class TestEtiquettesTailscaleEtExterieur(CasReseau):

    def test_adresse_tailscale_consigne_de_l_application_et_avertissement(self):
        page = self.ouvrir(["http://100.101.102.103:%d/"])
        self.verifier_consignes("#etiquettes-apercu", CONSIGNE_TAILSCALE)
        avertissement = page.locator("#etiquettes-avertissement-reseau .avertissement-reseau[data-portee='tailscale']")
        self.assertEqual(avertissement.count(), 1)
        self.assertIn("page d'erreur de son navigateur, pas Prévo", avertissement.inner_text())
        self.assertEqual(page.locator("#etiquettes-wifi").count(), 0)          # pas de Wi-Fi à nommer
        self.assertIn(CONSIGNE_TAILSCALE, page.inner_text("#etiquettes-rappel-consigne"))

    def test_adresse_joignable_de_partout_ni_consigne_ni_avertissement(self):
        page = self.ouvrir(["https://gmao.exemple.fr/"])
        self.assertTrue(page.locator("#etiquettes-apercu .etiquette").count() > 0)
        self.assertEqual(page.locator(".etiquette-consigne, .etiquette.avec-consigne").count(), 0)
        self.assertEqual(page.locator(".avertissement-reseau, #etiquettes-rappel-consigne, #etiquettes-wifi").count(), 0)


class TestParametresAcces(acces.CasAcces):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not acces.COMPTES_JSON:
            acces.setUpModule()

    def test_avertissement_suit_l_adresse_des_qr(self):
        page = self.page
        instance = self.lancer()
        donnees = self.dossier / "donnees"
        from test_socle_lot3 import ecrire_parametre
        ecrire_parametre(donnees, "adresse_qr", "http://192.168.50.10:8080/")
        self.session(instance)
        self.ouvrir_parametres(instance.url)
        self.attendre_carte()
        avertissement = page.locator("#acces-avertissement-qr .avertissement-reseau[data-portee='locale']")
        self.assertEqual(avertissement.count(), 1)
        texte = avertissement.inner_text()
        self.assertIn("http://192.168.50.10:8080/", texte)
        self.assertIn(CONSEQUENCE_4G, texte)
        self.assertIn("Aussi hors de l'atelier", texte)
        self.assertEqual(avertissement.locator("a[href='#/parc/etiquettes']").count(), 1)
        # Adresse joignable de partout : plus d'avertissement.
        ecrire_parametre(donnees, "adresse_qr", "https://gmao.exemple.fr/")
        page.reload()
        attendre_pret(page)
        page.wait_for_selector("#carte-sauvegardes")
        self.attendre_carte()
        self.assertEqual(page.locator("#acces-avertissement-qr .avertissement-reseau").count(), 0)


if __name__ == "__main__":
    unittest.main()
