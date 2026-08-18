# 01 — Setup Zigbee (Zigbee2MQTT + coordinateur)

## Coordinateur Zigbee

| Élément | Valeur |
|---|---|
| Dongle actuel | Zigbee 3.0 USB générique, puce **EFR32MG21** + antenne externe SMA (équivalent ZBDongle-E) |
| Pont USB-série | **CH340** (`idVendor 1a86`, `idProduct 7523`) — *pas* un CP210x |
| Port série | `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` → `/dev/ttyUSB0` |
| Adapter Z2M | `ember` |
| Firmware | EmberZNet **7.5.0 [GA]**, EZSP v13, type 170 |
| Port USB physique | port **bleu USB 3.0** du Pi (stable) — éviter le port noir USB 2.0 |

> ⚠️ Le `SerialNumber` du CH340 est vide → le nom by-id est générique. Reste unique tant qu'aucun autre périphérique 1a86 n'est branché. Si on rebranche un autre device 1a86, vérifier `ls /dev/serial/by-id/`.

### Historique dongle
- **Ancien** : Sonoff ZBDongle-P (puce **TI CC2652P** + CP2102N) → confirmé **mort/DOA** (muet sur EZSP/bootloader/SPINEL/CPC à tous baudrates, testé `universal-silabs-flasher` + resets RTS/DTR + power-cycle sur 2 ports USB). Détecté au niveau USB mais puce muette. Retour Amazon.
- **Remplacement** : EFR32MG21 ci-dessus. Changement de chipset → adapter passé de `zstack` à **`ember`**.

## Réseau Zigbee formé

| Param | Valeur |
|---|---|
| Channel | **15** (évite WiFi 2.4 GHz Freebox) |
| PAN ID | 40972 |
| Ext PAN ID | `9b 4d a8 9e 73 26 8f c6` |
| Network key | fixée dans `configuration.yaml` (secret) |
| Backup | `/app/data/coordinator_backup.json` |

## Config Zigbee2MQTT

- Image Docker : `ghcr.io/koenkk/zigbee2mqtt:latest` (v2.12.0, zigbee-herdsman 10.4.0)
- Données host : `~/zigbee2mqtt-data/` → `/app/data` dans le conteneur
- Frontend : **port 8081** (8080 déjà pris par un process `node` sur ce Pi)
- MQTT : `mqtt://localhost:1883` (Mosquitto en Docker, network host)
- ⚠️ `onboarding: false` **obligatoire** (sinon serveur d'onboarding codé en dur sur 8080 → crash EADDRINUSE)
- `rtscts: false` (CH340 sans flow control matériel → ASH bascule en software flow control, normal)

### Commande de lancement du conteneur

```bash
PORT=/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0
docker run -d \
  --name zigbee2mqtt \
  --network host \
  --restart unless-stopped \
  -v ~/zigbee2mqtt-data:/app/data \
  -v /run/udev:/run/udev:ro \
  --device=$PORT:$PORT \
  -e TZ=Europe/Paris \
  ghcr.io/koenkk/zigbee2mqtt:latest
```

> Le `--device` est figé à la création du conteneur. Si le dongle change de port by-id, **supprimer et recréer** le conteneur (`docker rm`), un simple `docker start` ne suffit pas.

## État appairage
- **11 devices appairés** (1 coordinateur + 2 routeurs Sonoff + 8 capteurs Aqara) — voir `02-capteurs-aqara.md` pour le mapping.
- `permit_join` **fermé** après appairage (sécurité).
- ⚠️ **Z2M 2.x** : `permit_join: true` dans `configuration.yaml` n'ouvre **PAS** réellement le réseau. Il faut l'ouvrir via MQTT :
  ```bash
  docker exec mosquitto mosquitto_pub -h localhost \
    -t 'zigbee2mqtt/bridge/request/permit_join' -m '{"time":254}'   # 0 pour fermer
  ```
  Fenêtre max 254 s par requête (limite spec Zigbee) — relancer si besoin.

## Vérifs utiles

```bash
ls /dev/serial/by-id/                 # nom du port
docker logs -f zigbee2mqtt            # logs live
docker logs zigbee2mqtt | grep -i interview   # suivi appairage
```
