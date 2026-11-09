# fanuc-vision-pc

**Cellule de création de dessin** : le PC reçoit une image, en extrait les
formes, et le robot FANUC (stylo dans la pince) **les dessines**. Les points
partent vers le contrôleur R-30iB Mate (LR Mate 200iD/4S) par Socket Messaging
KAREL ; une caméra vérifie le dessin obtenu.

## Architecture

| Équipement | Rôle |
|---|---|
| PC vision | dépôt de l'image, traitement, extraction des formes, envoi TCP, page web |
| R-30iB Mate | reçoit les points du dessin en ASCII (KAREL `recv_path.kl`), les écrit en continu dans les PR[10..n] |
| S7-1500 | lance le cycle (UOP/PNS sur PROFINET) et **autorise ou refuse l'envoi** des corrections (bit DB100.DBX0.0) |
| Sony XC-56 | photo du dessin réalisé pour l'étape de vérification (analogique → frame grabber du PC) |

## Pipeline en 4 étapes

1. `pipeline/step1_bw.py` — noir & blanc : niveaux de gris, flou gaussien, seuil d'Otsu
2. `pipeline/step2_contours.py` — formes : `cv2.findContours` (formes claires ou sombres, détection automatique), reconnaissance des primitives — **angulaire** (lignes reliées par des angles), **ligne**, **arc**, **cercle** —, conversion px → mm, trajectoires fermées, et **remplissage de l'intérieur** des formes par **contours concentriques** (`FILL_SHAPES`) — chaque anneau suit la forme (cercles dans un cercle, carrés dans un carré) et reste économe en points (`FILL_SPACING_MM`, `FILL_CHORD_MM`) ; arcs et cercles sont interpolés en points (`ARC_CHORD_MM`) car le TP ne trace que des lignes
3. `pipeline/step3_ascii.py` — trame ASCII pour le R-30iB Mate : **tout le dessin dans une seule trame**, points numérotés en continu ; entre deux trajectoires, deux points de déplacement sont insérés à `Z_TRAVEL_MM` (**feutre levé** : aucun trait de liaison) ; un dernier point remonte le feutre à la fin
4. `pipeline/step4_verify.py` — photo de la caméra XC-56, comparaison avec l'image de référence ; si le taux d'erreur ≥ 10 %, le dessin est recalculé **et renvoyé au robot seulement si la S7-1500 l'autorise** (`pipeline/plc.py`, snap7)

## Installation

```bash
pip install -r requirements.txt
```

requirements.txt : `opencv-python`, `numpy`, `python-snap7`.

### PC vision prêt en une commande

```bash
bash setup.sh
```

Le script crée un environnement virtuel `.venv`, installe les dépendances et
vérifie qu'OpenCV fonctionne. Ensuite :

```bash
source .venv/bin/activate && python app.py
```

## Démarrage

```bash
ROBOT_IP=192.168.0.20 PLC_IP=192.168.0.10 python app.py
```

Puis ouvrir `http://localhost:8000/` dans un navigateur.

## Visual Studio Code

Ouvrir le dossier du projet dans VS Code (extension **Python** installée) :

- **Run and Debug (F5) ▸ "Serveur web (app.py) - hôte"** : lance le serveur web
  (hôte) avec les variables d'environnement pré-remplies ;
- **Run and Debug ▸ "Code 2 : calcul des formes (debug pas à pas)"** : applique
  les codes 1 et 2 sur `uploads/design.png` (ou l'image passée en argument),
  affiche les formes, sauvegarde `uploads/bw.png` et `uploads/preview.png`
  et imprime la trame ASCII du code 3 ;
- placer des **points d'arrêt** dans `pipeline/step2_contours.py`
  (`extract`) ou `pipeline/step3_ascii.py` (`frame_for`) pour dérouler les
  calculs pas à pas ;
- l'extension **Remote - SSH** permet de faire tout cela à distance sur le
  PC vision de la cellule (le calcul reste sur le PC, jamais dans le navigateur) ;
- **Dev Containers** : le dossier `.devcontainer/` permet d'ouvrir le projet
  dans un conteneur prêt à l'emploi via la commande « Dev Containers:
  Reopen in Container » (dépendances et port 8000 déjà configurés).

La page web permet de :

- déposer une image (PNG/JPG) ;
- la traiter en noir et blanc ;
- extraire les formes, avec la **liste complète des points** de chaque
  trajectoire, leur **type** (angulaire, ligne, arc, cercle, mixte)
  et les PR correspondants ;
- envoyer le dessin au robot (bouton désactivé si le PLC refuse) ;
- lancer la vérification caméra avec le verdict d'erreur.

## Configuration (variables d'environnement)

| Variable | Défaut | Description |
|---|---|---|
| `ROBOT_IP` | 192.168.0.20 | adresse IP du R-30iB Mate |
| `ROBOT_PORT` | 59002 | port du tag SM serveur (S2) |
| `WEB_PORT` | 8000 | port du serveur web |
| `SCALE_MM_PER_PX` | 0.2 | étalonnage px → mm (à affiner !) |
| `Z_MM` | -15.0 | hauteur de **trace** (feutre en contact avec le support) |
| `Z_TRAVEL_MM` | -80.0 | hauteur de **déplacement** entre les formes (feutre levé) |
| `W_DEG`, `P_DEG`, `R_DEG` | 180, 0, 0 | orientation imposée à l'outil |
| `MIN_AREA_PX` | 80 | aire minimale d'une forme |
| `FILL_SHAPES` | 1 | remplir l'intérieur des formes par contours concentriques (0 = contours seuls) |
| `FILL_SPACING_MM` | 3.0 | espacement des anneaux de remplissage |
| `FILL_CHORD_MM` | 1.0 | corde max entre deux points d'un anneau (mm) |
| `CORNER_MIN_DEG` | 35.0 | déviation minimale pour qu'un sommet soit un angle |
| `LINE_TOL_PX` | 1.5 | tolérance d'alignement d'une ligne (px) |
| `ARC_TOL_PX` | 2.0 | tolérance d'ajustement d'un arc ou cercle (px) |
| `ARC_CHORD_MM` | 0.1 | corde max entre deux points d'un arc (mm) |
| `CAM_INDEX` | 0 | index du périphérique vidéo (frame grabber de la XC-56) |
| `PLC_IP` | 192.168.0.10 | adresse de la S7-1500 |
| `PLC_RACK`, `PLC_SLOT` | 0, 1 | rack et slot du CPU |
| `PLC_DB`, `PLC_BYTE`, `PLC_BIT` | 100, 0, 0 | bit d'autorisation d'envoi |
| `ERROR_THRESHOLD_PCT` | 10.0 | seuil de correction de l'étape 4 |
| `DEMO` | 1 | sans snap7/sans robot, les appels sont simulés |

## S7-1500

Activer "Permettre l'accès distant (PUT/GET)" dans les propriétés du CPU
(TIA Portal) pour que `python-snap7` puisse lire le bit d'autorisation.
Côté PLC, ce bit peut piloter le démarrage d'un cycle de reprise via les UOP
(PNS/RSR) du robot.

## KAREL + TP (robot)

**Le robot est SERVEUR** (tag `S2:`) : il écoute sur le port 59002 et attend
que le PC se connecte. Configuration une seule fois sur le pendant :
MENUS → SETUP → Host Comm → F4 SHOW → **Servers** → tag S2 → F3 DETAIL :
Protocol = `SM`, Startup State = `START`, Port = `59002`, puis F2 ACTION →
DEFINE et START (soit `$HOSTS_CFG[2].$SERVER_PORT = 59002`).

Avant chaque utilisation : **enseigner PR[10]** près du support avec le stylo —
il sert de modèle (configuration du robot) pour tous les points reçus.

Programmes à charger sur le robot :

- `karel/recv_path.kl` — reçoit **tout le dessin en une connexion** et écrit
  les points **en continu** dans `PR[10]` à `PR[10+n-1]` (`SET_POS_REG`), et
  le nombre de points `n` dans `R[3]` (`SET_INT_REG`) — seuls **R[1] à R[3]**
  sont utilisés : compteur de boucle, numéro de PR, nombre de points.
  Compiler en `recv_path.pc` (ktrans / RoboGuide) puis charger sur le
  contrôleur (FTP).
- `karel/MAIN.ls` — programme TP de dessin : `CALL RECV_PATH` (attend le PC),
  puis boucle `FOR R[1]=1 TO R[3]` avec `L PR[R[2]]` (100 mm/s, CNT100 —
  réduire pour les premiers essais). À recopier sur le pendant (11 lignes)
  ou charger si l'option ASCII est installée.

Déroulement d'un cycle : lancer `MAIN` sur le robot (il attend dans
`RECV_PATH`) → sur le PC, déposer l'image, étapes 1 et 2, puis « Envoyer » →
le KAREL remplit les PR, répond `ACK`, et le TP trace le dessin (les
déplacements stylo levé sont déjà inclus dans les points).

## Page GitHub

Pour publier la page web en statique :

1. Settings → Pages
2. Source : main, dossier `/docs`
3. URL : `https://schadow126.github.io/fanuc-vision-pc/`

La page publiée fonctionne alors en mode démo (sans serveur local, sans robot).

## Sécurité

- Serveur web en réseau local uniquement.
- Premiers essais : vitesse robot réduite, main sur l'arrêt d'urgence.
- `Z_MM` (trace) et `Z_TRAVEL_MM` (déplacement) sont exprimés dans l'UFRAME du
  programme TP : enseigner l'étalonnage caméra dans le même repère
  (`UFRAME_NUM`).
- `Z_TRAVEL_MM` (-80) est **plus éloigné de 0** que `Z_MM` (-15) : vérifier au
  premier essai que ce « lever de feutre » va bien dans le sens opposé au
  support (sens de l'axe Z de l'UFRAME).
