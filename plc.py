# -*- coding: utf-8 -*-
"""
plc.py - Autorisation d'envoi par l'automate S7-1500.

Dans la cellule, le S7-1500 est le chef d'orchestre : le PC ne doit envoyer
de points au robot que si l'automate l'autorise (le PLC lance ensuite le
cycle cote robot via PROFINET / UOP-PNS).

Modes (variable d'environnement PLC_MODE) :
  demo    : autorise toujours (mise au point, par defaut)
  file    : autorise si le fichier work/plc_allow.txt existe
            (l'automate ou un script de passerelle cree/supprime ce fichier)
  socket  : interroge une passerelle TCP (PLC_GATEWAY_IP:PLC_GATEWAY_PORT)
            et attend la reponse "OK"

En production, adaptez la fonction is_send_authorized() a votre liaison
reelle avec le S7-1500 (Modbus TCP, OPC UA, ou passerelle personnalisee).
"""

import os
import socket
from pathlib import Path

ALLOW_FILE = Path("work") / "plc_allow.txt"


def is_send_authorized():
    mode = os.environ.get("PLC_MODE", "demo").lower()
    if mode == "demo":
        return True
    if mode == "file":
        return ALLOW_FILE.exists()
    if mode == "socket":
        host = os.environ.get("PLC_GATEWAY_IP", "192.168.1.1")
        port = int(os.environ.get("PLC_GATEWAY_PORT", "9600"))
        try:
            with socket.create_connection((host, port), timeout=1.0) as s:
                s.sendall(b"AUTH?")
                return s.recv(8).strip() == b"OK"
        except OSError:
            return False
    return False


def status():
    return {
        "mode": os.environ.get("PLC_MODE", "demo"),
        "authorized": is_send_authorized(),
    }
