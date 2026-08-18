# AEGIS — Documentation du projet

AEGIS est l'interface de supervision d'une alarme maison DIY basee sur Zigbee, MQTT, Flask et SQLite.

Cette documentation regroupe :

- l'installation de l'infrastructure Zigbee,
- la mise en service des capteurs,
- la strategie design de l'application web,
- la stack technique retenue,
- le guide d'integration UI du frontend.

## Parcours recommande

1. Lire `01-zigbee-setup.md` pour l'infrastructure.
2. Lire `02-capteurs-aqara.md` pour les capteurs d'ouverture.
3. Lire `07-design-interface.md` pour la vision produit AEGIS.
4. Lire `08-stack-technique.md` pour la pile technique.
5. Lire `09-guide-integration-ui.md` avant toute evolution visuelle de `webapp/`.
6. Lire `14-messagerie.md` pour les alertes (service `aegis-notifier`).

## Perimetre de l'application web

Le frontend AEGIS est dans `webapp/` et repose sur :

- Flask + Jinja2,
- CSS pur,
- polling HTTP pour les etats live,
- assets SVG dedies pour la marque et les icones.

Le principe de travail a conserver est simple :

- ne pas casser l'existant,
- isoler la couche design de la logique metier,
- garder une experience propre sur desktop et mobile.
