"""
Point d'entrée du module "collaboratif" (visage + tête/corps + voix).

Lance ce script pendant que SuperTuxKart est ouvert et au premier plan.
Ctrl+C dans le terminal (ou 'q' dans la fenêtre de debug) pour arrêter
proprement.
"""

import time

from input_controller import KeyboardController
from face_module import FaceWorker
from voice_module import VoiceWorker


def main():
    controller = KeyboardController()
    face_worker = FaceWorker(controller)
    voice_worker = VoiceWorker(controller)

    print("Démarrage du visage + de la voix... (Ctrl+C pour arrêter)")
    face_worker.start()
    voice_worker.start()

    try:
        while face_worker.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nArrêt demandé...")
    finally:
        face_worker.stop()
        voice_worker.stop()
        face_worker.join(timeout=2)
        voice_worker.join(timeout=2)
        controller.release_all()
        print("Arrêt propre, aucune touche laissée enfoncée.")


if __name__ == "__main__":
    main()
