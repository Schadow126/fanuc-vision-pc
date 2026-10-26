@TB@markdown
# FANUC Vision PC — Envoi de points PC → Robot par Socket Messaging

Mini application **Python** (sans dépendance) + **page web** pour envoyer des points `X Y Z W P R` à un robot **FANUC LR Mate 200iD/4S** (contrôleur **R-30iB Mate**) via l'option **Socket Messaging KAREL**.

## Architecture

`mermaid
flowchart LR
    NAV[Navigateur] -- HTTP :8080 --> PC[PC vision - app.py]
    PC -- TCP :59002 --> ROB[R-30iB Mate - KAREL recv_point.kl - PR]
    PLC[S7-1500] -- PROFINET UOP/PNS --> ROB
    CAM[Sony XC-56] -- frame grabber --> PC
`

## Contenu du dépôt

- `app.py` — serveur web + client TCP vers le contrôleur (bibliothèque standard uniquement)
- `static/index.html` — page de contrôle (fonctionne aussi en mode démo sans backend)
- `karel/recv_point.kl` — programme KAREL de réception (à traduire et charger dans le robot)
- `docs/index.html` — copie de la page pour hébergement **GitHub Pages**

## Démarrage rapide

`bash
git clone https://github.com/Schadow126/fanuc-vision-pc.git
cd fanuc-vision-pc
ROBOT_IP=192.168.1.10 python app.py
`

Puis ouvrir **http://localhost:8080** dans un navigateur du PC.

Variables d'environnement : `ROBOT_IP`, `ROBOT_PORT` (59002 par défaut), `WEB_PORT` (8080), `DEMO=1` (démo sans robot).

## Côté robot (R-30iB Mate)

1. Option **Socket Messaging** + **KAREL** installées.
2. Configurer le tag **C2** : MENU → SETUP → Host Comm → Clients → protocole **SM**,
   IP du PC, et `$HOSTC_CFG[2].$SERVER_PORT = 59002`.
3. Charger et traduire `recv_point.kl` (KAREL translator), puis appeler `CALL RECV_POINT`
   depuis le programme TP avant `L PR[10]`.
4. Le point est exprimé dans l'**UFRAME/UTOOL** du programme TP — étalonnez la caméra
   (pixels → mm) dans ce même repère.

## API HTTP

| Méthode | Route      | Corps / réponse                                  |
|---------|------------|--------------------------------------------------|
| GET     | /api/config| `{robot_ip, robot_port, web_port, demo}`   |
| POST    | /api/ping  | Test TCP → `{ok, latency_ms}`              |
| POST    | /api/send  | `{x,y,z,w,p,r}` → `{ok, reply}`      |

Exemple :
`bash
curl -X POST http://localhost:8080/api/send -H 'Content-Type: application/json' -d '{"x":150, "y":-80, "z":50, "w":180, "p":0, "r":90}'
`

## GitHub Pages (mode démo)

La page `docs/index.html` fonctionne **sans backend** (mode démo) : elle simule l'envoi.
Pour l'héberger : **Settings → Pages → Deploy from a branch → main → /docs**.
Depuis la page hébergée, saisir l'URL du PC (ex. `http://IP_PC:8080`) pour piloter le robot en réel (CORS activé dans app.py).

## Sécurité

⚠️ Application de mise au point : ne pas exposer le port 8080 hors du réseau local de la cellule.
Le S7-1500 reste responsable de la sécurité (arrêts d'urgence filaires) et du lancement de cycle (UOP/PNS via PROFINET).

## Licence

Code fourni à titre d'exemple pédagogique, sans garantie. KAREL, FANUC et LR Mate sont des marques de FANUC.