# 12 — Benchmark des vendeurs d'alarme maison (2026)

Étude de marché des principaux acteurs de l'alarme résidentielle (télésurveillée
et DIY), pour nourrir l'amélioration du système auto-hébergé AEGIS (Raspberry Pi
5 + Zigbee + caméras Tapo + YOLO + notifs mail/Telegram + sirène Zigbee à venir).
Recherche web, sources citées par vendeur.

## 1. Vendeurs étudiés

11 acteurs couvrant les deux modèles dominants : télésurveillance pro française/
européenne (Verisure, Bosch, Somfy) et DIY américain avec option monitoring
(ADT, Ring, SimpliSafe, Google Nest, Arlo, Ajax, Abode, Frontpoint).

---

### Verisure (Securitas Direct)

**Modèle** : télésurveillance 24/7 obligatoire, abonnement + installation
professionnelle (pas de mode autonome sans abonnement).

- **Capteurs** : centrale d'alarme, détecteurs d'ouverture, détecteur de
  mouvement (avec variante extérieure), détecteur de bris de glace (en option),
  détecteur de fumée/CO, lecteur de badges. Caméras propriétaires + caméra Arlo
  en option. Détection de présence par IA sur les caméras (visages/silhouettes).
- **Anti-sabotage / résilience** : autoprotection (ouverture boîtier, arrachement
  détecteur, coupure de câble) déclenche une alarme technique. Détection de
  perte de signal / brouillage avec alerte immédiate à l'app et au centre de
  télésurveillance. **Réseau ATN propriétaire** (antennes/stations propres,
  indépendant des réseaux mobiles classiques) en secours du GSM/4G — contourne
  le brouillage GSM classique. Batterie de secours sur la centrale. Certification
  **NFA2P** (CNPP) qui impose des exigences de résistance au sabotage/brouillage.
- **Différenciateur exclusif** : **Brouillard Anti-Cambriolage (BAC©)** — un
  générateur de fumée opaque qui envahit la pièce en quelques secondes pour
  aveugler/faire fuir l'intrus après intrusion confirmée. Unique sur le marché.
- **Modes d'armement** : total/partiel via badge, clavier ou app My Verisure.
- **Levée de doute** : centre de télésurging certifié, intervention humaine sur
  alerte confirmée, délai moyen d'intervention agent 7-15 min en zone urbaine.
- **UX** : app My Verisure, badges NFC, extensions modulaires (serrure connectée,
  caméra).
- **Prix** : à partir de **34,90 €/mois** + installation **~199 € HT**. Coût très
  supérieur aux solutions DIY sur la durée (contrat pluriannuel fréquent).

Sources : [presse-citron.net](https://www.presse-citron.net/domotique/alarme-maison/avis-verisure/prix-surveillance/), [verisure.fr — alarme anti-brouillage GSM](https://www.verisure.fr/alarme-anti-brouillage-gsm), [verisure.fr — brouilleur alarme](https://www.verisure.fr/guide-securite/systeme-d-alarme/types-d-alarme/alarme-gsm/brouilleur-alarme-comment-ca-marche), [journaldugeek.com](https://www.journaldugeek.com/alarme/prix-verisure/), [connexit.fr — autoprotection](https://connexit.fr/autoprotection-alarme-systeme-anti-sabotage/)

---

### ADT (ADT+ / Blue by ADT)

**Modèle** : télésurveillance pro par défaut (plans $24,99-$39,99/mois), matériel
DIY-installable (« Self Setup ») ou installation pro.

- **Capteurs** : contact porte/fenêtre, mouvement PIR, détecteur de fumée/CO,
  caméras (intérieur/extérieur), intégrations tierces (Google Nest, Yale, Netgear).
- **Anti-sabotage / résilience** : protocole **DECT ULE** dédié (hors bandes
  Wi-Fi encombrées), donc plus résistant au brouillage Wi-Fi classique.
  **Backup cellulaire 4G LTE (AT&T)** automatique si la Wi-Fi tombe (panne ou
  brouillage). Article dédié « How ADT is protecting smart homes from Wi-Fi
  jamming » — communication publique forte sur ce point.
- **Modes d'armement** : plans échelonnés Secure / Smart (+domotique) / Complete
  (+caméras, vérification vidéo, monitoring vidéo live 24/7).
- **Levée de doute** : vérification vidéo et monitoring vidéo live sur le plan
  Complete ($39,99/mois).
- **UX** : app ADT+, intégrations domotique tierces (thermostats, serrures,
  éclairage), commande vocale via Google/Alexa.
- **Différenciateur** : plus gros réseau télésurveillé des USA, écosystème
  domotique tiers très ouvert.

Sources : [security.org — ADT review](https://www.security.org/home-security-systems/adt/review/), [newsroom.adt.com — Wi-Fi jamming](https://newsroom.adt.com/safe-stories/how-adt-is-protecting-smart-homes-from-wi-fi-jamming), [security.org — ADT cost](https://www.security.org/home-security-systems/adt/)

---

### Ring Alarm (Amazon)

**Modèle** : DIY, autonome possible sans abonnement (app + notifications locales),
monitoring pro optionnel.

- **Capteurs** : contact porte/fenêtre, mouvement PIR, **détecteur de bris de
  glace par IA acoustique** (jusqu'à ~7,5 m, reconnaît différents types de verre
  pour réduire les fausses alarmes), capteur **inondation & gel** (déclenche la
  sirène si armé), bouton panique.
- **Anti-sabotage / résilience** : **backup cellulaire** (Alarm Cellular Backup)
  si la connexion internet tombe, stockage vidéo local sur microSD (Alarm Pro).
  Pas d'information publique détaillée sur la détection de tamper/brouillage RF
  (moins mis en avant que chez Ajax/Verisure/ADT).
- **Modes d'armement** : Home / Away via app, clavier, Alexa.
- **Levée de doute** : sirène déclenchée automatiquement par les capteurs
  secondaires (bris de glace, inondation) en mode armé ; monitoring pro
  disponible via plan Ring Home Pro+ (24/7, $20/mois).
- **UX** : app Ring, intégration Alexa forte, écosystème caméras Ring très large.
- **Prix** : kits matériel $199,99 à ~$350. Abonnement Ring Home Plus $10/mois
  (fonctions complètes, caméras illimitées, backup cellulaire), Pro+ $20/mois
  (+ monitoring pro 24/7).
- **Différenciateur** : le moins cher à l'entrée, très bien intégré à
  l'écosystème Alexa/caméras Ring, fonctionne en autonome sans abonnement.

Sources : [ring.com/plans](https://ring.com/plans), [ring.com — glass break sensor](https://ring.com/ring-sensors), [safehome.org — Ring Alarm pricing](https://www.safehome.org/security-systems/ring-alarm/), [home-security-reviews.com](https://home-security-reviews.com/ring-subscription-changes-2026/)

---

### SimpliSafe

**Modèle** : DIY, autonome possible, monitoring pro optionnel sans engagement.

- **Capteurs** : contact porte/fenêtre, mouvement **pet-immune jusqu'à ~23 kg**
  (réglable), détecteur de bris de glace (fréquence spécifique, ~6 m), capteur
  d'eau, détecteur de fumée (feux vifs et couvants).
- **Anti-sabotage / résilience** : **backup cellulaire AT&T LTE intégré** à la
  base, activation automatique si l'internet tombe, **batterie de secours 24h**
  en cas de coupure secteur. Tests utilisateurs publics de brouillage
  (« they even tried jamming their SimpliSafe system ») sans détail technique
  officiel équivalent à Ajax.
- **Modes d'armement** : Home/Away via app/clavier.
- **Levée de doute** : **alarmes vérifiées vidéo** (clip vidéo transmis au centre
  de télésurveillance dès l'événement) sur les plans Core et supérieurs — accélère
  la réponse police (dossiers vérifiés traités en priorité aux USA).
- **UX** : app SimpliSafe, clavier, badge, intégrations Alexa/Google.
- **Prix** : matériel $250-$730. Abonnements $22,99-$32,99/mois (Standard à Core),
  jusqu'à $80/mois pour les plans avec le plus de caméras/stockage.
- **Différenciateur** : bon rapport qualité/prix DIY + vérification vidéo
  accessible dès le plan milieu de gamme, sans engagement contractuel.

Sources : [security.org — SimpliSafe](https://www.security.org/home-security-systems/simplisafe/), [simplisafe.com — glass break](https://simplisafe.com/glassbreak-sensor), [simplisafe.com — motion pet friendly](https://simplisafe.com/motion-sensor), [safewise.com — SimpliSafe cost](https://www.safewise.com/home-security-systems/simplisafe/cost/)

---

### Google Nest (post Nest Secure)

**Modèle** : **Nest Secure a été arrêté par Google en avril 2024** — il n'existe
plus d'alarme Nest complète. Google vend désormais des caméras/capteurs isolés
(Nest Cam, Nest Doorbell) et laisse l'alarme aux partenaires (ADT intègre les
produits Nest).

- **Capteurs** : caméras intérieur/extérieur, sonnette, détection de personnes/
  véhicules/paquets par IA, **reconnaissance faciale** (abonnement).
- **Résilience** : dépend du réseau Wi-Fi domestique, pas de backup cellulaire
  natif (contrairement à ADT/Ring/SimpliSafe) — point faible notable pour une
  alarme complète.
- **Abonnement** : Google Home Premium (ex-Nest Aware) $10/mois ou $100/an —
  30 jours d'historique événementiel, alertes intelligentes, reconnaissance
  faciale.
- **Différenciateur** : qualité IA de détection/reconnaissance faciale parmi les
  meilleures du marché caméra, mais **plus de brique « alarme » (sirène, contact,
  clavier) autonome** — nécessite un partenaire (ADT) pour un système complet.
- **Enseignement clé** : le retrait de Nest Secure montre la fragilité du modèle
  "alarme intégrée propriétaire" face à un pivot stratégique fournisseur — argument
  fort en faveur du DIY auto-hébergé sur standards ouverts (Zigbee/MQTT).

Sources : [security.org — Nest Secure discontinued](https://www.security.org/home-security-systems/nest-security/review/), [safehome.org — Nest pricing](https://www.safehome.org/security-systems/nest-secure/), [adt.com — Google Nest Aware](https://www.adt.com/products/google-nest-aware)

---

### Arlo (Arlo Secure / Security System)

**Modèle** : DIY, caméras + capteurs multi-fonctions, abonnement pour l'IA avancée.

- **Capteurs** : **capteur 8-en-1** — mouvement, ouverture, inondation, gel,
  inclinaison (porte de garage), luminosité, écoute fumée/CO. Caméras avec
  détection **personne / véhicule / paquet / animal**, reconnaissance faciale
  (plans Plus/Premium).
- **Anti-sabotage / résilience** : peu d'information publique sur le backup
  cellulaire natif du hub (plus orienté caméras Wi-Fi/batterie que centrale
  d'alarme classique).
- **Différenciateur** : **Arlo Early Warning System** — combine reconnaissance
  de menace en temps réel + outils de dissuasion (sirène, lumière, message vocal)
  avant même l'intrusion confirmée, en détectant l'approche (personne/véhicule
  qui rôde).
- **Levée de doute** : vérification par IA multi-classes très fine, réduit les
  fausses alertes.
- **UX** : app Arlo Secure, intégrations Alexa/Google/HomeKit.
- **Prix** : kit de base $199,99 (hub + 2 capteurs + essai 30 j). Abonnements
  Plus $7,99-$17,99/mois, Premium jusqu'à $29,99/mois (ou $24,99 annualisé).
- **Différenciateur clé** : la meilleure détection IA multi-classes + dissuasion
  précoce avant intrusion du marché DIY.

Sources : [arlo.com/arlosecure](https://www.arlo.com/en-us/arlosecure.html), [t3.com — Arlo warning system](https://www.t3.com/home-living/smart-home/arlos-most-advanced-warning-system-is-here-and-its-detection-features-are-next-level), [security.org — Arlo cameras](https://www.security.org/security-cameras/arlo/)

---

### Ajax Systems

**Modèle** : matériel professionnel/semi-pro vendu via installateurs ou en kit,
autonome ou télésurveillé, très fort sur la fiabilité RF.

- **Capteurs** : gamme très large — contact, mouvement (dont extérieur, avec
  photo-vérification sur certains modèles), bris de glace, fumée/CO,
  inondation, vibration/choc (DoubleButton, LeaksProtect, FireProtect...).
- **Anti-sabotage / résilience** — **le plus avancé du panel** :
  - **Détection de brouillage (jamming) native** avec bascule automatique sur
    17 fréquences disponibles réparties sur 4 bandes européennes, alerte
    immédiate à l'utilisateur ET au centre de télésurveillance.
  - **Anti-masking** (détection d'obstruction volontaire d'un capteur).
  - **Tamper switch** sur chaque appareil (arrachement ou ouverture du boîtier).
  - **Chiffrement des communications** (Jeweller protocol).
  - **Batterie de secours du hub : jusqu'à 16h** sans secteur.
  - Autonomie batterie des capteurs jusqu'à **7 ans**, alerte 3 mois avant fin
    de vie de la pile.
- **Modes d'armement** : total / partiel / **nuit** (zones sélectives), groupes
  configurables, « Easy armed mode change » (changement de mode par simple
  passage de badge sans code sur le clavier).
- **UX** : claviers avec **tags/cartes NFC chiffrés DESFire** (quasi impossibles
  à cloner), app Ajax, gestion fine des droits par utilisateur/tag.
- **Prix** : kit de base ~$1 700 posé (Sipko Starter : hub + 2 mouvement + 2
  contact + 1 sirène), jusqu'à ~$2 800 pour un pack villa avec photo-vérification
  et détection incendie.
- **Différenciateur clé** : **la référence technique anti-sabotage/anti-brouillage
  du marché** — c'est le vendeur le plus pertinent à étudier pour durcir un
  système DIY.

Sources : [sipkosecurity.com — Ajax guide 2026](https://sipkosecurity.com/ajax-alarm-systems-the-2026-comprehensive-installation-ecosystem-guide/), [ajax.systems — wireless grade 3](https://ajax.systems/solutions/wireless-grade-3/), [sipkosecurity.com — Ajax jamming](https://sipkosecurity.com/ajax-alarm-being-jammed-what-actually-happens-and-how-to-detect-it/), [ajax.systems — Night mode](https://ajax.systems/support/posts/what-is-night-mode/), [ajax.systems — Tag](https://ajax.systems/products/tag/)

---

### Bosch Smart Home

**Modèle** : DIY pur, aucun monitoring professionnel proposé — 100% autonome.

- **Capteurs** : contrôleur central, contact porte/fenêtre II, détecteur de
  fumée II, caméra intérieure « Eyes », détecteur de mouvement (différencie
  humains/animaux par la reconnaissance de forme et de hauteur → moins de
  fausses alertes), répéteur radio.
- **Anti-sabotage / résilience** : peu de communication publique sur le
  backup cellulaire ou la détection de brouillage — orienté qualité de
  fabrication (marque historique de capteurs industriels) plus que
  résilience réseau anti-intrusion.
- **Modes d'armement** : scénarios personnalisables via l'app (armement,
  simulation de présence, alertes).
- **UX** : app Bosch Smart Home, intégrations domotiques larges (chauffage,
  volets, éclairage) car Bosch vient de l'électroménager/outillage — l'alarme
  est un sous-ensemble d'une offre maison connectée plus large.
- **Prix** : kits sans frais récurrents, mais matériel jugé cher pour ce qu'il
  offre (pas de prix 2026 précis trouvé).
- **Différenciateur clé** : zéro abonnement obligatoire, détection mouvement
  anti-animaux fiable, bonne intégration confort/domotique au-delà de la
  sécurité pure.

Sources : [fmb.org.uk — Bosch review](https://www.fmb.org.uk/homepicks/home-security/bosch-home-security-system-review/), [walmart.com — Bosch smart home sensors](https://www.walmart.com/browse/electronics/smart-home-alarms-and-sensors/bosch/3944_1229875_6357978_5155542/YnJhbmQ6Qm9zY2gie)

---

### Somfy Home Alarm

**Modèle** : DIY, plug & play, pas de télésurveillance intégrée par défaut
(orientée notification utilisateur + dissuasion).

- **Capteurs** : **IntelliTAG** (capteur combiné ouverture + **vibration**, alerte
  dès la tentative d'effraction, *avant* que l'intrusion soit consommée),
  détecteur de mouvement pet-immune jusqu'à 25 kg, sirène intérieure 110 dB.
- **Anti-sabotage / résilience** : peu de détails publics sur backup
  cellulaire/anti-brouillage (gamme plus orientée confort/notification que
  résilience réseau).
- **Modes d'armement** : **géofencing natif** — reconnaissance des porte-clés
  mains libres des occupants habituels, armement/désarmement automatique à
  l'approche/l'éloignement, sans code ni manipulation.
- **Levée de doute** : notification push immédiate app, pas de centre de
  télésurveillance intégré nativement (les offres françaises Somfy Protect
  historiques proposaient un partenariat avec un télésurveilleur).
- **UX** : app Somfy Protect, porte-clés mains libres, forte synergie avec les
  volets roulants/domotique Somfy (simulation de présence via volets).
- **Différenciateur clé** : détection **avant intrusion** (vibration sur
  tentative d'ouverture forcée) + géofencing mains libres très abouti.

Sources : [somfy.co.uk — Home Alarm Premium](https://www.somfy.co.uk/products/2401506/somfy-home-alarm-premium-smart-alarm-system), [somfy.co.uk — sensors](https://www.somfy.me/en-gc/products/home-alarm/sensors), [windowo.com — Somfy Advanced](https://www.windowo.com/somfy-home-alarm-advanced)

---

### Abode

**Modèle** : DIY, **fonctionne sans abonnement** (app, vidéo live, intégrations
gratuites), monitoring pro optionnel.

- **Capteurs** : contact, mouvement, capteurs additionnels via intégrations
  Zigbee/Z-Wave tierces (écosystème très ouvert).
- **Anti-sabotage / résilience** : **backup 4G intégré** de série sur le plan Pro,
  batterie de secours.
- **Modes d'armement** : Home/Away, automatisations via IFTTT.
- **UX** : compatible **Apple HomeKit, Alexa, Google Home, Zigbee, Z-Wave,
  IFTTT** — l'écosystème DIY le plus ouvert du panel. Installation DIY en
  ~15 minutes, fixation adhésive (aucun perçage/câblage).
- **Prix** : Standard $79,99/an ($8,49/mois, autosurveillance). Pro $245,99/an
  ($26,99/mois, monitoring pro 24/7 + 4G).
- **Différenciateur clé** : le plus proche philosophiquement d'un projet DIY —
  aucun abonnement obligatoire, interopérabilité maximale, faible coût d'entrée.

Sources : [goabode.com/plans](https://goabode.com/plans/), [security.org — Abode](https://www.security.org/home-security-systems/abode/), [goabode.com — geofencing](https://goabode.com/blog/geofencing-home-security/)

---

### Frontpoint

**Modèle** : DIY avec monitoring pro quasi systématique (100% cellulaire).

- **Capteurs** : contact, mouvement, gamme classique + caméras.
- **Anti-sabotage / résilience** : **100% cellulaire** (pas de dépendance
  Wi-Fi/box internet), **Crash & Smash protection** — le hub sonne la sirène et
  alerte immédiatement le centre si quelqu'un tente de le détruire/débrancher
  avant qu'il puisse communiquer l'alerte normalement. Batterie de secours 24h.
- **Modes d'armement** : Home/Away via app/clavier.
- **Prix** : matériel dès $69, abonnement Ultimate $49,99/mois (monitoring 24/7
  + cellulaire + vidéo + domotique), plan vidéo seul $14,99/mois.
- **Différenciateur clé** : **Crash & Smash** — la fonction la plus directement
  transposable à un projet DIY (détecter et alerter *avant* que le système soit
  neutralisé physiquement).

Sources : [security.org — Frontpoint](https://www.security.org/home-security-systems/frontpoint/), [safehome.org — Frontpoint reviews](https://www.safehome.org/security-systems/frontpoint/reviews/)

---

## 2. Matrice de fonctions

Légende : ✅ présent (inclus/natif) — 🟡 optionnel (accessoire ou plan payant
supérieur) — ❌ absent / non documenté.

| Fonction | Verisure | ADT | Ring | SimpliSafe | Nest* | Arlo | Ajax | Bosch | Somfy | Abode | Frontpoint |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Contact porte/fenêtre | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Mouvement PIR pet-immune | ✅ | ✅ | ✅ | ✅ | ❌ | 🟡 | ✅ | ✅ | ✅ | 🟡 | ✅ |
| Bris de glace (acoustique) | 🟡 | 🟡 | 🟡 | 🟡 | ❌ | ❌ | ✅ | ❌ | ❌ | 🟡 | 🟡 |
| Vibration / tentative d'effraction | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ |
| Fumée / CO | 🟡 | 🟡 | 🟡 | ✅ | ❌ | 🟡 | ✅ | ✅ | ❌ | 🟡 | 🟡 |
| Inondation / gel | 🟡 | 🟡 | 🟡 | ✅ | ❌ | ✅ | ✅ | 🟡 | ❌ | 🟡 | 🟡 |
| Caméra + détection IA personne | ✅ | ✅ | ✅ | 🟡 | ✅ | ✅ | 🟡 | ✅ | 🟡 | 🟡 | ✅ |
| Reconnaissance faciale | 🟡 | 🟡 | ❌ | ❌ | ✅ | 🟡 | ❌ | ❌ | ❌ | ❌ | ❌ |
| Tamper (arrachement/ouverture boîtier) | ✅ | 🟡 | ❌ | 🟡 | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ✅ (Crash&Smash) |
| Détection de brouillage RF/Wi-Fi | ✅ | ✅ (DECT ULE) | ❌ | ❌ | ❌ | ❌ | ✅ (best) | ❌ | ❌ | ❌ | ❌ |
| Batterie de secours centrale | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ (16h) | 🟡 | 🟡 | ✅ | ✅ (24h) |
| Backup cellulaire/4G | ✅ (+ réseau ATN propre) | ✅ | ✅ | ✅ | ❌ | ❌ | 🟡 | ❌ | ❌ | ✅ | ✅ (natif 100%) |
| Modes total/partiel/nuit/zones | ✅ | ✅ | 🟡 | 🟡 | ❌ | ❌ | ✅ | ✅ | 🟡 | ✅ | 🟡 |
| Géofencing / armement auto | 🟡 | 🟡 | 🟡 | 🟡 | ❌ | ❌ | 🟡 | 🟡 | ✅ (natif) | ✅ | 🟡 |
| Badge/NFC/clavier | ✅ | 🟡 | ✅ | ✅ | ❌ | ❌ | ✅ (DESFire) | 🟡 | ✅ (porte-clés) | 🟡 | ✅ |
| Commande vocale | 🟡 | ✅ | ✅ | 🟡 | ✅ | 🟡 | ❌ | 🟡 | 🟡 | ✅ | 🟡 |
| Vérification vidéo levée de doute | ✅ | ✅ (plan Complete) | 🟡 | ✅ | ❌ | ✅ (IA) | 🟡 | ❌ | ❌ | 🟡 | ✅ |
| Télésurveillance 24/7 humaine | ✅ (obligatoire) | ✅ | 🟡 | 🟡 | ❌ | ❌ | 🟡 | ❌ | ❌ | 🟡 | ✅ (défaut) |
| Sirène intérieure/extérieure | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | 🟡 | ✅ | ✅ | ✅ |
| Dissuasion active (fumée, lumière, message vocal) | ✅ (BAC©) | ❌ | ❌ | ❌ | ❌ | ✅ (Early Warning) | ❌ | ❌ | ❌ | ❌ | ❌ |
| Fonctionnement 100% sans abonnement | ❌ | ❌ | 🟡 | 🟡 | ❌ | 🟡 | 🟡 | ✅ | 🟡 | ✅ | ❌ |

\* Nest : plus d'offre "alarme" complète depuis l'arrêt de Nest Secure (04/2024),
uniquement caméras/capteurs isolés + reconnaissance IA — colonne indicative,
comparaison partielle.

---

## 3. Synthèse pour AEGIS

### (a) Fonctions "table stakes" — le minimum vital que TOUS proposent

Ce sont les fonctions présentes chez la quasi-totalité des vendeurs, quel que
soit le modèle (pro ou DIY) — considérer comme un plancher non négociable :

1. **Contact porte/fenêtre + mouvement PIR pet-immune** — base universelle.
2. **Sirène** (au moins intérieure) déclenchée à l'intrusion.
3. **App mobile** de pilotage (armer/désarmer, notifications, historique).
4. **Batterie de secours** sur la centrale (coupure secteur).
5. **Modes armé total / armé absent / désarmé** au minimum.
6. **Notification immédiate** à l'utilisateur en cas d'événement.
7. **Badge/code/clavier** pour l'armement/désarmement local (pas seulement app).

AEGIS a déjà 1, 3, 6 (mail/Telegram), 7 (à confirmer). Manquent structurellement :
2 (aucune sirène matérielle réelle — cf. audit `docs/10`), 4 (pas de secours
batterie documenté), 5 (modes partiels/zones à vérifier).

### (b) Fonctions différenciantes premium

Ce qui sépare les offres haut de gamme (Verisure, Ajax, Arlo, ADT) du DIY basique :

1. **Détection de brouillage RF/Wi-Fi active avec bascule de fréquence**
   (Ajax : 17 fréquences / 4 bandes ; ADT : DECT ULE hors Wi-Fi).
2. **Backup cellulaire automatique** indépendant de la box internet (quasi tous
   les acteurs américains l'ont ; rare chez les européens DIY).
3. **Réseau propriétaire indépendant du cellulaire classique** (Verisure ATN) —
   contourne même le brouillage GSM.
4. **Tamper/anti-masking par capteur** (arrachement, ouverture, obstruction).
5. **Dissuasion active** avant/pendant l'intrusion (brouillard Verisure,
   Early Warning Arlo avec lumière/message vocal, IntelliTAG Somfy qui détecte
   la tentative *avant* l'effraction consommée).
6. **Vérification vidéo automatique** envoyée au centre de télésurveillance
   (accélère la réponse policière aux USA — dossiers "verified" prioritaires).
7. **Géofencing natif** (armement/désarmement automatique par proximité, sans
   action utilisateur).
8. **Cartes/tags NFC chiffrés anti-clonage** (Ajax DESFire) plutôt que RFID nu.

### (c) 8-10 idées concrètes à reprendre pour AEGIS (DIY)

1. **Sirène physique + logique "Crash & Smash"** (Frontpoint) : le hub/Pi doit
   déclencher la sirène **avant** de tenter les actions lentes (notif, caméra).
   Directement lié au P0 de l'audit `docs/10` (aucune sirène réelle aujourd'hui).
2. **Backup 4G/LTE low-cost** (dongle USB 4G ou module SIM) pour continuer à
   notifier/télésurveiller si la box internet tombe ou est coupée par un
   cambrioleur — quasi tous les vendeurs sérieux l'ont, AEGIS ne l'a pas.
3. **Détection de perte de signal Zigbee par capteur** (heartbeat/timeout) :
   si un capteur Aqara ne répond plus (retiré, brouillé, pile HS), lever une
   alerte "sabotage possible" au lieu de rester silencieux — équivalent logiciel
   du tamper/jamming detection Ajax, faisable sans matériel dédié.
4. **Capteur de vibration/bris de glace sur les points d'accès** (fenêtres,
   porte d'entrée) pour détecter la tentative *avant* l'intrusion consommée
   (logique IntelliTAG Somfy) — plus de marge de réaction que le contact
   d'ouverture seul.
5. **Modes zones/nuit** : armer les capteurs périphériques (portes, jardin) la
   nuit tout en laissant les chambres désarmées pour circuler — actuellement
   AEGIS semble n'avoir que armé/désarmé global (à vérifier dans `devices.yaml`).
6. **Géofencing basé sur la présence du téléphone** (via l'app Home Assistant
   ou Owntracks) pour auto-armer/désarmer — fonction gratuite à implémenter,
   très appréciée (Somfy, Abode).
7. **Escalade en cascade des notifications** avec accusé de réception : mail →
   Telegram → appel vocal automatisé (Twilio) si aucun ack sous N minutes —
   inspiré du modèle télésurveillance humaine sans en payer le coût récurrent.
8. **File d'attente non-bloquante pour notif/sirène/snapshot** (asyncio ou
   thread pool dédié, séparé du thread MQTT) — corrige directement la cause
   racine identifiée dans l'audit `docs/10` (tout synchrone bloque tout).
9. **Vérification vidéo automatique jointe à l'alerte** (photo/clip pris sur
   TOUTES les caméras à portée de la zone déclenchée, pas une caméra arbitraire)
   pour permettre une levée de doute à distance sans se déplacer — logique
   "video verified alarm" de SimpliSafe/Frontpoint, gratuite à implémenter
   en local.
10. **Batterie de secours documentée/testée** pour le Raspberry Pi et le hub
    Zigbee (UPS HAT ou petite batterie USB-C) — coupure secteur = système mort
    aujourd'hui, alors que c'est un standard absolu chez tous les vendeurs
    étudiés.

---

## Sources principales

- [Verisure — prix 2026](https://www.presse-citron.net/domotique/alarme-maison/avis-verisure/prix-surveillance/), [anti-brouillage GSM](https://www.verisure.fr/alarme-anti-brouillage-gsm), [brouilleur alarme](https://www.verisure.fr/guide-securite/systeme-d-alarme/types-d-alarme/alarme-gsm/brouilleur-alarme-comment-ca-marche)
- [ADT review — security.org](https://www.security.org/home-security-systems/adt/review/), [ADT Wi-Fi jamming — newsroom.adt.com](https://newsroom.adt.com/safe-stories/how-adt-is-protecting-smart-homes-from-wi-fi-jamming)
- [Ring plans](https://ring.com/plans), [Ring sensors](https://ring.com/ring-sensors), [safehome.org Ring pricing](https://www.safehome.org/security-systems/ring-alarm/)
- [SimpliSafe — security.org](https://www.security.org/home-security-systems/simplisafe/), [SimpliSafe glass break](https://simplisafe.com/glassbreak-sensor), [SimpliSafe motion pet-friendly](https://simplisafe.com/motion-sensor)
- [Nest Secure discontinued — security.org](https://www.security.org/home-security-systems/nest-security/review/), [ADT Google Nest Aware](https://www.adt.com/products/google-nest-aware)
- [Arlo Secure plans](https://www.arlo.com/en-us/arlosecure.html), [Arlo Early Warning System — t3.com](https://www.t3.com/home-living/smart-home/arlos-most-advanced-warning-system-is-here-and-its-detection-features-are-next-level)
- [Ajax Systems 2026 guide — sipkosecurity.com](https://sipkosecurity.com/ajax-alarm-systems-the-2026-comprehensive-installation-ecosystem-guide/), [Ajax wireless grade 3](https://ajax.systems/solutions/wireless-grade-3/), [Ajax jamming — sipkosecurity.com](https://sipkosecurity.com/ajax-alarm-being-jammed-what-actually-happens-and-how-to-detect-it/), [Ajax Night mode](https://ajax.systems/support/posts/what-is-night-mode/), [Ajax Tag](https://ajax.systems/products/tag/)
- [Bosch home security review — fmb.org.uk](https://www.fmb.org.uk/homepicks/home-security/bosch-home-security-system-review/)
- [Somfy Home Alarm Premium](https://www.somfy.co.uk/products/2401506/somfy-home-alarm-premium-smart-alarm-system), [Somfy sensors](https://www.somfy.me/en-gc/products/home-alarm/sensors)
- [Abode plans](https://goabode.com/plans/), [Abode geofencing](https://goabode.com/blog/geofencing-home-security/), [security.org Abode](https://www.security.org/home-security-systems/abode/)
- [Frontpoint — security.org](https://www.security.org/home-security-systems/frontpoint/), [Frontpoint reviews — safehome.org](https://www.safehome.org/security-systems/frontpoint/reviews/)
- [Autoprotection alarme anti-sabotage — connexit.fr](https://connexit.fr/autoprotection-alarme-systeme-anti-sabotage/)
