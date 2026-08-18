# 10 — Audit alarme AEGIS (perf, failles, axes d'amélioration)

Audit du 2026-07-09, après incident réel : alarme armée, passage devant les
caméras sans détection, ouverture Chambre Noah → **alerte reçue trop tard,
aucune photo, aucune sirène, désarmement bloqué**. Note utilisateur : 5/100.

## 1. Cause racine unique : tout est synchrone sur le thread réseau MQTT

`Orchestrator._on_message` (thread de la boucle paho) appelle en direct des
opérations caméra **lentes et qui échouent** :

- `trigger_alarm()` → boucle `c.start_siren()` sur les 4 caméras, **en série**,
  sur le thread MQTT. Chaque appel `_do()` fait 2 tentatives + reconnexion
  pytapo + `sleep(2)`. Une caméra qui échoue coûte ~7 s.
- `arm()` / `disarm()` → même chose (`set_privacy` × 4) + `notify.send_alert`
  synchrone (SMTP 20 s, Telegram 15 s/timeout).

Conséquences mesurées dans l'incident (logs `aegis-orchestrator`) :

| Symptôme utilisateur | Preuve log | Cause |
|---|---|---|
| Activation trop longue | armé 17:12:44, "ALARME ARMÉE" 17:13:01 = **15 s** | notify Telegram/SMTP bloquant dans `arm()` |
| Message trop tard | ouverture 17:13:59, mail intrusion **17:14:42 = +43 s** | notify placé *après* 4 `start_siren()` en échec (23 s) |
| Pas d'alarme (sirène) | `startManualAlarm -40106` × Entrée/Cuisine/Couloir | API sirène non supportée + aucune sirène matérielle |
| Ne se désarme pas | thread MQTT monopolisé 17:13:59→17:14:42 | commande `aegis/alarm/set` non traitée tant que `trigger_alarm` bloque la boucle |
| Pas de photo | 0 capture le 09/07 | `snapshot_detect` ne sauvegarde que si YOLO ≥ 0.8 sur la caméra *fallback* (Entrée), pas là où était l'intrus |
| Rien pendant le passage devant caméras | veille 17:13:01→17:13:59 sans hit | conf 0.8 trop haut, YOLO sérialisé (1 lock/4 cams), frames go2rtc bufferisées, Salon en privacy (frames noires) |

## 2. Failles de sécurité / fiabilité (classées)

**P0 — l'alarme ne dissuade pas et ne se pilote pas en incident**
1. **Aucune sirène réelle.** `startManualAlarm` renvoie `-40106` sur C210/C200C
   (paramètre inexistant pour ce firmware) et il n'y a aucune sirène matérielle
   (`source: siren` absent de `devices.yaml`). Un intrus n'entend rien.
2. **Désarmement non garanti pendant l'alarme** : la boucle MQTT est bloquée par
   les appels caméra. Commande perdue/retardée → panique côté utilisateur.
3. **Caméra Salon HS en permanence** : `Invalid authentication data` →
   `Temporary Suspension 1800 s` en boucle. Pas de détection ni sirène salon, et
   pilote quand même une pièce entière.

**P1 — la détection rate des intrusions**
4. `conf = 0.8` : trop strict pour yolov8n sur un passage rapide / flou / nuit.
5. YOLO sérialisé (`_model_lock`) sur 4 caméras + veille bloquante par caméra →
   latence de détection de plusieurs secondes, une personne traverse le champ
   entre deux cycles.
6. `motion_seuil = 10000` = somme absdiff sur 640×360 : quasi toujours vrai
   (bruit capteur) → YOLO tourne pour rien, ou frames go2rtc identiques
   (buffer) → jamais vrai. Non fiable dans les deux sens.
7. Photos conditionnées à une détection YOLO **sur la caméra qui a déclenché** :
   une ouverture de capteur sans caméra dans la pièce (chambres) → photo prise
   sur une caméra arbitraire (`next(iter(cameras))`) qui ne voit pas l'intrus.

**P2 — durcissement**
8. Tempo entrée **60 s** : très long, laisse le temps de fouiller l'entrée.
9. Notifications à canal unique effectif (mail + Telegram séquentiels, bloquants,
   sans file ni retry) ; pas d'escalade (appel, sirène tierce).
10. `WTF_CSRF_TIME_LIMIT=None`, Cloudflare Access pas encore devant le hostname
    (cf. `docs/08`), à finaliser.

## 3. Axes d'amélioration (ordre d'impact)

**P0 — à faire tout de suite**
- **Découpler le thread MQTT** : `on_message` ne fait que muter l'état + poster
  dans une file ; un pool de workers exécute sirène/privacy/notify. Le
  désarmement doit être traité *avant* toute I/O caméra et **jamais** bloqué.
- Dans `trigger_alarm` : **notifier d'abord**, piloter les sirènes ensuite, en
  parallèle (`Thread`/`ThreadPool`), avec timeout court.
- `notify.send_alert` : envoi **asynchrone** (thread/queue), Telegram avant mail
  (plus rapide et fiable sur mobile), timeouts courts + retry léger.
- **Sirène qui marche** : soit corriger l'appel Tapo (tester `executeFunction`/
  `setAlarm`/`getAlarmConfig` selon firmware, cf. pytapo récent), soit — mieux —
  ajouter une **sirène Zigbee/Tuya matérielle** pilotée par MQTT (déclenchement
  < 1 s, indépendante des caméras et du cloud Tapo).
- Réparer/retirer **Salon** : creds locaux corrects, sinon le sortir du pilotage
  pour ne pas empoisonner les suspensions.

**P1 — fiabiliser la détection**
- Baisser `conf` à ~0.4–0.5 pour la classe *personne* (garder haut pour objets).
- Paralléliser l'inférence ou dédier un thread YOLO par caméra avec file, et
  lire les frames go2rtc en *drain* (vider le buffer avant de comparer).
- Recalibrer `motion_seuil` (normaliser par nb de pixels, ou fraction de pixels
  changés > delta) et tester nuit/jour.
- Découpler capture photo de la détection : sur alarme, **toujours** sauver N
  frames de la/les caméra(s) de la pièce concernée (et des voisines), annotées
  si YOLO trouve, brutes sinon.

**P2 — durcir**
- Tempo entrée réglable, défaut 20–30 s ; tempo de sortie explicite.
- File de notifications persistante + escalade (2e canal si pas d'ACK).
- Finaliser Cloudflare Access ; watchdog santé (bridge Zigbee, caméras,
  go2rtc) déjà partiellement là via `aegis/notify`.

## 4. Correctifs appliqués (2026-07-09)

Refactor `orchestrator/alarm.py` + `camera.py` :
- **Thread MQTT non bloquant** : `ThreadPoolExecutor` pour toute I/O caméra +
  notif. `arm()`/`disarm()`/`trigger_alarm()` mutent l'état, publient, puis
  délèguent. Testé : `arm`/`disarm` rendent la main en **1 ms** même avec des
  caméras simulées à 5 s. → règle *activation lente*, *message tard*, *ne se
  désarme pas*.
- **Désarmement prioritaire** : coupe la sirène externe (MQTT) et publie
  `disarmed` immédiatement, avant toute I/O caméra. Garde-fou `gen` : une tâche
  sirène lancée avant le désarmement ne se ré-exécute pas après.
- **Alerter d'abord** : notif asynchrone envoyée avant les sirènes.
- **Photos garanties** : `capture_always` sauvegarde une image de **chaque**
  caméra pendant l'alarme (annotée si YOLO, brute sinon). Testé : fichier
  `*_Vue_*.jpg` créé sans détection. → règle *pas de photo*.
- **Détection plus sensible** : `confidence` 0.8 → **0.45** (défaut app + base +
  config MQTT retenue). Lecture RTSP dé-bufferisée (drain go2rtc) pour des
  frames réellement postérieures.
- **Sirène caméra best-effort** multi-API + **hook sirène matérielle MQTT**
  (`SIREN_SET_TOPIC`, payload `warning` Zigbee). Tempo entrée défaut 60→**30 s**.

**Sirène caméra — RÉSOLUE via l'alarme embarquée (2026-07-09) :**
Le déclenchement *manuel* reste impossible (C210 fw 1.2.6 → `-40106` sur
`startManualAlarm`, `-40210` sur l'API siren). MAIS `getModuleSpec` confirme
`msg_alarm_list=['sound','light']` : la caméra a une **alarme embarquée** qui
sonne sur SA propre détection de mouvement. `setAlarm(on, sound, light, "high",
300)` marche (`error_code:0`, testé Entrée + Cuisine). Câblé : **armé → sirène
embarquée ON** (sonne dès que la caméra voit du mouvement), **désarmé → OFF**.
Entrée exclue (`onboard_siren:false` dans devices.yaml) pour garder les 30 s de
désarmement en rentrant. Limite : déclenchée par la détection *de la caméra*
(pas notre YOLO) → possibles faux positifs, mais seulement quand armé (maison
censée vide). Volume = haut-parleur caméra (dissuasif, pas une sirène 110 dB).

Pour une **vraie sirène forte** : ajouter une sirène Zigbee (IAS WD, Tuya/Neo)
appairée à Z2M → `SIREN_SET_TOPIC=zigbee2mqtt/<nom>/set` (hook prêt, déclenché
par notre logique/YOLO, indépendant des caméras).
2. **Salon** : `Invalid authentication data` (compte local salon incorrect) →
   ni détection ni contrôle salon. Corriger les creds locaux `TAPO_USER/PASSWORD`
   ou fournir `rtsp_user`/`rtsp_password` par caméra dans `devices.yaml`. N'impacte
   plus le reste (non bloquant).

## 4b. Perf + zone entrée temporisée (2026-07-09)

**Réactivité détection (4 caméras) :**
- Acquisition via **snapshot HTTP go2rtc** (`/api/frame.jpeg`) au lieu d'ouvrir un
  flux RTSP par cycle : go2rtc garde LA connexion caméra → ~0,25 s/image, décode
  mesuré 223 ms. `MOTION_GAP_S` 2→**1 s**. Cycle veille ~3 s → **~1,5 s** + YOLO
  0,33 s = **~1,8 s de latence** (vs ~3-4 s). Fallback RTSP conservé.
- YOLO reste sérialisé (`_model_lock`) — mesuré **334 ms/frame** sur le Pi5, torch
  utilise déjà les 4 cœurs ; paralléliser = plus lent. Détection sur les 4
  caméras via l'orchestrateur (conf 0.45, objets diffusés à toutes).

**Zone entrée temporisée** (`EXIT_DELAY_S=60`, `ENTRY_DELAY_S=30`) :
- Une caméra est « entrée » si sa pièce = pièce d'un `ENTRY_SENSORS` (auto). Elle
  n'utilise pas la sirène embarquée (il faut pouvoir désarmer au retour).
- **Sortie** : à l'armement, les caméras entrée restent **en privé 60 s** (le
  temps de sortir) ; pendant cette fenêtre l'ouverture de la porte d'entrée est
  **ignorée**. Puis activation auto.
- **Retour** : détection caméra entrée OU ouverture porte → **tempo 30 s** pour
  désarmer (pas d'alarme immédiate). Reste de la maison = **instantané**.
- Testé (logique complète) : sortie ignore porte+caméra entrée ; hors-entrée =
  alarme immédiate ; retour = tempo puis alarme si pas désarmé.

## 4c. Passe code complète — audit + correctifs (2026-07-10)

Revue de tout le code (`orchestrator/` + `webapp/`). Sécurité de base **saine** :
scrypt (werkzeug), CSRF global (flask-wtf, endpoints JSON non exemptés), toutes
les requêtes SQL **paramétrées** (aucune injection), secret depuis le vault,
rate-limiting login (10/min), `send_from_directory` (pas de traversal), MQTT/app
en localhost derrière cloudflared.

**Bugs corrigés :**
1. **Détection « Batte » = mauvaise classe COCO** : `39` = *bottle* (bouteille), pas
   une batte. Corrigé en `34` (*baseball bat*) dans `camera.py` OBJECTS +
   `app.py` OBJECT_CATALOG. Config retenue republiée → `classes:[0,43,76,34]`.
2. **`camera._try()` non thread-safe** : muait le niveau du logger global
   (`setLevel(CRITICAL)`) pour taire les essais sirène ; avec 4 caméras en
   parallèle dans le pool, une course pouvait **éteindre définitivement** les logs
   caméra. Remplacé par un flag `quiet` sur `_do()` (log DEBUG au lieu d'ERROR).
3. **`app.api_state` réutilisait `g`** (global de requête Flask) comme variable de
   boucle → shadowing risqué. Renommé `grp`.

**🔴 Faille critique CORRIGÉE — broker MQTT ouvert sur le LAN :** Mosquitto
écoutait sur `0.0.0.0:1883` avec `allow_anonymous true` → **n'importe qui sur le
Wi-Fi pouvait publier `aegis/alarm/set {"state":"disarmed"}` et désarmer
l'alarme**, ou injecter de faux états capteurs/caméras. Fix : conteneur recréé
avec publication des ports sur **`127.0.0.1` uniquement** (`-p 127.0.0.1:1883:1883`,
idem 9001). Z2M (net=host) et les services systemd joignent toujours
`127.0.0.1:1883` ; le LAN n'a plus accès. Volumes conservés (retained survit).
Conf sauvegardée `mosquitto.conf.bak`. (Option défense en profondeur : ajouter
`password_file` + `allow_anonymous false`, à répercuter sur tous les clients.)

**Durcissement déjà en place (vérifié) :** `HTTPS=true` (cookie `Secure` actif),
`SECRET_KEY` défini dans le vault (secret persistant). Reste : finaliser
**Cloudflare Access** devant `aegis.tremontraimi.com` (cf. `docs/08`).

## 4d. Contrôle caméra 100 % LOCAL — fin des suspensions (2026-07-10)

Cause des « Temporary Suspension » (30 min) : le contrôle pytapo (privacy, sirène
embarquée) passait par une **auth cloud** (email + `cloudPassword`), et les
handshakes cloud répétés (restarts, échecs) déclenchaient le verrou anti-abus des
C210. Découverte : le contrôle marche en **auth LOCALE directe** avec
`Tapo(host, "admin", <mot de passe du compte cloud>)` — **sans** `cloudPassword`,
donc **sans round-trip TP-Link → aucune suspension possible**. Le mot de passe
RTSP ne convient pas pour le contrôle ; c'est le mot de passe du *compte cloud*
qu'il faut, avec l'utilisateur `admin`. Validé (auth + écriture setDayNightMode)
sur Entrée, Cuisine, Couloir.

Implémenté : `camera.py` (`ctrl_user`/`ctrl_password`, `_do` construit un `Tapo`
local unique réutilisé) + `alarm.py _build_cameras` (`TAPO_CTRL_USER` défaut
`admin`, `TAPO_CTRL_PASSWORD`→fallback `TAPO_CLOUD_PASSWORD`). `ctrl_local`
supprimé de `devices.yaml` (obsolète). Overrides par caméra possibles
(`ctrl_user`/`ctrl_password`). Salon : repasse en local dès l'expiration de sa
dernière suspension (même compte, plus de cloud pour la relancer). Vision
nocturne = **auto** sur les 4 (à confirmer sur Salon au déblocage).

## 5. Verdict

Le 5/100 est mérité **par la chaîne de déclenchement**, pas par l'idée : capteurs
Zigbee, mapping et UI sont sains. Les 4 échecs viennent d'une seule racine
(exécution synchrone bloquante sur le thread MQTT) + de l'absence de sirène
réelle. En traitant les P0, on repasse à une alarme qui *alerte vite, prend des
photos et se désarme* même si les caméras Tapo font des leurs.
