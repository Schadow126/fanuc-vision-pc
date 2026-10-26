# fanuc-vision-pc

Cellule vision + robot FANUC : le PC traite l'image, génère les points et
trajectoires, les convertit en trames ASCII pour le contrôleur
**R-30iB Mate** (LR Mate 200iD/4S), et vérifie le résultat avec la caméra
**Sony XC-56**. L'automate **Siemens S7-1500** (PROFINET) lance le cycle et
**autorise ou refuse chaque envoi** vers le robot.

## Architecture

    [S7-1500] --PROFINET (UOP/PNS)--> [R-30iB Mate]   lancement du cycle + autorisation d'envoi
    [Image déposée sur la page web]
        |
        v
    CODE 1  step1_process.py   image -> noir et blanc (seuillage Otsu)
        |
        v
    CODE 2  step2_points.py    N&B -> contours -> points (mm) + trajectoires
        |
        v
    CODE 3  step3_ascii.py    points -> trames "X Y Z W P R\r" -> socket TCP -> KAREL
        |
        v
    [Robot trace]  ...  CODE 4  step4_verify.py
        photo XC-56 -> comparaison avec l'image N&B -> taux d'erreur
        si erreur >= 10 % : points corrigés (dx, dy) -> renvoyés au CODE 3
        uniquement si le S7-1500 autorise l'envoi.

## Les 4 codes

| Code | Fichier | Rôle |
|------|---------|------|
| 1 | `pipeline/step1_process.py` | image déposée -> noir et blanc |
| 2 | `pipeline/step2_points.py`  | image N&B -> points et trajectoires (mm) |
| 3 | `pipeline/step3_ascii.py`  | points -> trames ASCII -> R-30iB Mate |
| 4 | `pipeline/step4_verify.py` | photo XC-56 -> comparaison -> correction si erreur >= 10 % |

Côté robot : `karel/recv_point.kl` (KAREL, Socket Messaging) reçoit une trame
par connexion, écrit le point dans un registre de position (PR) et répond ACK.

## Installation

    pip install -r requirements.txt      # opencv-python, numpy
    python app.py

Ouvrir http://localhost:8080. Déposez une image : le pipeline se pilote
depuis la page (générer, envoyer, vérifier).

## Variables d'environnement

| Variable | Défaut | Rôle |
|----------|--------|------|
| `ROBOT_IP` | 192.168.1.10 | IP du R-30iB Mate |
| `ROBOT_PORT` | 59002 | port socket KAREL (tag C2) |
| `CAMERA_INDEX` | 0 | index OpenCV de la XC-56 / frame grabber |
| `SCALE_MM_PER_PX` | 0.1 | étalonnage caméra (mm par pixel) |
| `ERROR_LIMIT_PCT` | 10 | seuil de correction du code 4 |
| `PLC_MODE` | demo | autorisation S7-1500 : demo / file / socket |
| `WEB_PORT` | 8080 | port du serveur web |

## Autorisation S7-1500 (`plc.py`)

- `PLC_MODE=demo` : autorise tout (sans automate, pour les essais).
- `PLC_MODE=file` : autorisé si le fichier `plc_authorize.txt` contient `1`.
- `PLC_MODE=socket` : lecture d'un mot d'autorisation sur l'automate
  (GETJOB / lecture DB). Le code 3 et le renvoi du code 4 sont bloqués
  tant que l'autorisation est absente.

## Routes HTTP

| Route | Rôle |
|-------|------|
| GET `/` | page web (dépôt d'image + pipeline) |
| GET `/api/config` | configuration (JSON) |
| GET `/api/plc` | état d'autorisation du S7-1500 |
| GET `/files/<f>` | images de travail (bw.png, traj.png, camera.png) |
| POST `/api/process` | CODE 1 : upload -> noir et blanc |
| POST `/api/generate` | CODE 2 : points et trajectoires |
| POST `/api/send` | CODE 3 : trames ASCII -> robot (bloqué si PLC refuse) |
| POST `/api/verify` | CODE 4 : photo XC-56, comparaison, correction |

## Mode démo

La page fonctionne aussi sans backend (GitHub Pages) : le traitement noir et
blanc est alors fait dans le navigateur (canvas) et les résultats sont
simulés. Pour le vrai pipeline, lancer `python app.py` sur le PC vision.

## Sécurité

- Réseau local isolé uniquement ; le serveur n'a pas d'authentification.
- Premiers mouvements en vitesse réduite, sans outil, zone dégagée.
- Vérifier UFRAME/UTOOL et la configuration du PR avant tout envoi.
- L'étalonnage (`SCALE_MM_PER_PX`) doit correspondre au repère utilisateur.
