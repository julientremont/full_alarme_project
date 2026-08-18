# 02 — Capteurs Aqara + routeurs (mapping)

Appairage réalisé le 2026-06-19. Réseau Zigbee channel 15, PAN ID 40972.

## Routeurs Sonoff S60ZBTPF (prises secteur, rôle Router)

| Nom Z2M | Emplacement | IEEE | Notes |
|---|---|---|---|
| `routeur_chambres` | Placard central, côté chambres | `0xa4c1380df670ffff` | Identifié via extinction LED réseau |
| `routeur_salon` | Placard central, côté salon/cuisine | `0xa4c1380d77b9ffff` | |

> Astuce identification S60 : `{"network_indicator": false}` éteint la LED bleue → repérage physique. Toggle relais (`{"state":"TOGGLE"}`) fait un clic audible si besoin.
> ⚠️ OTA dispo : firmware installé `4098`, dernier `8194`. Non appliqué (pas nécessaire, risque). À voir plus tard via frontend.

## Capteurs d'ouverture Aqara MCCGQ11LM (porte/fenêtre, EndDevice)

`contact: true` = fermé, `contact: false` = ouvert. Batterie 100% à l'appairage.

| Nom Z2M | Emplacement physique | IEEE | Route mesh (au scan) | LQI |
|---|---|---|---|---|
| `porte_entree` | Porte palière (entrée) | `0x00158d008c8bf0e4` | routeur_chambres | 128 |
| `fenetre_chambre_parents` | Fenêtre chambre parents | `0x00158d008c8bfa02` | routeur_chambres | 144 |
| `fenetre_chambre_noah` | Fenêtre chambre Noah | `0x00158d008c8bf350` | routeur_chambres | 172 |
| `fenetre_chambre_mia` | Fenêtre chambre Mia | `0x00158d008c8bf0ba` | **coordinateur (direct)** | 201 |
| `fenetre_cuisine` | Fenêtre cuisine | `0x00158d008c8bf3fb` | routeur_salon | 183 |
| `porte_fenetre_salon_gauche` | Porte-fenêtre salon, gauche | `0x00158d008c8bf36f` | routeur_salon | 174 |
| `porte_fenetre_salon_milieu` | Porte-fenêtre salon, milieu | `0x00158d008c8bf465` | routeur_salon | 185 |
| `porte_fenetre_salon_droite` | Porte-fenêtre salon, droite | `0x00158d008c8bf320` | routeur_salon | 165 |

> Méthode d'identification gauche/milieu/droite (capteurs identiques) : ouvrir/fermer une porte-fenêtre à la fois et lire quel IEEE publie `contact` (topic `zigbee2mqtt/<ieee>`).

## Topologie mesh (scan 2026-06-19)

- 7/8 capteurs passent par un routeur (mesh OK), LQI 128–185.
- `fenetre_chambre_mia` en direct coordinateur mais LQI 201 (excellent) → OK, pas un signal faible.
- Routeurs : `routeur_chambres`→coord LQI 165, `routeur_salon`→coord LQI 123, liaison inter-routeurs ~103-106. Redondance présente.

### Re-scanner la topologie

```bash
docker exec mosquitto mosquitto_pub -h localhost \
  -t 'zigbee2mqtt/bridge/request/networkmap' -m '{"type":"raw","routes":true}'
# réponse retained sur: zigbee2mqtt/bridge/response/networkmap
```

## État réseau
- `permit_join` **fermé** après appairage (sécurité). Pour rajouter un device :
  `docker exec mosquitto mosquitto_pub -h localhost -t 'zigbee2mqtt/bridge/request/permit_join' -m '{"time":254}'`
