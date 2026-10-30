# fanuc-vision-pc

Cellule vision + robot FANUC : le PC reçoit une image, en extrait des points et
des trajectoires, les convertit en trames ASCII et les envoie au contrôleur
R-30iB Mate (LR Mate 200iD/4S) par Socket Messaging KAREL.

## Architecture

| Équipement | Rôle |
|---|---|
| PC vision | dépôt de l'image, traitement, extraction des trajectoires, envoi TCP, page web |
| R-30iB Mate | reçoit les points en ASCII (KAREL `recv_path.kl`), les écrit dans les PR[10..n] |
| S7-1500 | lance le cycle (UOP/PNS sur PROFINET) et **autorise ou refuse l'envoi** des corrections (bit DB100.DBX0.0) |
| Sony XC-56 | photo du résultat pour l'étape de vérification (analogique → frame grabber du PC) |

## Pipeline en 4 étapes

1. `pipeline/step1_bw.py` — noir & blanc : niveaux de gris, flou gaussien, seuil d'Otsu
2. `pipeline/step2_contours.py` — points et trajectoires : `cv2.findContours` sur les formes, `approxPolyDP`, conversion px → mm, trajectoires fermées
3. `pipeline/step3_ascii.py` — trames ASCII pour le R-30iB Mate : ligne 1 = nombre de points, puis n lignes `X Y Z W P R` (CRLF) ; les trajectoires sont envoyées les unes après les autres
4. `pipeline/step4_verify.py` — photo de la caméra XC-56, comparaison avec l'image traitée ; si le taux d'erreur ≥ 10 %, les points/trajectoires sont recalculés **et envoyés au robot seulement si la S7-1500 l'autorise** (`pipeline/plc.py`, snap7)

## Installation

```bash
pip install -r requirements.txt
```

requirements.txt : `opencv-python`, `numpy`, `python-snap7`.

## Démarrage

```bash
ROBOT_IP=192.168.1.10 PLC_IP=192.168.1.1 python app.py
```

Puis ouvrir `http://localhost:8000/` dans un navigateur.

La page web permet de :

- déposer une image (PNG/JPG) ;
- la traiter en noir et blanc ;
- extraire les points et trajectoires des formes ;
- les envoyer au robot (bouton désactivé si le PLC refuse) ;
- lancer la vérification caméra avec le verdict d'erreur.

## Configuration (variables d'environnement)

| Variable | Défaut | Description |
|---|---|---|
| `ROBOT_IP` | 192.168.1.10 | adresse IP du R-30iB Mate |
| `ROBOT_PORT` | 59002 | port du tag SM (C2 client) |
| `WEB_PORT` | 8000 | port du serveur web |
| `SCALE_MM_PER_PX` | 0.2 | étalonnage px → mm (à affiner !) |
| `Z_MM`, `W_DEG`, `P_DEG`, `R_DEG` | 50, 180, 0, 0 | hauteur/orientation imposées aux points |
| `MIN_AREA_PX` | 80 | aire minimale d'une forme |
| `CAM_INDEX` | 0 | index du périphérique vidéo (frame grabber de la XC-56) |
| `PLC_IP` | 192.168.1.1 | adresse de la S7-1500 |
| `PLC_RACK`, `PLC_SLOT` | 0, 1 | rack et slot du CPU |
| `PLC_DB`, `PLC_BYTE`, `PLC_BIT` | 100, 0, 0 | bit d'autorisation d'envoi |
| `ERROR_THRESHOLD_PCT` | 10.0 | seuil de correction de l'étape 4 |
| `DEMO` | 1 | sans snap7/sans robot, les appels sont simulés |

## S7-1500

Activer "Permettre l'accès distant (PUT/GET)" dans les propriétés du CPU
(TIA Portal) pour que `python-snap7` puisse lire le bit d'autorisation.
Côté PLC, ce bit peut piloter le démarrage d'un cycle de reprise via les UOP
(PNS/RSR) du robot.

## KAREL (robot)

`karel/recv_path.kl` reçoit les trames TCP (port 59002, tag C2) et écrit
chaque point dans les Position Registers `PR[10]` à `PR[10+n-1]`.
Compiler `recv_path.pc` via Robot Studio puis l'appeler depuis un programme TP
(voir `recv_path.kl` pour un exemple `CALL` + boucle `L PR[i]`).
Le robot écoute sur le port 59002, une connexion à la fois, un robot à la fois.

## Page GitHub

Pour publier la page web en statique :

1. Settings → Pages
2. Source : main, dossier `/docs`
3. URL : `https://schadow126.github.io/fanuc-vision-pc/`

La page publiée fonctionne alors en mode démo (sans serveur local, sans robot).

## Sécurité

- Serveur web en réseau local uniquement.
- Premiers essais : vitesse robot réduite, main sur l'arrêt d'urgence.
- Les points sont exprimés dans l'UFRAME du programme TP : enseigner l'étalonnage
  caméra dans le même repère que celui utilisé par le TP (`UFRAME_NUM`).
