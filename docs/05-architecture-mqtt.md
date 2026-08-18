# 05 — Architecture MQTT

Broker : **Mosquitto** (Docker, `--network host`, `allow_anonymous true`, port 1883).
Bus unifié entre Zigbee2MQTT, l'app AEGIS et l'orchestrateur alarme.

## Topics

### Zigbee2MQTT (existant)
| Topic | Sens | Contenu |
|---|---|---|
| `zigbee2mqtt/bridge/state` | Z2M → tous | `online`/`offline` |
| `zigbee2mqtt/<friendly_name>` | Z2M → tous | état device (capteurs : `{"contact":true/false,...}`) |
| `zigbee2mqtt/bridge/request/permit_join` | → Z2M | ouverture appairage |

### Alarme AEGIS (namespace `aegis/`)
| Topic | Publié par | Reçu par | Contenu | Retained |
|---|---|---|---|---|
| `aegis/alarm/set` | App | Orchestrateur | `{"state":"armed"\|"disarmed","by":<user>}` | **oui** |
| `aegis/alarm/state` | Orchestrateur | App | `{"state","mode":"idle"\|"searching","since"}` | **oui** |
| `aegis/alarm/event` | Orchestrateur | App | `{"type","label","detail","ts"}` | non |
| `aegis/camera/<key>/state` | Orchestrateur | App | `{"key","label","reachable","privacy","ts"}` | **oui** |
| `aegis/plug/<key>/state` | Service prises | App | `{"key","label","on","reachable","model","rssi","power","energy_today","voltage"}` | **oui** |
| `aegis/plug/<key>/set` | App | Service prises | `{"on": true\|false}` | non |
| `aegis/notify` | App (moniteur santé) | Orchestrateur | `{"title","line","key","force"}` → mail+Telegram | non |

- `set` **retenu** → au redémarrage, l'orchestrateur retrouve le dernier ordre et ré-affirme l'état caméra.
- `state` **retenu** → l'app affiche l'état immédiatement (`/api/alarm`).
- `event.type` ∈ `armed|disarmed|door|intrusion|info`. L'app les journalise (`category="alarm"`).

## Flux

**Armer** : App `/controle` → `POST /api/alarm/set {arm}` → publie `aegis/alarm/set {armed}` (retained)
→ orchestrateur : privacy OFF, `state {armed,idle}`, `event {armed}` → app journalise + affiche.

**Ouverture de porte (armé)** : `zigbee2mqtt/<porte> {contact:false}` → orchestrateur détecte le
front fermé→ouvert → `event {door}` + alerte mail + `state {armed,searching}` (10 min) → app.

**Détection personne (armé)** : caméra → YOLO → capture `webapp/captures/` + `event {intrusion}`
+ alerte mail (cooldown) → app (journal + galerie).

## Qui écoute quoi
- **App AEGIS** (`webapp/mqtt_state.py`) : `zigbee2mqtt/+`, `zigbee2mqtt/bridge/state`,
  `aegis/alarm/state`, `aegis/alarm/event`. Publie `aegis/alarm/set`.
- **Orchestrateur** (`orchestrator/alarm.py`) : `aegis/alarm/set`, `zigbee2mqtt/+`.
  Publie `aegis/alarm/state`, `aegis/alarm/event`.
- **Notifier** (`orchestrator/notifier.py`, service `aegis-notifier`) : **lecture seule**
  sur `aegis/alarm/state`, `aegis/alarm/event`, `aegis/plug/+/state`,
  `aegis/camera/+/state`, `aegis/sensor/sirene/state`, `zigbee2mqtt/+`.
  Ne publie rien : il envoie mail/Telegram. Voir `docs/14-messagerie.md`.
  Depuis le 18/08/2026 c'est lui qui émet TOUTES les alertes ; l'orchestrateur
  n'envoie plus (`AEGIS_ORCH_NOTIFY=0`) pour éviter les doublons.

## Sécurité / à durcir
- Mosquitto en `allow_anonymous` sur le LAN. Acceptable (réseau local, pas exposé).
  Durcissement possible : `password_file` + ACL par client. À faire avant d'ouvrir le broker hors LAN.
- Voir `docs/06-securite.md`.
