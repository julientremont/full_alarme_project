"""
setup_gdrive_auth.py — Autorisation Google Drive pour AEGIS (à faire UNE fois).

Le Pi est headless : on ouvre l'URL d'autorisation dans TON navigateur via un
tunnel SSH, et Google renvoie le code sur le port local du Pi.

  1) Sur ton PC, connecte-toi au Pi avec un tunnel :
        ssh -L 8765:localhost:8765 j.tremont@<ip-du-pi>
  2) Sur le Pi :
        cd ~/Documents/Projets/full_alarme_project/orchestrator
        uv run python setup_gdrive_auth.py
  3) Copie l'URL affichée dans le navigateur de TON PC, autorise avec le compte
     Google qui possède le dossier Drive cible.
  4) Terminé : le token est écrit et se rafraîchit ensuite tout seul.

Le compte Google autorisé doit avoir accès en écriture au dossier
PATH_DRIVE_ENTREE_TAPO_CAPTURES.
"""
import os

from dotenv import load_dotenv

for vault in ("/home/j.tremont/.secrets/vault.env",
              os.path.join(os.path.dirname(__file__), ".env")):
    if os.path.exists(vault):
        load_dotenv(vault)

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CLIENT = os.getenv("GOOGLE_CREDENTIALS_PATH")
TOKEN = os.getenv("GDRIVE_TOKEN_PATH", "/home/j.tremont/.secrets/gdrive_token.json")
PORT = int(os.getenv("GDRIVE_AUTH_PORT", "8765"))

if not CLIENT or not os.path.exists(CLIENT):
    raise SystemExit(f"GOOGLE_CREDENTIALS_PATH introuvable : {CLIENT!r}")

flow = InstalledAppFlow.from_client_secrets_file(CLIENT, SCOPES)
creds = flow.run_local_server(host="localhost", port=PORT, open_browser=False,
                              authorization_prompt_message="Ouvre cette URL dans ton navigateur :\n{url}")

os.makedirs(os.path.dirname(TOKEN), exist_ok=True)
with open(TOKEN, "w") as f:
    f.write(creds.to_json())
os.chmod(TOKEN, 0o600)
print(f"\n✅ Token écrit : {TOKEN}\nRedémarre l'orchestrateur : sudo systemctl restart aegis-orchestrator")
