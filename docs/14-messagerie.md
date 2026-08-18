# 14 — Messagerie AEGIS (service `aegis-notifier`)

Ajouté le **2026-08-18**, après une panne silencieuse d'alerte de plusieurs semaines.

## L'incident : une alarme muette sans le moindre signe

**Symptôme** : plus aucune notification (ni mail, ni Telegram) depuis mi-juillet.
Ni les armements/désarmements, ni l'intrusion réelle du 14 août. Aucune erreur
dans les logs, tous les services `active`, capteurs et caméras opérationnels.

**Cause racine** : `alarm.py` charge le vault avec `load_dotenv()` **au démarrage
du process**. Les identifiants vivent ensuite dans la mémoire de ce process.

| Date | Événement |
|---|---|
| 2026-07-19 16:26 | démarrage de `aegis-orchestrator` (vault de cette date en mémoire) |
| 2026-08-03 09:49 | **le vault est modifié** (identifiants de notification) |
| 2026-07-19 → 2026-08-18 | le process n'a jamais rechargé le vault → **muet** |

Le silence total s'explique par `notify.py`, qui sort **sans rien journaliser**
quand un identifiant manque :

```python
if not token or not chat_ids:
    return                      # aucun log : la panne est invisible
if not (sender and app_password and recipients):
    return                      # idem côté mail
```

**Méthode de diagnostic** (reproductible) : publier sur `aegis/detection/config`
→ le handler journalise immédiatement, donc MQTT et le dispatch fonctionnent ;
publier sur `aegis/notify` → *aucun* log, donc le défaut est bien dans `notify`.

## Le choix : découpler la messagerie de l'alarme

La messagerie est désormais un service **séparé**, `aegis-notifier`
(`orchestrator/notifier.py`), qui ne fait que **lire** le bus MQTT.

Pourquoi séparé plutôt que corriger l'orchestrateur :

- il se redémarre à volonté **sans jamais interrompre la surveillance** ;
- il **recharge le vault à chaque démarrage** (`load_dotenv(override=True)`) ;
- une panne de messagerie ne peut plus affecter la détection, et inversement.

`alarm.py` conserve son code d'envoi, désactivé par défaut pour éviter les
doublons — `AEGIS_ORCH_NOTIFY=1` le réactive si l'on veut revenir en arrière.

## Ce que le service envoie

| Déclencheur | Message |
|---|---|
| `aegis/alarm/event` `armed` / `disarmed` | 🛡️ / 🔓 avec l'auteur et l'heure |
| `aegis/alarm/event` `door` | 🚪 ouverture + rappel du délai avant déclenchement |
| `aegis/alarm/event` `intrusion` | 🚨 déclencheur, heure, caméras ayant détecté |
| **intrusion active** | 🚨 **rappel toutes les `NOTIFIER_REPEAT_S`** (défaut 120 s) jusqu'au désarmement, avec la durée écoulée |
| panne d'un équipement | ⚠️ alerte **immédiate** horodatée, puis rappel dans le récap tant que non résolue |
| retour à la normale | ✅ notification de rétablissement |
| chaque matin à `NOTIFIER_DAILY_AT` (08:00) | 📋 récapitulatif complet |

Le récapitulatif liste **chaque capteur individuellement** (« en marche »,
ouvert/fermé, batterie %), les caméras, les prises, la sirène, le réseau Zigbee,
puis les anomalies en cours avec leur ancienneté.

> **Note de conception.** Un capteur d'ouverture qui ne bouge pas pendant des
> jours produit exactement la même signature qu'un aimant décollé : impossible
> de distinguer les deux. Cette heuristique ne déclenche donc **aucune alerte** —
> pendant une absence, des capteurs immobiles sont le comportement normal. Le
> contrôle matinal repose sur le fait que chaque capteur *répond* et annonce sa
> batterie, ce qui est vérifiable sans ambiguïté.

## Deux pièges corrigés le 18/08 (après retour terrain)

**1. Faux positif caméras à chaque armement.** L'armement rallume les prises
Tapo : les caméras mettent 30-60 s à démarrer. Le contrôle santé les déclarait
en panne dans cet intervalle. Un délai de grâce `NOTIFIER_CAMERA_BOOT_S`
(240 s) suspend leur vérification après un armement.

**2. Un capteur muet passait pour vivant.** Le service datait chaque capteur à
l'heure de RÉCEPTION du message. Or au démarrage, le broker relivre les
messages **retenus** : un capteur silencieux depuis dix jours paraissait avoir
parlé à l'instant, batterie « 100 % » comprise — valeur figée au dernier
contact réel. Le récapitulatif affirmait donc « en marche » sans aucune preuve,
en contradiction avec l'application (qui, elle, mesure depuis son propre
démarrage et disait vrai).

Correction : `last_seen` a été activé dans Zigbee2MQTT (à chaud, via
`zigbee2mqtt/bridge/request/options`, sans redémarrage). Chaque payload porte
désormais la date réelle du dernier contact radio. Le récapitulatif distingue
trois cas :

| Affichage | Signification |
|---|---|
| ✅ « vu il y a X » | contact radio horodaté et récent — **prouvé** |
| ❔ « dernier contact inconnu » | seule une valeur retenue est disponible — **on ne sait pas** |
| ❌ « MUET depuis X » | horodatage fiable et trop ancien — **panne confirmée** |

> Règle retenue : ne jamais présenter une donnée mémorisée comme une mesure
> fraîche. Un tableau de bord qui affiche « tout va bien » sans preuve est plus
> dangereux qu'un tableau de bord qui affiche « je ne sais pas ».

## Réglages (vault ou `orchestrator/.env`)

| Variable | Défaut | Rôle |
|---|---|---|
| `NOTIFIER_REPEAT_S` | `120` | intervalle des rappels pendant une intrusion |
| `NOTIFIER_DAILY_AT` | `08:00` | heure du récapitulatif |
| `NOTIFIER_HEALTH_EVERY_S` | `60` | fréquence du contrôle matériel |
| `NOTIFIER_SENSOR_MUTE_H` | `6` | silence capteur (h) considéré comme anormal |
| `NOTIFIER_NODE_TIMEOUT_S` | `300` | silence routeur/prise (s) considéré comme anormal |
| `NOTIFIER_CAMERA_BOOT_S` | `240` | délai de grâce caméras après un armement |
| `AEGIS_ORCH_NOTIFY` | `0` | remettre l'envoi dans l'orchestrateur (doublons) |

Destinataires : table `recipients` de `aegis.db` (gérée dans /admin), avec
repli sur `MAIL_RECEPTION` / `TELEGRAM_CHAT_IDS` du vault.

## Exploitation

```bash
sudo systemctl status aegis-notifier
journalctl -u aegis-notifier -f
sudo systemctl restart aegis-notifier      # sans effet sur la surveillance
```

Les anomalies en cours survivent au redémarrage (`orchestrator/.notifier_state.json`).

## Leçon à retenir

**Un canal d'alerte doit être testé, pas supposé.** Le système était vert
partout — services actifs, matériel sain — alors que la fonction la plus
critique était hors service depuis un mois. Le récapitulatif quotidien sert
précisément de preuve de vie : son absence est elle-même un signal.

Reste ouvert (cf. `docs/11`) : un canal indépendant d'Internet (SMS/4G). Mail et
Telegram tombent tous les deux si la box est coupée.
