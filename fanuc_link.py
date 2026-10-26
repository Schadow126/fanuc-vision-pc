"""
fanuc_link.py - liaison socket TCP avec le controleur FANUC (KAREL Socket Messaging).

Protocole ASCII (chaque ligne terminee par CR, cf. ATR_EOL = 13) :

    ROBOT -> PC    : "TAKE_PHOTO\r"      demande de cycle vision
    PC    -> ROBOT : "X Y Z W P R\r"     point corrige (mm / degres, UFRAME)
    ROBOT -> PC    : "ACK\r"             accuse de reception
    PC    -> ROBOT : "ERROR msg\r"       en cas d'echec (le KAREL rendra NOK au PLC)

Le robot est CLIENT (tag C2, protocole SM) ; le PC est SERVEUR.
"""
import logging
import socket
from typing import Callable

import config

log = logging.getLogger("fanuc_link")


class FanucLink:
    """Serveur TCP mono-client pour le controleur FANUC."""

    def __init__(self) -> None:
        self._srv: socket.socket | None = None
        self._conn: socket.socket | None = None

    # ------------------------------------------------------------- serveur
    def start(self) -> None:
        """Ouvre le port d'ecoute."""
        self._srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._srv.bind((config.ROBOT_HOST, config.ROBOT_PORT))
        self._srv.listen(1)
        log.info("Serveur en ecoute sur le port %d", config.ROBOT_PORT)

    def wait_robot(self) -> socket.socket:
        """Attend la connexion du robot et retourne le socket."""
        assert self._srv is not None, "start() doit etre appele avant"
        log.info("Attente de connexion du robot...")
        conn, addr = self._srv.accept()
        conn.settimeout(config.SOCKET_TIMEOUT_S)
        log.info("Robot connecte depuis %s", addr)
        self._conn = conn
        return conn

    # ---------------------------------------------------------- trames I/O
    def _read_line(self) -> str:
        """Lit une ligne terminee par CR depuis le robot."""
        buf = b""
        assert self._conn is not None
        while not buf.endswith(config.TERMINATOR):
            chunk = self._conn.recv(64)
            if not chunk:
                raise ConnectionError("Le robot a ferme la connexion")
            buf += chunk
        return buf.decode("ascii").strip()

    def _send_line(self, text: str) -> None:
        """Envoie une ligne terminee par CR au robot."""
        assert self._conn is not None
        self._conn.sendall(text.encode("ascii") + config.TERMINATOR)

    # ------------------------------------------------------------- cycle
    def run_cycle(self, photo_and_compute: Callable[[], tuple] | None,
                  on_result: Callable[[bool, str], None]) -> None:
        """
        Boucle d'echange pour une connexion :
        attend TAKE_PHOTO -> execute la vision -> renvoie le point ou ERROR -> attend ACK.
        """
        while True:
            try:
                line = self._read_line()
            except (ConnectionError, socket.timeout):
                log.warning("Connexion robot perdue")
                return

            if line != "TAKE_PHOTO":
                log.warning("Trame inattendue du robot : %r", line)
                continue

            log.info("Demande de photo recue du robot")
            point = photo_and_compute()  # capture + comparaison -> (x,y,z,w,p,r)

            if point is None:
                self._send_line("ERROR vision")
                on_result(False, "echec de la vision (piece non detectee / correlation faible)")
            else:
                trame = " ".join("%.3f" % v for v in point)
                self._send_line(trame)
                ack = self._read_line()
                ok = ack == "ACK"
                on_result(ok, trame if ok else "pas d'accuse robot (%r)" % ack)

    def stop(self) -> None:
        for s in (self._conn, self._srv):
            if s is not None:
                try:
                    s.close()
                except OSError:
                    pass
