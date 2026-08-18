# Prompt à coller dans Claude Code

> Ouvre Claude Code à la racine du repo `Security`, puis colle le bloc ci-dessous.

---

Tu travailles dans mon repo de surveillance (caméra Tapo + YOLOv8 + Flask).
Objectif : ajouter un **frontend web AEGIS**, sobre et pro, desktop + mobile,
SANS casser la boucle de détection existante (`src/main.py`).

Avant de coder, lis ces fichiers de référence dans `aegis-handoff/` :
- `DESIGN_SPEC.md` (critique, tokens, specs écran, architecture, API)
- `aegis.css` (styles prêts à l'emploi — à placer dans `src/web/static/css/`)
- `assets/shield.svg` (logo)

## Contexte code (existant)
- `src/main.py` : boucle mouvement → détection YOLO → Drive + e-mail.
- `src/utils/iadetection.py` : `OBJECTS_TO_DETECT = {0:Personne, 43:Knife,
  76:Scissors, 39:Baseball_bat}`, confiance 0.8, `verifier_mouvement` (seuil 10000).
- `src/tapo/tapo.py` : flux RTSP `rtsp://user:pass@ip:554/stream1`.
- `src/googl/` : `Mail.py` (SMTP Gmail), `gdrive.py` (upload/list Drive).
- Logs par module dans `src/utils/logger.py`.

## À faire
1. Créer `src/web/` (Flask) :
   - `state.py` : état partagé **thread-safe** (`armed`, `camera_online`,
     `events[]`, `settings`).
   - `app.py` : routes pages + API (ci-dessous).
2. Faire écrire `main.py` dans `state.py` à chaque évènement (mouvement,
   détection objet + confiance, alerte envoyée) au lieu de logger seulement.
   Respecter le flag `armed` : ne lancer la détection que si `armed=True`.
3. Routes JSON :
   - `GET  /api/status`   → armed, camera_online, détections du jour
   - `GET  /api/events`   → journal (objet, heure, confiance, alerte)
   - `POST /api/arm`      → armer / désarmer
   - `GET  /api/stream`   → MJPEG du flux Tapo (OpenCV → multipart)
   - `GET/POST /api/settings` → objets surveillés, seuil mouvement, e-mail, cadence
4. Pages (`src/web/templates/`) : `login`, `dashboard`, `camera`, `journal`,
   `ai_detection`, `settings` + `base.html` (sidebar desktop / tab bar mobile).
5. `src/web/static/css/aegis.css` : partir du fichier fourni.

## Direction visuelle (identité AEGIS — NE PAS dévier)
- Thème sombre. Fond `#06080B`/`#0A0D10`, cartes `#0F141A`, bordures `#1A2029`.
- Texte `#E5EBEC` / `#8A94A0` / `#6B7480`. Accents : cyan `#00B2FF` (actif/lien),
  vert `#22D07A` (protégé/OK), rouge `#F0454B` (alerte/REC).
- Police **Satoshi** (Fontshare). Grille 8px, rayons 10–20px.
- Bouclier = SVG 2D plat (`assets/shield.svg`), teinté vert quand protégé.
- **RÈGLE D'OR** : peu de texte, forte hiérarchie, aucun chiffre décoratif.
  Une info primaire par carte. Aucun écosystème Zigbee inventé.
- Navigation : Tableau de bord · Caméra · Journal · Détection IA · Paramètres.
  Desktop = sidebar 240px ; mobile = tab bar en bas (cibles ≥ 44px).

## Écrans (voir `DESIGN_SPEC.md` §4 + maquette HTML pour le rendu exact)
- **Login** : bouclier centré, 2 champs, 1 bouton, zéro marketing.
- **Dashboard** : héro état de protection (bouclier + anneau animé + bouton
  Armer/Désarmer) ; 2 stats (détections du jour, caméra en ligne) ;
  3 derniers évènements ; lien vers le journal.
- **Caméra** : flux MJPEG grand format + boîtes de détection (label + %),
  badge REC, boutons Capturer/Plein écran ; liste détections récentes +
  puces des objets surveillés.
- **Journal** : timeline verticale, point coloré par gravité, filtres, groupé par jour.
- **Détection IA** : toggles objets surveillés, seuil de confiance (slider),
  stats de détection, statut du modèle YOLOv8.
- **Paramètres** : caméra (IP/statut/test), alertes (e-mail, cadence),
  sensibilité mouvement (slider), système. Mappe 1:1 sur les constantes backend.

## Contraintes
- Ne modifie pas la logique de détection, seulement l'ajout d'écriture d'état
  + le respect du flag `armed`.
- CSS/JS **vanilla** (pas de build). UI en **français**.
- Commits atomiques : (a) state+api, (b) hook main.py, (c) templates+css,
  (d) live stream. Documente le lancement (`flask run`) dans le README.

Commence par me proposer le plan de fichiers, puis attends mon feu vert.
