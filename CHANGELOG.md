# Journal des modifications

Toutes les modifications notables de Prévo sont consignées dans ce fichier.

Le format s'appuie sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/), et le projet
suit le [versionnage sémantique](https://semver.org/lang/fr/).

## [Non publié]

### Corrigé

- **Ouverture plus rapide avec un serveur sous Linux.** Chaque petit fichier de l'application attendait environ 40 ms
  avant de partir (délai du réseau propre à Linux) : l'ouverture prenait près d'une seconde de trop. Sous Windows, rien
  ne change.

## [2.4.1] - 2026-11-20

- Clôture : le compte rendu reprend le mot de relève laissé par le collègue qui a passé la main ; il suffit de le compléter.
- Premier accès par QR : le téléphone reste connecté 30 jours. Aide des habilitations corrigée : Prévo signale, et ne refuse que si vous l'avez réglé.

**Correctif de la 2.4.0.** Même format de données (format 6) : rien à faire à la mise à jour. Il reprend les décisions
prises après le rejeu de la livraison 2 et corrige deux textes d'aide.

### Modifié

- **Clôture d'un OT passé de main en main.** Dans la fenêtre de clôture, un compte rendu vide reprend le dernier mot de
  relève (« Passer la main »), avec « Repris du mot de relève de … » : le technicien le complète au lieu de retaper le
  diagnostic. Le texte repris compte comme compte rendu : relisez-le et ajoutez ce qui a été fait. Un compte rendu
  déjà écrit reste tel quel.
- **Premier accès par QR.** La session ouverte après le choix du mot de passe est en « rester connecté » (30 jours,
  réglable) : plus de nouvelle connexion dès le lendemain sur son propre téléphone.
- **Contrats dont le préavis est aussi long que la reconduction** (location reconduite chaque mois avec un mois de
  préavis…). Au lieu de « préavis dépassé » en permanence, la fiche dit « résiliable à tout moment : une lettre envoyée
  au plus tard le … arrête le contrat le … », sans alerte. « Noter la résiliation » y arrête le contrat à cette fin-là,
  celle que la lettre atteint.

### Corrigé

- **Aide des habilitations.** L'aide de la fiche d'OT et le guide annonçaient un refus systématique. Une habilitation
  manquante est signalée ; Prévo ne refuse que si « Habilitation électrique absente » est réglée sur « Bloquante », et
  seulement pour les habilitations électriques (en mode Solo, un simple rappel).
- **Aide du champ « Habilitation requise »** de la machine : elle proposait « BR ». Elle renvoie maintenant
  l'électricité vers « Risque électrique » et garde ce champ pour les autres habilitations (CACES…) ; les valeurs déjà
  saisies restent vérifiées.
- **Serveur.** Le contrôle des formules dans les fichiers reçus est plus rapide sur une grosse base (même résultat).

## [2.4.0] - 2026-11-16

- Plus simple au quotidien : mode Solo pour un technicien seul, assistant d'installation, clôture d'un OT en une fois, fiche d'OT sur téléphone, OT à valider visibles du responsable.
- Depuis la 2.1 : réserves des contrôles réglementaires, habilitations, garanties et contrats, coût de l'arrêt, pannes récurrentes. Vos données sont sauvegardées puis passent au format 6.

**Première version stable depuis la 2.1.2.** Elle rassemble la 2.2.0 bêta 1 (section plus bas), le lot 1 d'ergonomie
avec le mode Solo et le lot 2 d'ergonomie, tous deux détaillés ci-dessous. Les équipes de 1 à 5 personnes ont été
rejouées sur 18 parcours avant la publication. Au premier lancement, Prévo garde une copie de la base
(`avant-format-v6`) puis passe les données au format 6 ; une version plus ancienne les rouvre en lecture seule. Copiez
tout de même votre dossier de données avant la mise à jour.

### Lot 2 d'ergonomie, livraison 1 (proposé pour la 2.4.0-beta.1)

Les frictions relevées au retest du 14/11/2026 sont reprises une à une avec le responsable du projet. Cette première
livraison corrige l'installation, l'accueil, la fiche d'un ordre de travail, le bilan et le serveur ; la seconde est
listée en fin de section.

#### Ajouté

- **Pannes récurrentes.** Une machine qui a 3 pannes en 30 jours est signalée : tuile « Pannes récurrentes » sur
  l'accueil du responsable (et du mode Solo), bandeau « Panne à répétition » sur la demande qu'il traite et sur l'OT
  correctif ouvert, avec les interventions précédentes en lien. La mention est renforcée quand deux pannes ont la même
  cause. Les deux seuils se règlent dans Paramètres ; l'opérateur ne voit rien de tout cela.
- **Historique de la machine plus complet.** Chaque ligne dit le technicien, le temps passé et, pour une panne, la
  cause et le remède en clair ; trois boutons « Pannes / Préventif / Tout » filtrent la liste. Sur téléphone, un
  bouton « Historique » le fait venir à l'écran. Aucun montant n'y figure, et le demandeur n'a pas cette carte.
- **Qui accepte une demande.** Paramètres › « Qui peut accepter une demande » : « Le responsable et les techniciens »
  (par défaut) ou « Le responsable seulement ». Quand les techniciens le peuvent, « Je prends » accepte la demande et
  crée l'OT à leur nom en un geste ; le responsable voit sur son accueil « Demandes prises par les techniciens ».
- **« Prendre la suite »** sur un OT en attente ou en cours chez un collègue, avec une confirmation qui le nomme ;
  **« Reprendre le travail »** sur son propre OT en attente. Clore un OT en attente ne demande plus de le reprendre.
- **Fiche d'un OT sur téléphone** : une barre fixe en bas porte le bouton de la prochaine étape, sans défiler jusqu'à la
  carte Actions.
- **Responsable qui répare aussi.** Tout compte responsable reçoit d'office sa fiche de technicien : il peut mettre un
  OT à son nom, et « Je prends cet OT » lui est proposé. L'assistant le dit à l'étape du compte.
- **Taux horaire moyen du service** (Paramètres, facultatif) : utilisé pour un technicien sans taux propre. Sans
  aucun taux, l'heure reste « sans taux horaire » et rien n'est supposé.
- **Import des machines** : la question « Combien d'heures par jour tournent vos machines ? » est posée quand des
  machines importées n'ont pas ces heures ; vide, elle est passée. Un bouton « Importer des machines » est aussi
  à l'écran Parc.
- **Durées saisies à la main** : « 1h15 », « 1 h 15 », « 1:15 », « 75 min », « 1,25 » sont compris pour le temps passé,
  la durée d'arrêt et le temps prévu ; une saisie non comprise est dite sous le champ. Les durées s'affichent
  « 1 h 15 », « 2 h », « 45 min » partout, bilan compris.
- **Visite préventive** : quand tout est coché sans anomalie, le compte rendu « Visite faite, rien à signaler. » est
  rempli d'office ; le temps prévu est proposé comme temps passé ; la clôture dit « Prochaine visite : le … » ; sur
  une anomalie constatée, l'OT de réparation est proposé après la clôture.
- **Calendrier du préventif** : les visites suivantes d'une gamme à date fixe sont montrées, en plus clair et
  marquées « prévue » ; les gammes au compteur ou au seuil n'en ont pas, la légende le dit.
- **Réglages du responsable** : « Les techniciens peuvent créer des articles du magasin » (désactivé par défaut) ;
  « Dictée vocale » autorisée ou non (l'assistant pose la question sur une base neuve ; le micro reste affiché, un
  appui dit alors « La dictée n'a pas été activée par votre responsable ») ; « L'atelier n'a pas de Wi-Fi ».
- **Assistant d'installation** : un encadré annonce « Votre identifiant sera : prénom.nom » dès le nom saisi, une
  fenêtre le redit une fois le compte créé, et l'écran de connexion le propose déjà rempli. L'assistant demande aussi
  « Y a-t-il du Wi-Fi dans l'atelier ? » et, sinon, explique deux solutions : un poste de déclaration relié par câble,
  ou une borne Wi-Fi réservée à Prévo.
- **Poste de déclaration** : un appareil invité comme poste (case dans Équipe › Accès › Appareils) n'ouvre que
  « Signaler un problème », demande « Votre nom » à chaque déclaration et se vide après chaque envoi.
- **Page du téléphone qui ne fait pas encore confiance au PC** : « Pourquoi cet écran ? », trois schémas des gestes à
  faire, et l'alternative pour qui ne veut pas installer la clé.
- **Fichier de diagnostic** : Paramètres › « Préparer un fichier de diagnostic », pour le responsable. Il contient la
  version, la configuration sans secret et les journaux ; la carte dit qu'il contient les noms des comptes.
- **Journal du serveur** (`donnees/journal-serveur.log`) écrit dans tous les cas, sans secret, y compris les erreurs
  d'écran du poste ; jamais écrit sur des données d'un format plus récent (lecture seule).

#### Modifié

- **Fiche d'un ordre de travail** : un seul bouton en bleu, celui de la prochaine étape utile pour la personne ;
  « Marquer préparé » et « Annuler l'OT » passent sous « Plus d'options ». Dans la frise, Préparé et Planifié sont
  marqués « facultatif ». En mode Solo, la fenêtre « Clore » ne parle plus de deux clôtures.
- **Après sa clôture technique**, le technicien lit « Votre part est terminée. Le responsable validera. ».
- **Accueil du technicien** : « Mes ordres de travail » en une seule liste, pannes d'abord ; « À prendre (n) » ;
  « En attente dans l'équipe (n) », avec le prénom du collègue et le motif. Sur téléphone, ces blocs passent
  au-dessus de l'aide.
- **Accueil** : « Demandes à traiter », « Ordres en retard » et « Urgences ouvertes » remplacent les sigles. Les
  « Préventifs de la semaine » comptent les visites dues d'après le calendrier, OT créé ou non.
- **Tableau de bord** : il s'ouvre sur les quatre chiffres du bilan ; le reste est replié par famille (Fiabilité,
  Préventif, Retards, Coûts et stock, Heures, Par équipement). L'accueil de la direction commence par ces chiffres.
  Un coût sans taux ni prix est dit « non chiffré », plus jamais « 0,00 € ». « Heures des OT clôturés et coût » et
  « x de préventif sur y pointées » disent qu'il s'agit de deux mesures.
- **Bilan du mois** : deux lignes en plus (OT en retard, délai de prise en charge) ; « Voir le bilan » propose tous les
  mois qui ont des données ; « Figer » devient « Enregistrer ce bilan », « Rapports figés » devient
  « Bilans enregistrés ».
- **Installation** : « Installer Prévo » vient d'abord sur l'écran de première ouverture, puis la démo, puis la base
  vide en petit lien. Une seule adresse est donnée aux téléphones (celle de la carte qui porte la connexion du PC) ;
  les autres sont sous « Autres adresses de ce PC ». Pendant l'installation, la fiche d'accès ne donne ni adresse ni
  QR : « Les téléphones pourront se connecter dès que vous aurez cliqué sur Terminer ».
- **Étiquettes QR** : la consigne Wi-Fi passe au-dessus du QR, en plus gros. Sur ce PC seulement, ou sans Wi-Fi,
  « Imprimer » dit d'abord que les QR ne s'ouvriront pas sur les téléphones et donne les deux solutions.
- **Accueil et « Mes demandes »** se mettent à jour sans recharger : à l'arrivée sur l'écran, puis toutes les 5 s, sans
  jamais redessiner pendant une saisie.
- **Textes** : plus de numéro de règle dans les textes affichés ; l'aide ne cite plus l'« Atelier Usinage » ; le bouton
  de l'écran Préventif dit « Nouvelle visite périodique (gamme) » ; le choix d'une machine d'une gamme montre
  repère, désignation et emplacement avec recherche. En mode Solo, les textes ne parlent plus de « votre
  responsable » ni d'« Équipe › ».
- Un opérateur qui flashe le QR d'une machine sans y être autorisé lit sur l'écran de connexion quoi faire ; après
  son invitation, il arrive sur la fiche de cette machine et non sur l'accueil.

#### Corrigé

- **Paramètres › Accès et installation** ne montre plus que les dernières erreurs du serveur, et dit « Aucune erreur
  notée. » quand il n'y en a pas, au lieu de ses 20 dernières lignes.
- **Fiche de la machine vue par le demandeur** : plus d'historique des OT (qui disait « Tout (0) » en mode serveur).
- Le récapitulatif de l'assistant espace la question de la dictée comme les autres blocs.
- Le tableau de bord garde la famille que vous venez d'ouvrir, même quand un redessin suit aussitôt le clic.

#### Sécurité (mode serveur avec comptes)

- **Le serveur applique pour le technicien ce que l'écran permettait sur le magasin.** Sur `articles.csv`, un technicien
  ne peut plus écrire que la colonne du stock (sortie, retour) ; il ne crée un article que si le réglage du
  responsable l'autorise ; modifier ou retirer un article lui est refusé. Un script tiers qui écrivait `articles.csv`
  avec une session de technicien reçoit désormais un refus.
- Un technicien ne peut accepter une demande que si le réglage le permet, et avec un OT créé à son nom ; refuser,
  différer, regrouper ou supprimer une demande lui est refusé.
- **Le journal du serveur et « Préparer un fichier de diagnostic » sont réservés au responsable** : refusés au
  technicien, au demandeur, à l'appareil et à la direction. Aucun secret n'y est écrit, et le mot de passe provisoire
  d'une réinitialisation ne va qu'à l'écran.
- Le taux horaire moyen n'est servi ni au technicien, ni au demandeur, ni à l'appareil.

#### Livraison 2 (même proposition 2.4.0-beta.1)

Les frictions du rejeu de la livraison 1 (15/11/2026) ont été reprises une à une avec le responsable du projet ;
cette livraison fait les quatre grosses décisions restantes et les précisions de cette revue.

Ajouté :

- **Fenêtre de clôture unique.** « Clôturer » et « Clore » ouvrent la même fenêtre : tout ce qui est exigé est marqué
  d'une étoile et rempli d'avance (fin à maintenant, temps proposé, compte rendu repris, case de sécurité) ; ce qui
  manque est listé en haut, à jour pendant la saisie, et le bouton dit « il manque N éléments » au lieu de refuser
  après coup. « Autre (préciser) » en tête des codes cause et remède. Pour une panne : « La machine était-elle
  arrêtée ? » (le bilan compte les arrêts). Visite préventive : la fenêtre dit les contrôles faits ou l'anomalie,
  propose le temps de la gamme et donne la prochaine visite.
- **Clôtures incomplètes** (réglage du responsable, désactivé par défaut) : le technicien clôture malgré un champ
  vide ; le responsable retrouve ces OT sur son accueil (« Clôtures à compléter ») et les complète ; la validation
  exige toujours une clôture complète.
- **Dépannage provisoire** : case et mot à la clôture d'une panne ; à la validation, « Créer l'OT de remise en
  état » crée en un clic la réparation programmée, remplie et liée à la panne.
- **Ajouter des utilisateurs** : carte sur l'accueil (Solo compris) et dans Équipe ; opérateurs invités par QR (par
  le responsable ou un technicien) ; techniciens et Direction par un QR où la personne choisit son mot de passe (fiche
  du technicien créée avec le compte, plus de mot de passe provisoire). « Créer un compte » propose « Nouvelle fiche
  à ce nom » par défaut. « Paramètres › Accès et installation » devient un lien.
- **Passer la main** : motif, collègue ou « à qui est disponible », mot de relève (dictée possible) affiché en tête
  de l'OT et sur l'accueil du collègue ; **« Journée terminée »** sur l'accueil du technicien ; **renforts** (« Ajouter
  un technicien ») : l'OT apparaît chez chacun, chacun saisit son temps, les temps manquants sont rappelés à la
  clôture sans bloquer.
- **Habilitations simplifiées** : liste fixe à cocher (BR ; B1, B1V, B2, B2V, BC ; H0 ; H1, H2, HC), « Risque
  électrique » sur la machine, habilitation attendue déduite selon dépannage ou travail planifié ; autres
  autorisations jamais bloquantes. Réglage « signalée seulement » (par défaut) ou « bloquante » ; jamais de blocage
  tant qu'aucune habilitation n'est saisie ; « À prendre » montre l'habilitation attendue et, en bloquant, qui peut
  prendre l'OT. Solo : plus de rappel tant qu'aucune n'est saisie sur sa fiche.
- **Pièce hors magasin** sur l'OT (onglet Exécution et fenêtre de clôture) : désignation, quantité, prix facultatif ;
  comptée dans le coût, « non chiffrée » sans prix, jamais dans le stock. Magasin, onglet « Hors magasin »
  (responsable) : « Saisir le prix », « Créer l'article » prérempli. Réglage « Les techniciens peuvent saisir le prix
  des pièces hors magasin » (désactivé par défaut).
- **Bilan chiffré** : étape facultative « Pour chiffrer votre bilan » dans l'assistant (taux horaire moyen, heures de
  marche par jour) ; bouton « Renseigner » sur les cartes « non chiffré » et « à compléter » ; en bas du bilan, une
  ligne renvoie au détail de l'écran Indicateurs.
- **Page d'attente du téléphone** pendant l'installation : « Téléphone connecté. Prévo s'ouvrira quand l'installation
  sera terminée », dans la langue du téléphone ; l'assistant redonne l'adresse et le QR.

Modifié :

- Statuts d'OT affichés « Terminé, à valider » et « Clôturé », types « Panne » et « Réparation programmée »
  (affichage seulement, données inchangées) ; bandeau d'un OT clôturé plus clair ; « Clore » dit « OT-… : clôturé. ».
- L'écran de connexion qui suit l'installation explique pourquoi le mot de passe est redemandé.
- L'accueil du responsable met « Connecter un téléphone » en haut tant qu'aucun téléphone ne s'est connecté.
- Le champ « Consignes » de l'OT devient « Consignes de sécurité (responsable) ».

Corrigé après le rejeu de la livraison 2 (15/11/2026) :

- Fiche technicien, « Ajouter une habilitation » : les cases BR à HC cochées sont enfin enregistrées, une ligne par
  case, et l'intitulé n'est plus exigé quand une case est cochée (L19).
- Accueil du responsable : les OT « Terminé, à valider » sont comptés (« · N OT à valider », ou à la place de « Rien
  d'urgent ») avec un bouton « OT à valider : N » ; liste des OT : état « À valider » (responsable).
- « Passer la main » à un collègue ajoute sa ligne aux prises en charge (« X a passé la main à Y ») ; ce n'est pas
  compté comme une reprise (L16).
- L'assistant d'installation donne à la Direction un QR de premier accès au lieu d'un mot de passe provisoire ; il ne
  répond qu'après « Terminer » (L05).
- Bilan et Indicateurs : un taux sous 100 % ne s'affiche plus « 100,0 % » (plafond 99,9 %).

Format de données 6 : colonnes de l'OT pour les renforts, la relève (mot, qui, quand, motif) et la remise en état ;
risque électrique de la machine ; pièce hors magasin (désignation, prix, type de mouvement « hors magasin »). Passage
automatique au format 6 après une sauvegarde « avant-format-v6 » ; un ZIP au format 5 est migré à l'import.

Sécurité (mode serveur avec comptes) :

- Le seul droit nouveau du technicien est d'inviter un opérateur. Le QR de premier accès est à usage unique, valable
  24 h, lié à un compte ; seule son empreinte est écrite.
- Journal des modifications fermé au technicien et à la Direction ; leurs écrans n'en reçoivent que les lignes utiles
  (`/api/journal/extraits`).
- Avant « Terminer », les adresses réseau du PC ne servent que la page d'attente, sans aucune donnée ; tout le reste
  répond 404 sans contenu.
- Le prix d'une pièce hors magasin n'est montré au technicien que si le responsable l'a autorisé ; le serveur tient
  la règle.

### Lot 1 d'ergonomie et mode Solo (proposé pour la 2.3.0-beta.1)

Corrections tirées du test d'ergonomie par taille d'équipe du 13/11/2026 (18 passages, équipes de 1 à 5).

#### Ajouté

- **Mode Solo, pour celui qui est seul à la maintenance.** L'assistant demande d'abord « Qui fait la maintenance ? »
  (seul ou en équipe), puis « Qui d'autre ouvre Prévo ? » (mon téléphone, les opérateurs par QR, la direction en
  lecture seule). En Solo, les pannes déclarées par les opérateurs deviennent d'elles-mêmes des ordres de travail à
  votre nom, « Démarrer » est proposé tout de suite, la fiche n'a que trois états (à faire, en cours, fini),
  l'habilitation est un rappel et non un refus, le menu n'a ni Équipe ni Planning, et l'accueil montre ce qui vous
  attend aujourd'hui. Paramètres › « Organisation : seul ou en équipe » : passer en équipe ne supprime rien ; le
  retour en Solo est possible quand il ne reste qu'un technicien actif.
- **« Je prends cet OT »** sur tout ordre de travail sans technicien, et **« Reprendre cet OT à mon nom »** sur celui
  d'un collègue (congé, changement d'équipe), avec une confirmation qui le nomme. Chaque prise est notée dans l'OT
  (qui, quand, à qui) ; le collègue la voit sur son accueil, le responsable dans « Reprises récentes ». Un OT qui a un
  technicien se démarre sans passer par le planning.
- **Retour vers l'opérateur.** La demande suit son ordre de travail : « En cours », puis « Réparée » avec la date et
  le prénom du technicien. À la clôture, « Un mot pour l'opérateur » (facultatif, dictée possible). En flashant de
  nouveau le QR de la machine, l'opérateur voit ses dernières demandes et où elles en sont. Mêmes droits d'accès
  qu'avant : ni coûts, ni autre donnée personnelle que le prénom du technicien.
  Bases existantes : au passage au format 5, une demande déjà acceptée dont l'ordre de travail est en cours ou clos
  prend « En cours » ou « Réparée ». La démo en montre des exemples, certains avec un mot du technicien.
- **Rôle « Direction », en lecture seule** : tableau de bord, bilan mensuel, historique des machines et des ordres de
  travail. Aucune modification, aucun accès à l'administration (refusés aussi par le serveur). Proposé dans
  l'assistant d'installation et dans Équipe › Accès.
- **Codes cause et remède prêts à l'emploi** : une base neuve reçoit une liste de départ (15 causes, 12 remèdes,
  10 symptômes), modifiable ; « Ajouter la liste de départ » pour une base existante. « Autre (préciser) » avec un
  champ libre. À l'import de vos propres codes, un code de départ que rien ne cite laisse sa place au vôtre de
  même libellé, et l'aperçu le dit.
- **Bilan du mois en cours**, y compris le premier mois d'utilisation, sans rien figer : « Voir le bilan ». Le bilan
  nomme ce qui manque (heures par jour des machines, taux horaires, prix des pièces, coût d'une heure d'arrêt) et dit
  dans quel écran le renseigner ; un coût incomplet est dit « Partiel », jamais donné comme un total.
- **Après « Démarrer »**, la fiche d'un ordre de travail s'ouvre sur l'onglet Exécution, celui de la check-list. Sur
  l'accueil du technicien, « Vos OT repris par un collègue » passe en tête.
- **Étiquettes QR** : la consigne « Connectez-vous au Wi-Fi de l'usine pour déclarer une panne » est imprimée sous le
  QR quand l'adresse de Prévo est locale ou privée (avec le nom du Wi-Fi si vous le donnez). Les écrans Étiquettes,
  Paramètres › Accès et la fiche d'accès préviennent que ces QR ne s'ouvriront pas hors du réseau de l'usine.

#### Modifié

- **Format des données 5** : `demandes` gagne les statuts « En cours » et « Réparée » et les colonnes
  `mot_technicien`, `date_reparation`, `repare_par` ; `ordres_travail` gagne `cause_precision`, `remede_precision` et
  `prises_en_charge`. Le passage est automatique, précédé de la sauvegarde `avant-format-v5`. Une version 2.2 ouvre
  une base au format 5 en lecture seule.
- **Clôture d'un ordre de travail préventif ou réglementaire** : ni code cause ni code remède exigés. Une liste de
  codes vide ne bloque plus aucune clôture : un message dit où créer les codes.
- Étiquette de 24 par planche : le QR passe de 30 à 27 mm pour laisser la place à la consigne.

#### Corrigé

- **Première installation** : après « Créer une base vide », le lien « Installer Prévo (assistant) » ouvre bien
  l'assistant, sans recharger la page ; il affichait la fiche d'accès.
- **Tableau de bord** : les pannes, la durée d'arrêt et le MTTR ne tombent plus à zéro quand les machines n'ont pas
  leurs heures de fonctionnement par jour.
- Le message « Vos données de Prévo 1.2 sont là » n'apparaît plus sur une base que cette version vient de créer vide.
- Un lien vers un document refusé à votre rôle mène à une page de Prévo qui dit quoi faire, au lieu d'un texte brut.
- Un lien vers un document ouvert sans être connecté (le rapport mensuel reçu par mail) affiche l'écran de connexion
  de Prévo, puis le document s'ouvre. Les droits ne changent pas.
- **Assistant d'installation** : l'attente pendant la fabrication du certificat est dite à côté du bouton grisé.
- **Fiche d'accès** : les deux QR, qui portaient la même adresse, sont réunis en un seul qui dit les deux usages.
- **Fiche d'un ordre de travail vue par la Direction** : les informations en texte, sans formulaire grisé.

### Corrections après une relecture critique de la 2.2.0 bêta 1 (12/11/2026)

### Sécurité (mode serveur avec comptes)

- Un technicien ne peut plus changer un prix ni le coût d'arrêt d'une machine, et un demandeur ne peut plus créer une
  demande déjà acceptée, en envoyant au serveur un fichier dont une colonne est en double.
- Les justificatifs d'habilitation et les documents de contrats restent réservés au responsable quand ils ne sont plus
  cités : document remplacé, ligne supprimée, import ZIP. Limite : un document au nom libre n'est réservé que tant
  qu'une ligne le cite.
- Un technicien ne peut plus vider ni modifier le journal ; le serveur écrit lui-même le profil de chaque ligne ajoutée.
- Les valeurs des colonnes cachées (taux horaires, prix, montants) ne se retrouvent plus à partir de la version d'un
  fichier.
- Le serveur refuse une cellule qui commence par un tiret suivi d'une formule (`-1+…`), comme le navigateur ; un nombre
  négatif reste accepté.

### Corrigé

- **Restauration d'une sauvegarde d'avant la 2.2** (dont `avant-format-v4`) : les réserves, garanties et contrats créés
  depuis sont vidés, au lieu de rester et de se rattacher à un autre contrôle ou équipement. La copie de sécurité
  `avant-restauration` les garde, et le message de fin nomme les tables vidées.
- **« Annuler cet import »** n'échoue plus quand l'import avait créé une table qui n'existait pas.
- **Contrat à reconduction tacite** : « Noter la résiliation » est refusé tant que la date de fin enregistrée est
  passée ; il faut d'abord « Reconduire ». Le contrat ne passe plus à « terminé » un an trop tôt.
- **Dérogation d'habilitation** : un texte saisi dans un motif ne vaut plus dérogation ; si la ligne du journal ne peut
  pas être écrite, le responsable en est prévenu et l'écran montre l'OT réellement écrit.
- **Import ZIP coupé en route** (onglet fermé, panne) : à la réouverture, un bandeau dit que la base est incomplète et
  nomme la sauvegarde à restaurer.
- **Import ZIP d'une autre base** : la confirmation liste les comptes dont la fiche de technicien change de personne.
- **Import depuis un tableur** : « 1.200 » ou « 1,200 » porte une note à l'aperçu (« lu comme 1,2, et non 1 200 ») ;
  une fiche retirée est dite retirée ; une image que le serveur refuse est sautée et nommée, sans arrêter l'import.
- **Passage au format 4 sur le serveur** : une base dont le fichier des contrôles a deux colonnes ajoutées à la main
  sous le même nom reprend bien ses réserves ; une date de contrôle illisible ne bloque plus les écritures suivantes.
- **Garanties** : le filtre « se terminent bientôt » compte les mêmes garanties que l'accueil.
- **« Tester une sauvegarde »** signale une sauvegarde dont un fichier est abîmé.

## [2.2.0-beta.1] - 2026-11-12

**Bêta de la 2.2, « le dirigeant dort tranquille » : réserves des contrôles, habilitations, garanties et contrats de
prestataires, coût de l'arrêt.** C'est une bêta : copiez votre dossier de données avant de la lancer (Prévo fait aussi
sa propre sauvegarde `avant-format-v4`). Les données passent au format 4 ; une 2.1 les rouvre en lecture seule, une
1.2.x ou une 2.0.0 bêta 1 n'a pas cette garde.

**Le principe.** Prévo est une aide au suivi ; la responsabilité reste celle de l'employeur. Il rappelle des échéances
et garde des preuves ; toute périodicité ou durée proposée est sourcée et modifiable, et Prévo ne dit jamais qu'un
équipement est en règle. Cette phrase figure sur les écrans concernés, dans le guide et dans le README.

### Ajouté

- **Réserves des contrôles, une ligne par réserve** : à la réalisation d'un contrôle, chaque ligne saisie devient une
  réserve. Le responsable peut la lever (date et commentaire), la modifier, en ajouter, ou créer un OT depuis elle
  (pré-rempli et relié). Une nouvelle réalisation n'efface plus aucune réserve : celles qui ne sont pas levées restent
  ouvertes. Le contrôle passe en « réserves à lever (n) » ; les réserves en retard sont rappelées à l'accueil et dans
  le rapport mensuel.
- **Catalogue de contrôles réglementaires sourcés** : créer un contrôle depuis le catalogue pré-remplit la périodicité,
  la référence du texte, la nature de la source et la date de relecture (« relu le 08/11/2026 »), avec le lien
  Légifrance. Modifier la périodicité la marque « saisie ». Une relecture du catalogue est proposée, jamais appliquée
  toute seule. Les points qui dépendent de votre organisme de contrôle portent la mention « à confirmer avec votre
  organisme de contrôle ».
- **Habilitations plus complètes** : type choisi dans un catalogue (électricité, CACES, travail en hauteur…), recyclage
  proposé (recommandation, jamais obligation), échéance calculée depuis l'obtention et modifiable, justificatif joint.
  L'autorisation de conduite de l'employeur est distincte du CACES et peut s'appuyer sur lui comme justificatif. Le
  technicien voit ses habilitations sur son accueil, sans le justificatif.
- **Écran « Garanties et contrats »** (responsable) : liste avec compteurs, onglets et filtres, total des contrats en
  cours (ceux sans montant sont comptés à part, jamais estimés). Chaque fiche donne l'échéance, « Écrire au
  prestataire » (un lien mail, Prévo n'envoie rien), « Noter la résiliation », « Reconduire », « Retirer » (la ligne
  reste) et l'historique.
- **Alertes de garanties et de contrats** : 60 jours par défaut, réglables dans Paramètres (de 1 à 365). Un contrat à
  reconduction tacite passe « à décider » avant sa date limite de résiliation ; une garantie ou un contrat « se
  termine bientôt ». Une tuile « Garanties et contrats » est ajoutée à l'accueil du responsable.
- **Sur la fiche équipement** : badge « Sous garantie jusqu'au … » et carte « Garanties et contrats » (sans montant pour
  le technicien) ; à la création d'un OT correctif et à l'acceptation d'une demande, un rappel « appeler le fournisseur
  avant d'intervenir ? » (il ne bloque rien).
- **Coût de l'arrêt** : le coût d'une heure d'arrêt se saisit sur la fiche équipement (responsable seul ; vide = « non
  chiffré »). Le coût de l'arrêt est la somme, par équipement, de la durée d'arrêt fois ce coût horaire, au centime
  près. Le rapport mensuel gagne une tuile « Coût de l'arrêt » (« Partiel » s'il manque quelque chose), un Pareto par
  coût et la formule dans « Comprendre » ; l'écran Indicateurs, un Pareto « Coût de l'arrêt » et une carte « Non
  chiffré » avec le lien « Saisir le coût horaire ». Les équipements sans coût et les pannes sans durée sont listés,
  jamais estimés.
- **Import depuis un tableur** : les garanties, les contrats de prestataires, les réserves des contrôles et la colonne
  du coût horaire d'arrêt des équipements s'importent comme le reste ; les observations d'un import de contrôles sont
  reprises en réserves.
- **Guide, aide à l'écran et glossaire** : le guide a une section « Garanties et contrats » et des compléments sur les
  réserves, les habilitations et le coût de l'arrêt (en français et en anglais) ; l'aide à l'écran est réécrite pour
  les nouveaux écrans ; le glossaire donne les termes de la 2.2 dans les cinq langues.
- **Démo** : trois garanties et quatre contrats, trois réserves, six équipements chiffrés, des contrôles tirés du
  catalogue.

### Modifié

- **L'habilitation exigée par un OT bloque désormais** : créer, modifier, planifier un OT ou le passer à « Planifié »
  est refusé si l'OT (ou son équipement) exige une habilitation que le technicien n'a pas en cours de validité. Un OT
  sans exigence n'est jamais bloqué. Seul le responsable peut passer outre, par une fenêtre où la case à cocher et le
  motif sont obligatoires ; le journal garde qui, quand, quel OT et quelle habilitation. Même règle au planning.
- **Droits** : les garanties, les contrats et les réserves sont écrits par le responsable seul. Le coût horaire d'arrêt
  et le montant annuel des contrats sont cachés au technicien, au demandeur et à l'appareil. Les justificatifs
  d'habilitation et les documents des contrats ne sont servis qu'au responsable.
- **Démo corrigée** : réservoir d'air à 48 mois, frigo selon la charge, aération d'après l'arrêté du 8 octobre 1987.
- **Traductions de la 2.2 relues** : anglais (britannique), turc, italien et portugais du Portugal ; le turc, l'italien
  et le portugais restent des traductions automatiques.
- **Dépôt GitHub transféré à l'organisation prevo-pro** : le code, les releases et les signalements sont désormais sur
  <https://github.com/prevo-pro/prevo> ; les anciennes adresses `github.com/nicoboy49/prevo` redirigent. Prévo accepte
  les deux adresses comme lien de téléchargement d'une mise à jour, et `version.json` mène à la page de téléchargement
  de prevo.pro, la seule que les versions déjà installées gardent toutes.

### Corrigé

- Un deuxième rapport de contrôle le même jour échouait dans une autre langue que le français.
- Un contrat résilié restait « à décider » ; la résiliation d'un contrat tacite dont la fin enregistrée est passée est
  refusée (« Reconduisez d'abord »).
- Avec des comptes, le technicien ne peut plus lire le rapport mensuel figé (déjà corrigé dans la 2.1.1).
- Après un changement de format, un journal abîmé n'affichait pas le bandeau du responsable ; le technicien et le
  demandeur voient maintenant un message simple (« Fichier abîmé : prévenez le responsable »).
- En mode serveur, une table absente (garanties d'une base tout juste passée au format 4) laissait une requête
  ouverte.

### Format de données 4

- La base passe de 24 à 27 fichiers : trois tables (`reserves_controle`, `garanties`, `contrats_prestataires`) et dix
  colonnes (coût d'une heure d'arrêt, habilitation exigée par un OT, recyclage, justificatif, type et nature de la
  source des habilitations, origine et référence de la périodicité des contrôles).
- Au premier lancement, Prévo fait une sauvegarde `avant-format-v4`, puis reprend le texte des observations de chaque
  contrôle réglementaire en réserves, une par ligne (les observations sont conservées, la reprise ne se fait qu'une
  fois par contrôle). Les réserves déjà levées reçoivent le commentaire « levée avant la 2.2, date inconnue ».
- Une 2.1 qui rouvre cette base la lit en lecture seule, sans rien modifier ; ses sauvegardes ne contiennent que ses
  24 tables. Une 1.2.x ou une 2.0.0 bêta 1 n'a pas cette garde : mettez-les à jour avant de rouvrir une base 2.2.
- Aucune route serveur, aucune bibliothèque et aucune connexion réseau nouvelles.

**Mise à jour.** Copiez d'abord votre dossier de données, puis placez la 2.2.0-beta.1 dans le même dossier. Pas de
`version.json` pour une bêta : les installations existantes ne la reçoivent pas d'elles-mêmes.

## [2.1.2] - 2026-11-12

**Correctif de sécurité : plusieurs failles du mode serveur avec comptes sont fermées.** Mise à jour recommandée pour
les installations en mode serveur avec comptes (connexion par identifiant, accès depuis le réseau ou le téléphone) ;
en mode dossier, en mode serveur sans comptes et dans la démo, rien ne change. Rien d'autre ne change (mêmes écrans,
même format de données).

**Ce qui pouvait arriver.** Aucun écran de Prévo ne le permettait : il fallait envoyer au serveur des fichiers
préparés à la main, en étant connecté avec un compte ou depuis un téléphone enrôlé. De cette façon, un compte
technicien pouvait changer le prix d'un article ou d'un achat, alors que Prévo lui cache les prix. Un compte demandeur,
ou un téléphone enrôlé, pouvait créer une demande déjà marquée « Acceptée » et reliée à un ordre de travail, sans
décision du responsable. Un compte technicien pouvait vider ou modifier le journal, et un compte demandeur ou un
téléphone enrôlé pouvait y ajouter une ligne signée « responsable ». Enfin, un compte technicien pouvait retrouver, par
essais successifs, les taux horaires et les prix que Prévo lui cache. Concerné : la 2.1.1 ; la 2.0.0 et la 2.1.0
portent le même code.

### Sécurité (mode serveur avec comptes)

- **Prix et demandes** : un technicien ne peut plus changer un prix, et un demandeur ne peut plus créer une demande
  déjà acceptée, en envoyant au serveur un fichier dont une colonne est en double.
- **Journal** : un technicien ne peut plus vider ni modifier le journal ; le serveur écrit lui-même, sur chaque ligne
  ajoutée, le profil de la personne connectée.
- **Valeurs cachées** : les taux horaires et les prix cachés au technicien ne se retrouvent plus à partir de la
  version d'un fichier.
- **Formules** : le serveur refuse une cellule qui commence par un tiret suivi d'une formule (`-1+…`), comme le
  navigateur le fait déjà ; un nombre négatif reste accepté.
- **Rien d'autre ne change** : le responsable écrit ses fichiers et son journal comme avant, et sans comptes tout
  reste comme avant.

**Rien à faire.** Mettez la 2.1.2 dans le même dossier, comme pour toute mise à jour : vos données restent, aucun
réglage n'est à changer. Le serveur crée de lui-même un petit fichier `.cle-versions` dans `donnees/acces/` :
laissez-le en place.

## [2.1.1] - 2026-11-11

**Correctif de sécurité : le rapport mensuel figé n'est plus servi au technicien (mode avec comptes).** Mise à jour
recommandée pour les installations en mode serveur avec comptes (connexion par identifiant, accès depuis le réseau ou
le téléphone) ; en mode dossier, en mode serveur sans comptes et dans la démo, rien ne change. Rien d'autre ne change
(mêmes écrans, même format de données).

**Ce qui pouvait arriver.** Un compte technicien pouvait obtenir un rapport mensuel figé en le demandant directement
au serveur par son adresse : son nom figure dans les paramètres, que le technicien lit, même si aucun de ses écrans ne
propose ce rapport. Le rapport montre notamment le coût de maintenance du mois et, pour un équipement au-delà du
seuil « réparer ou remplacer », son coût sur 12 mois et sa valeur de remplacement : des montants que Prévo cache au
technicien partout ailleurs. Les comptes demandeurs et les téléphones enrôlés étaient déjà refusés. Concerné : la 2.0.0
et la 2.1.0.

### Corrigé

- **Rapport mensuel figé réservé au responsable** : avec les comptes, le serveur ne le sert plus qu'au responsable ;
  le technicien reçoit le même refus que le demandeur.
- **Rien d'autre ne change** : les autres documents restent ouverts au technicien comme avant, le responsable ouvre
  ses rapports comme avant, et sans comptes tout reste servi.

**Rien à faire.** Mettez la 2.1.1 dans le même dossier, comme pour toute mise à jour : vos données restent, aucun
réglage n'est à changer, les rapports déjà figés restent où ils sont.

## [2.1.0] - 2026-11-08

Lot 5 du chantier multilingue : turc, italien et portugais du Portugal.

### Ajouté

- **Prévo en turc, en italien et en portugais du Portugal** : toute l'interface, l'aide à l'écran et les messages du
  serveur, en traduction automatique ; le sélecteur de langue les propose sous leur nom (Türkçe, Italiano,
  Português). Une mention « Traduction automatique — corrections bienvenues » (pied du menu, « Ce poste », « À
  propos ») ouvre le formulaire GitHub « Corriger une traduction », pré-rempli avec la langue et la version.
- **Aide longue et guide en anglais** pour ces trois langues (le guide en français ou en anglais seulement).
- **Lettres turques** (ğ, İ, ş) dessinées dans la police de Prévo (sous-ensemble latin-ext de Sora).
- **Glossaire métier en cinq langues** (docs/GLOSSAIRE.md) et contrôle de sa cohérence
  (outils/controler_glossaire.py).

### Modifié

- **Wiki rédigé par l'IA dans la langue de l'installation** (en français jusqu'ici) : ses garde-fous (consignes de
  sécurité, nouveauté, dates, comptages) valent dans les cinq langues.
- **Masquage avant l'envoi à l'IA** : les numéros de téléphone internationaux (+ ou 00, turcs, italiens, portugais,
  britanniques) sont masqués comme les numéros français.

## [2.0.0] - 2026-11-08

Première version stable de la 2.0 : elle reprend aussi tout ce qu'apportent la 2.0.0 bêta 1 et la bêta 2
(sections ci-dessous). Depuis la 1.2 : placez la 2.0 dans le même dossier ; Prévo fait une sauvegarde avant la mise à
jour, puis met vos données au format courant.

### Ajouté

- **Prévo en anglais** : toute l'interface, l'aide à l'écran, les messages du serveur et sa console existent en
  français et en anglais (anglais britannique ; nombres, montants et dates au format de la langue). Sélecteur
  « Français / English » dans « Ce poste » et au pied du menu ; sur la porte des téléphones et l'écran de connexion, un
  globe et les langues écrites chacune dans sa langue. Le choix fait sur la porte est repris par l'application.
- **Langue de l'installation** : « Langue de Prévo » dans Paramètres › Entreprise, demandée à la création de la base.
  C'est la langue des postes qui n'ont rien choisi, de la console du serveur, et des textes que Prévo écrit lui-même
  dans les données (historique des OT, titres pré-remplis…).
- **Langue du compte** : sur « Ce poste », chacun garde sa langue « pour mon compte » (sur tous les postes où il se
  connecte) ou « pour ce poste seulement » ; le responsable la règle à la création du compte et dans Équipe › Accès.
- **Démo** : elle s'ouvre dans la langue du navigateur (sinon en anglais) ; changer de langue y efface les
  modifications, et Prévo prévient avant.
- **Rapport mensuel** : figé dans la langue choisie au moment de le figer.
- **Assistant IA** : il répond dans la langue de l'écran ; la dictée suit la langue active.
- **Devise** réglable (EUR par défaut, CHF, GBP, USD, TRY ou un autre code) ; aucun montant n'est converti.
- **« Suggérer une amélioration »** (À propos et pied du menu) : un formulaire GitHub pré-rempli avec la version, la
  langue et le navigateur, rien d'autre ; à défaut, contact@prevo.pro.
- **Saisie gardée** : si la session prend fin pendant une saisie, l'écran de connexion s'affiche sans rien effacer ; le
  même compte retrouve l'écran et sa saisie, il reste à enregistrer (une autre personne ne la voit pas).
- **Guide et documentation en anglais** : `GUIDE.en.html` (l'aide à l'écran et « À propos » ouvrent le guide de la
  langue), README, guide d'installation, feuille de route, guide de contribution (avec « Ajouter ou corriger une
  langue »), politique de sécurité et code de conduite.
- **Brouillons** : la déclaration d'un problème et le compte rendu d'un OT sont gardés au fur et à mesure dans le
  navigateur de l'appareil, pour le compte qui les a tapés : un téléphone resté en veille, dont la page se recharge,
  les retrouve. Rien n'est envoyé au serveur avant l'enregistrement ; le brouillon est effacé à l'enregistrement, ou
  au bout de 7 jours.

### Modifié

- **Signalement des nouvelles versions activé par défaut** : une lecture de `prevo.pro/version.json` par jour et par
  poste, sans cookie, sans adresse de page et sans redirection ; jamais dans la démo. Un bandeau l'explique une fois ;
  la case est dans Paramètres › Mises à jour. Le lien « Télécharger » ne mène qu'à prevo.pro ou au dépôt GitHub.
- **Recherche et tri** : la recherche tolère les lettres turques (« isik » trouve « Işık ») ; le tri suit la langue.
- **Identifiants des comptes** : une seule règle ramène les noms à des lettres simples (« Ayşe Işık » → ayse.isik) ;
  un deuxième compte au même nom demande « C'est une autre personne » ; un identifiant qui pourrait désigner deux
  comptes est refusé à la connexion, qui demande l'identifiant exact. Les comptes existants ne sont pas renommés.
- **Import ZIP** : les réglages absents du ZIP (langue, devise, réglages de la 2.0) gardent la valeur de la base, et la
  confirmation les nomme ; en mode Solo, si votre fiche « moi » n'est plus claire après l'import, Prévo vous demande
  qui vous êtes au lieu de deviner.
- **« Commencer vide »** ouvre directement une base vide ; la démo peut s'y charger plus tard (démo › Exporter en ZIP,
  puis Paramètres › Sauvegardes › Importer un ZIP).
- **Saisies** : « N/A », « NTR » et « nothing to report » sont refusés comme « RAS » ; « yes / no » est compris comme
  « oui / non ».
- **ZIP jusqu'à 4 Go** : l'export et l'import lisent et écrivent le ZIP par morceaux, un document à la fois, au lieu
  de tout charger en mémoire. Un ZIP peut maintenant faire 4 Go (4 Go une fois décompressé, 10 000 fichiers au plus ;
  toujours 50 Mo par table et 10 Mo par document).
- **Avertissement avant un gros export** : Prévo ne prévient plus qu'au-delà de 500 Mo (au lieu de 150 Mo). Écrit par
  morceaux, le ZIP demande au navigateur jusqu'à une fois et demie sa taille en mémoire, au lieu de 5 à 6 fois.
- **Navigateur trop ancien** : lire ou écrire un ZIP par morceaux demande un navigateur récent (Chrome, Edge, Firefox
  ou Safari). Un navigateur trop ancien refuse l'export et l'import ZIP avec un message clair : mettez-le à jour, ou
  copiez simplement votre dossier de données pour le sauvegarder ou le transporter.
- **Fichier ouvert dans Excel** : le message nomme le fichier et dit quoi faire (« Le fichier « equipements.csv » est
  ouvert dans Excel ou un autre logiciel : fermez-le, puis réessayez. »), dans les deux modes ; la saisie reste dans
  le formulaire.
- **Place des documents (mode serveur)** : 4 Go par défaut au lieu de 2 Go, comme l'import ZIP ; quand elle est
  pleine, le message dit où l'agrandir (Paramètres › Accès et installation, sur le PC serveur).
- **Import ZIP** : si le fichier ZIP est modifié, déplacé ou supprimé pendant l'import, Prévo le dit clairement et
  n'importe rien ; il suffit de relancer l'import.

### Retiré

- **JSZip** : Prévo n'embarque plus cette bibliothèque, qui gardait tout le ZIP en mémoire ; il lit et écrit les ZIP
  lui-même. Les ZIP exportés par les versions précédentes (1.2 et bêtas de la 2.0) restent lisibles.

## [2.0.0-beta.2] - 2026-11-05

Deuxième bêta de la 2.0 (pré-version : pour essayer, pas pour la production ; la version stable reste la 1.2.1).
Elle se met par-dessus la bêta 1 : vos données sont migrées automatiquement, après une sauvegarde « avant mise à jour ».

### Corrigé

- **Plus de perte de données sur un fichier abîmé** : si un fichier de données est abîmé hors de Prévo (une note tapée
  dans Excel, un guillemet oublié), Prévo ne le réécrit plus jamais, ne perd plus ce qu'il n'avait pas su lire, affiche
  un bandeau « Fichier abîmé » et garde votre saisie dans le formulaire. Seules la restauration d'une sauvegarde et
  l'import ZIP peuvent le remplacer.
- **Un fichier abîmé ne bloque plus la sauvegarde quotidienne** : elle est faite, marquée « abîmé » au manifeste, et
  les 7 dernières sauvegardes saines sont toujours gardées.

### Ajouté

- **Un format de données versionné** : chaque base porte son format, décrit dans [docs/FORMAT.md](docs/FORMAT.md).
- **Migration automatique** : au démarrage, une base d'un format plus ancien est mise à niveau étape par étape, après
  une sauvegarde « avant mise à jour ».
- **Lecture seule d'une base plus récente** : si les données viennent d'une version de Prévo plus récente que la
  vôtre, Prévo les lit sans rien modifier.
- **Sauvegardes** : une avant chaque mise à jour, une par jour, gardées 30 jours ; celles d'avant mise à jour ne sont
  jamais effacées.
- **Export ZIP complet** (Paramètres › Sauvegardes) : tous les fichiers de données, les documents, les rapports figés
  et un manifeste. Le dossier des accès n'y est jamais ; avec les comptes, le responsable seul peut l'exporter.
- **Export « données seules »** (sans les documents) : plus léger, importable comme l'export complet ; l'import ne
  supprime alors aucun document existant. Avant un export complet de plus de 150 Mo, qui demande beaucoup de mémoire,
  Prévo prévient et propose les données seules.
- **Import ZIP** : contrôle du fichier, confirmation détaillée, sauvegarde avant remplacement, retour arrière
  automatique en cas d'échec.
- **Tout ce que Prévo exporte, Prévo peut le réimporter** : un ZIP produit par l'export est toujours accepté à
  l'import, y compris pour une grosse base ; l'export prévient avant de produire un ZIP que l'import refuserait. Limites
  d'un ZIP : 400 Mo et 10 000 entrées ; 50 Mo par table ; 10 Mo par document.
- **Base avec un fichier abîmé** : l'export la marque « abîmé » au manifeste et garde le fichier tel quel ; l'import le
  retrouve dans le même état, avec le bandeau « Fichier abîmé ».
- **Signalement des versions** : une bêta est prévenue de la 2.0.0 finale (comparaison correcte des numéros de version).

### Modifié

- **Hébergement derrière nginx ou IIS** : Prévo accepte l'enregistrement d'une table jusqu'à 50 Mo. Si Prévo est
  derrière un de ces serveurs, relevez sa limite d'envoi (nginx : `client_max_body_size 52m;` ; IIS :
  `maxAllowedContentLength="54525952"`), sinon les grosses tables seront refusées. Détail dans
  [docs/INSTALLATION.md](docs/INSTALLATION.md).

## [2.0.0-beta.1] - 2026-10-28

Publiée d'abord sous le numéro 2.0.0, renommée « bêta 1 » le 2026-11-04.

Le lot 7 : l'accès et l'installation (le détail est dans [docs/PILOTAGE.md](docs/PILOTAGE.md), l'installation pour
l'informaticien dans [docs/INSTALLATION.md](docs/INSTALLATION.md)). Version majeure : au-delà de ce PC, la connexion
devient obligatoire.

### Ajouté

- **Connexion et rôles** : au-delà de ce PC, chaque personne a son compte et le serveur vérifie les droits de chaque
  rôle ; un demandeur peut n'avoir qu'un téléphone enrôlé par QR, sans mot de passe.
- **Assistant d'installation** : trois questions au premier lancement (qui, depuis où, votre compte), le https de
  l'atelier, Tailscale hors de l'atelier, le démarrage avec le PC et la copie des sauvegardes ; Python est dans le zip.
- **Trois portées** : ce PC (comme avant, sans mot de passe), le Wi-Fi de l'atelier, aussi hors de l'atelier. Prévo
  refuse d'écouter le réseau sans comptes ni https.
- **https sans rien acheter** : une page d'entrée guide chaque téléphone pas à pas pour « faire confiance au PC
  atelier » (Android, iPhone), puis ouvre la fiche demandée en https ; le certificat de l'atelier est fabriqué par
  mkcert, livré dans le zip avec son empreinte vérifiée. Les étiquettes QR gardent l'adresse de la page d'entrée.
- **Équipe › Accès** (responsable) : comptes (rôle, technicien lié, mot de passe provisoire montré une fois,
  réinitialiser, désactiver), invitations QR pour les téléphones des demandeurs, révocation immédiate, journal des
  connexions consultable et exportable.
- **Écran de connexion** : « rester connecté sur cet appareil », changement obligatoire d'un mot de passe provisoire,
  déconnexion ; mot de passe oublié : `Reinitialiser_mot_de_passe.bat` sur le PC serveur.
- **Hors de l'atelier** : Tailscale détecté et guidé (jamais installé à votre place), signalé sur l'accueil du
  responsable s'il est déconnecté ou si sa clé expire ; ou derrière le mandataire inverse de l'entreprise (nginx,
  Caddy, IIS, Cloudflare Tunnel).
- **Démarrer avec le PC** : tâche planifiée au démarrage, règle du pare-feu en réseau privé et veille désactivée sur
  secteur, en une seule invite d'administrateur ; retrait depuis Paramètres.
- **Mode Solo** : pour une personne seule, menu allégé, technicien « moi », « Nouvel OT » en premier et clôture en une
  étape.
- **Sauvegardes** : copie externe chaque nuit (clé USB, NAS, dossier synchronisé ; 30 gardées), « Tester » une
  sauvegarde, une sauvegarde manuelle par minute au plus (60 gardées).
- **Paramètres › Accès et installation** : chaque réglage de l'assistant se refait depuis le PC serveur, avec l'état du
  serveur (actif depuis, adresses, Tailscale, copie externe, dernières lignes du journal).
- **Aide à l'écran** : à la première ouverture de chaque écran, un encart en haut de la page dit ce qu'il contient,
  ce qu'on y fait et propose un geste à essayer, avec un lien vers la partie du guide ; il ne bloque rien,
  « Compris » le ferme pour de bon sur ce poste. Les textes suivent le profil (accueil, demandes, ordres de travail,
  page du wiki) ; dans la démo en ligne, l'accueil rappelle qu'on peut tout essayer. Lien « Explications » dans le
  menu ; dans Ce poste, la case pour la couper et « Revoir toutes les explications ».
- **docs/INSTALLATION.md** : la configuration (`prevo.config.json`), les mandataires, les services, les comptes, le
  journal et les sauvegardes, pour l'informaticien.

### Modifié

- Le zip embarque Python 3.14 (paquet officiel Windows 64 bits) : rien à installer ; ailleurs, un Python 3.11 ou plus
  récent suffit.
- Sans configuration, le serveur n'écoute que sur ce PC (127.0.0.1) ; la console et l'accueil disent quand un
  téléphone ne peut pas joindre Prévo.
- Le guide : chapitre 2 réécrit autour de l'assistant, chapitre 3 « Les rôles et les profils », nouveau chapitre 8
  « Accès et installation » (connexion, faire confiance au PC atelier, Tailscale, démarrage, Solo, RGPD, annuaire).
- En mode serveur, le fournisseur d'IA et sa clé se règlent sur le PC serveur, jamais dans les navigateurs ; avec les
  comptes, l'assistant IA est réservé aux techniciens et au responsable.
- Documents joints : le serveur ajoute la date et l'heure devant leur nom ; `.doc` et `.xls` sont refusés ; les
  fichiers autres que les images, les PDF et les rapports figés s'ouvrent en téléchargement.

### Sécurité

- Corrections de l'audit de la version 1.1 : contrôle des fichiers CSV reçus (E2), clé de l'IA gardée sur le PC
  serveur (M1 à M3), en-têtes de sécurité (F1), limites de ressources : 32 requêtes à la fois et quota du dossier des
  documents (F2), documents (F4), chemins notés tels quels dans le journal du serveur (I2), rubrique RGPD du guide (I4).
- Mots de passe hachés (scrypt), sessions dans un cookie HttpOnly, attente puis blocage après des échecs de
  connexion, journal des connexions gardé un an ; la clé privée du certificat de l'atelier ne part jamais dans une
  sauvegarde.

### Migration

- Une installation 1.2 garde ses fichiers CSV : l'assistant les montre et n'y touche pas. Les profils mémorisés ne
  servent plus quand les comptes sont exigés. Les étiquettes QR imprimées en 1.2 restent valables (même adresse,
  même port : la page d'entrée). Lancé sans configuration, le serveur reste en portée « ce PC », comme avant.

## [1.2.1] - 2026-11-04

**Correctif important : protection contre une perte de données sur fichier abîmé.** Mise à jour recommandée pour
tous les utilisateurs de la 1.2.0 ; rien d'autre ne change (mêmes écrans, même format de données).

**Ce qui pouvait arriver.** Si l'un des fichiers CSV de Prévo était abîmé en dehors de Prévo (une note tapée à
droite du tableau dans Excel, un guillemet oublié dans le Bloc-notes, une copie ou une synchronisation interrompue),
Prévo le relisait du mieux qu'il pouvait, puis le réenregistrait à la première modification, parfois dès
l'ouverture (quand il crée les ordres de travail préventifs du jour) : ce qu'il n'avait pas pu lire était perdu,
sans avertissement. La sauvegarde du jour gardait l'original.

### Corrigé

- **Un fichier abîmé n'est plus jamais réécrit** : Prévo refuse de l'enregistrer, en mode dossier comme en mode
  serveur ; seule la restauration d'une sauvegarde peut le remplacer.
- **Bandeau « Fichier abîmé » dès l'ouverture** : il nomme le fichier et dit quoi faire ; un enregistrement refusé le
  dit aussi, et la saisie reste dans le formulaire.
- Le refus couvre toutes les écritures : formulaires, ordres de travail préventifs créés à l'ouverture, journal (une
  ligne de journal refusée ne fait pas échouer l'action), passage au format (aucune sauvegarde refaite à chaque
  ouverture) ; le serveur répond 409 `fichier_abime` à une écriture directe (`PUT` ou ajout).

**Si le bandeau apparaît.** Le responsable ferme Excel (ou le programme qui a ouvert le fichier), puis ouvre
Paramètres › Sauvegardes et clique sur « Restaurer… » devant la sauvegarde du jour, ou celle de la veille si le
fichier était déjà abîmé (« Une seule table » ne remet que ce fichier ; Prévo copie d'abord l'état actuel dans une
copie de sécurité). Il peut aussi réparer le fichier : ce qui ne va pas est décrit dans Paramètres › Contrôle de la
base. Les autres profils préviennent le responsable. Aide : https://github.com/prevo-pro/prevo/issues

## [1.2.0] - 2026-10-24

Le lot 6 : le wiki de maintenance, l'encyclopédie de l'atelier (le détail est dans
[docs/PILOTAGE.md](docs/PILOTAGE.md)). Le logiciel prend le nom **Prévo**.

### Ajouté

- **Wiki de maintenance** (menu « Wiki ») : une page par machine, par panne, par article, par technicien, par
  intervention et par savoir-faire, calculée à partir des données de l'atelier (pannes et ce qui les a réglées,
  interventions, pièces consommées, stock, consignation en tête de page, petits numéros vers les ordres de travail
  cités) et complétée par des textes courts (« En bref » et « Astuces » d'une machine, « À quoi il sert » d'un
  article, savoir-faire communs aux machines) ; recherche sans IA sur les noms, les interventions et les textes ;
  accueil « Ce que l'atelier sait » ; ce que voit chaque profil est borné (le demandeur ne voit ni les techniciens
  ni les interventions, les prix restent au responsable).
- **Astuce pour la prochaine fois** : une phrase courte saisie à la clôture technique d'un ordre de travail,
  cherchée avec les pages du wiki.
- **Ingestion par l'assistant IA** : à la clôture administrative, l'ordre de travail entre dans la file du wiki ;
  le responsable la traite depuis le journal du wiki (« Traiter la file ») sur un poste où l'IA est réglée ; le
  modèle propose, Prévo contrôle (rien d'inventé, chaque phrase cite un ordre de travail, aucune consigne de
  sécurité, longueurs, un seul savoir-faire par geste, relance avec la raison du refus), le responsable valide,
  rejette ou relance ; les contradictions se tranchent ; l'écriture à la main et le contrôle du wiki restent
  possibles. Coût mesuré sur la démo avec Claude Sonnet : 0,026 $ par ordre de travail.
- **Signalement des nouvelles versions** (responsable, Paramètres > « Me signaler les nouvelles versions de
  Prévo », désactivé par défaut) : Prévo lit `https://prevo.pro/version.json` au plus une fois par jour et par
  poste et, quand une version plus récente existe, le dit sur l'accueil du responsable et dans « À propos », avec
  le lien de téléchargement et les nouveautés. Rien ne s'installe tout seul.
- Démo : son wiki a été rédigé par Claude Sonnet avec la consigne de Prévo (227 interventions, 42 pages), relu
  par un relecteur indépendant ; chapitre « Le wiki de maintenance » du guide ; outil de release qui écrit
  `version.json`.

### Modifié

- Le logiciel s'appelle désormais **Prévo** (l'ancien nom était déjà celui d'une autre GMAO). Le nom
  change partout : écrans, guide, documents, en-tête `X-Prevo`, variables `PREVO_*`, fichiers produits
  (`prevo-export-…`, `prevo-v…`). Sur chaque poste, le profil, le thème, les réglages de l'assistant
  et le dossier de données sont à choisir de nouveau une fois.
- Format des données en **version 3** : deux tables de plus (`wiki_pages.csv`, `wiki_journal.csv`, 24 fichiers)
  et la colonne `astuce` des ordres de travail, ajoutées au premier enregistrement après une sauvegarde
  « avant-format-v3 » ; les fichiers des versions 1 et 2 restent lus.
- La carte « Résumer l'historique » de la fiche d'un équipement (assistant IA du lot 4) est remplacée par le
  lien vers la page du wiki de la machine.

## [1.1.0] - 2026-10-22

Le lot 5 : reprendre ses données existantes (le détail est dans [docs/PILOTAGE.md](docs/PILOTAGE.md)).

### Ajouté

- Assistant « Importer des données » (responsable, depuis Paramètres ou l'accueil d'une base vide) : fichiers
  Excel (.xlsx, .xls), OpenDocument (.ods), CSV et collage ; colonnes reconnues par leur titre (proposition
  de l'IA possible, titres seulement) et retenues sur le poste ; aperçu de chaque ligne avant d'écrire (à
  créer, à mettre à jour, identique, refusée, doublon) ; sauvegarde « Avant import » puis « Annuler cet
  import » ; lignes refusées téléchargeables ; modèles à remplir.
- Reprise de l'historique des interventions d'une autre GMAO : ordres de travail clôturés, ancien numéro
  gardé dans le compte rendu, doublons sûrs et supposés montrés, durée d'arrêt jamais inventée.
- Accueil du responsable repensé (synthèse, « À traiter en premier », compteurs, tuiles à surveiller),
  menu latéral allégé, barre du bas en verre dépoli sur téléphone, notifications en bulle.
- Démo en ligne (outil de construction et guide de déploiement) et zip de release allégé ; licence MIT
  seule dans LICENSE et NOTICE pour les bibliothèques tierces ; guide de contribution, formulaires
  d'issues.

### Modifié

- Disponibilité : une panne sans durée d'arrêt n'est plus comptée 0 h ; elle est exclue du MTTR et de la
  disponibilité (et listée), pour tous les ordres de travail.
- Une ligne importée que le formulaire de l'écran refuserait est refusée de la même façon.

### Corrigé

- Ouverture plus rapide d'une grande base : la génération du préventif ne relit plus toute la table à
  chaque ordre de travail créé.

## [1.0.0] - 2026-10-21

Première version, qui réunit les lots 1 à 4 du cahier des charges (le détail, lot par lot, est dans
[docs/PILOTAGE.md](docs/PILOTAGE.md)).

### Ajouté

- Lot 1, le socle : trois modes de stockage (dossier, serveur Python local, démo en mémoire) avec
  écritures concurrentes gérées entre postes, profils Demandeur, Technicien et Responsable, parc
  d'équipements, demandes d'intervention et ordres de travail au cycle de vie complet.
- Lot 2 : maintenance préventive, magasin de pièces, sortie de pièces depuis l'ordre de travail,
  encart des causes fréquentes, format de fichiers v2 (sauvegarde « Avant format 2 » au passage).
- Lot 3 : indicateurs et graphiques, planning de la semaine, étiquettes QR par lot, contrôles
  réglementaires, équipe et habilitations, rapport mensuel figé.
- Lot 3 bis : préventif suggéré (créer une gamme, revoir le préventif, revoir ou allonger une
  gamme) ; Prévo ne modifie jamais une gamme tout seul.
- Lot 4 : assistant IA facultatif qui propose sans décider (Ollama dans l'atelier, ou service en
  ligne autorisé par le responsable), dictée vocale, écran « Ce poste » avec thème clair, https en
  option, guide d'utilisation imprimable, fiche technique des fichiers CSV.
- Données dans 22 fichiers CSV lisibles dans Excel ; 907 tests automatisés.

[Non publié]: https://github.com/prevo-pro/prevo/compare/v2.4.0...HEAD
[2.4.0]: https://github.com/prevo-pro/prevo/compare/v2.1.2...v2.4.0
[2.2.0-beta.1]: https://github.com/prevo-pro/prevo/compare/v2.1.1...v2.2.0-beta.1
[2.1.2]: https://github.com/prevo-pro/prevo/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/prevo-pro/prevo/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/prevo-pro/prevo/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/prevo-pro/prevo/compare/v2.0.0-beta.2...v2.0.0
[2.0.0-beta.2]: https://github.com/prevo-pro/prevo/compare/v2.0.0-beta.1...v2.0.0-beta.2
[2.0.0-beta.1]: https://github.com/prevo-pro/prevo/compare/v1.2.0...v2.0.0-beta.1
[1.2.1]: https://github.com/prevo-pro/prevo/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/prevo-pro/prevo/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/prevo-pro/prevo/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/prevo-pro/prevo/releases/tag/v1.0.0
