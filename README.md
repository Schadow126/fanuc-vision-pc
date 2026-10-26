# fanuc-vision-pc

PC vision pour cellule robotisee **FANUC LR Mate 200iD/4S** (controleur R-30iB Mate) :

- camera **Sony XC-56** (analogique) via frame grabber ;
- comparaison image reelle / image de reference (**OpenCV**) ;
- envoi du point corrige `X Y Z W P R` au robot par **socket TCP** (KAREL Socket Messaging, tag SM) ;
- le **S7-1500** lance le cycle via PROFINET (UOP/PNS).

## Architecture

```
S7-1500 ---PROFINET (PNS/RSR, UOP/GO/UO)---> R-30iB Mate
XC-56   ---frame grabber---> PC ---socket TCP :59002---> KAREL ---> PR[n] ---> TP : L PR[n]
```

## Protocole

| Sens | Trame | Signification |
|---|---|---|
| Robot vers PC | `TAKE_PHOTO\r` | demande de cycle vision |
| PC vers Robot | `X Y Z W P R\r` | point corrige (mm / deg, UFRAME) |
| PC vers Robot | `ERROR vision\r` | echec (correlation < seuil) |
| Robot vers PC | `ACK\r` | accuse de reception |

## Demarrage

```bash
pip install -r requirements.txt
python main.py --save-ref    # 1x : enregistrer l'image de reference
python main.py               # lancer le serveur vision
```

## Configuration

Editer `config.py` : port socket, index camera, matrice d'etalonnage
pixels vers mm, seuils de correlation, garde-fous.

## Etalonnage

1. Placer la piece en position parfaite puis `python main.py --save-ref`.
2. Deplacer la piece de distances connues, relever les ecarts pixels,
   en deduire l'echelle `mm/px` et l'offset vers `CALIB_MATRIX`.

## Cote robot

- Tag client `C2` : SETUP > Host Comm > protocol `SM`, IP du PC, port 59002
  (`$HOSTC_CFG[2].$SERVER_PORT = 59002`).
- Charger `karel/recv_point.kl` (option Socket Messaging requise).
- Le TP appelle `recv_point` puis execute `L PR[10]` (UFRAME/UTOOL identiques
  a ceux utilises pour l'etalonnage !).
