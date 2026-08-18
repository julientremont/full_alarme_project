# AEGIS — supervision alarme maison

Interface web de supervision/contrôle de l'alarme DIY Zigbee (projet `full_alarme_project`).
Design & sécurité repris de `calsport`. Détails : `../docs/07-design-interface.md`.

## Pages
- **/** Matériel — état live de l'infra Zigbee, sécurité, caméras, capteurs (vert=on, rouge=off, bleu=fermé, orange=ouvert, gris=non installé).
- **/cameras** — flux caméras + sélecteur, avec visionneuse intégrable via variables d'environnement quand les flux sont disponibles.
- **/journal** — événements (ouvertures/fermetures live, armé/désarmé à venir).
- **/detection** — Détection IA : objets surveillés, seuil de confiance, sensibilité au mouvement, statut du modèle YOLOv8 et statistiques (dérivées des captures). Les réglages sont diffusés à l'orchestrateur (retenu) sur `aegis/detection/config` et appliqués en direct.
- **/admin** (admin uniquement) — gestion des comptes.

## Comptes & permissions
- **Admin** : voit tous les onglets + l'onglet Administration. Au moins un admin actif est garanti (impossible de bloquer/supprimer/rétrograder le dernier).
- **Création de comptes** (depuis /admin) : identifiant, mot de passe (≥8), choix des **onglets visibles** (Matériel / Caméras / Journal), option admin.
- **Par compte** : modifier les onglets, **bloquer/débloquer** l'accès, promouvoir/rétrograder admin, réinitialiser le mot de passe, supprimer.
- Un blocage est **immédiat** : la session active de l'utilisateur est invalidée à la requête suivante (`before_request` recharge l'utilisateur depuis la BDD).
- La sidebar n'affiche que les onglets autorisés ; un accès direct à une URL non autorisée renvoie **403**.

## Installation (Raspberry Pi)
```bash
cd webapp
uv sync                              # crée .venv + installe les deps
cp .env.example .env && nano .env    # définir AEGIS_SECRET_KEY (token_hex(32))
uv run python create_user.py julien --admin
```

## Lancer
```bash
# dev
uv run flask --app app run --host 127.0.0.1 --port 5002
# prod (systemd)
sudo cp config/aegis.service /etc/systemd/system/
sudo systemctl enable --now aegis
```
Puis exposer via Cloudflare Tunnel (`config/cloudflared.yml`).

## Architecture
- `app.py` — Flask (auth session + CSRF + rate-limit), routes pages + `/api/state`, `/api/events`, `/api/detection`.
- `mqtt_state.py` — thread paho-mqtt abonné à `zigbee2mqtt/#`, registre d'état en mémoire, journalise les changements de contact.
- `database.py` — SQLite : users + events + settings (réglages détection).
- `devices.yaml` — registre déclaratif du matériel (un seul endroit à éditer).
- ⚠️ gunicorn **1 worker** (l'état MQTT vit dans le process) — voir `aegis.service`.

## Intégration caméras
- La page `/cameras` peut afficher une visionneuse réelle si des variables `AEGIS_CAMERA_<KEY>_...` sont définies dans `.env`.
- Champs supportés : `VIEWER_URL`, `VIEWER_MODE` (`iframe`, `video`, `image`), `SNAPSHOT_URL`, `TRANSPORT`, `NOTE`.
- Exemple : `AEGIS_CAMERA_CAM_ENTREE_VIEWER_URL=https://go2rtc.local/stream.html?src=entree`

## À brancher plus tard
- Caméras : brancher la passerelle RTSP→HLS/WebRTC réelle du script YOLO/Tapo ou d'un viewer équivalent.
- Armer/désarmer + sirène : page `/controle` publiant sur MQTT vers l'orchestrateur Python.
