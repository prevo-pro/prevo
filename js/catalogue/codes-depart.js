'use strict';
// Codes de défaillance de départ (T515, correction A2 du lot 1 ergonomie) : une base NEUVE les reçoit, écrits dans la
// langue de l'installation choisie à sa création (les libellés deviennent alors des données de l'utilisateur : ils se
// modifient et se suppriment dans Paramètres › Codes de défaillance). Une seule source pour le navigateur (« Créer une
// base vide », bouton « Ajouter la liste de départ ») et pour le serveur (serveur.py, codes_de_depart : base « vide » de
// l'assistant d'installation), qui lit tel quel le JSON écrit entre les deux lignes repères « // <json> » et
// « // </json> ». Codes communs à toutes les langues (uniques dans toute la table, 12 caractères au plus) ; libellé de
// chaque langue déclarée (repli sur le français). La démonstration garde ses propres codes (js/demo-donnees.js).
(function () {
  'use strict';
  const LISTE =
// <json>
{"langues": ["fr", "en", "tr", "it", "pt-PT"], "codes": [
  {"famille": "symptôme", "code": "S-ARRET", "libelle": {"fr": "Machine arrêtée", "en": "Machine stopped", "tr": "Makine durdu", "it": "Macchina ferma", "pt-PT": "Máquina parada"}},
  {"famille": "symptôme", "code": "S-DEMARRAGE", "libelle": {"fr": "Ne démarre pas", "en": "Will not start", "tr": "Çalışmaya başlamıyor", "it": "Non si avvia", "pt-PT": "Não arranca"}},
  {"famille": "symptôme", "code": "S-BRUIT", "libelle": {"fr": "Bruit anormal", "en": "Abnormal noise", "tr": "Anormal ses", "it": "Rumore anomalo", "pt-PT": "Ruído anormal"}},
  {"famille": "symptôme", "code": "S-VIBRATION", "libelle": {"fr": "Vibrations", "en": "Vibration", "tr": "Titreşim", "it": "Vibrazioni", "pt-PT": "Vibrações"}},
  {"famille": "symptôme", "code": "S-FUITE", "libelle": {"fr": "Fuite (air, huile, eau)", "en": "Leak (air, oil, water)", "tr": "Kaçak (hava, yağ, su)", "it": "Perdita (aria, olio, acqua)", "pt-PT": "Fuga (ar, óleo, água)"}},
  {"famille": "symptôme", "code": "S-CHAUFFE", "libelle": {"fr": "Échauffement anormal", "en": "Overheating", "tr": "Aşırı ısınma", "it": "Surriscaldamento", "pt-PT": "Aquecimento anormal"}},
  {"famille": "symptôme", "code": "S-ALARME", "libelle": {"fr": "Alarme ou message de défaut", "en": "Alarm or fault message", "tr": "Alarm veya arıza mesajı", "it": "Allarme o messaggio di guasto", "pt-PT": "Alarme ou mensagem de avaria"}},
  {"famille": "symptôme", "code": "S-CASSE", "libelle": {"fr": "Pièce cassée ou déformée", "en": "Broken or bent part", "tr": "Kırık veya eğilmiş parça", "it": "Pezzo rotto o deformato", "pt-PT": "Peça partida ou deformada"}},
  {"famille": "symptôme", "code": "S-DEGRADE", "libelle": {"fr": "Fonctionnement dégradé (lent, irrégulier)", "en": "Degraded operation (slow, erratic)", "tr": "Bozuk çalışma (yavaş, düzensiz)", "it": "Funzionamento degradato (lento, irregolare)", "pt-PT": "Funcionamento degradado (lento, irregular)"}},
  {"famille": "symptôme", "code": "S-QUALITE", "libelle": {"fr": "Défaut de qualité du produit", "en": "Product quality defect", "tr": "Ürün kalite hatası", "it": "Difetto di qualità del prodotto", "pt-PT": "Defeito de qualidade do produto"}},
  {"famille": "cause", "code": "C-USURE", "libelle": {"fr": "Usure normale", "en": "Normal wear", "tr": "Normal aşınma", "it": "Usura normale", "pt-PT": "Desgaste normal"}},
  {"famille": "cause", "code": "C-MECA", "libelle": {"fr": "Défaut mécanique (casse, desserrage, désalignement)", "en": "Mechanical fault (breakage, loosening, misalignment)", "tr": "Mekanik arıza (kırılma, gevşeme, eksen kaçıklığı)", "it": "Guasto meccanico (rottura, allentamento, disallineamento)", "pt-PT": "Avaria mecânica (rotura, desaperto, desalinhamento)"}},
  {"famille": "cause", "code": "C-ELEC", "libelle": {"fr": "Défaut électrique", "en": "Electrical fault", "tr": "Elektrik arızası", "it": "Guasto elettrico", "pt-PT": "Avaria elétrica"}},
  {"famille": "cause", "code": "C-PNEU", "libelle": {"fr": "Défaut pneumatique (fuite d'air)", "en": "Pneumatic fault (air leak)", "tr": "Pnömatik arıza (hava kaçağı)", "it": "Guasto pneumatico (perdita d'aria)", "pt-PT": "Avaria pneumática (fuga de ar)"}},
  {"famille": "cause", "code": "C-HYDRAU", "libelle": {"fr": "Défaut hydraulique (fuite d'huile)", "en": "Hydraulic fault (oil leak)", "tr": "Hidrolik arıza (yağ kaçağı)", "it": "Guasto idraulico (perdita d'olio)", "pt-PT": "Avaria hidráulica (fuga de óleo)"}},
  {"famille": "cause", "code": "C-LUBRIF", "libelle": {"fr": "Lubrification insuffisante", "en": "Insufficient lubrication", "tr": "Yetersiz yağlama", "it": "Lubrificazione insufficiente", "pt-PT": "Lubrificação insuficiente"}},
  {"famille": "cause", "code": "C-ENCRASSE", "libelle": {"fr": "Encrassement", "en": "Fouling or clogging", "tr": "Kirlenme veya tıkanma", "it": "Incrostazione o intasamento", "pt-PT": "Sujidade ou entupimento"}},
  {"famille": "cause", "code": "C-REGLAGE", "libelle": {"fr": "Mauvais réglage", "en": "Incorrect setting", "tr": "Yanlış ayar", "it": "Regolazione errata", "pt-PT": "Afinação incorreta"}},
  {"famille": "cause", "code": "C-UTILISAT", "libelle": {"fr": "Mauvaise utilisation", "en": "Misuse", "tr": "Hatalı kullanım", "it": "Uso scorretto", "pt-PT": "Utilização incorreta"}},
  {"famille": "cause", "code": "C-SURCHARGE", "libelle": {"fr": "Surcharge", "en": "Overload", "tr": "Aşırı yük", "it": "Sovraccarico", "pt-PT": "Sobrecarga"}},
  {"famille": "cause", "code": "C-MATIERE", "libelle": {"fr": "Défaut de matière ou de produit", "en": "Material or product defect", "tr": "Malzeme veya ürün hatası", "it": "Difetto di materiale o di prodotto", "pt-PT": "Defeito de material ou de produto"}},
  {"famille": "cause", "code": "C-AUTOMAT", "libelle": {"fr": "Défaut d'automatisme ou de capteur", "en": "Control system or sensor fault", "tr": "Otomasyon veya sensör arızası", "it": "Guasto di automazione o di sensore", "pt-PT": "Avaria de automatismo ou de sensor"}},
  {"famille": "cause", "code": "C-CORROSION", "libelle": {"fr": "Corrosion", "en": "Corrosion", "tr": "Korozyon", "it": "Corrosione", "pt-PT": "Corrosão"}},
  {"famille": "cause", "code": "C-EXTERIEUR", "libelle": {"fr": "Cause extérieure (énergie, environnement)", "en": "External cause (power supply, environment)", "tr": "Dış neden (enerji, ortam)", "it": "Causa esterna (energia, ambiente)", "pt-PT": "Causa externa (energia, ambiente)"}},
  {"famille": "cause", "code": "C-INCONNUE", "libelle": {"fr": "Cause non trouvée", "en": "Cause not found", "tr": "Neden bulunamadı", "it": "Causa non trovata", "pt-PT": "Causa não encontrada"}},
  {"famille": "remède", "code": "R-REMPLACE", "libelle": {"fr": "Remplacement de pièce", "en": "Part replaced", "tr": "Parça değişimi", "it": "Sostituzione del pezzo", "pt-PT": "Substituição de peça"}},
  {"famille": "remède", "code": "R-REPARE", "libelle": {"fr": "Réparation", "en": "Repair", "tr": "Onarım", "it": "Riparazione", "pt-PT": "Reparação"}},
  {"famille": "remède", "code": "R-REGLAGE", "libelle": {"fr": "Réglage", "en": "Adjustment", "tr": "Ayar", "it": "Regolazione", "pt-PT": "Afinação"}},
  {"famille": "remède", "code": "R-NETTOYAGE", "libelle": {"fr": "Nettoyage", "en": "Cleaning", "tr": "Temizlik", "it": "Pulizia", "pt-PT": "Limpeza"}},
  {"famille": "remède", "code": "R-GRAISSAGE", "libelle": {"fr": "Graissage ou lubrification", "en": "Greasing or lubrication", "tr": "Gresleme veya yağlama", "it": "Ingrassaggio o lubrificazione", "pt-PT": "Lubrificação (massa ou óleo)"}},
  {"famille": "remède", "code": "R-SERRAGE", "libelle": {"fr": "Resserrage", "en": "Retightening", "tr": "Yeniden sıkma", "it": "Serraggio", "pt-PT": "Reaperto"}},
  {"famille": "remède", "code": "R-REARMEMENT", "libelle": {"fr": "Réarmement ou redémarrage", "en": "Reset or restart", "tr": "Sıfırlama veya yeniden başlatma", "it": "Riarmo o riavvio", "pt-PT": "Rearme ou reinício"}},
  {"famille": "remède", "code": "R-PROVISOIRE", "libelle": {"fr": "Dépannage provisoire", "en": "Temporary fix", "tr": "Geçici onarım", "it": "Riparazione provvisoria", "pt-PT": "Reparação provisória"}},
  {"famille": "remède", "code": "R-AMELIORE", "libelle": {"fr": "Modification ou amélioration", "en": "Modification or improvement", "tr": "Değişiklik veya iyileştirme", "it": "Modifica o miglioramento", "pt-PT": "Modificação ou melhoria"}},
  {"famille": "remède", "code": "R-PRESTA", "libelle": {"fr": "Intervention d'un prestataire", "en": "Contractor called in", "tr": "Dış firma müdahalesi", "it": "Intervento di un'impresa esterna", "pt-PT": "Intervenção de um prestador de serviços"}},
  {"famille": "remède", "code": "R-CONSIGNE", "libelle": {"fr": "Consigne ou formation de l'utilisateur", "en": "User instruction or training", "tr": "Kullanıcıya talimat veya eğitim", "it": "Istruzioni o formazione dell'utente", "pt-PT": "Instrução ou formação do utilizador"}},
  {"famille": "remède", "code": "R-CONTROLE", "libelle": {"fr": "Contrôle sans intervention", "en": "Checked, no action needed", "tr": "Müdahalesiz kontrol", "it": "Controllo senza intervento", "pt-PT": "Verificação sem intervenção"}}
]}
// </json>
  ;
  function geler(valeur) {
    if (valeur && typeof valeur === 'object') {
      Object.keys(valeur).forEach((cle) => geler(valeur[cle]));
      Object.freeze(valeur);
    }
    return valeur;
  }
  geler(LISTE);
  /** Lignes { famille, code, libelle } dans la langue `langue` (code déclaré ; repli sur le français). */
  function lignes(langue) {
    return LISTE.codes.map((c) => ({ famille: c.famille, code: c.code, libelle: c.libelle[langue] || c.libelle.fr }));
  }
  window.CodesDeDepart = Object.freeze({ codes: LISTE.codes, lignes });
})();
