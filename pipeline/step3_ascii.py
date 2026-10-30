# -*- coding: utf-8 -*-
"""
CODE 3 - Conversion ASCII et envoi vers le R-30iB Mate.

Convertit chaque trajectoire (liste de points X Y Z W P R) en trames ASCII
lues par le programme KAREL recv_path.kl via Socket Messaging :

    ligne 1  : nombre de points de la trajectoire (INTEGER)
    lignes n : "X Y Z W P R" separes par des blancs, CR final

Chaque trajectoire est envoyee sur une connexion ; le KAREL stocke les
points dans PR[10], PR[11], ... et le programme TP parcourt ces PR.
"""
import socket


def frames_for(traj):
    """Construit la trame ASCII d'une trajectoire."""
    lines = [str(len(traj))]
    for pt in traj:
        lines.append("{:.2f} {:.2f} {:.2f} {:.1f} {:.1f} {:.1f}".format(
            pt["x"], pt["y"], pt["z"], pt["w"], pt["p"], pt["r"]))
    return "\r\n".join(lines) + "\r\n"


def send_traj(traj, ip, port, timeout=5.0, sock=None):
    """Envoie une trajectoire ; renvoie la reponse du robot ('ACK' / 'ERR')."""
    data = frames_for(traj).encode("ascii")
    close = False
    if sock is None:
        sock = socket.create_connection((ip, port), timeout=timeout)
        sock.settimeout(timeout)
        close = True
    try:
        sock.sendall(data)
        reply = sock.recv(64).decode("ascii", errors="replace").strip()
    finally:
        if close:
            sock.close()
    return reply or "(aucune reponse)"


def send_path(trajs, ip, port, timeout=5.0):
    """Envoie toutes les trajectoires ; renvoie la liste des reponses."""
    replies = []
    for i, traj in enumerate(trajs):
        reply = send_traj(traj, ip, port, timeout)
        replies.append("trajectoire " + str(i + 1) + "/" + str(len(trajs)) +
                       " (" + str(len(traj)) + " pts) : " + reply)
    return replies
