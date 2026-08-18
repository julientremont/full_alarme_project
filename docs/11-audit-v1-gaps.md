# 11 — Audit AEGIS comme produit d'alarme : angles morts et manques

Audit du 2026-07-12. Complète `docs/10-audit-securite-perf.md` (incident réel,
refactor non-bloquant, zone entrée temporisée, sirène embarquée, faille MQTT
LAN corrigée, contrôle caméra 100 % local). **Ce document ne re-liste pas ce
qui a déjà été corrigé** : il évalue AEGIS contre les attentes d'une alarme
résidentielle sérieuse (type Verisure/Ajax) et liste ce qui manque encore.

Légende gravité : **P0** = compromet la fonction de base de l'alarme (détecter
et dissuader une intrusion réelle) — **P1** = dégrade fortement la fiabilité ou
l'usage — **P2** = durcissement/qualité de vie.

État : **absent** / **partiel** / **présent**.

---

## 1. Détection anti-sabotage (tamper)

| # | Point | Gravité | Pourquoi ça compte | État AEGIS |
|---|---|---|---|---|
| 1.1 | Arrachement/décrochage d'un capteur Zigbee | P0 | Un cambrioleur qui repère le contact sur la porte peut l'arracher pour couper la remontée sans jamais générer d'ouverture. Les capteurs Aqara n'ont pas d'interrupteur anti-sabotage exploité ici. | **Absent.** `mqtt_state.py` ne détecte l'absence d'un capteur qu'au bout de `SENSOR_TIMEOUT = 3 * 3600` (3 h, `webapp/mqtt_state.py:20`) — bien trop lent pour un tamper temps réel. Aucune alerte immédiate sur perte de liaison capteur. |
| 1.2 | Arrachement/occultation caméra | P0 | Masquer/débrancher une caméra doit lever une alerte, pas juste couper le flux silencieusement. | **Absent.** `camera.py` ne détecte pas la coupure d'alimentation caméra (uniquement les échecs pytapo, journalisés en interne, pas notifiés à l'utilisateur comme un événement tamper). |
| 1.3 | Brouillage Zigbee (jamming) | P0 | Un brouilleur RF est l'attaque classique contre les alarmes Zigbee/Z-Wave low-cost : plus aucun capteur ne remonte, sans que ça ressemble à une panne. | **Absent.** Seul le bridge Z2M (`bridge_online`, `app.py:150`) est surveillé — un brouillage qui coupe les capteurs sans couper le coordinateur lui-même ne serait pas vu avant 3 h (cf. 1.1), et aucune détection de niveau de bruit RF / perte de liaison anormalement groupée. |
| 1.4 | Brouillage/coupure Wi-Fi (caméras) | P1 | Les caméras Tapo sont en Wi-Fi ; un brouilleur ou une simple coupure AP les rend muettes sans alerte dédiée. | **Partiel.** `_do()` journalise les échecs pytapo mais ne remonte pas d'événement "caméra injoignable" à l'utilisateur (contrairement aux prises, cf. 1.6). |
| 1.5 | Coupure secteur (Pi / box / caméras / sirène) | P0 | La coupure de courant est l'attaque la plus simple et la plus radicale : tout s'éteint, plus de détection, plus d'alerte, plus de sirène. | **Absent.** Aucune UPS documentée ni surveillance d'alimentation. Une coupure secteur = silence total, y compris côté notification (rien ne peut alerter si le Pi est éteint). |
| 1.6 | Coupure Internet | P0 | Couper la box est une façon simple de neutraliser les notifications sans toucher à l'alimentation. | **Absent** en tant que canal de secours (cf. §2.2) ; **partiel** en détection : `healthz` (`app.py:732`) existe mais n'est interrogé par personne d'externe (pas de monitoring tiers), donc une coupure Internet = silence, pas d'alerte "je suis hors ligne" (impossible par construction si le canal de sortie est coupé — nécessite un canal indépendant, cf. 4G/SMS). |
| 1.7 | Extinction du Raspberry Pi (soft ou franche) | P0 | Si l'intrus (ou n'importe qui avec accès physique) éteint le Pi, toute la chaîne s'arrête — capteurs, orchestrateur, webapp, notifs. | **Absent.** `Restart=on-failure` (systemd) relance le process s'il crashe, mais rien ne détecte/alerte une extinction de la machine elle-même (pas de watchdog externe, pas de notification "dernier signe de vie" manquant). |

**Synthèse §1** : AEGIS n'a aucune détection anti-sabotage temps réel. Tout
repose sur l'hypothèse que l'attaquant coupe une porte/fenêtre plutôt que
l'infrastructure elle-même — hypothèse fausse pour un cambrioleur qui a
repéré les caméras/capteurs (très visibles, Wi-Fi/Zigbee grand public).

## 2. Résilience infrastructure

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 2.1 | Batterie de secours (UPS) Pi + box + sirène | P0 | Sans onduleur, une simple micro-coupure ou un disjoncteur coupé annule toute la protection pendant la fenêtre où l'intrusion est la plus probable (nuit, personne à la maison). | **Absent**, aucune mention dans le code/doc. |
| 2.2 | Canal de secours si Internet coupé (4G/SMS) | P0 | Toute la notification (mail SMTP, Telegram) dépend d'Internet. `docs/08` mentionne "notifs Telegram/**SMS Free Mobile**" comme cible, mais `notify.py` n'implémente que mail + Telegram (`orchestrator/notify.py:1-109`, aucune trace de SMS/API Free Mobile). Sans modem 4G indépendant, couper la box = 0 alerte possible, quelle que soit la qualité de la détection. | **Absent** (SMS documenté comme "à introduire", jamais codé — écart doc/code confirmé). |
| 2.3 | Watchdog / heartbeat process | P1 | Détecter qu'un composant (orchestrateur, webapp, health_monitor) est figé/mort, pas juste crashé. | **Partiel.** systemd `Restart=on-failure` (`aegis-orchestrator.service`, `aegis.service`) relance en cas de crash, mais rien ne détecte un thread figé (deadlock) qui ne crashe pas le process ; pas de heartbeat externe (ex. envoi périodique "je suis vivant" surveillé par un tiers type Healthchecks.io/UptimeRobot). |
| 2.4 | Redémarrage auto après coupure secteur | P2 | Le Pi doit redémarrer seul au retour du courant. | **Vraisemblablement présent** (comportement par défaut Raspberry Pi OS/BIOS, pas de configuration contraire trouvée) mais **non vérifié dans le code/doc** — à confirmer physiquement (BIOS/firmware Pi 5 n'a pas toujours l'auto power-on). |
| 2.5 | Persistance de l'état armé après coupure | P1 | Si le Pi redémarre pendant que la maison est vide et armée, l'alarme doit revenir armée, pas désarmée par défaut. | **Partiel/ambigu.** `Orchestrator.run()` (`alarm.py:474-486`) attend 5 s l'état MQTT retenu (`retain=True` sur `aegis/alarm/set`, cf. `app.py:726-727`) ; si aucune commande retenue n'arrive, il **redémarre désarmé** (`log.info("Aucune commande retenue — démarrage désarmé")`, `alarm.py:481`). Le broker Mosquitto tourne en conteneur avec volumes (retained survit, cf. docs/10 §4c) donc en théorie l'état retenu persiste — mais le comportement par défaut en cas de doute est **désarmé**, ce qui est le choix sûr pour ne pas se retrouver bloqué dehors, mais dangereux si la coupure visait justement à désarmer silencieusement pendant une absence. |

## 3. Modes d'armement (granularité)

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 3.1 | Armement partiel (nuit / présence) | P1 | Une vraie alarme permet d'armer le périmètre (portes/fenêtres, caméras communes) en gardant les chambres "libres" pour dormir sans déclencher à chaque passage nocturne. | **Absent.** `api_alarm_set` (`webapp/app.py:717-729`) n'accepte que `arm`/`disarm` global. `Orchestrator.arm()`/`disarm()` (`alarm.py:272-347`) n'ont pas de notion de sous-ensemble de capteurs/caméras. |
| 3.2 | Armement par zone | P1 | Isoler une aile (ex. chambres enfants) de la surveillance pendant que le reste est armé. | **Absent**, même limite que 3.1 — seule granularité existante est la "zone entrée" temporisée (`entry_zone`, `alarm.py:145-159`), qui gère un délai, pas une désactivation de zone. |
| 3.3 | Armement "présence" (dissuasion sans surveillance intérieure) | P2 | Utile si quelqu'un reste à la maison mais veut garder portes/fenêtres surveillées. | **Absent**, pas de troisième état outre armé/désarmé. |

## 4. Faux positifs / vérification / levée de doute

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 4.1 | Filtrage animaux domestiques | P1 | Sans filtre, un chat/chien déclenche l'alarme complète (sirène, notif, réveil). YOLO classe `person` (0) est filtré par confiance mais aucune classe animal n'est exclue explicitly — pas un souci si pas d'animaux, mais absence de logique dédiée si le foyer en acquiert un. | **Non applicable actuellement** mais **absent** structurellement (`camera.py` OBJECTS = personne/couteau/ciseaux/batte uniquement, pas de logique de suppression animal). |
| 4.2 | Détection IA de nuit | P1 | La confiance YOLO chute fortement en vision nocturne (bruit IR, contraste faible) : plus de ratés ou plus de faux positifs selon le réglage. | **Partiel.** Vision nocturne "auto" sur les caméras (docs/10 §4d) mais aucun réglage `conf` différencié jour/nuit, aucune validation terrain mentionnée sur détection nocturne réelle. |
| 4.3 | Sirène embarquée déclenchée par la détection **de la caméra**, pas par YOLO | P1 | La sirène caméra (`set_onboard_alarm`, `camera.py:147-156`) sonne sur la détection de mouvement propriétaire Tapo, pas sur notre YOLO calibré — risque de faux positifs (reflets, insectes, changement de luminosité) qui sonnent la sirène sans qu'AEGIS ait confirmé une personne. Assumé et documenté (docs/10 §4c) comme compromis acceptable "maison censée vide" mais reste un vecteur de fausses alertes fréquentes/fatigue utilisateur. | **Présent mais avec limite connue et non mitigée.** |
| 4.4 | Séquence de confirmation avant escalade complète | P1 | Une alarme sérieuse distingue "détection" (notification discrète) de "confirmée" (sirène + escalade), pour réduire les fausses alertes qui épuisent la vigilance. | **Absent.** `trigger_alarm()` (`alarm.py:421-439`) déclenche notif + sirène externe + sirènes caméra + captures en une seule étape dès la première détection, sans étage intermédiaire de confirmation (ex. 2 détections rapprochées, ou detection + non-réponse). |
| 4.5 | Levée de doute vidéo à distance | P2 | Pouvoir vérifier en direct ce qui se passe avant d'agir/appeler la police. | **Partiel.** `/cameras/live/<key>` (`app.py:667-696`) permet un flux live, mais uniquement si déjà armé et **uniquement fonctionnel sur le salon** (docs/08 dernière ligne : "Ne marche pour l'instant que sur le salon"). Pas de clip vidéo joint automatiquement à l'alerte — l'utilisateur doit ouvrir l'app et naviguer manuellement pendant l'incident. |

## 5. Détection d'intrusion (couverture)

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 5.1 | Chambres sans caméra (angle mort vidéo) | P0 | `devices.yaml` : caméras uniquement Entrée/Salon/Cuisine/Couloir. Chambre parents, Chambre Noah, Chambre Mia n'ont **que** des capteurs de contact fenêtre — aucune preuve visuelle, aucune détection de présence intérieure dans ces pièces. Une intrusion par une fenêtre de chambre restée entrouverte, ou sans passer par une ouverture surveillée, n'est pas vue. | **Absent** (confirmé, `webapp/devices.yaml:39-41` vs `:30-33`). C'est exactement le scénario de l'incident du 2026-07-09 (Chambre Noah, docs/10). |
| 5.2 | Détecteurs de mouvement PIR dédiés | P1 | La seule détection de mouvement est la comparaison de frames caméra (`camera.py motion()`), donc uniquement où il y a une caméra et seulement quand elle n'est pas en privacy. Pas de PIR Zigbee indépendant, moins cher, plus rapide, fonctionnant aussi dans le noir sans dépendre de la charge YOLO. | **Absent.** |
| 5.3 | Détecteur de bris de glace / vibration | P1 | Une fenêtre cassée sans ouverture du battant (verre brisé, cadre resté fermé) ne déclenche jamais un capteur de contact. | **Absent** de `devices.yaml` (aucun `kind: glassbreak`/`vibration`). |
| 5.4 | Porte de garage | P2 | Non applicable si pas de garage dans le logement — à confirmer, mais rien dans le registre. | **Absent / non applicable**, à vérifier selon le bien réel. |
| 5.5 | Détecteur fumée/CO | P0 (sécurité vie, hors périmètre "intrusion" strict) | Une "alarme maison" au sens large inclut souvent la sécurité incendie/CO ; absence totale ici bien que ce ne soit pas le périmètre initial du projet. | **Absent.** À clarifier si volontairement hors scope (alarme anti-intrusion uniquement) — si oui, le dire explicitement pour ne pas laisser croire à une protection incendie qui n'existe pas. |
| 5.6 | Caméra Salon état | P1 | Historique de suspensions/auth cassée (docs/10). Si non totalement stabilisée, c'est un angle mort vidéo sur la plus grande pièce commune. | **À reconfirmer** — docs/10 §4d indique un retour en local prévu "au déblocage", statut définitif non documenté ici. |

## 6. Alerte & escalade

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 6.1 | Accusé de réception (ACK) de l'alerte | P1 | Sans ACK, personne ne sait si l'alerte envoyée a été vue par quelqu'un — critique la nuit (téléphone en silencieux). | **Absent.** `notify.send_alert` (`notify.py:98-109`) envoie et journalise l'échec technique (SMTP/Telegram HTTP status) mais ne trace pas de lecture/réponse utilisateur. |
| 6.2 | Escalade multi-destinataire séquencée | P1 | Si le contact principal ne répond pas en N minutes, alerter un second contact (voisin, famille, télésurveillance). | **Absent.** Les destinataires mail/Telegram (`_mail_recipients`, `_telegram_chat_ids`, `notify.py:48-59`) reçoivent tous simultanément, sans hiérarchie ni relance différée. |
| 6.3 | Appel téléphonique / SMS | P0 | Un mail ou un message Telegram peut être manqué (notifications silencieuses, téléphone en Do Not Disturb) ; un appel vocal ou SMS a un statut d'alerte plus fort et perce plus souvent les modes silencieux. | **Absent**, comme 2.2 — documenté comme cible ("SMS Free Mobile") jamais implémenté. |
| 6.4 | Télésurveillance professionnelle | P2 (fonctionnalité) | Une vraie centrale d'alarme a une option d'intervention humaine/déplacement d'agent. Hors de portée d'un projet DIY, mais à nommer comme limite assumée du produit. | **Absent par conception** — acceptable si assumé, à documenter comme choix. |
| 6.5 | File de notification persistante avec retry | P1 | `notify.py` envoie une fois, best-effort (`try/except` avale l'échec, log seulement) ; pas de file, pas de retry différé, pas de garantie de livraison si SMTP/Telegram sont temporairement indisponibles au moment précis de l'intrusion. | **Absent** (déjà identifié comme axe P2 dans docs/10 §3, toujours pas fait). |
| 6.6 | Ordre de priorité des canaux | P2 | `trigger_alarm` notifie mail + Telegram en parallèle dans le même appel (`notify.send_alert`), sans ordre de priorité configurable par type d'événement/heure. | **Partiel** — Telegram et mail sont envoyés dans le même appel synchrone du thread pool (`_send_email` puis `_send_telegram`, `notify.py:107-108`), donc mail (SMTP, jusqu'à 20 s de timeout) peut retarder l'envoi Telegram si SMTP traîne, malgré l'exécution "asynchrone" par rapport au thread MQTT. |

## 7. Journalisation & preuve

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 7.1 | Stockage des captures **local uniquement** | P0 | `storage.py` écrit dans `webapp/captures/` sur le Pi lui-même (`CAPTURES_DIR`, `storage.py:14-17`). Si le Pi est volé/détruit pendant/après l'intrusion (scénario réaliste — c'est souvent l'objectif ou la conséquence), **toutes les preuves photo disparaissent avec lui**. Pas de sauvegarde offsite (cloud, NAS distant, autre machine). | **Absent** (limite explicitement assumée dans le code comme un "avantage" — "pas de dépendance externe" — mais c'est aussi un risque de preuve non documenté). |
| 7.2 | Journal d'événements (SQLite) — intégrité | P1 | `database.py` table `events` (insert simple, `INSERT INTO events...`, `database.py:172`) n'a ni hash-chaînage, ni export automatique, ni protection contre modification/suppression locale — un accès physique/logique au Pi permet de réécrire l'historique. | **Absent** (pas critique pour du DIY personnel, mais à connaître si le journal doit un jour servir de preuve). |
| 7.3 | Rétention/purge des captures | P2 | `MAX_CAPTURES = 500` (`storage.py:18`) purge automatiquement les plus anciennes — bon réflexe anti-saturation disque, mais **aucune caméra active pendant l'incident n'est protégée d'une purge si un autre événement survient rapidement après** (pas de "verrou" sur les preuves d'un incident en cours d'investigation). | **Présent** (purge) mais **sans exception pour preuves à conserver**. |
| 7.4 | Horodatage fiable | P2 | Les événements utilisent `time.time()` / horloge système du Pi ; sans NTP vérifié explicitement documenté, un décalage d'horloge fausserait la chronologie en cas de litige. | **Non documenté** — vraisemblablement correct (NTP par défaut Raspberry Pi OS) mais pas vérifié/mentionné. |

## 8. UX & exploitation

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 8.1 | Armement/désarmement par badge NFC | P1 | Plus rapide et plus fiable qu'un login web pendant le délai d'entrée (30 s, `ENTRY_DELAY_S`, `alarm.py:56`) — surtout pour un enfant ou en cas de mains chargées. `docs/08` liste "NFC : firmware ESP … à trancher" comme brique prévue mais jamais livrée ; l'entrée `badgeuse` dans `devices.yaml:17` est un simple **doorbell** décoratif, non câblé à `arm()`/`disarm()`. | **Absent** (planifié, jamais implémenté). |
| 8.2 | Application mobile dédiée | P2 | Le webapp est responsive mais reste un site web classique (login + CSRF), pas une app avec notifications push natives. | **Absent** (Telegram fait office de canal "mobile" de facto). |
| 8.3 | Géofencing (armement auto au départ) | P2 | Réduit le risque d'oubli d'armement en sortant. | **Absent.** |
| 8.4 | Retour d'état clair pendant le délai d'entrée | P1 | Pendant les 30 s de tempo entrée, l'utilisateur doit savoir combien de temps il lui reste pour désarmer sans paniquer. | **Partiel/à vérifier front.** Le back publie un `publish_event("door", "Présence entrée"/"Entrée ouverte", ...)` avec le délai en texte (`alarm.py:385,403`), mais rien dans le code revu ne montre de compte à rebours visuel/sonore côté UI ou notification poussée immédiate au déclenchement du tempo (à confirmer côté templates `webapp/templates/`). |
| 8.5 | Délai de sortie/entrée fixes, non ajustables par utilisateur final | P2 | `EXIT_DELAY_S`/`ENTRY_DELAY_S` sont des variables d'environnement (`alarm.py:56-57`), pas des réglages exposés dans l'admin webapp — changer le tempo nécessite d'éditer le `.env` et de redémarrer le service. | **Partiel** (réglable, mais pas en libre-service pour l'utilisateur non technique). |

## 9. Sécurité (surface restante)

| # | Point | Gravité | Pourquoi | État |
|---|---|---|---|---|
| 9.1 | Cloudflare Access devant le hostname | P1 | Sans authentification en amont, l'app web (login + CSRF, correctement implémentés) reste directement exposée sur Internet via le tunnel — une seule couche de défense. Identifié depuis docs/08 et 10, toujours listé "reste à finaliser". | **Absent** (toujours non fait à ce jour). |
| 9.2 | MFA sur le login admin | P2 | Un compte admin unique protégé par mot de passe seul reste vulnérable au phishing/réutilisation de mot de passe malgré scrypt + rate-limit. | **Absent.** |
| 9.3 | Mise à jour du système (Pi OS, dépendances, firmware caméras) | P1 | Pas de mécanisme de mise à jour automatique/mention de cadence de patch mentionnée dans la doc (`docs/08` liste des versions figées, ex. `pytapo==3.3.54` volontairement pinné pour compat KLAP) — bon pour la stabilité, mais aucun processus de suivi des CVE sur Flask/gunicorn/paho-mqtt/ultralytics. | **Absent/non documenté.** |
| 9.4 | Secrets : rotation | P2 | Vault hors-repo (`/home/j.tremont/.secrets/vault.env`) : bonne pratique de stockage, mais aucune politique de rotation mentionnée (mots de passe Tapo, token Telegram, app password Gmail). | **Partiel** (bien stocké, jamais tourné). |
| 9.5 | Broker MQTT : `allow_anonymous` | P2 | Le fix appliqué (docs/10 §4c) restreint l'écoute à `127.0.0.1`, ce qui suffit tant que rien d'autre ne tourne sur le Pi ou n'est exposé — mais l'option de défense en profondeur (`password_file`, `allow_anonymous false`) proposée dans docs/10 n'a pas été appliquée. | **Partiel** (mitigé par le binding local, pas par l'auth). |

---

## Verdict global

L'incident du 2026-07-09 et les correctifs qui ont suivi (docs/10) ont réglé
la **chaîne de déclenchement** : l'alarme alerte vite, prend des photos, et se
désarme même si les caméras Tapo déraillent. C'est une base saine et un vrai
progrès.

Mais évaluée comme **produit d'alarme résidentielle complet**, AEGIS a
aujourd'hui un point commun avec beaucoup de systèmes DIY : elle protège très
bien contre le scénario "quelqu'un ouvre une porte/fenêtre surveillée pendant
que tout le reste fonctionne normalement", et n'a **aucune réponse** dès qu'un
attaquant s'en prend à l'infrastructure elle-même (coupe le courant, le Wi-Fi,
la box, ou arrache un capteur) — ce qui est précisément ce que fait un
cambrioleur qui a repéré des caméras et capteurs visibles. Les manques les
plus graves (§1 tamper, §2.1/2.2 résilience, §5.1 chambres sans caméra, §6.3
appel/SMS, §7.1 preuves locales) sont tous des scénarios où l'alarme peut être
neutralisée ou rendue aveugle **silencieusement**, sans qu'aucune notification
ne parte — c'est la caractéristique commune à traiter en priorité.
