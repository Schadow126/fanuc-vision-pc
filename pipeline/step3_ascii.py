# -*- coding: utf-8 -*-
"""
CODE 3 - Trames ASCII et envoi vers le R-30iB Mate.

Trame d'une trajectoire = nombre de points, puis une ligne "X Y Z W P R"
par point (fins de ligne CR+LF). Une connexion par trajectoire ; le KAREL
recv_path.kl stocke les points dans PR[10], PR[11], ... et repond ACK.
"""
import socket

import config


def frame_for(traj):
    """Construit la trame ASCII d'une trajectoire."""
    lines = [str(len(traj))]
    for pt in traj:
        lines.append("{:.2f} {:.2f} {:.2f} {:.1f} {:.1f} {:.1f}".format(
            pt["x"], pt["y"], pt["z"], pt["w"], pt["p"], pt["r"]))
    return "\r\n".join(lines) + "\r\n"


def send_traj(traj):
    """Envoie une trajectoire ; renvoie la reponse du robot."""
    with socket.create_connection(
            (config.ROBOT_IP, config.ROBOT_PORT),
            timeout=config.SOCKET_TIMEOUT) as sock:
        sock.sendall(frame_for(traj).encode("ascii"))
        return sock.recv(64).decode("ascii", errors="replace").strip() or "(aucune reponse)"


def send_path(trajs):
    """Envoie toutes les trajectoires ; renvoie les reponses."""
    return [send_traj(traj) for traj in trajs]
