"""
Entry point for the legacy module (face + head + voice).

Run this script while SuperTuxKart is open and in foreground.
Ctrl+C in terminal (or 'q' in debug window) to stop cleanly.
"""

import time

from input_controller import KeyboardController
from face_module import FaceWorker
from voice_module import VoiceWorker


def main():
    controller = KeyboardController()
    face_worker = FaceWorker(controller)
    voice_worker = VoiceWorker(controller)

    print("Starting face + voice modules... (Ctrl+C to stop)")
    face_worker.start()
    voice_worker.start()

    try:
        while face_worker.is_alive():
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    finally:
        face_worker.stop()
        voice_worker.stop()
        face_worker.join(timeout=2)
        voice_worker.join(timeout=2)
        controller.release_all()
        print("Clean shutdown, no keys left pressed.")


if __name__ == "__main__":
    main()
