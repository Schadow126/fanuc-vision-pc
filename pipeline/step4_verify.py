# -*- coding: utf-8 -*-
"""
CODE 4 - step4_verify.py
Recupere la photo de la caméra Sony XC-56 (via frame grabber / VideoCapture),
la compare a l'image traitee (reference noir et blanc), calcule le taux
d'erreur, et si taux >= ERROR_LIMIT_PCT (10 % par defaut) recree les points
et trajectoires avec les corrections, puis les renvoie au CODE 3 (ASCII ->
R-30iB Mate) UNIQUEMENT si le S7-1500 autorise l'envoi.

Entree : work/bw.png, work/points.json, camera XC-56 (CAMERA_INDEX)
Sortie : work/camera.png, taux d'erreur, points corriges, envoi eventuel
"""

import cv2
import numpy as np
from pathlib import Path
from . import step3_ascii


def grab_camera(camera_index, out_path):
    """Capture une image de la XC-56 (frame grabber vu par OpenCV)."""
    cap = cv2.VideoCapture(camera_index)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise RuntimeError("camera XC-56 injoignable (index " + str(camera_index) + ")")
    cv2.imwrite(str(out_path), frame)
    return str(out_path)


def _to_binary(img):
    """Image quelconque -> binaire nette (Otsu)."""
    if img.ndim == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    img = cv2.resize(img, (1000, 1000))
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    _, b = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return b


def compare(bw_path, camera_path):
    """Taux d'erreur en % entre reference N&B et photo camera."""
    ref = cv2.imread(str(bw_path), cv2.IMREAD_GRAYSCALE)
    cam = cv2.imread(str(camera_path), cv2.IMREAD_GRAYSCALE)
    if ref is None or cam is None:
        raise RuntimeError("image de comparaison introuvable")
    refb = _to_binary(ref)
    camb = _to_binary(cam)
    diff = cv2.absdiff(refb, camb)
    error_rate = float(np.count_nonzero(diff > 127)) / float(diff.size) * 100.0
    return round(error_rate, 2)


def correction_offset_mm(bw_path, camera_path, scale_mm_per_px):
    """
    Calcule la correction : deplacement du centroide des objets entre
    l'image de reference et la photo camera (pour une correction simple
    de translation X/Y).
    """
    ref = _to_binary(cv2.imread(str(bw_path), cv2.IMREAD_GRAYSCALE))
    cam = _to_binary(cv2.imread(str(camera_path), cv2.IMREAD_GRAYSCALE))

    def centroid_mass(binary):
        inv = 255 - binary                     # objets sombres
        m = cv2.moments(inv, binaryImage=True)
        if m["m00"] == 0:
            return None
        return (m["m10"] / m["m00"], m["m01"] / m["m00"])

    c_ref = centroid_mass(ref)
    c_cam = centroid_mass(cam)
    if c_ref is None or c_cam is None:
        return 0.0, 0.0
    dx_px = c_cam[0] - c_ref[0]                 # camera vs reference
    dy_px = c_cam[1] - c_ref[1]
    dx_mm = -dx_px * scale_mm_per_px            # correction = -l'erreur
    dy_mm = +dy_px * scale_mm_per_px            # axe image y inverse
    return round(dx_mm, 3), round(dy_mm, 3)


def apply_offset(points_data, dx_mm, dy_mm):
    """Recreer les points/trajectoires avec la correction appliquee."""
    corrected = {
        "trajectories": [],
        "scale_mm_per_px": points_data.get("scale_mm_per_px"),
        "z_mm": points_data.get("z_mm"),
        "correction": {"dx_mm": dx_mm, "dy_mm": dy_mm},
    }
    for traj in points_data.get("trajectories", []):
        pts = []
        for pt in traj["points"]:
            pts.append([round(pt[0] + dx_mm, 3), round(pt[1] + dy_mm, 3),
                        pt[2], pt[3], pt[4], pt[5]])
        corrected["trajectories"].append({"id": traj["id"], "points": pts})
    return corrected


def run(bw_path, camera_index, work_dir, points_json,
        robot_ip, robot_port, error_limit, is_authorized,
        scale_mm_per_px, timeout=5.0):
    """Sequence complete du CODE 4."""
    work_dir = Path(work_dir)
    cam_path = work_dir / "camera.png"

    grab_camera(camera_index, cam_path)
    error_rate = compare(bw_path, cam_path)

    result = {"error_rate": error_rate, "limit": error_limit,
              "camera_url": "files/camera.png"}

    if error_rate < error_limit:
        result["action"] = "aucune correction : taux < limite"
        return result

    # Taux >= limite : recreer les points avec les corrections
    points_data = Path(points_json).read_text(encoding="utf-8")
    import json
    points_data = json.loads(points_data)
    dx_mm, dy_mm = correction_offset_mm(bw_path, cam_path, scale_mm_per_px)
    corrected = apply_offset(points_data, dx_mm, dy_mm)
    (work_dir / "points_corrected.json").write_text(
        json.dumps(corrected, indent=2), encoding="utf-8")
    result["corrected"] = {"dx_mm": dx_mm, "dy_mm": dy_mm}
    result["points_file"] = "points_corrected.json"

    # Renvoi au CODE 3 seulement si le S7-1500 autorise l'envoi
    if is_authorized():
        send = step3_ascii.send_all(corrected, robot_ip, robot_port, timeout)
        result["action"] = "points corriges et renvoyes au robot"
        result["resent"] = send["sent"]
    else:
        result["action"] = "points corriges mais envoi BLOQUE par le S7-1500"
        result["resent"] = 0
        result["blocked_by"] = "S7-1500"
    return result
