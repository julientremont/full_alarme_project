# AEGIS — Spécification design

Référence complète pour la refonte de l'interface. Rendu pixel exact :
`AEGIS Redesign.dc.html`.

---

## 1. Constat critique (maquette d'origine)

| Problème | Correction |
|---|---|
| **Trop de texte** — chaque carte empile nom + état + sous-titre + LQI + %. | Une info primaire par carte, le reste en secondaire discret. |
| **Effet « IA / slop »** — logo chromé 3D, « l'œil qui voit tout », KPIs décoratifs (100 % santé réseau…). | Bouclier plat argenté (2D), une seule métrique héro, zéro chiffre décoratif. |
| **Décalage produit** — coordinateur Zigbee, routeurs, capteurs porte/fenêtre, NFC : absents du code. | Navigation recentrée : Tableau de bord · Caméra · Journal · Détection IA · Paramètres. |

## 2. Ce que le backend fait vraiment

Boucle `main.py` : connexion caméra Tapo → détection de mouvement (diff de
2 images à 10 s) → si mouvement, YOLOv8 pendant 30 s → si objet surveillé
(confiance ≥ 0.8), annotation, sauvegarde Google Drive + e-mail (1re capture
puis 1 toutes les 4).

- **Objets surveillés** : Personne, Couteau, Ciseaux, Batte (classes YOLO 0/43/76/39).
- **Sorties** : image annotée, upload Drive, e-mail avec photo jointe.
- **Logs** par module (main, ia, tapo, mail, drive) → source du Journal.

## 3. Tokens

| Token | Valeur | Usage |
|---|---|---|
| `--bg` / `--bg-app` | `#06080B` / `#0A0D10` | Fond page / app |
| `--surface` | `#0F141A` | Cartes |
| `--surface-2` | `#0B0F14` | Cartes imbriquées, champs |
| `--border` / `--border-2` | `#1A2029` / `#232B35` | Contours 1px |
| `--text-hi` / `--text-mid` / `--text-low` | `#E5EBEC` / `#8A94A0` / `#6B7480` | Texte 3 niveaux |
| `--cyan` | `#00B2FF` | Actif, liens, focus |
| `--green` | `#22D07A` | Protégé, en ligne, OK |
| `--red` | `#F0454B` | Alerte, objet dangereux, REC |

- **Typo** : Satoshi (Fontshare). 900 titres, 700 sous-titres, 500 corps.
- **Grille** 8px. **Rayons** 10–20px.
- **Boutons** : primaire = fond `#E5EBEC` texte foncé ; secondaire = surface +
  contour ; danger = rouge.
- **Toucher mobile** ≥ 44px.
- **Bouclier** : SVG 2D plat (`assets/shield.svg`), teinté vert quand protégé.

## 4. Écrans

- **Connexion** — bouclier centré, 2 champs, un bouton. Aucun texte marketing.
- **Tableau de bord** — héro : état de protection (bouclier + anneau animé) +
  bouton Armer/Désarmer. À droite : 2 stats (détections du jour, état caméra) +
  3 derniers évènements.
- **Caméra** — flux RTSP grand format + boîtes de détection (label + %),
  badge REC, boutons Capturer / Plein écran ; colonne détections récentes +
  puces objets surveillés.
- **Journal** — timeline verticale (point coloré par gravité) : objet, heure,
  confiance, « alerte envoyée ». Filtres. Groupé par jour.
- **Détection IA** — toggles objets surveillés, seuil de confiance (slider),
  graphe 7 jours + répartition, statut du modèle YOLOv8.
- **Paramètres** — caméra (IP, statut, test), alertes (e-mail, cadence),
  sensibilité mouvement (slider), système. Mappe 1:1 sur les constantes backend.

Desktop = sidebar 240px. Mobile = tab bar en bas.

## 5. Architecture & fichiers

```
src/
├─ web/
│  ├─ app.py            # Flask : routes pages + API JSON
│  ├─ state.py          # état partagé (armed, camera, events, settings)
│  ├─ static/
│  │   ├─ css/aegis.css # tokens + composants (fourni)
│  │   ├─ js/aegis.js   # polling état, arm/désarm, live
│  │   └─ img/shield.svg
│  └─ templates/
│      ├─ base.html
│      ├─ login.html  dashboard.html  camera.html
│      └─ journal.html  ai_detection.html  settings.html
└─ (existant : main.py, utils/iadetection.py, tapo/, googl/)
```

| Endpoint | Rôle |
|---|---|
| `GET /api/status` | armé/désarmé, caméra en ligne, nb détections du jour |
| `GET /api/events` | journal (objet, heure, conf, alerte) |
| `POST /api/arm` | armer / désarmer la surveillance |
| `GET /api/stream` | MJPEG du flux Tapo (OpenCV → multipart) |
| `GET/POST /api/settings` | objets surveillés, seuil mouvement, e-mail, cadence |

### Notes d'intégration
- `state.py` doit être **thread-safe** (`threading.Lock`) car `main.py` (boucle)
  et Flask (requêtes) y accèdent en parallèle.
- `main.py` lit `state.armed` à chaque tour de boucle ; s'il est `False`,
  ne pas lancer `detect_objects`.
- Chaque détection ajoute un évènement à `state.events` :
  `{ts, type: "person"|"knife"|..., conf, alert_sent: bool, image_id}`.
- `/api/stream` : réutiliser l'ouverture `cv2.VideoCapture(rtsp_url)` de
  `tapo.py`, encoder chaque frame en JPEG et yield en `multipart/x-mixed-replace`.
