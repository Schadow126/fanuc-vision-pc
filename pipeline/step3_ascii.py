# -*- coding: utf-8 -*-
"""
CODE 3 - Trame ASCII et envoi vers le R-30iB Mate (dessin).

TOUTES les trajectoires sont envoyees en UNE SEULE connexion, avec une
numerotation continue des points :

    ligne 1   : nombre TOTAL de points n
    lignes 2..: n fois "X Y Z W P R" (fins de ligne CR+LF)

Creation de dessin : le robot tient un stylo et trace chaque forme.
- un premier point est insere AU-DESSUS du premier point de trace
  (Z_TRAVEL_MM, stylo leve) : le robot descend, puis trace ;
- entre deux formes, deux points de deplacement a Z_TRAVEL_MM
  (aucun trait de liaison) ;
- un dernier point remonte le stylo a la fin du dessin.

Le programme TP parcourt simplement les PR dans l'ordre.
"""
import socket

import config


def _fmt(pt):
    return "{:.2f} {:.2f} {:.2f} {:.1f} {:.1f} {:.1f}".format(
        pt["x"], pt["y"], pt["z"], pt["w"], pt["p"], pt["r"])


def frame_for(trajs):
    """Construit la trame ASCII de tout le dessin (toutes les formes)."""
    pts = []
    if trajs:
        arrivee = dict(trajs[0][0]); arrivee["z"] = config.Z_TRAVEL_MM
        pts.append(arrivee)  # arrive au-dessus du premier point (stylo leve)
    for i, traj in enumerate(trajs):
        if i > 0:  # deplacement stylo leve entre deux formes
            fin = dict(trajs[i - 1][-1]); fin["z"] = config.Z_TRAVEL_MM
            debut = dict(traj[0]); debut["z"] = config.Z_TRAVEL_MM
            pts += [fin, debut]
        pts += traj
    fin = dict(pts[-1]); fin["z"] = config.Z_TRAVEL_MM
    pts.append(fin)  # remonte le stylo a la fin du dessin
    return "\r\n".join([str(len(pts))] + [_fmt(p) for p in pts]) + "\r\n"


def send_path(trajs):
    """Envoie tout le dessin en une connexion ; reponse du robot."""
    with socket.create_connection(
            (config.ROBOT_IP, config.ROBOT_PORT),
            timeout=config.SOCKET_TIMEOUT) as sock:
        sock.sendall(frame_for(trajs).encode("ascii"))
        return sock.recv(64).decode("ascii", errors="replace").strip() or "(aucune reponse)"
