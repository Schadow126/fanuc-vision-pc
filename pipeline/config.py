# -*- coding: utf-8 -*-
"""Configuration de la cellule (surchargeable par variables d'environnement)."""
import os

# Robot FANUC R-30iB Mate
ROBOT_IP = os.environ.get("ROBOT_IP", "192.168.1.10")
ROBOT_PORT = int(os.environ.get("ROBOT_PORT", "59002"))
WEB_PORT = int(os.environ.get("WEB_PORT", "8080"))
SOCKET_TIMEOUT = float(os.environ.get("SOCKET_TIMEOUT", "5"))

# Etalonnage caméra / plan de travail : mm par pixel et hauteur de travail
SCALE_MM_PER_PX = float(os.environ.get("SCALE_MM_PER_PX", "0.2"))
Z_MM = float(os.environ.get("Z_MM", "50.0"))
W_DEG = float(os.environ.get("W_DEG", "180.0"))
P_DEG = float(os.environ.get("P_DEG", "0.0"))
R_DEG = float(os.environ.get("R_DEG", "0.0"))
MIN_AREA_PX = int(os.environ.get("MIN_AREA_PX", "80"))

# Camera Sony XC-56 (analogique -> frame grabber = peripherique video)
CAM_INDEX = int(os.environ.get("CAM_INDEX", "0"))

# Autorisation S7-1500 (snap7 : PUT/GET actifs sur le PLC)
PLC_IP = os.environ.get("PLC_IP", "192.168.1.1")
PLC_RACK = int(os.environ.get("PLC_RACK", "0"))
PLC_SLOT = int(os.environ.get("PLC_SLOT", "1"))
PLC_DB = int(os.environ.get("PLC_DB", "100"))
PLC_BYTE = int(os.environ.get("PLC_BYTE", "0"))
PLC_BIT = int(os.environ.get("PLC_BIT", "0"))

# Seuil de correction : si taux d'erreur >= 10 %, regenerer les trajectoires
ERROR_THRESHOLD_PCT = float(os.environ.get("ERROR_THRESHOLD_PCT", "10.0"))

DEMO = os.environ.get("DEMO", "0") == "1"
