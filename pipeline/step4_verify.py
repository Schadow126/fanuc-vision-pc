# -*- coding: utf-8 -*-
"""
CODE 4 - Verification camera Sony XC-56 et correction.

Photo de la camera, comparaison avec l'image de reference (code 1).
Si le taux d'erreur >= seuil : nouvelles trajectoires calculees depuis la
photo, puis envoi au robot UNIQUEMENT si la S7-1500 l'autorise.
"""
import cv2
import numpy as np

import config
import plc
import step1_bw
import step2_contours
import step3_ascii


def capture():
    """Une photo de la camera (None si inaccessible)."""
    cap = cv2.VideoCapture(config.CAM_INDEX)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def error_rate(ref, cam):
    """Taux d'erreur en % entre deux images binaires (0 = identiques)."""
    if cam.shape != ref.shape:
        cam = cv2.resize(cam, (ref.shape[1], ref.shape[0]))
    diff = cv2.absdiff(ref, cam)
    diff[diff < 40] = 0  # ignore les petits ecarts
    return 100.0 * np.count_nonzero(diff) / diff.size


def run(bw_ref):
    """Cycle complet de verification."""
    frame = capture()
    if frame is None:
        return {"ok": False,
                "error": "camera XC-56 inaccessible (frame grabber / CAM_INDEX)"}

    bw_cam = step1_bw.to_bw(frame)
    err = error_rate(bw_ref, bw_cam)

    if err < config.ERROR_THRESHOLD_PCT:
        return {"ok": True, "error_pct": round(err, 2), "corrected": False,
                "verdict": "CONFORME (" + str(round(err, 2)) + " %)"}

    # Ecart >= seuil : on recalcule les trajectoires depuis la photo
    trajs = step2_contours.extract(bw_cam)
    result = {"ok": True, "error_pct": round(err, 2), "corrected": False,
              "verdict": "ECART DETECTE (" + str(round(err, 2)) + " %)",
              "trajectories": len(trajs),
              "points": sum(len(t) for t in trajs)}

    # Autorisation S7-1500 obligatoire avant tout envoi au robot
    if not plc.is_authorized():
        result["blocked_by_plc"] = True
        result["verdict"] += " - ENVOI BLOQUE PAR LA S7-1500"
        return result

    result["corrected"] = True
    result["robot"] = step3_ascii.send_path(trajs)
    result["verdict"] += " - trajectoires corrigees envoyees"
    return result
