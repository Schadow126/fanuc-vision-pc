# -*- coding: utf-8 -*-
"""
CODE 4 - Verification camerea Sony XC-56 et correction.

Recupere une photo de la camera Sony XC-56 (analogique -> frame grabber,
peripherique video index CAM_INDEX), la traite comme le code 1, la compare
pixel a pixel avec l'image de reference traitee, et :

  - taux d'erreur < 10 %  -> rien a faire, piece conforme ;
  - taux d'erreur >= 10 % -> regenere les points et trajectoires depuis la
    photo de la camera, PUIS verifie l'autorisation de la S7-1500 :
      - autorisee  -> envoie les trajectoires corrigees au code 3 ;
      - refusee    -> blocage, l'envoi sera retente au prochain appel.
"""
import cv2
import numpy as np

import config
import plc
import step1_bw
import step2_contours
import step3_ascii


def capture(index=None):
    """Prend une photo avec la camera (retourne une image BGR ou None)."""
    idx = config.CAM_INDEX if index is None else index
    cap = cv2.VideoCapture(idx)
    if not cap.isOpened():
        return None
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def error_rate(bw_ref, bw_cam):
    """Taux d'erreur en % entre deux images binaires (0 = identiques)."""
    if bw_cam.shape != bw_ref.shape:
        bw_cam = cv2.resize(bw_cam, (bw_ref.shape[1], bw_ref.shape[0]))
    diff = cv2.absdiff(bw_ref, bw_cam)
    _, diff = cv2.threshold(diff, 40, 255, cv2.THRESH_BINARY)
    return 100.0 * float(np.count_nonzero(diff)) / float(diff.size)


def run(bw_ref):
    """Cycle complet de verification. Renvoie un dictionnaire de resultat."""
    frame = capture()
    if frame is None:
        return {"ok": False, "error": "camera XC-56 inaccessible "
                                      "(verifier le frame grabber / CAM_INDEX)"}
    bw_cam = step1_bw.to_bw(frame)
    err = error_rate(bw_ref, bw_cam)
    result = {"ok": True, "error_pct": round(err, 2), "corrected": False}

    if err < config.ERROR_THRESHOLD_PCT:
        result["verdict"] = "CONFORME (erreur " + str(round(err, 2)) + " % < " +                             str(config.ERROR_THRESHOLD_PCT) + " %)"
        return result

    # Ecart >= seuil : on regenere les trajectoires depuis la photo camera
    result["verdict"] = "ECART DETECTE (" + str(round(err, 2)) + " % >= " +                         str(config.ERROR_THRESHOLD_PCT) + " %)"
    trajs = step2_contours.extract(
        bw_cam, config.SCALE_MM_PER_PX, config.Z_MM,
        config.W_DEG, config.P_DEG, config.R_DEG, config.MIN_AREA_PX)
    result["trajs"] = len(trajs)
    result["points"] = sum(len(t) for t in trajs)

    # Autorisation S7-1500 obligatoire avant tout envoi au robot
    if not plc.is_authorized():
        result["blocked_by_plc"] = True
        result["verdict"] += " - ENVOI BLOQUE PAR LA S7-1500"
        return result

    replies = step3_ascii.send_path(trajs, config.ROBOT_IP, config.ROBOT_PORT)
    result["corrected"] = True
    result["robot"] = replies
    result["verdict"] += " - trajectoires corrigees envoyees"
    return result
