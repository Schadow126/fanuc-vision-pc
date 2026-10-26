"""
main.py - point d'entree du PC vision.

Usage :
    python main.py                 # cycle normal : serveur socket + vision
    python main.py --save-ref      # enregistre l'image de reference (robot en position parfaite)
"""
import logging
import signal
import sys
from datetime import datetime

from fanuc_link import FanucLink
from vision_processing import Vision

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s : %(message)s",
)
log = logging.getLogger("main")


def main() -> int:
    vision = Vision()

    if "--save-ref" in sys.argv:
        vision.save_reference()
        return 0

    link = FanucLink()
    link.start()

    def photo_and_compute():
        """Appele a chaque TAKE_PHOTO du robot."""
        try:
            offset = vision.compute_offset(vision.grab())
            if offset is None:
                return None
            return vision.build_point(offset)
        except Exception as exc:  # on rend NOK au robot quoi qu'il arrive
            log.error("Erreur vision : %s", exc)
            return None

    def on_result(ok: bool, detail: str) -> None:
        verdict = "OK" if ok else "NOK"
        log.info("Resultat %s - %s", verdict, detail)
        with open("cycle_log.csv", "a", encoding="utf-8") as f:
            f.write("%s,%s,%s\n" % (datetime.now().isoformat(), verdict, detail))

    def _shutdown(signum, _frame):
        log.info("Signal %s recu - arret", signum)
        link.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while True:
        link.wait_robot()
        try:
            link.run_cycle(photo_and_compute, on_result)
        except Exception as exc:
            log.error("Erreur liaison : %s", exc)
        finally:
            link.stop()
            link.start()  # re-arme le serveur pour la connexion suivante


if __name__ == "__main__":
    sys.exit(main())
