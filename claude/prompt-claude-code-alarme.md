# Contexte projet : Alarme DIY Zigbee/NFC — Raspberry Pi 5

## Objectif
Système d'alarme maison auto-hébergé (style Verisure sans abonnement) sur Raspberry Pi 5, appartement 110m² (Neuilly). Stack : Zigbee2MQTT + Mosquitto + Aqara + NFC custom + caméras Tapo + sirène.

## Environnement Pi
- Raspberry Pi 5, 16GB RAM, Debian 12 Bookworm 64-bit
- Conteneurs Docker déjà actifs : `n8n` (port 5678), `mosquitto` (1883/9001)
- User : `j.tremont`
- Réseau : Freebox + extension WiFi à l'autre bout de l'appart (WiFi indépendant du Zigbee)

## État matériel — DÉJÀ FAIT
- ✅ Mosquitto opérationnel en Docker (`~/mosquitto/`), permissions OK, tourne sans erreur
- ✅ 2× prises Sonoff S60ZBTPF (routeurs Zigbee) branchées et alimentées, une de chaque côté du placard central (entre chambres et salon/cuisine), clignotent en bleu (attente réseau — normal, pas encore appairées)
- ✅ 8× capteurs Aqara MCCGQ11LM collés sur portes/fenêtres (1/chambre ×3, cuisine, entrée, 3× salon) — **piles PAS encore activées**
- ❌ Ancien coordinateur Sonoff ZBDongle-P (puce TI CC2652P + CP2102N) confirmé **mort** (DOA) : aucune réponse sur EZSP/bootloader/SPINEL/CPC/Router à aucun baudrate, testé avec `universal-silabs-flasher`, resets RTS/DTR + baudrate + power-cycle à froid sur 2 ports USB différents (2.0 et 3.0). Détecté au niveau USB (idVendor 0x10c4) mais puce muette. Retour Amazon en cours.
- ✅ **Nouveau coordinateur reçu** : dongle Zigbee 3.0 USB, puce **EFR32MG21** + antenne externe SMA (générique, équivalent ZBDongle-E) — PAS le même chipset que l'ancien (CC2652P → EFR32MG21)
- ✅ Câble d'extension USB-A→USB-A 3m (Sonero, USB 3.0, passif) reçu pour sortir l'antenne du placard
- ⚠️ Le port USB **bleu (USB 3.0)** du Pi est confirmé stable ; le port noir (USB 2.0) avait produit des erreurs `cp210x failed set request 0x12 status: -110` avec l'ancien dongle — à garder en tête si nouveau souci de communication USB

## Config Zigbee2MQTT
- Pas encore installé en Docker à ce stade (`/opt/zigbee2mqtt/data` n'existe pas)
- Plan : conteneur `ghcr.io/koenkk/zigbee2mqtt`, `--network host`, volume `~/zigbee2mqtt-data:/app/data`, `--device=/dev/serial/by-id/<nouveau-dongle>`
- Frontend Z2M : port **8081** (8080 déjà pris par un autre service sur ce Pi)
- Canal Zigbee à fixer : **15, 20, 25 ou 26** (éviter interférence WiFi 2.4GHz Freebox)
- ⚠️ IMPORTANT : `onboarding: true` dans la config par défaut lance un serveur d'onboarding codé en dur sur le port 8080 qui plante en EADDRINUSE — mettre `onboarding: false` explicitement
- Adapter à utiliser pour le NOUVEAU dongle EFR32MG21 : **`adapter: ember`** (pas `zstack`, qui était pour l'ancien CC2652P)

## Architecture cible complète (rappel)
- Coordinateur Zigbee + 2 routeurs Sonoff + 8 capteurs Aqara → mesh Zigbee
- Module NFC entrée : LilyGO T-Display-S3 + PN532 + LED WS2812 + buzzer, alimenté 230V via HLK-5M05 + Wago 221 sur ligne interphone — **pas encore monté/soudé**
- 6× caméras Tapo C210, coupées physiquement via prises Tapo P110 pour vie privée
- Sirène Zigbee Tuya TS0601 — **pas encore reçue/installée**
- Logique : délai sortie 3min, délai entrée 60s porte palière, alerte immédiate fenêtres, YOLO ciblé par zone, MQTT bus unifié (Z2M + ESPHome + orchestrateur Python), notifs Telegram primaire + SMS Free Mobile fallback
- 3 badges NFC (toi, Aga, Nadia) — bons tags NFC (MIFARE/NTAG) reçus, anciens T5577 125kHz incompatibles écartés

## Tâches immédiates à faire avec Claude Code

1. **Identifier le port série du nouveau dongle EFR32MG21**
   `ls /dev/serial/by-id/` → noter le nouveau nom exact (différent de l'ancien `usb-ITead_Sonoff...`)

2. **Installer/relancer Zigbee2MQTT en Docker**
   - Créer `~/zigbee2mqtt-data/configuration.yaml` avec : `adapter: ember`, le bon port série, `channel: 15`, `onboarding: false`, `frontend.port: 8081`, `mqtt.server: mqtt://localhost:1883`
   - Lancer le conteneur avec `--network host`, `--device=<port>`, volume data + `/run/udev:ro`
   - Vérifier les logs : coordinateur Ember doit démarrer sans boucle d'erreur, génération PAN ID / network key

3. **Appairer les 2 prises Sonoff S60ZBTPF**
   - `permit_join: true` dans Z2M
   - Vérifier qu'elles apparaissent en rôle **Router** (pas EndDevice)
   - Renommer : `routeur_chambres`, `routeur_salon`

4. **Activer et appairer les 8 capteurs Aqara MCCGQ11LM**
   - Retirer film plastique des piles un par un
   - Appairer dans Z2M, renommer immédiatement selon l'emplacement (ex: `porte_entree`, `fenetre_chambre1`, `fenetre_chambre2`, `fenetre_chambre3`, `fenetre_cuisine`, `porte_fenetre_salon_1/2/3`)

5. **Vérifier la topologie mesh**
   - Dans Z2M, contrôler que les capteurs les plus éloignés passent bien par un routeur (LQI/route map) et pas directement par le coordinateur en signal faible

## Reste du projet (pas encore attaqué)
- Montage physique module NFC (soudures LilyGO + PN532 + LED + buzzer, alimentation HLK-5M05 sur ligne interphone)
- Réception et installation sirène Tuya TS0601
- Script Python orchestrateur (MQTT subscribe → logique armé/désarmé → délais entrée/sortie → trigger YOLO ciblé par zone → notifs Telegram/SMS)
- Intégration avec le script YOLO/Tapo déjà existant (caméras coupées via Tapo P110 en mode présence)

## Documentation continue (obligatoire)
À chaque bloc majeur terminé (install Z2M, appairage routeurs, appairage capteurs, montage NFC, sirène, script orchestrateur, sécurisation...), créer/mettre à jour un fichier `.md` dédié dans un dossier `docs/` du projet. Un fichier par sujet, pas un seul fichier fourre-tout :
- `docs/01-zigbee-setup.md` — config Z2M, adapter, canal, port série, historique dongle mort/remplacé
- `docs/02-capteurs-aqara.md` — mapping nom ↔ emplacement physique ↔ IEEE address
- `docs/03-nfc-module.md` — schéma câblage LilyGO/PN532/HLK-5M05, badges enregistrés
- `docs/04-siren-alarme.md` — config sirène, logique délais entrée/sortie
- `docs/05-architecture-mqtt.md` — topics MQTT, flux orchestrateur Python
- `docs/06-securite.md` — durcissement (permit_join désactivé après appairage, accès réseau, secrets/tokens)
- `docs/07-design-interface.md` — si dashboard/interface créée (Grafana, web UI custom, etc.)
- `docs/08-stack-technique.md` — tout logiciel/outil/langage/version utilisé ou ajouté en cours de route (Python + version, gestionnaire de paquets — uv/pip/poetry —, librairies, React/frontend si UI créée, Docker images et tags, dépendances système apt). Mettre à jour dès qu'un nouvel outil est introduit, avec la raison du choix.

Chaque `.md` doit rester à jour : ne pas dupliquer l'info, éditer le fichier existant si le sujet est déjà couvert. Avant de clore une étape, écrire ou mettre à jour le `.md` correspondant avant de passer à la suite.

## Questions à poser si besoin
Avant tout choix non trivial ou ambigu (langage/librairie non précisé ici, structure de dossier, nom de service, version majeure d'un outil, arbitrage UX sur une interface), poser la question plutôt que de supposer. Ne pas bloquer sur des détails mineurs réversibles (nom de variable, formattage) — trancher seul et documenter le choix dans le `.md` concerné.

## Notes de style
- Communication terse et directe, français, pas de blabla
- Toujours vérifier l'état réel (logs, `cat` config) avant de proposer un fix, ne pas supposer
