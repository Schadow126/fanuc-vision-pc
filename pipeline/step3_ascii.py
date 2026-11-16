# -*- coding: utf-8 -*-
"""
CODE 3 - Export du dessin vers le R-30iB Mate par FICHIER (option A).

Le controleur n'a pas l'option User Socket Messaging (R648) : pas de
socket KAREL. Le PC ecrit DESSIN.TXT puis le depose sur le controleur :

  - TRANSPORT=usb : le fichier est copie sur une cle USB (USB_PATH),
    a brancher ensuite sur le port USB du controleur (peripherique
    UD1:) ;
  - TRANSPORT=ftp : le fichier est depose par FTP sur le controleur
    (il arrive alors dans MD: ; remplacer UD1: par MD: dans le
    recv_path.kl).

FORMAT DE DESSIN.TXT (ASCII, unites en mm, lignes separees par CR+LF) :

    ligne 1                  : nombre de trajectoires
    pour chaque trajectoire :
        1 ligne              : nombre de points du lot
        n lignes             : "X Y Z W P R"

Chaque lot est AUTONOME : un point AU-DESSUS du premier point de trace
(Z_TRAVEL_MM, stylo leve), les points de trace, puis un point de
remontee a Z_TRAVEL_MM. Le programme TP (karel/MAIN) charge un lot par
CALL RECV_PATH et le trace d'une seule trajectoire continue : le stylo
se leve tout seul entre deux formes, sans trait de liaison.
"""
import shutil
from pathlib import Path

import config


def _fmt(pt):
    return "{:.2f} {:.2f} {:.2f} {:.1f} {:.1f} {:.1f}".format(
        pt["x"], pt["y"], pt["z"], pt["w"], pt["p"], pt["r"])


def lots_for(trajs):
    """Chaque trajectoire -> lot autonome : approche + trace + remontee."""
    lots = []
    for traj in trajs:
        trace = list(traj["points"])
        if not trace:
            continue
        haut_debut = dict(trace[0]); haut_debut["z"] = config.Z_TRAVEL_MM
        haut_fin = dict(trace[-1]); haut_fin["z"] = config.Z_TRAVEL_MM
        lots.append([haut_debut] + trace + [haut_fin])
    return lots


def dessin_txt(trajs):
    """Construit le contenu ASCII complet de DESSIN.TXT."""
    lots = lots_for(trajs)
    lignes = [str(len(lots))]
    for lot in lots:
        lignes.append(str(len(lot)))
        lignes.extend(_fmt(p) for p in lot)
    return "\r\n".join(lignes) + "\r\n"


frame_for = dessin_txt  # compatibilite : ancien nom de la fonction


def _depose_ftp(chemin):
    """Depose le fichier par FTP sur le controleur (il arrive dans MD:)."""
    import ftplib
    ftp = ftplib.FTP(config.ROBOT_IP, timeout=config.SOCKET_TIMEOUT)
    try:
        ftp.login(config.FTP_USER, config.FTP_PASS)
        with open(chemin, "rb") as f:
            ftp.storbinary("STOR " + config.DESSIN_FILE, f)
    finally:
        ftp.quit()


def send_path(trajs):
    """Genere DESSIN.TXT puis le depose (usb ou ftp) ; message de retour."""
    fichier = Path(config.EXPORT_DIR) / config.DESSIN_FILE
    fichier.parent.mkdir(parents=True, exist_ok=True)
    fichier.write_bytes(dessin_txt(trajs).encode("ascii"))
    if config.DEMO:
        return "DEMO : " + str(fichier) + " genere (pas de depot)"
    try:
        if config.TRANSPORT == "ftp":
            _depose_ftp(str(fichier))
            return ("DESSIN.TXT depose par FTP sur " + config.ROBOT_IP
                    + " (fichier dans MD:)")
        if config.TRANSPORT == "usb":
            cible = Path(config.USB_PATH) / config.DESSIN_FILE
            shutil.copyfile(str(fichier), str(cible))
            return (str(cible) + " pret : brancher la cle sur le port USB "
                    "du controleur (UD1:)")
        return str(fichier) + " genere (TRANSPORT inconnu : " + config.TRANSPORT + ")"
    except OSError:
        raise
    except Exception as exc:  # ftplib etc. -> meme type d'erreur pour app.py
        raise OSError(str(exc))
