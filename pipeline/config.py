# -*- coding: utf-8 -*-
"""Configuration de la cellule (surchargeable par variables d'environnement)."""
import os

# Robot FANUC R-30iB Mate
ROBOT_IP = os.environ.get("ROBOT_IP", "192.168.0.20")
ROBOT_PORT = int(os.environ.get("ROBOT_PORT", "59002"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8000"))
SOCKET_TIMEOUT = float(os.environ.get("SOCKET_TIMEOUT", "5"))

# Transport du dessin vers le robot (option A : pas de R648 User Socket
# Messaging, donc pas de socket KAREL). Le PC ecrit DESSIN.TXT puis :
#   "usb" : copie vers USB_PATH, cle a brancher sur le port USB du
#           controleur (peripherique UD1:) avant de lancer MAIN ;
#   "ftp" : depot par FTP sur le controleur (fichier dans MD: ;
#           remplacer UD1: par MD: dans karel/recv_path.kl).
TRANSPORT = os.environ.get("TRANSPORT", "usb")
EXPORT_DIR = os.environ.get("EXPORT_DIR", "uploads")   # dossier local du fichier genere
DESSIN_FILE = os.environ.get("DESSIN_FILE", "DESSIN.TXT")
USB_PATH = os.environ.get("USB_PATH", "E:/")           # ou la cle USB apparait sur le PC
FTP_USER = os.environ.get("FTP_USER", "anonymous")
FTP_PASS = os.environ.get("FTP_PASS", "")

# Points max par lot = nombre de PR reserves au dessin sur le robot
# (PR[74..100] : 27 PR, les autres etant utilises par la cellule).
# Une trajectoire plus longue est DECOUPEE en sous-lots dont le premier
# point repete le dernier trace : le stylo se repose exactement dessus
# (pas de trou, juste un leve de stylo au raccord).
LOT_MAX_POINTS = int(os.environ.get("LOT_MAX_POINTS", "27"))

# Dessin : etalonnage px -> mm, hauteur de trace et hauteur de deplacement
SCALE_MM_PER_PX = float(os.environ.get("SCALE_MM_PER_PX", "0.2"))
Z_MM = float(os.environ.get("Z_MM", "-15.0"))                 # feutre en contact
Z_TRAVEL_MM = float(os.environ.get("Z_TRAVEL_MM", "-80.0"))   # feutre leve entre formes
W_DEG = float(os.environ.get("W_DEG", "180.0"))
P_DEG = float(os.environ.get("P_DEG", "0.0"))
R_DEG = float(os.environ.get("R_DEG", "0.0"))
MIN_AREA_PX = int(os.environ.get("MIN_AREA_PX", "80"))

# Reconnaissance des primitives (code 2) et trajectoires interieures
INNER_TRAJECTORIES = os.environ.get("INNER_TRAJECTORIES", "1") == "1"  # tracer les traits interieurs de l'image
INNER_MIN_GAP_PX = float(os.environ.get("INNER_MIN_GAP_PX", "8.0"))  # ecart mini trait interieur / contour (px)
TRAIT_MAX_W_PX = float(os.environ.get("TRAIT_MAX_W_PX", "3.0"))  # epaisseur max d'un petit trait lineaire (px)
MIN_TRAIT_PX = float(os.environ.get("MIN_TRAIT_PX", "8.0"))     # longueur mini d'un petit trait lineaire (px)
CORNER_MIN_DEG = float(os.environ.get("CORNER_MIN_DEG", "35.0"))  # deviation mini d'un angle
LINE_TOL_PX = float(os.environ.get("LINE_TOL_PX", "1.5"))        # tolerance d'alignement (px)
ARC_TOL_PX = float(os.environ.get("ARC_TOL_PX", "2.0"))          # tolerance arc / cercle (px)
ARC_CHORD_MM = float(os.environ.get("ARC_CHORD_MM", "0.1"))     # corde max entre 2 points d'arc

# Noir et blanc (code 1)
BW_MEDIAN_PX = int(os.environ.get("BW_MEDIAN_PX", "3"))  # nettoyage des pixels isoles apres seuillage (0 = desactive)

# Mode squelette (dessins au trait : traits fins entrelaces, ex. cercles a rayons)
SQUELETTE_MAX_PX = float(os.environ.get("SQUELETTE_MAX_PX", "6.0"))            # demi-epaisseur max d'un composant "dessin au trait" (0 = desactive)
SQUELETTE_ELAGUE_PX = float(os.environ.get("SQUELETTE_ELAGUE_PX", "4.0"))      # epines supprimees du squelette (px)
SQUELETTE_JONCTION_PX = float(os.environ.get("SQUELETTE_JONCTION_PX", "8.0"))  # rayon de regroupement des croisements (px)
SQUELETTE_VIRAGE_DEG = float(os.environ.get("SQUELETTE_VIRAGE_DEG", "35.0"))   # virage max pour fusionner deux traits alignes (deg)
SQUELETTE_LIGNE_RMS_PX = float(os.environ.get("SQUELETTE_LIGNE_RMS_PX", "1.2"))  # RMS max pour reconnaitre une ligne du squelette (px)

# Camera Sony XC-56 (analogique -> frame grabber = peripherique video)
CAM_INDEX = int(os.environ.get("CAM_INDEX", "0"))

# Autorisation S7-1500 (snap7 : PUT/GET actifs sur le PLC)
PLC_IP = os.environ.get("PLC_IP", "192.168.0.10")
PLC_RACK = int(os.environ.get("PLC_RACK", "0"))
PLC_SLOT = int(os.environ.get("PLC_SLOT", "1"))
PLC_DB = int(os.environ.get("PLC_DB", "100"))
PLC_BYTE = int(os.environ.get("PLC_BYTE", "0"))
PLC_BIT = int(os.environ.get("PLC_BIT", "0"))

# Seuil de correction : si taux d'erreur >= 10 %, regenerer les trajectoires
ERROR_THRESHOLD_PCT = float(os.environ.get("ERROR_THRESHOLD_PCT", "10.0"))

# DEMO=1 (defaut) : sans robot ni PLC, les envois sont autorises/simules.
# Mettre DEMO=0 en production.
DEMO = os.environ.get("DEMO", "1") == "1"
