# 07 — Interface web « AEGIS » (design + stratégie)

App web de supervision/contrôle de l'alarme. Nom : **AEGIS** (bouclier protecteur). Renommable trivialement (constante `APP_NAME`).

---

> **Origine** : le projet a démarré comme un clone du design `calsport` (`/home/j.tremont/Documents/Projets/calsport`). Depuis, l'UI a été **entièrement retravaillée** en un système autonome — la section A ci-dessous est désormais la **source de vérité du design AEGIS** (et non plus un simple calque de calsport). La sécurité (A.3) et le déploiement (A.4) restent, eux, calqués sur calsport.

## Partie A — Design system AEGIS (source de vérité)

Fichier maître : `webapp/static/style.css` (en-tête `/* AEGIS - source of truth UI */`). **Toute modif future doit passer par les tokens CSS** (variables `:root`), jamais de couleur/taille en dur.

> **Alignement design (2026-07)** : l'UI a été alignée « au pixel » sur la proposition `claude/aegis-handoff/aegis.css` + `DESIGN_SPEC.md` (la maquette HTML `AEGIS Redesign.dc.html` citée dans les README n'a jamais été livrée). Résultat : **palette plate et sobre**, suppression des dégradés / glass / grille de fond / halos, titres en couleur pleine. Le lien CSS est versionné (`style.css?v=<mtime>`, contexte `asset_v`) pour casser le cache navigateur/Cloudflare.

### A.1 Tokens (`:root` dans `style.css`)
- **Fonds / surfaces** (plates) : `--bg-black:#0A0D10` (fond app), `--bg-deep:#06080B`, `--surface`/`--bg-panel:#0F141A` (cartes), `--surface-2`/`--bg-panel-soft:#0B0F14` (champs, cartes imbriquées), `--bg-panel-hover:#131A22`, `--sidebar-bg:#0C1016`, `--shell-line:#171E26`.
- **Bordures** (1px pleines) : `--border-subtle:#1A2029`, `--border-strong:#232B35`, `--border-accent:rgba(0,178,255,.28)`.
- **Accent** : `--accent-cyan:#00B2FF`, `--accent-glow:rgba(0,178,255,.12)`.
- **Couleurs d'état** (sémantique matériel, voir A.5) : `--green:#22D07A`, `--red:#F0454B`, `--orange:#FF9C42`, `--blue:#2E86C9`, `--gray:#6B7480`.
- **Texte** : `--text-primary:#E5EBEC`, `--text-secondary:#8A94A0`, `--text-muted:#6B7480`, `--text-dim:#6B7480` (alias silver conservés : `--silver-strong:#E5EBEC`, `--silver:#C6CDD6`, `--silver-soft:#8A94A0`).
- **Rayons** : `--radius-xl:20px` / `lg:18px` / `md:14px` / `sm:10px`.
- **Espacement** (échelle, à utiliser partout) : `--space-1:4px` … `--space-6:32px`.
- **Dimensions** : `--sidebar-width:240px`, `--header-height:74px`. **Transition** : `--transition:.15s cubic-bezier(.4,0,.2,1)`.
- **Polices** : `--font-main:'Satoshi','Inter',system-ui…` (Satoshi chargée via Fontshare : `https://api.fontshare.com/v2/css?f[]=satoshi@300,400,500,700,900`), `--font-mono:ui-monospace,'SFMono-Regular'…`.

### A.2 Fond & surfaces
- **Body** : fond **plat** `var(--bg-black)`. Plus de dégradés ni pseudo-éléments décoratifs (`body::before`/`::after` = `none`). `overflow:hidden` (sauf `.login-page` qui scrolle).
- **`.panel`** = brique visuelle de base : surface plate `var(--surface)`, bordure 1px `var(--border-subtle)`, `--radius-lg`, **sans** ombre ni liseré ni bordure interne (pseudo-éléments désactivés). Padding standard `20px`. Tout bloc de contenu est un `.panel`. Cartes imbriquées (metric-card, dev, ev, cam-btn…) = `var(--surface-2)`.

### A.3 Typographie
- **Titres** (`.page-title`, `.metric-value`, `.err-code`, `.auth-title`, `.protection-title`) : **couleur pleine** `var(--text-primary)`, `letter-spacing:-0.04em`. Tailles fluides en `clamp()`. (Plus de dégradé silver.)
- **Eyebrows / labels / pills / badges** : `0.68rem`, `font-weight:700`, `letter-spacing:.09em`, `text-transform:uppercase`. `.eyebrow` = cyan, `.eyebrow-muted` = `--text-muted`.
- **Wordmark** `AEGIS` (`.brand-name`, `.auth-wordmark`) : `font-weight:900`, `letter-spacing:.22em`, uppercase, `var(--text-primary)`.
- **Corps** : `--text-secondary` ; notes/méta : `--text-muted` ; libellés de champ : `--text-dim`.

### A.4 Assets & icônes (vrais fichiers, plus d'inline ad hoc)
- **`webapp/static/aegis-mark.svg`** — logo **bouclier** 128×128 avec dégradés (`shield-stroke` silver, `shield-fill`, `core-fill`, `eye-fill`, `cyan-glow`). Utilisé comme `<img class="brand-mark">` dans : header (`.logo-icon`), sidebar (`.sidebar-panel-icon`), emblème dashboard (`.core-mark`), login (`.auth-mark`), erreur (`.err-icon`).
- **`webapp/static/aegis-icons.svg`** — **sprite SVG** de `<symbol>` : `icon-menu, logout, login, dashboard, camera, journal, admin, antenna, router, siren, bell, door, window, dot, plug, detection`. Référencé via `<svg><use href="…/aegis-icons.svg#icon-NAME"></use></svg>`.
- **`webapp/static/favicon.svg`** — 64×64.
- **Tailles d'icône** : classes `.icon-xs:14` / `sm:18` / `md:22` / `lg:30`.
- **Côté Jinja** : macro `icon(name, classes, stroke)` dans `base.html`. **Côté JS** (dashboard) : `set KNOWN_ICONS` + fallback `dot` + `escapeHtml`.
- **Ajouter une icône** = 3 endroits : (1) nouveau `<symbol>` dans `aegis-icons.svg`, (2) entrée `KNOWN_ICONS` du JS dashboard si rendue dynamiquement, (3) champ `icon:` dans `webapp/devices.yaml`.

### A.5 Système de couleurs d'état (inchangé sémantiquement)
Classe `c-{green|red|orange|blue|gray}` posée sur la carte → définit la variable locale `--c`, consommée par : la **pastille** `.pill`, le **point** `.dot`/`.ev-dot`/`.event-preview-dot` (avec glow), et la **barre latérale** des cartes (`.dev::after`, `.sensor-card::after`, `.ev::after`). Côté caméras, ton via `data-tone="green|red|blue|orange|gray"`.
Mapping métier : **vert** = sécurisé / online / fermé-récent · **bleu** = fermé · **orange** = ouvert · **rouge** = hors ligne/alerte · **gris** = non installé/inconnu/en attente. (Calculé serveur-side dans `mqtt_state.py`, voir `docs/02`.)

### A.6 Layout & navigation
- **Header** fixe 74px (fond plat) : `logo-link` (bouclier + `brand-name` + `brand-tagline`), `header-meta` (**horloge live** JS, masquée < 992px), `user-badge#mqttBadge` (pulse-dot + état réseau MQTT, classes `.is-online`/`.is-offline`), bouton déconnexion.
- **Sidebar** 240px plate (`--sidebar-bg`, bordure `--shell-line`) : `sidebar-panel` (bouclier), `sidebar-nav-link` (icône + libellé ; état `.active` = fond `rgba(0,178,255,.10)` + bord cyan, liseré cyan `::before`), `sidebar-footer` (`system-card`). Liens conditionnés par `nav_tabs` + `is_admin`. Onglets : Tableau de bord · Activation alarme · Caméras · Journal · **Détection IA** (+ Administration si admin).
- **Responsive** : sidebar en **drawer** < 992px (burger `menuBtn` + overlay, gestion focus + touche Échap) **et** barre d'onglets fixe en bas `.mobile-tabbar` < 760px (`mobile-tab`).
- **Pages publiques** (login, erreur) : `main-layout-public` / `chat-area-public`, **sans** sidebar ni tabbar.

### A.7 Composants clés (réutiliser, ne pas réinventer)
- **Cartes device** : `.dev.asset-card` (infra, ~150px) et `.sensor-card` (capteurs, grille `minmax(220px,1fr)`) — barre latérale couleur, icône, label + room, `.pill` d'état, `.meta-chip` (LQI/batterie/W). Construites en JS (`assetCard()` / `sensorCard()` dans `dashboard.html`).
- **Dashboard** : `command-panel` (hero) → `protection-core` (`core-emblem` = 3 `core-orbit` + bouclier, + `protection-title`/`state-pill`) + `command-metrics` (4 `metric-card-compact`) ; bandeau `live-status` (`data-state=loading|ok|error`) ; `event-preview-panel` ; `shortcut-panel` (`shortcut-card`) ; puis `#groups` (ancres `#group-infrastructure`, `#group-capteurs`).
- **Pastilles** : `.pill`/`.badge` (`badge-admin/on/off/me`), `.state-pill` (`-safe/-warning/-alert/-neutral`), `.meta-chip`, `.section-count`, `.empty-badge` — toutes pilule arrondie 999px, uppercase.
- **Boutons** : `.btn-primary`/`.login-btn` (**fond clair plein `--text-primary`, texte foncé**), `.btn-mini` (+ survols teintés `.btn-ok/-warn/-danger`), `.btn-link`.
- **Formulaires** : `.fld`/`.form-group` (label uppercase dim, input ≥50px, focus = ring cyan), `.chk` (cases `accent-color:cyan`), `.tabchecks`.
- **Détection IA** (`detection.html`) : `.switch` (interrupteur cyan), `input[type=range]` stylé (piste + pouce cyan), `.obj-toggle` (case objet, `:checked` = teinte cyan), `.obj-bars`/`.day-bars` (statistiques). API `GET/POST /api/detection`.
- **États vides** : `.empty-state` (bordure pointillée). **Flash** : `.flash-ok`/`.flash-err`.
- **Caméras** : `.camera-layout` (2 col), `.cam-view` (texture rayée « no-signal » type `.stream` de la propo) + `.cam-overlay`, liste `.cam-btn` (`data-tone`), `.info-tile` méta.

### A.8 Accessibilité & motion (à préserver)
`:focus-visible` rings cyan globaux, `aria-current`/`aria-expanded`/`aria-busy`, `role=status|alert`, `.sr-only`, et bloc `@media (prefers-reduced-motion: reduce)` (coupe animations + pulse-dot). **Breakpoints** : 1280 / 1080 / 992 / 760 / 600.

### A.9 Règles pour les modifs futures
1. Toujours styliser via **tokens** (`var(--…)`) ; aucune couleur/rayon/espacement en dur.
2. Nouveau bloc visuel → l'envelopper dans `.panel` (surface plate) ; titres en couleur pleine, eyebrow au-dessus. **Pas de dégradé/glass** — rester sur la palette plate.
3. État coloré → poser une classe `c-{couleur}` (jamais recolorer pastille/point/barre à la main).
4. Icône → sprite `aegis-icons.svg` + macro/`KNOWN_ICONS` (cf. A.4).
5. Garder la cohérence responsive (drawer + mobile-tabbar) et l'accessibilité (A.8).
6. `style.css` est la **source unique** ; pas de CSS inline en dur dans les templates (sauf assets type `<img>`).

### A.10 Sécurité (modèle calsport, inchangé)
- **Auth** : sessions Flask signées (`app.secret_key` depuis vault, jamais en dur ; `RuntimeError` si absente). Décorateur `@login_required` (redirige `/login` si pas de `user_id` en session).
- **Mots de passe** : `werkzeug.security` scrypt (`auth.py` : `hash_password`/`check_password`). Zéro secret en dur.
- **Cookies** : `SESSION_COOKIE_HTTPONLY=True`, `SAMESITE="Lax"`, `SECURE` activé si `HTTPS=true`, `PERMANENT_SESSION_LIFETIME=24h`.
- **CSRF** : `flask_wtf.CSRFProtect` global ; `<meta name="csrf-token">` + champ caché `csrf_token()` dans les forms.
- **Rate limiting** : `flask_limiter` — `10/min` sur `/login`, `30-60/min` sur les API.
- **Rôles** : `is_admin` via colonne DB **ou** env `ADMIN_USERS` (usernames CSV).
- **Secrets** : chargés depuis un vault hors-repo (`/home/j.tremont/.secrets/vault.env`) + `.env` via `EnvironmentFile` systemd. `.env.example` documenté.

### A.11 Déploiement (modèle à reprendre)
- **systemd** (`config/calsport.service`) : `User=j.tremont`, venv, `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ReadWritePaths` limité, `Restart=on-failure`. Flask bind **127.0.0.1** uniquement.
- **Cloudflare Tunnel** (`config/cloudflared.yml`) : `cloudflared` → `http://127.0.0.1:<port>`, hostname dédié, catch-all 404. Pas de port ouvert sur la box.
- **Prod** : gunicorn + gevent listés dans les deps.

---

## Partie B — Stratégie AEGIS

### B.1 Différence clé vs calsport
Calsport = CRUD nutrition. AEGIS = **supervision temps réel d'état matériel** + **contrôle** (armer/désarmer) + **flux caméra**. Le cœur n'est pas une DB mais l'**état live des devices** (MQTT) et un **journal d'événements**.

### B.2 Pile retenue
- Flask + Jinja2 + flask-wtf (CSRF) + flask-limiter — **identique calsport** (cohérence, sécurité éprouvée).
- **paho-mqtt** : thread d'arrière-plan abonné à `zigbee2mqtt/#` → maintient un **registre d'état en mémoire**.
- **SQLite** (`aegis.db`) : users + **journal d'événements** (armement, désarmement, ouverture/fermeture, alertes) — persistant.
- Frontend : polling léger `GET /api/state` (toutes ~2-3 s) → rendu des pastilles. (SSE/WebSocket en option v2.)
- Déploiement : systemd + cloudflared, calqués sur calsport (hostname dédié type `alarme.tremontraimi.com`).

### B.3 Registre matériel (config déclarative `webapp/devices.yaml`)
Chaque équipement = type + source d'état + pièce. Codes couleur statut :
- **Équipements** (antenne/coordinateur, routeurs, caméras, sonnette, sirène/alarme) : **vert = ON/online**, **rouge = OFF/offline**.
- **Capteurs d'ouverture** : **bleu = fermé**, **orange = ouvert**, **rouge = offline/HS**.

Sources d'état :
- `zigbee` : via MQTT (coordinateur, 2 routeurs, 8 capteurs, future sirène TS0601) → live, déjà disponible.
- `camera` / `doorbell` / `siren` : **placeholders** tant que le matériel n'est pas installé (état `unknown`/gris), branchés plus tard.

### B.4 Pages (MVP → cible)
| Route | Rôle | État data |
|---|---|---|
| `/login` | Connexion (design calsport, icône bouclier) | — |
| `/` Dashboard | Tuiles **Matériel** : coordinateur/antenne, routeurs, caméras, sonnette, sirène (vert/rouge) + grille **capteurs** (bleu/orange/rouge) | **live Zigbee** + placeholders |
| `/cameras` | Flux caméras Tapo en direct + sélecteur de caméra | placeholder (caméras coupées via P110) |
| `/journal` | Journal : armé/désarmé, ouvertures, alertes (flux temps réel + historique) | SQLite + live |
| `/controle` | Armer / désarmer (bouton unique) | écrit sur MQTT `aegis/alarm/set` vers l'orchestrateur |
| `/detection` | **Détection IA** : objets surveillés, seuil de confiance, sensibilité mouvement, statut modèle YOLOv8, stats (dérivées des captures) | SQLite (réglages) + MQTT `aegis/detection/config` (retenu) vers l'orchestrateur ; stats depuis `captures/` |

### B.5 Intégration avec le reste du projet
- AEGIS **lit** l'état via MQTT (déjà branché sur Mosquitto, network host).
- L'**orchestrateur Python** (à venir, `docs/05-architecture-mqtt.md`) publiera l'état armé/désarmé et les alertes sur MQTT ; AEGIS s'y abonne pour le journal et le dashboard, et publiera les commandes armer/désarmer (page `/controle`).
- Caméras : intégration ultérieure avec le script YOLO/Tapo existant (flux + bascule présence via P110).

### B.6 Sécurité spécifique AEGIS
- App de **sécurité domestique** → exposition Cloudflare avec **Access** (auth Cloudflare en plus du login Flask) recommandée. À minima : login Flask + rate-limit + HTTPS tunnel.
- Aucune commande d'armement sans session authentifiée + CSRF.
- Secrets MQTT/API hors-repo (vault), comme calsport.

> Détail des outils/versions ajoutés : voir `docs/08-stack-technique.md`.

> Guide concret d'evolution UI : voir `docs/09-guide-integration-ui.md`.
