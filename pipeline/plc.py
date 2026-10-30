# -*- coding: utf-8 -*-
"""
Autorisation S7-1500.

Le PLC garde la main sur le cycle : avant tout envoi de trajectoires
corrigees vers le robot, le PC lit un bit d'autorisation dans une DB
(protocole S7 via snap7 - activer "Permettre la communication PUT/GET"
dans les parametres de protection de la S7-1500).

Sans snap7 installe, la fonction renvoie True (mode demonstration) ;
en production, installerez : pip install python-snap7
"""
import config

try:
    import snap7
    _HAS_SNAP7 = True
except ImportError:
    _HAS_SNAP7 = False


def is_authorized():
    """True si la S7-1500 autorise l'envoi vers le robot."""
    if config.DEMO or not _HAS_SNAP7:
        return True  # mode demonstration : pas de PLC
    client = snap7.client.Client()
    try:
        client.connect(config.PLC_IP, config.PLC_RACK, config.PLC_SLOT)
        data = client.db_read(config.PLC_DB, config.PLC_BYTE, 1)
        return bool(data[0] & (1 << config.PLC_BIT))
    finally:
        try:
            client.disconnect()
        except Exception:
            pass
