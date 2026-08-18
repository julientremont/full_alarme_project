# 13 — Feuille de route AEGIS v2 (synthèse audit v1 × benchmark marché)

Croisement du rapport d'audit interne (`docs/11`) et du benchmark des 11 grands
vendeurs (`docs/12`). **Constat commun aux deux analyses** : les faiblesses les
plus graves d'AEGIS ne sont pas dans la finesse de détection, mais dans les
scénarios où l'alarme est **neutralisée silencieusement** — coupure courant,
coupure Internet, sabotage/brouillage capteur, vol du Pi. C'est exactement ce que
les leaders (Ajax, Verisure, ADT, Frontpoint) traitent en priorité (backup 4G,
batterie, anti-jamming, "Crash & Smash"). On aligne la v2 là-dessus d'abord.

Priorités : **P0 = anti-neutralisation** (une alarme qu'on éteint sans bruit ne
sert à rien), **P1 = couverture & fiabilité de détection**, **P2 = confort/UX**.

## P0 — Résilience & anti-sabotage (à faire avant toute autre détection)

| # | Amélioration | Équivalent marché | Approche DIY (stack actuelle) | Coût/effort |
|---|---|---|---|---|
| 1 | **Photos poussées hors-site à l'alarme** | Vérification vidéo télésurveillance | Envoyer les captures en **photo Telegram** (le bot sait envoyer des images), pas juste du texte → preuves sauvées même si le Pi est volé. | ~0 € · faible (notify.py) |
| 2 | **Sirène physique + déclenchement immédiat** ("Crash & Smash") | Frontpoint, tous | Sirène **Zigbee IAS WD** (déjà prévue, hook prêt) ; sonner dès la 1re détection confirmée, avant l'escalade lente. | ~20 € · faible |
| 3 | **Batterie de secours (UPS)** | Table stakes | UPS HAT sur le Pi **+ onduleur** pour box Internet + coordinateur Zigbee ; publier `secteur perdu` sur coupure. | 40-80 € · moyen |
| 4 | **Canal de secours si Internet coupé** | Backup 4G (Ajax/ADT/US) | Étape 1 : **SMS Free Mobile API** en 3e canal d'escalade (compte déjà dispo, cf. `docs/08`). Étape 2 : **routeur/dongle 4G en failover WAN** pour survivre à une coupure box. | 0 € puis ~30-60 € |
| 5 | **Détection anti-sabotage / heartbeat capteurs** | Anti-jamming Ajax, tamper | Watchdog par capteur : `last_seen` court **en mode armé** (vs 3 h actuel) ; perte inattendue d'un ou plusieurs capteurs Zigbee → **alerte tamper/brouillage**. Utiliser l'`availability` Z2M. | 0 € · moyen (mqtt_state.py) |
| 6 | **Persistance & auto-reprise de l'état armé** | Table stakes | Vérifier que l'état armé survit à un reboot Pi (retained MQTT déjà là) + watchdog systemd + `Restart=always`. Alerter au redémarrage inattendu. | 0 € · faible |

## P1 — Couverture & fiabilité de détection

| # | Amélioration | Équivalent marché | Approche DIY | Coût/effort |
|---|---|---|---|---|
| 7 | **Capteurs PIR + vibration dans les pièces sans caméra** (chambres) | PIR pet-immune, IntelliTAG Somfy | Capteurs **mouvement Aqara** + **vibration** Zigbee sur chambres/fenêtres → comble le trou de l'incident du 09/07 (Chambre Noah). | ~15 €/capteur · faible |
| 8 | **Étage de confirmation avant escalade totale** | Levée de doute | 1re détection → pré-alarme (photo + notif douce) ; confirmation (2e détection / mouvement + contact) → sirène + escalade. Réduit les faux positifs. | 0 € · moyen (alarm.py) |
| 9 | **Vérification vidéo ciblée sur la zone déclenchée** | Verisure/Arlo | Sur alarme, prioriser la caméra de la **pièce du capteur** (mapping déjà présent) + voisines, plutôt qu'une caméra arbitraire. | 0 € · faible |
| 10 | **Détection de bris de glace** | Ajax/Bosch | Capteur bris de glace Zigbee sur baies vitrées salon → détecte avant ouverture du battant. | ~20 €/capteur · faible |

## P2 — Modes, UX & exploitation

| # | Amélioration | Équivalent marché | Approche DIY | Coût/effort |
|---|---|---|---|---|
| 11 | **Modes d'armement zones/nuit/partiel** | Table stakes | Étendre `aegis/alarm/set` : `total` / `nuit` (périmètre armé, chambres libres) / `partiel` ; taguer les capteurs par zone dans `devices.yaml`. | 0 € · moyen |
| 12 | **Escalade multi-canal avec accusé de réception** | ADT/Verisure | Chaîne Telegram → mail → **SMS** → **appel** (Twilio/CallMeBot) ; bouton ACK Telegram ; si pas d'ACK en N min → contact suivant. | ~0-qq € · moyen |
| 13 | **Armement par NFC/badge** | Ajax DESFire | Câbler la `badgeuse` (déjà dans le registre) à `arm()/disarm()` ; lecteur NFC PN532 sur le Pi. | ~10 € · moyen |
| 14 | **Géofencing** | Ring/SimpliSafe | Armement/désarmement auto selon la présence des téléphones (Owntracks/Home Assistant → MQTT). | 0 € · moyen |
| 15 | **Durcissement final** | — | Cloudflare Access devant le hostname (en cours), MàJ auto, intégrité du journal. | 0 € · faible |

## Ordonnancement conseillé (rapport valeur/effort)

**Sprint 1 (quasi gratuit, gros gain sécurité)** : #1 photos Telegram hors-site,
#4a SMS Free Mobile, #5 heartbeat/tamper, #6 watchdog + reprise, #9 caméra ciblée.
**Sprint 2 (petit matériel)** : #2 sirène Zigbee, #7 PIR/vibration chambres, #3 UPS.
**Sprint 3 (confort)** : #11 modes nuit/zones, #8 confirmation, #12 escalade+ACK.
**Sprint 4 (avancé)** : #4b failover 4G, #13 NFC, #14 géofencing, #10 bris de glace.

## État Sprint 1 (2026-07-12) — TERMINÉ

- ✅ **#1 Photos hors-site** : sur **Google Drive** (choix user, pas Telegram), rangées
  par caméra/date (`orchestrator/drive.py`, OAuth). ⚠️ reste l'auth OAuth unique
  (`setup_gdrive_auth.py`) côté user.
- ⛔ **#4 SMS** : abandonné (choix user).
- ✅ **#5 Anti-sabotage/heartbeat** : `webapp/app.py health_monitor` — quand armé,
  perte du coordinateur / d'un routeur / d'une prise Zigbee → alerte « Sabotage
  possible » immédiate ; tous les routeurs muets ensemble → « Brouillage suspecté ».
- ✅ **#6 Watchdog + reprise** : services en `Restart=always` (drop-ins systemd,
  StartLimitIntervalSec=0) ; reprise de l'état armé via MQTT retenu ; **notif
  « AEGIS redémarré — alarme armée/désarmée »** à chaque démarrage (signal tamper).
- ✅ **#9 Caméra ciblée** : la caméra de la zone déclenchée est capturée en premier
  (`alarm._alarm_loop`), toutes les autres suivent.
- ➕ **2FA TOTP** (hors roadmap, demande user) : Google Authenticator sur le login.

## Note stratégique
Google a arrêté Nest Secure (avril 2024, alarme abandonnée → simple partenariat
ADT). Argument de fond : miser sur un **DIY à standards ouverts** (Zigbee/MQTT)
plutôt qu'un écosystème propriétaire fermé qui peut disparaître. La v2 doit rester
sur ces standards.
