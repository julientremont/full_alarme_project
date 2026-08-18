# 09 — Guide d'integration UI AEGIS

Guide de reference pour faire evoluer la couche visuelle de `webapp/` sans toucher a la logique metier.

## Perimetre

Ce guide couvre uniquement :

- le shell visuel,
- les tokens CSS,
- les assets de marque,
- les icones partagees,
- les conventions de composants,
- les retours d'etat et d'accessibilite.

Ne pas utiliser ce document pour changer les routes, les permissions, le polling, les APIs Flask ou la logique MQTT.

## Fichiers de reference

Les points d'entree principaux sont :

- `webapp/templates/base.html` : shell global, navigation, macros `shield()` et `icon()`.
- `webapp/templates/login.html` : ecran public de connexion.
- `webapp/templates/dashboard.html` : supervision live du materiel.
- `webapp/templates/cameras.html` : ecran pret pour l'integration video.
- `webapp/templates/journal.html` : historique live des evenements.
- `webapp/templates/admin.html` : gestion des comptes.
- `webapp/static/style.css` : design system et composants.
- `webapp/static/aegis-mark.svg` : symbole principal AEGIS.
- `webapp/static/favicon.svg` : favicon SVG.
- `webapp/static/aegis-icons.svg` : sprite d'icones partage.

## Identite visuelle

### Direction retenue

- univers sombre anthracite,
- surfaces premium legerement metalliques,
- cyan technique pour l'accent,
- vert reserve aux etats sains / securises,
- argent clair pour les assets de marque,
- typographie `Inter`.

### Tokens CSS principaux

Les variables sont definies dans `webapp/static/style.css`.

| Token | Usage |
|---|---|
| `--bg-black` / `--bg-deep` | fonds principaux |
| `--bg-panel` / `--bg-panel-soft` | surfaces et cartes |
| `--accent-cyan` | accent principal, focus, etat actif |
| `--green` / `--red` / `--orange` / `--blue` / `--gray` | statuts metier |
| `--text-primary` / `--text-secondary` / `--text-muted` | hierarchie typographique |
| `--radius-xl` a `--radius-sm` | arrondis |
| `--transition` | animation courte standard |
| `--sidebar-width` / `--header-height` | structure globale |

Regle : toute nouvelle couleur ou rayon doit d'abord etre declare comme token avant d'etre utilise directement.

## Assets de marque

### Symbole principal

- fichier : `webapp/static/aegis-mark.svg`
- usage : header, login, hero dashboard, erreur, sidebar card
- principe : ne pas dupliquer le logo en inline dans les templates

### Favicon

- fichier : `webapp/static/favicon.svg`
- branche dans `base.html` et `login.html`

### Icnes systeme

- fichier : `webapp/static/aegis-icons.svg`
- toutes les icones UI doivent venir de ce sprite
- ne pas reintroduire de SVG inline dupliques dans les templates

## Utilisation des icones

### Cote Jinja

Dans `base.html`, la macro `icon()` permet d'inserer une icone partagee :

```jinja
{{ icon('camera', 'icon icon-sm', '2') }}
```

Parametres :

- nom de l'icone,
- classes CSS,
- epaisseur de trait.

### Cote JavaScript

Pour les cartes injectees en JS, reutiliser `icons_sprite` au lieu de reconstruire des `<path>` inline.

Exemple :

```js
const ICON_SPRITE = {{ icons_sprite|tojson }};
return `<svg class="icon icon-md" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><use href="${ICON_SPRITE}#icon-camera"></use></svg>`;
```

## Structure de page

Le pattern par defaut est :

1. `page`
2. `hero` ou `hero hero-single`
3. `summary-grid` si un ecran a des indicateurs rapides
4. `panel section-panel` pour les blocs fonctionnels
5. `extra_scripts` pour le JavaScript specifique a la page

Composants structurants :

- `panel` : conteneur principal reutilisable
- `hero-copy` / `hero-brand` : bloc d'introduction
- `metric-card` : indicateur chiffre
- `section-head` : titre + meta d'une section
- `live-status` : retour de synchronisation ou d'etat live

## Conventions de composants

### Dashboard / materiel

- `dev` : carte d'equipement
- `dev-ic` : icone du device
- `pill` : statut principal
- `meta-chip` : telemetrie secondaire

### Journal

- `ev` : entree de timeline
- `ev-tag` : type d'evenement
- `ev-meta` : horodatage + detail

### Administration

- `create-form` : creation de compte
- `user-card` : carte d'utilisateur
- `btn-primary` : action principale
- `btn-mini` : actions secondaires ou de maintenance

### Cameras

- `cam-stage-card` : zone de visualisation
- `cam-btn` : selecteur d'une camera
- `cam-meta-grid` : informations d'integration

## Live et synchronisation

Les ecrans live doivent conserver ces regles :

- afficher un statut discret de synchronisation,
- utiliser `role="status"` et `aria-live="polite"`,
- utiliser `aria-busy="true|false"` pendant les fetch,
- conserver le dernier rendu utile en cas d'erreur reseau,
- garder des messages courts : chargement, a jour, erreur reseau.

## Accessibilite

Les points non negociables deja en place :

- focus clavier visible via `:focus-visible`,
- `role="alert"` pour les erreurs et flash messages,
- `aria-current="page"` sur la navigation active,
- `aria-expanded` et fermeture `Escape` pour la sidebar mobile,
- `aria-pressed` pour les selecteurs a etat,
- `prefers-reduced-motion: reduce` respecte dans `style.css`,
- labels explicites pour les champs de formulaire.

Toute nouvelle interaction doit rester utilisable sans souris.

## Regles d'evolution

Faire :

- reutiliser les tokens existants,
- etendre le sprite d'icones au lieu de coller des SVG inline,
- privilegier les petits changements localises,
- garder le rendu desktop et mobile coherent,
- placer le JS specifique dans `extra_scripts`.

Eviter :

- ajouter un framework JS pour une simple evolution visuelle,
- dupliquer le meme composant avec un autre nom,
- ajouter des couleurs d'etat concurrentes,
- coupler la presentation a la logique metier.

## Check-list avant merge UI

- les templates se rendent sans erreur,
- les assets `aegis-mark.svg`, `favicon.svg` et `aegis-icons.svg` restent servis,
- la navigation mobile fonctionne au clavier,
- les etats live gardent un feedback lisible,
- le comportement metier n'est pas modifie,
- le rendu reste stable en dessous de `992px` et `600px`.

## Liens utiles

- Strategie design : `07-design-interface.md`
- Stack technique : `08-stack-technique.md`
- Application concernee : `webapp/`
