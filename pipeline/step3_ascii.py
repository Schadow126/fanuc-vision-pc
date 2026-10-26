# -*- coding: utf-8 -*-
"""
CODE 3 - step3_ascii.py
Convertit les points et trajectoires en trames ASCII pour le R-30iB Mate
et les envoie par Socket Messaging (TCP, tag SM, port 59002).

Trame : "X Y Z W P R\r" six REAL separes par des blancs, terminee par CR.
Cote robot, le programme KAREL recv_point.kl lit les 6 REAL et ecrit le PR.

Chaque point est envoye sur sa propre connexion (connect / send / ACK / close),
coherent avec recv_point.kl qui lit un point puis fait MSG_DISCO.
"""

import socket


def point_to_ascii(x, y, z, w, p, r):
    return "{:.3f} {:.3f} {:.3f} {:.3f} {:.3f} {:.3f}".format(x, y, z, w, p, r)


def frames_from_points(points_data):
    """Aplatit toutes les trajectoires en une liste de trames ASCII."""
    frames = []
    for traj in points_data.get("trajectories", []):
        for pt in traj.get("points", []):
            frames.append(point_to_ascii(*pt))
    return frames


def send_frame(frame, ip, port, timeout=5.0):
    """Envoie une trame et lit l'accuse du KAREL (ACK / ERR)."""
    with socket.create_connection((ip, port), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall((frame + "\r").encode("ascii"))
        reply = s.recv(64).decode("ascii", errors="replace").strip()
    return reply or "(aucune reponse)"


def send_all(points_data, ip, port, timeout=5.0, first=1, count=None):
    """
    Envoie les trames au robot. 'first'/'count' permettent de limiter
    l'envoi (utile en mise au point : envoyer seulement 5 points).
    """
    frames = frames_from_points(points_data)
    frames = frames[first - 1:first - 1 + (count if count else len(frames))]
    acks = []
    for i, frame in enumerate(frames, start=first):
        reply = send_frame(frame, ip, port, timeout)
        acks.append({"n": i, "frame": frame, "reply": reply})
    return {"sent": len(acks), "acks": acks}
