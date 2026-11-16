# fanuc-vision-pc

**Cellule de création de dessin** : le PC reçoit une image, en extrait les
formes, et le robot FANUC (stylo dans la pince) **les dessine**. Les trajectoires
partent vers le contrôleur R-30iB Mate (LR Mate 200iD/4S) par fichier
`DESSIN.TXT` (clé USB `UD1:` ou FTP), lu par un programme KAREL ;
une caméra vérifie le dessin obtenu.

## Architecture

| Équipement | Rôle |
|---|---|
| PC vision | dépôt de l'image, traitement, extraction des formes, génération de `DESSIN.TXT` (clé USB / FTP), page web |
| R-30iB Mate | lit `DESSIN.TXT` par lot (KAREL `recv_path.kl`, sans option Socket Messaging), charge chaque trajectoire dans PR[74..100] (27 PR réservés au dessin) |
| S7-1500 | lance le cycle (UOP/PNS sur PROFINET) et **autorise ou refuse l'envoi** des corrections (bit DB100.DBX0.0) |
| Sony XC-56 | photo du dessin réalisé pour l'étape de vérification (analogique → frame grabber du PC) |

## Pipeline en 4 étapes

1. `pipeline/step1_bw.py` — noir & blanc : carte **« distance au blanc »** (255 − canal le plus clair : les couleurs claires — jaune, rouge — restent de l'encre, un passage en niveaux de gris les perdrait), flou gaussien, seuil d'Otsu, nettoyage médian (`BW_MEDIAN_PX`)
2. `pipeline/step2_contours.py` — formes : `cv2.findContours` (formes claires ou sombres, détection automatique), reconnaissance des primitives — **angulaire** (lignes reliées par des angles), **ligne**, **arc**, **cercle** —, conversion px → mm, trajectoires fermées, et **traits intérieurs de l'image** (`INNER_TRAJECTORIES`) : les contours internes réellement dessinés à l'intérieur des formes sont extraits via la hiérarchie et tracés avec le moins de points possible — **jamais de remplissage généré** ; les **petits traits linéaires** (fins, d'aire quasi nulle) sont reconnus même sous `MIN_AREA_PX` et réduits à leur axe en **2 points** (`TRAIT_MAX_W_PX`, `MIN_TRAIT_PX`) ; arcs et cercles sont interpolés en points (`ARC_CHORD_MM`) car le TP ne trace que des lignes ; **dessins au trait** (`SQUELETTE_MAX_PX`) : les composantes fines (cercles entrelacés avec leurs rayons, lettres…) sont amincies en **squelette** (Guo-Hall), leurs traits suivis sur leur **axe médian** puis fusionnés — deux rayons opposés d'une même droite donnent **une seule ligne à 2 points**, les arcs d'un même cercle se recollent en **un cercle complet**
3. `pipeline/step3_ascii.py` — **`DESSIN.TXT`** pour le R-30iB Mate (transport par fichier, l'option User Socket Messaging R648 n'étant pas installée) : une trajectoire par **lot autonome** — un point d'approche à `Z_TRAVEL_MM` (**feutre levé**), les points de trace, un point de remontée à `Z_TRAVEL_MM` — chaque lot tenant dans les 27 PR du dessin (`LOT_MAX_POINTS`), une trajectoire plus longue étant **découpée en sous-lots** au point de raccord répété (le stylo se repose exactement sur le trace, sans trou) — puis dépôt selon `TRANSPORT` : `usb` (copie sur la clé USB à brancher sur le port du contrôleur, périphérique `UD1:`) ou `ftp` (dépôt sur le serveur FTP du contrôleur)
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
  (`extract`) ou `pipeline/step3_ascii.py` (`dessin_txt`) pour dérouler les
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
| `ROBOT_PORT` | 59002 | port du tag SM serveur (inutilisé en transport par fichier) |
| `TRANSPORT` | usb | transport du dessin : `usb` (copie sur la clé, `USB_PATH`) ou `ftp` (dépôt FTP sur le contrôleur) |
| `EXPORT_DIR` | uploads | dossier local où `DESSIN.TXT` est généré |
| `DESSIN_FILE` | DESSIN.TXT | nom du fichier du dessin |
| `USB_PATH` | E:/ | lettre/dossier où la clé USB apparaît sur le PC |
| `FTP_USER`, `FTP_PASS` | anonymous, (vide) | identifiants FTP du contrôleur |
| `LOT_MAX_POINTS` | 27 | points max par lot = les 27 PR du dessin (PR[74..100]) ; une trajectoire plus longue est découpée en sous-lots |
| `WEB_PORT` | 8000 | port du serveur web |
| `SCALE_MM_PER_PX` | 0.2 | étalonnage px → mm (à affiner !) |
| `Z_MM` | -15.0 | hauteur de **trace** (feutre en contact avec le support) |
| `Z_TRAVEL_MM` | -80.0 | hauteur de **déplacement** entre les formes (feutre levé) |
| `W_DEG`, `P_DEG`, `R_DEG` | 180, 0, 0 | orientation imposée à l'outil |
| `MIN_AREA_PX` | 80 | aire minimale d'une forme |
| `INNER_TRAJECTORIES` | 1 | tracer aussi les traits intérieurs dessinés dans l'image (0 = contours externes seuls) |
| `INNER_MIN_GAP_PX` | 8.0 | écart minimal entre un trait intérieur et le contour (moins = intérieur du trait, ignoré) |
| `TRAIT_MAX_W_PX` | 3.0 | épaisseur maximale d'un petit trait linéaire (px) |
| `MIN_TRAIT_PX` | 8.0 | longueur minimale d'un petit trait linéaire (px) |
| `CORNER_MIN_DEG` | 35.0 | déviation minimale pour qu'un sommet soit un angle |
| `LINE_TOL_PX` | 1.5 | tolérance d'alignement d'une ligne (px) |
| `ARC_TOL_PX` | 2.0 | tolérance d'ajustement d'un arc ou cercle (px) |
| `ARC_CHORD_MM` | 0.1 | corde max entre deux points d'un arc (mm) |
| `BW_MEDIAN_PX` | 3 | nettoyage des pixels isolés après le seuillage (0 = désactivé) |
| `SQUELETTE_MAX_PX` | 6.0 | demi-épaisseur max d'une composante « dessin au trait » (0 = désactivé) |
| `SQUELETTE_ELAGUE_PX` | 4.0 | épines supprimées du squelette (px) |
| `SQUELETTE_JONCTION_PX` | 8.0 | rayon de regroupement des croisements (px) |
| `SQUELETTE_VIRAGE_DEG` | 35.0 | virage max pour fusionner deux traits alignés (deg) |
| `SQUELETTE_LIGNE_RMS_PX` | 1.2 | RMS max pour reconnaître une ligne du squelette (px) |
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

## KAREL + TP (robot) — transport par fichier (option A)

L'option **User Socket Messaging (R648) n'est pas installée** sur ce
contrôleur : pas de socket KAREL. Le dessin transite par un fichier
**`DESSIN.TXT`** que le PC dépose sur la **clé USB du contrôleur
(périphérique `UD1:`)** — ou par FTP, le fichier arrive alors dans
`MD:` (remplacer `UD1:` par `MD:` dans `karel/recv_path.kl`).
**Aucune configuration Host Comm n'est nécessaire.**

Avant chaque utilisation : **enseigner PR[10]** près du support avec le
stylo — il sert de modèle (configuration du robot) pour tous les points
et **n'est jamais écrasé** (les points du dessin vont dans `PR[74..100]`).
PR occupés par le dessin : PR[9] (approche), PR[10] (modèle), PR[74..100] (points)
— 29 PR au total sur les 33 autorisés ; tous les autres PR de la cellule
(1-8, 11-41, 50, 60-62, 70-73, et les blocs libres 42-49, 51-59, 63-69)
restent disponibles.

Programmes à charger sur le robot :

- `karel/recv_path.kl` — lit **un lot par appel** dans `DESSIN.TXT` :
  saute les trajectoires déjà tracées (compteur `R[5]`), charge la
  suivante dans `PR[74]` à `PR[74+n-1]` (`SET_POS_REG`, n ≤ 27), met le nombre
  de points dans `R[3]`, les restantes dans `R[4]`, et incrémente `R[5]`
  (`SET_INT_REG`). Garde-fou `MAX_POINTS` = 27 (= `LOT_MAX_POINTS` côté PC) : un lot trop
  grand arrête le dessin avec un message au pendant ; côté PC, les
  trajectoires longues sont découpées en sous-lots automatiquement. Compiler en `recv_path.pc`
  (ktrans / RoboGuide), puis charger le `.pc` sur le contrôleur
  (menu FILES, ou FTP en mode binaire).
- `karel/MAIN.ls` — programme TP de dessin : `R[4]=0`, `R[5]=0`,
  approche `J PR[9]`, puis boucle `LBL[10]` : `CALL RECV_PATH` ;
  si `R[3]=0` le dessin est terminé ; sinon `FOR R[1]=1 TO R[3]` avec
  `L PR[R[2]]` (points dans `PR[74..100]`, 100 mm/s, CNT100 — réduire pour
  les premiers essais).
  À recopier sur le pendant (16 lignes) ou charger si l'option ASCII
  est installée.

Déroulement d'un cycle :

1. PC : déposer l'image, étapes 1 et 2, puis « Envoyer » → `DESSIN.TXT`
   est généré dans `EXPORT_DIR` et copié sur la clé USB (`USB_PATH`) ou
   déposé par FTP (`TRANSPORT`) ;
2. brancher la clé sur le **port USB du contrôleur** (`UD1:`) ;
3. robot : lancer `MAIN` — chaque `CALL RECV_PATH` charge un lot, le TP
   le trace d'un seul trait ; le stylo se lève automatiquement entre les
   formes (les points de remontée à `Z_TRAVEL_MM` sont inclus dans
   chaque lot) ; `MAIN` s'arrête seul quand `DESSIN.TXT` est épuisé.

Si `MAIN` est arrêté en cours de dessin, le relancer reprend le dessin
**depuis le début** (`R[5]` est remis à zéro au démarrage de `MAIN`).

Clé USB : la formater via le contrôleur si nécessaire
(MENU → FILE → F5 [UTIL] → FORMAT) ; clés de 32 Mo à 2 Go en FAT
recommandées (cf. cours TPE-B n° 380, § 20.2).

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
