# -*- coding: utf-8 -*-
"""
Autorisation S7-1500.

Avant tout envoi de trajectoires vers le robot, le PC lit un bit
d'autorisation dans une DB du PLC (snap7 - activer PUT/GET sur la S7-1500).
Sans snap7 ou en mode DEMO : autorise (demonstration).
"""
import config

try:
    import snap7
except ImportError:
    snap7 = None


def is_authorized():
    """True si la S7-1500 autorise l'envoi vers le robot."""
    if config.DEMO or snap7 is None:
        return True
    client = snap7.client.Client()
    try:
        client.connect(config.PLC_IP, config.PLC_RACK, config.PLC_SLOT)
        data = client.db_read(config.PLC_DB, config.PLC_BYTE, 1)
        return bool(data[0] & (1 << config.PLC_BIT))
    finally:
        client.disconnect()
