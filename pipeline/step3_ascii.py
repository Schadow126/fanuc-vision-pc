# -*- coding: utf-8 -*-
"""
CODE 3 - Trame ASCII et envoi vers le R-30iB Mate.

TOUTES les trajectoires sont envoyees en UNE SEULE connexion, avec une
numerotation continue des points :

    ligne 1   : nombre TOTAL de points n (toutes trajectoires)
    lignes 2..: n fois "X Y Z W P R" (fins de ligne CR+LF)

Chaque trajectoire etant fermee, elle finit par son point de depart.
Le KAREL recv_path.kl stocke les points en continu dans PR[10], PR[11], ...
puis repond ACK.
"""
import socket

import config


def frame_for(trajs):
    """Construit la trame ASCII de toutes les trajectoires."""
    points = [pt for traj in trajs for pt in traj]
    lines = [str(len(points))]
    for pt in points:
        lines.append("{:.2f} {:.2f} {:.2f} {:.1f} {:.1f} {:.1f}".format(
            pt["x"], pt["y"], pt["z"], pt["w"], pt["p"], pt["r"]))
    return "\r\n".join(lines) + "\r\n"


def send_path(trajs):
    """Envoie toutes les trajectoires en une connexion ; reponse du robot."""
    with socket.create_connection(
            (config.ROBOT_IP, config.ROBOT_PORT),
            timeout=config.SOCKET_TIMEOUT) as sock:
        sock.sendall(frame_for(trajs).encode("ascii"))
        return sock.recv(64).decode("ascii", errors="replace").strip() or "(aucune reponse)"
