# -*- coding: utf-8 -*-
"""
CODE 3 - Trame ASCII et envoi vers le R-30iB Mate (dessin).

TOUTES les trajectoires sont envoyees en UNE SEULE connexion, avec une
numerotation continue des points :

    ligne 1   : nombre TOTAL de points n
    lignes 2..: n fois "X Y Z W P R" (fins de ligne CR+LF)

Creation de dessin : le robot tient un feutre et trace chaque forme.
Entre deux formes, deux points de deplacement sont inseres a Z_TRAVEL_MM
(feutre LEVE au-dessus de la fin de la forme, puis au-dessus du debut de la
suivante) : aucun trait de liaison n'est trace. Un dernier point remonte le
feutre a la fin du dessin. Le programme TP parcourt simplement les PR.
"""
import socket

import config


def _fmt(pt):
    return "{:.2f} {:.2f} {:.2f} {:.1f} {:.1f} {:.1f}".format(
        pt["x"], pt["y"], pt["z"], pt["w"], pt["p"], pt["r"])


def frame_for(trajs):
    """Construit la trame ASCII de tout le dessin (toutes les formes)."""
    pts = []
    for i, traj in enumerate(trajs):
        if i > 0:  # deplacement feutre leve entre deux formes
            fin = dict(trajs[i - 1][-1]); fin["z"] = config.Z_TRAVEL_MM
            debut = dict(traj[0]); debut["z"] = config.Z_TRAVEL_MM
            pts += [fin, debut]
        pts += traj
    fin = dict(pts[-1]); fin["z"] = config.Z_TRAVEL_MM
    pts.append(fin)  # remonte le feutre a la fin du dessin
    return "\r\n".join([str(len(pts))] + [_fmt(p) for p in pts]) + "\r\n"


def send_path(trajs):
    """Envoie tout le dessin en une connexion ; reponse du robot."""
    with socket.create_connection(
            (config.ROBOT_IP, config.ROBOT_PORT),
            timeout=config.SOCKET_TIMEOUT) as sock:
        sock.sendall(frame_for(trajs).encode("ascii"))
        return sock.recv(64).decode("ascii", errors="replace").strip() or "(aucune reponse)"
