# fanuc-vision-pc

**Cellule de création de dessin** : le PC reçoit une image, en extrait les
formes, et le robot FANUC (feutre dans la pince) **les dessine**. Les points
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
2. `pipeline/step2_contours.py` — formes : `cv2.findContours` (formes claires ou sombres, détection automatique), `approxPolyDP`, conversion px → mm, trajectoires fermées
3. `pipeline/step3_ascii.py` — trame ASCII pour le R-30iB Mate : **tout le dessin dans une seule trame**, points numérotés en continu ; entre deux formes, deux points de déplacement sont insérés à `Z_TRAVEL_MM` (**feutre levé** : aucun trait de liaison) ; un dernier point remonte le feutre à la fin
4. `pipeline/step4_verify.py` — photo de la caméra XC-56, comparaison avec l'image de référence ; si le taux d'erreur ≥ 10 %, le dessin est recalculé **et renvoyé au robot seulement si la S7-1500 l'autorise** (`pipeline/plc.py`, snap7)

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
- extraire les formes, avec la **liste complète des points** de chaque
  trajectoire (et les PR correspondants) ;
- envoyer le dessin au robot (bouton désactivé si le PLC refuse) ;
- lancer la vérification caméra avec le verdict d'erreur.

## Configuration (variables d'environnement)

| Variable | Défaut | Description |
|---|---|---|
| `ROBOT_IP` | 192.168.1.10 | adresse IP du R-30iB Mate |
| `ROBOT_PORT` | 59002 | port du tag SM (C2 client) |
| `WEB_PORT` | 8000 | port du serveur web |
| `SCALE_MM_PER_PX` | 0.2 | étalonnage px → mm (à affiner !) |
| `Z_MM` | -15.0 | hauteur de **trace** (feutre en contact avec le support) |
| `Z_TRAVEL_MM` | -80.0 | hauteur de **déplacement** entre les formes (feutre levé) |
| `W_DEG`, `P_DEG`, `R_DEG` | 180, 0, 0 | orientation imposée à l'outil |
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

`karel/recv_path.kl` reçoit **une seule connexion contenant tout le dessin**
et écrit les points **en continu** dans les Position Registers `PR[10]` à
`PR[10+n-1]`. Les déplacements feutre levé sont déjà inclus dans la trame :
le programme TP se contente de parcourir `L PR[10]` à `L PR[10+n-1]`.
Compiler `recv_path.pc` via Robot Studio puis l'appeler depuis un programme TP.
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
- `Z_MM` (trace) et `Z_TRAVEL_MM` (déplacement) sont exprimés dans l'UFRAME du
  programme TP : enseigner l'étalonnage caméra dans le même repère
  (`UFRAME_NUM`).
- `Z_TRAVEL_MM` (-80) est **plus éloigné de 0** que `Z_MM` (-15) : vérifier au
  premier essai que ce « lever de feutre » va bien dans le sens opposé au
  support (sens de l'axe Z de l'UFRAME).
