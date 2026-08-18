# AEGIS — Dossier de passation

Dépose ce dossier `aegis-handoff/` à la racine de ton repo **Security**, puis
ouvre Claude Code à la racine du repo.

## Comment l'utiliser

1. Copie le contenu de **`PROMPT.md`** et colle-le dans Claude Code.
2. Claude Code lira automatiquement les fichiers de référence de ce dossier :
   - **`DESIGN_SPEC.md`** — critique, tokens, specs de chaque écran, architecture, API.
   - **`aegis.css`** — feuille de style prête à l'emploi (tokens + composants). À copier dans `src/web/static/css/`.
   - **`assets/shield.svg`** — le logo bouclier (SVG 2D plat).
3. Laisse Claude Code proposer son plan de fichiers, valide, puis go.

## Contenu

```
aegis-handoff/
├─ README.md          ← ce fichier
├─ PROMPT.md          ← à coller dans Claude Code
├─ DESIGN_SPEC.md     ← référence design complète
├─ aegis.css          ← styles réutilisables (vanilla, sans build)
└─ assets/
   └─ shield.svg      ← logo AEGIS
```

## Maquettes de référence

Le rendu pixel exact est dans `AEGIS Redesign.dc.html` (ouvrable dans le
navigateur). Tous les écrans y figurent, desktop + mobile :
Connexion · Tableau de bord · Caméra · Journal · Détection IA · Paramètres.

## Rappel produit

Backend réel : caméra Tapo (RTSP) → détection de mouvement → YOLOv8 →
sauvegarde Google Drive + e-mail. **L'UI ne doit exposer que ces fonctions
réelles.** Pas d'écosystème Zigbee inventé.
