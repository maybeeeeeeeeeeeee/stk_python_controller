"""
Module "visage" : webcam + Mediapipe Face Landmarker.

Détecte :
- le sourire (continu)          -> Accelerate
- la bouche grande ouverte      -> Fire (impulsion)
- les sourcils levés (option)   -> Turbo (impulsion)
- un clin d'œil gauche/droit    -> Left/Right (continu, assistance)
- la tête tournée               -> Look back (continu)
- un hochement de tête bref     -> Rescue (impulsion)

Lance ce module dans un thread séparé, il ne fait qu'appeler les méthodes
du KeyboardController partagé.
"""

import math
import threading
import time

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import config


def _blendshape_dict(result) -> dict:
    """Transforme la sortie brute de Mediapipe en dict {nom: score}."""
    if not result.face_blendshapes:
        return {}
    return {c.category_name: c.score for c in result.face_blendshapes[0]}


def _yaw_pitch_from_matrix(matrix) -> tuple[float, float]:
    """
    Extrait yaw/pitch (en degrés) approximatifs à partir de la matrice de
    transformation faciale renvoyée par Mediapipe.

    Décomposition heuristique, suffisante pour du seuillage. Si les valeurs
    te paraissent inversées en testant (DEBUG_WINDOW=True), inverse le
    signe correspondant plus bas.
    """
    r = np.array(matrix).reshape(4, 4)[:3, :3]
    pitch = math.degrees(math.atan2(-r[2, 0], math.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)))
    yaw = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return yaw, pitch


class _NodDetector:
    """Détecte un hochement de tête bref: le pitch descend puis remonte vite."""

    def __init__(self, dip_threshold_deg: float, max_duration_s: float):
        self.dip_threshold_deg = dip_threshold_deg
        self.max_duration_s = max_duration_s
        self._dip_start = None

    def update(self, pitch_deg: float) -> bool:
        """Retourne True au moment exact où un hochement complet est détecté."""
        now = time.monotonic()
        if pitch_deg < -self.dip_threshold_deg:
            if self._dip_start is None:
                self._dip_start = now
        else:
            if self._dip_start is not None:
                duration = now - self._dip_start
                self._dip_start = None
                if duration <= self.max_duration_s:
                    return True
        return False


class FaceWorker(threading.Thread):
    def __init__(self, controller):
        super().__init__(daemon=True)
        self._controller = controller
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        base_options = mp_python.BaseOptions(model_asset_path=config.FACE_MODEL_PATH)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
        )
        landmarker = vision.FaceLandmarker.create_from_options(options)

        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)

        nod_detector = _NodDetector(config.NOD_PITCH_DIP_DEG, config.NOD_MAX_DURATION_S)
        start_time = time.monotonic()

        try:
            while not self._stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    continue

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                timestamp_ms = int((time.monotonic() - start_time) * 1000)
                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                shapes = _blendshape_dict(result)
                if shapes:
                    self._process_expressions(shapes)

                if result.facial_transformation_matrixes:
                    yaw, pitch = _yaw_pitch_from_matrix(
                        result.facial_transformation_matrixes[0]
                    )
                    self._process_head_pose(yaw, pitch, nod_detector)

                if config.DEBUG_WINDOW:
                    self._draw_debug(frame, shapes)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break
        finally:
            cap.release()
            if config.DEBUG_WINDOW:
                cv2.destroyAllWindows()

    # -- Traitement des expressions -----------------------------------------------------
    def _process_expressions(self, shapes: dict):
        smile = (shapes.get("mouthSmileLeft", 0) + shapes.get("mouthSmileRight", 0)) / 2
        active = smile > config.SMILE_ENGAGE
        inactive = smile < config.SMILE_RELEASE
        if active:
            self._controller.set_continuous("accelerate", "face_smile", True)
        elif inactive:
            self._controller.set_continuous("accelerate", "face_smile", False)

        if shapes.get("jawOpen", 0) > config.JAW_OPEN_THRESHOLD:
            self._controller.pulse("fire", config.JAW_OPEN_COOLDOWN_S)

        if config.EYEBROW_ENABLED:
            brow = (
                shapes.get("browOuterUpLeft", 0) + shapes.get("browOuterUpRight", 0)
            ) / 2
            if brow > config.EYEBROW_THRESHOLD:
                self._controller.pulse("turbo", config.EYEBROW_COOLDOWN_S)

        blink_l = shapes.get("eyeBlinkLeft", 0)
        blink_r = shapes.get("eyeBlinkRight", 0)

        wink_left = blink_l > config.WINK_LEFT_ENGAGE and blink_r < config.WINK_LEFT_RELEASE_OTHER_EYE
        wink_right = blink_r > config.WINK_RIGHT_ENGAGE and blink_l < config.WINK_RIGHT_RELEASE_OTHER_EYE

        self._controller.set_continuous("left", "face_wink", wink_left)
        self._controller.set_continuous("right", "face_wink", wink_right)

    # -- Traitement de l'orientation de la tête ------------------------------------------
    def _process_head_pose(self, yaw_deg: float, pitch_deg: float, nod_detector: _NodDetector):
        turned = abs(yaw_deg) > config.LOOK_BACK_YAW_THRESHOLD_DEG
        self._controller.set_continuous("look_back", "head_yaw", turned)

        if nod_detector.update(pitch_deg):
            self._controller.pulse("rescue", config.RESCUE_COOLDOWN_S)

    # -- Fenêtre de debug pour la calibration --------------------------------------------
    def _draw_debug(self, frame, shapes: dict):
        y = 20
        for name in (
            "mouthSmileLeft",
            "mouthSmileRight",
            "jawOpen",
            "browOuterUpLeft",
            "browOuterUpRight",
            "eyeBlinkLeft",
            "eyeBlinkRight",
        ):
            value = shapes.get(name, 0.0)
            cv2.putText(
                frame, f"{name}: {value:.2f}", (10, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
            )
            y += 18
        cv2.imshow("Debug visage (q pour quitter)", frame)
