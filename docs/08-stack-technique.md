# 08 — Stack technique

Tout outil/langage/lib/version introduit en cours de route, avec la raison du choix. À mettre à jour dès qu'un nouvel outil est ajouté.

## Infrastructure Zigbee
| Outil | Version | Rôle | Pourquoi |
|---|---|---|---|
| Docker | (système) | Conteneurs | Déjà en place sur le Pi |
| Mosquitto | conteneur | Broker MQTT | Bus unifié du projet (network host, ports 1883/9001) |
| Zigbee2MQTT | 2.12.0 (image `ghcr.io/koenkk/zigbee2mqtt:latest`) | Pont Zigbee↔MQTT | Standard, adapter `ember` pour EFR32MG21 |
| zigbee-herdsman | 10.4.0 | Lib Zigbee de Z2M | — |

## Application web AEGIS (`webapp/`)
Choix : **reprise de la stack `calsport`** (Flask) pour cohérence, sécurité éprouvée, et familiarité. Voir `07-design-interface.md`.

| Outil | Version | Rôle | Pourquoi |
|---|---|---|---|
| Python | 3.11 (Pi) / `requires-python >=3.11` | Langage | Dispo système, suffisant |
| uv | 0.9.7 | Gestionnaire env/paquets | Rapide, déjà utilisé sur le Pi (calsport) ; `.venv` dédié par app |
| Flask | 3.1.x | Framework web | Léger, identique calsport |
| flask-wtf | 1.3 | Protection CSRF | Sécurité formulaires/commandes |
| flask-limiter | 4.1 | Rate limiting | Anti-bruteforce login |
| werkzeug | 3.1 | Hash mdp (scrypt) | Standard, zéro secret en dur |
| paho-mqtt | 2.1 | Client MQTT | Thread d'arrière-plan abonné à `zigbee2mqtt/#` (API v2) |
| pyyaml | 6.0 | Parse `devices.yaml` | Registre matériel déclaratif |
| python-dotenv | 1.x | Secrets via `.env`/vault | Aligné calsport |
| gunicorn | 26.0 | Serveur WSGI prod | **1 worker** (état MQTT en mémoire process) + threads |
| SQLite | (stdlib) | users + journal d'événements | Pas de serveur DB à gérer |

### Front
- HTML/Jinja2 + CSS pur (pas de framework JS). Police **Inter** (Google Fonts), thème dark + accent cyan `#00d1ff` (repris calsport).
- Mises à jour live par **polling** `fetch('/api/state')` toutes les 3 s (SSE/WebSocket envisageable en v2).

### Déploiement
- systemd (`webapp/config/aegis.service`) bind `127.0.0.1:5002`, durcissement (`NoNewPrivileges`, `ProtectSystem=strict`).
- Cloudflare Tunnel (`webapp/config/cloudflared.yml`) → hostname dédié. Cloudflare Access recommandé (auth amont).

## Reste à introduire (à compléter le moment venu)
- Orchestrateur alarme : Python + paho-mqtt (logique armé/désarmé, délais, notifs Telegram/SMS Free Mobile).
- NFC : firmware ESP (LilyGO T-Display-S3 + PN532) — ESPHome ou Arduino (à trancher).
- Caméras : passerelle RTSP→HLS/WebRTC (ex: go2rtc / MediaMTX) pour le live dans AEGIS — à choisir.

## Orchestrateur alarme (`orchestrator/`) — ajouté 2026-06-28
Réutilise les briques du projet `Security` (arrêté), réécrites autour de MQTT.

| Outil | Version | Rôle | Pourquoi |
|---|---|---|---|
| Python | 3.12 (venv uv) | Langage | aligné Security (ultralytics) |
| paho-mqtt | 2.1 | Bus MQTT | commandes/état/événements alarme |
| pytapo | **==3.3.54** (pin) | Contrôle caméra Tapo (privacy) | 3.4.x casse l'auth C210 (KLAP) |
| opencv-python + numpy | — | RTSP + mouvement | repris de Security |
| ultralytics (YOLOv8n) | 8.3.x | Détection personne/objets | repris de Security |
| pyyaml / python-dotenv | — | devices.yaml / vault | — |

- Stockage captures : **local** (`webapp/captures/`), servi par l'app. Google Drive abandonné (compte de service sans quota sur Drive perso ; OAuth Security cassé). Plus de dépendance Google.
- Notifications : Gmail SMTP (mail court, `notify.py`).
- Service systemd : `aegis-orchestrator`.

## Service prises Tapo (`orchestrator/plugs.py`) — ajouté 2026-07-07
| Outil | Version | Rôle | Pourquoi |
|---|---|---|---|
| python-kasa | 0.10.2 | Contrôle/télémétrie prises Tapo P100/P110 | pilotage local KLAP + énergie |

- 4 prises (cuisine .2, entrée .128, couloir .126, salon .30). Registre : `webapp/devices.yaml` (source `plug`, `host`).
- Service systemd **`aegis-plugs`** : poll ~20 s → publie `aegis/plug/<key>/state` (retained) ; écoute `aegis/plug/<key>/set`.
- Contrôle depuis l'app (Matériel) : bouton on/off si l'utilisateur a l'onglet **Contrôle** ; API `POST /api/plug/<key>/set`.
- ⚠️ **Identifiants** : les prises nécessitent le **compte cloud Tapo** (login appli), différent du compte local caméra (`TAPO_USER/PASSWORD`). À mettre dans le vault : `TAPO_CLOUD_EMAIL` + `TAPO_CLOUD_PASSWORD`. Tant qu'absent, prises en « En attente » et service non démarré.
- P100 = on/off seul (pas de mesure) ; P110 = + énergie (W, kWh, V). Détecté par prise via le module `Energy`.

## Vue caméra en direct (go2rtc) — ajouté 2026-07-07
| Outil | Rôle | Pourquoi |
|---|---|---|
| go2rtc (Docker `alexxit/go2rtc`, `--network host`, 127.0.0.1:1984) | Passerelle RTSP→MP4/WebRTC | Le navigateur ne lit pas le RTSP ; go2rtc repackage en MP4 (faible latence, sans transcodage) |

- Config : `go2rtc/go2rtc.yaml` (4 flux `cam_*` = RTSP des caméras ; creds RTSP injectés par env `CAM_USER/CAM_PASS` depuis le vault, pas en dur).
- L'app **proxifie** le flux : `GET /cameras/live/<key>` (Flask, derrière login) → `go2rtc /api/stream.mp4?src=<key>`. go2rtc reste sur 127.0.0.1 (non exposé).
- **Vue live uniquement quand l'alarme est ARMÉE** (désarmé = privacy = caméras coupées). Sinon 409 + placeholder « Armez pour voir ».
- Onglet Caméras : sélectionner une caméra → `<video>` live si armé.
- gunicorn passé à **8 threads** (chaque spectateur occupe un thread pour le flux).
- ⚠️ Ne marche pour l'instant que sur le **salon** (RTSP OK) ; entrée/cuisine/couloir dès que leur compte local RTSP est unifié.

## Service de messagerie (`orchestrator/notifier.py`) — ajouté 2026-08-18
Service systemd **`aegis-notifier`**, séparé de l'orchestrateur. Réutilise
`notify.py` (Gmail SMTP + Telegram) ; aucune dépendance nouvelle.

- **Pourquoi séparé** : l'orchestrateur gardait en mémoire le vault de son
  démarrage (19/07) ; le vault ayant été modifié le 03/08, ses alertes tombaient
  dans le vide **sans aucun log**. Le notifier recharge le vault à chaque
  démarrage et peut être relancé sans interrompre la surveillance.
- Envoie : armé/désarmé, ouverture, intrusion, **rappels toutes les 2 min pendant
  une intrusion**, pannes matériel horodatées, **récapitulatif quotidien à 08:00**.
- Détail complet et réglages : `docs/14-messagerie.md`.
