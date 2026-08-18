# Full Alarme Project

Projet d'alarme maison DIY base sur Zigbee, MQTT et une interface web Flask nommee **AEGIS**.

Le depot contient deux axes principaux :

- `docs/` : la documentation technique du projet, publiee avec MkDocs Material.
- `webapp/` : l'application web AEGIS pour superviser les equipements, les capteurs et le journal.

## Demarrage rapide

### Outils du depot racine

Le workflow racine utilise `uv`.

```bash
make setup
make install_precommit
make run_tests
make build_docs
make serve_docs_locally
```

Commandes equivalentes sans `make` :

```bash
uv sync --extra dev
uv run pytest tests/
uv run --extra dev mkdocs build
uv run --extra dev mkdocs serve --livereload -a localhost:8001
```

La documentation locale est servie sur `http://localhost:8001`.

Pour publier sur `gh-pages`, utiliser `make deploy_docs` avec un remote Git configure et des identifiants valides.

### Webapp AEGIS

```bash
cd webapp
uv sync
cp .env.example .env
uv run python create_user.py julien --admin
uv run flask --app app run --host 127.0.0.1 --port 5002
```

L'application est ensuite accessible sur `http://127.0.0.1:5002`.

## Structure utile

```text
docs/                 Documentation MkDocs du projet
webapp/               Interface web AEGIS (Flask, Jinja2, SQLite, MQTT)
src/                  Code Python du depot racine
tests/                Tests Python du depot racine
config/               Configurations complementaires
notebooks/            Explorations et notes techniques
mkdocs.yaml           Configuration MkDocs
Makefile              Commandes de travail via uv
```

## Documentation disponible

- `docs/01-zigbee-setup.md` : installation de l'infrastructure Zigbee.
- `docs/02-capteurs-aqara.md` : mise en service des capteurs d'ouverture.
- `docs/07-design-interface.md` : vision produit et strategie UI d'AEGIS.
- `docs/08-stack-technique.md` : pile technique retenue.
- `docs/09-guide-integration-ui.md` : conventions d'integration frontend pour `webapp/`.

## AEGIS en bref

- Stack : Flask, Jinja2, SQLite, `paho-mqtt`, CSS pur.
- Etat live : polling HTTP sur `/api/state`, alimente par un thread MQTT.
- Pages MVP : tableau de bord, cameras, journal, administration.
- Deploiement cible : `systemd` + Cloudflare Tunnel.

Voir aussi `webapp/README.md` pour les details d'installation et d'exploitation de l'application.
