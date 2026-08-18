# 04 — Alarme, caméra & orchestrateur

Boucle d'alarme MVP : 1 caméra Tapo C210 (salon) pilotée depuis AEGIS, détection
YOLO, captures locales, alertes courtes. Code : `orchestrator/`.

## Vue d'ensemble

```
[App AEGIS /controle] --MQTT aegis/alarm/set--> [Orchestrateur] --pytapo--> [Caméra Tapo C210]
                                                      |  ^ zigbee2mqtt/<capteurs> (ouvertures)
                                                      |  └── captures JPEG --> webapp/captures/ (galerie app)
                                                      └── aegis/alarm/state + aegis/alarm/event --> [App: état + journal]
```

- **Bus** : Mosquitto (Docker, `allow_anonymous`, network host).
- **Orchestrateur** : service systemd `aegis-orchestrator` (venv uv 3.12, `orchestrator/`).
- **App** : onglet **Contrôle** (permission assignable) arme/désarme ; journal + galerie captures.

## Logique (machine à états — multi-caméras, révisé 2026-07-07)

| État | Caméras (privacy) | Détection |
|---|---|---|
| **Désarmé** | privacy **ON** (coupées, ne filment pas) | aucune |
| **Armé / veille** | privacy **OFF** | 1 thread/caméra : compare 2 images **toutes les 2 s** → si mouvement, **YOLO** |
| **Armé / alarme** | privacy OFF | **sirène sur toutes les caméras** + photo/YOLO toutes les **10 s** |

- **Mapping pièce↔caméra↔capteur** : chaque caméra réelle (entrée, salon, cuisine…) couvre les ouvertures de sa pièce. Capteur ouvert → **YOLO direct** sur la caméra de la même pièce.
- **Déclencheurs d'alarme** : personne/objet détecté (YOLO), **ou** ouverture d'un capteur (hors entrée) = déclenchement **direct**.
- **Porte d'entrée** (`ENTRY_SENSORS`) : **tempo 60 s** avant déclenchement (le temps de désarmer). Désarmer pendant la tempo annule.
- **Alarme** : `startManualAlarm()` (sirène) sur **toutes** les caméras + 1 notification + photos/YOLO toutes les 10 s. **Arrêt uniquement au désarmement manuel** via l'app (`stopManualAlarm` + privacy ON).
- Objets surveillés : Personne, Couteau, Ciseaux, Batte (conf ≥ 0.8). Captures dans `webapp/captures/`.

> ⚠️ **Rate-limit auth C210** : pytapo suspend l'auth (~30 min) si trop de handshakes rapprochés (« Temporary Suspension »). La session est **mise en cache et réutilisée** ; éviter les redémarrages en rafale. Le flux RTSP (détection) utilise le compte local et n'est pas affecté.

## Caméra — mode privacy (choix de conception)

Activation/coupure via `pytapo` `setPrivacyMode()` — **instantané**, pas de reboot, pas
d'usure (vs couper l'alimentation par la prise P110). Désarmé = privacy ON = la caméra
ne filme pas (vie privée à la maison).

> ⚠️ **pytapo épinglé à `3.3.54`**. La 3.4.x casse l'auth du C210 (« Invalid authentication data », changement KLAP). Ne pas mettre à jour sans tester.
> ⚠️ Le C210 rejette une **ré-auth trop rapprochée** → `camera.set_privacy()` ouvre une session fraîche à chaque appel, sérialisée par un verrou, avec 1 retry. Au démarrage l'orchestrateur attend 5 s l'état retenu avant d'agir (évite un double-toggle).

## Captures (stockage local, pas Drive)

**Décision** : captures stockées **localement** sur le Pi (`webapp/captures/`) et affichées
dans l'app (onglet Caméras → « Dernières captures »). Rétention : 500 dernières (`MAX_CAPTURES`).

> Pourquoi pas Google Drive : un **compte de service ne peut pas écrire dans un Drive perso**
> (`storageQuotaExceeded` — nécessiterait un Shared Drive Workspace). Et l'ancien projet
> `Security` plantait en boucle (`Token invalide`) car son token OAuth expirait (écran de
> consentement en mode *Testing* → refresh token mort tous les 7 jours). Le local supprime
> toute dépendance Google. Sauvegarde hors-site possible plus tard (OAuth en *Production*).

## Notifications

Un **seul message court et pro** par événement (anti-spam, cooldown 300 s pour les
intrusions ; armement/désarmement et ouverture de porte = toujours envoyés). Pas de photo
en pièce jointe : « va voir dans l'app ». Mail via Gmail SMTP (`notify.py`,
`MAIL_ENVOI/RECEPTION/MP` du vault). Telegram = évolution future possible.

## Service & exploitation

```bash
# logs
journalctl -u aegis-orchestrator -f
# redémarrer après modif code
sudo systemctl restart aegis-orchestrator
# état alarme courant
docker exec mosquitto mosquitto_sub -h localhost -t 'aegis/alarm/state' -C 1
```

Fichiers : `orchestrator/alarm.py` (machine à états + MQTT), `camera.py` (privacy + YOLO),
`storage.py` (captures locales), `notify.py` (alertes), `config/aegis-orchestrator.service`.
Config : vault `/home/j.tremont/.secrets/vault.env` + `orchestrator/.env` (optionnel,
voir `.env.example` : `SEARCH_SECONDS`, `SCAN_WINDOW`, `ALERT_COOLDOWN_S`, `CAMERA_LABEL`…).

## Remplacement du projet `Security`

Le service `security-camera` (ancien projet `/home/j.tremont/Documents/Projets/Security`)
est **arrêté et désactivé** — remplacé par cet orchestrateur (mêmes briques YOLO/RTSP,
réécrites autour de MQTT + privacy + stockage local).

## Reste à faire / pistes
- Flux caméra **en direct dans l'app** (passerelle RTSP→WebRTC type go2rtc/MediaMTX).
- Prise P110 : l'intégrer comme device contrôlable (Zigbee = routeurs Sonoff ; la P110 est WiFi → `python-kasa`).
- Délais sortie/entrée, sirène Tuya TS0601, Telegram, multi-caméras.
