#!/usr/bin/env python3
"""Suivi de plusieurs visages a la webcam, avec Mediapipe FaceLandmarker.

Rend, pour chaque visage vu, ce dont le jeu a besoin :

    x        position horizontale du visage dans l'image, de 0 a 1
    roulis   inclinaison de la tete en degres (tete penchee vers l'epaule)
    formes   les scores d'expression : sourire, bouche ouverte...
    boite    le rectangle du visage, pour le dessiner

Pourquoi ne pas reutiliser face_module.py du depot de l'equipe
--------------------------------------------------------------
Il est fige a UN visage (num_faces=1, en dur dans son code, pas dans son
config), et le volet collaboratif en demande trois. Il decompose aussi la
matrice de transformation pour obtenir les angles, ce qui n'est pas necessaire
ici : le roulis se lit directement sur la droite qui joint les deux yeux.

Le roulis, calcule et non recu
------------------------------
Le point 33 est le coin externe d'un oeil, le 263 celui de l'autre, dans le
maillage a 478 points de Mediapipe. L'angle de la droite qui les joint EST le
roulis de la tete. Meme raisonnement qu'au TP1 pour le volant du telephone :
un angle qu'on calcule a partir de deux points qu'on voit ne derive pas et ne
connait pas de blocage de cardan, contrairement a un angle qu'on nous donne.
"""

import math
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import config_collab as cfg

OEIL_A = 33      # coin externe d'un oeil
OEIL_B = 263     # coin externe de l'autre


def angle_ligne(dx, dy):
    """Angle d'une DROITE non orientee, en degres, ramene dans (-90, +90].

    Pourquoi pas simplement atan2
    -----------------------------
    Une droite et son opposee sont la meme droite : une tete droite mesure 0
    degre, qu'on aille de l'oeil gauche vers le droit ou l'inverse. atan2, lui,
    rend 0 dans un sens et 180 dans l'autre.

    Et 180, c'est exactement la coupure de atan2. Mesure faite le 2026-09-22 :
    avec l'image en miroir, une tete au repos tombait pile sur cette coupure,
    et deux poses ecartees de 20 degres donnaient un ecart calcule de -340
    degres. Le kart braquait a fond sur un mouvement de tete anodin.

    Ramener l'angle dans (-90, +90] supprime le probleme a la racine : le repos
    est a 0, loin de toute coupure, et une tete ne penche de toute facon jamais
    au-dela de 90 degres.
    """
    a = math.degrees(math.atan2(dy, dx))
    while a > 90.0:
        a -= 180.0
    while a <= -90.0:
        a += 180.0
    return a


class Visage:
    """Un visage vu sur une image, reduit a ce qui sert au jeu."""

    def __init__(self, x, y, roulis, formes, boite):
        self.x = x                # 0 = bord gauche de l'image, 1 = bord droit
        self.y = y
        self.roulis = roulis      # degres
        self.formes = formes      # {nom: score}
        self.boite = boite        # (x1, y1, x2, y2) en pixels

    def forme(self, nom):
        return self.formes.get(nom, 0.0)


class SuiviVisages:
    """Ouvre la webcam et rend la liste des visages vus, image par image."""

    def __init__(self):
        self.capture = None
        self.detecteur = None
        self.largeur = cfg.CAMERA_LARGEUR
        self.hauteur = cfg.CAMERA_HAUTEUR
        # Mediapipe exige des horodatages STRICTEMENT croissants. Les compter
        # en millisecondes d'horloge en repete un des que deux images tombent
        # dans la meme milliseconde, et la detection leve une exception -- le
        # bug rencontre dans le module de l'equipe. Un simple compteur ne peut
        # pas avoir ce probleme.
        self._horodatage = 0

    def demarrer(self):
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=cfg.MODELE_VISAGE),
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False,
            running_mode=vision.RunningMode.VIDEO,
            num_faces=3,
        )
        self.detecteur = vision.FaceLandmarker.create_from_options(options)

        self.capture = cv2.VideoCapture(cfg.CAMERA_INDEX, cv2.CAP_DSHOW)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.CAMERA_LARGEUR)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.CAMERA_HAUTEUR)
        if not self.capture.isOpened():
            raise RuntimeError('Impossible d ouvrir la camera %d.' % cfg.CAMERA_INDEX)

        self.largeur = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.hauteur = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return self

    def lire(self):
        """Une image et les visages qu'elle contient. Rend (image, [Visage])."""
        ok, image = self.capture.read()
        if not ok:
            return None, []

        # Miroir : chacun se voit comme dans une glace, donc "le joueur de
        # gauche" est bien celui que les joueurs appellent gauche. Le retournement
        # se fait AVANT la detection, pour que les x rendus soient deja les bons.
        if cfg.MIROIR:
            image = cv2.flip(image, 1)

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self._horodatage += 1
        resultat = self.detecteur.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
            self._horodatage)

        visages = []
        for i, points in enumerate(resultat.face_landmarks):
            formes = {}
            if i < len(resultat.face_blendshapes):
                formes = {c.category_name: c.score
                          for c in resultat.face_blendshapes[i]}
            visages.append(self._construire(points, formes, image.shape))
        return image, visages

    def _construire(self, points, formes, forme_image):
        h, l = forme_image[0], forme_image[1]

        xs = [p.x for p in points]
        ys = [p.y for p in points]
        boite = (int(min(xs) * l), int(min(ys) * h),
                 int(max(xs) * l), int(max(ys) * h))

        a, b = points[OEIL_A], points[OEIL_B]
        # Les coordonnees sont normalisees chacune par SA dimension : les
        # multiplier par la largeur et la hauteur avant l'atan2, sinon l'angle
        # est fausse par le rapport d'image (ici 16/9, soit 78 % d'erreur).
        dx = (b.x - a.x) * l
        dy = (b.y - a.y) * h
        roulis = angle_ligne(dx, dy)

        # Le retournement miroir inverse le signe de l'angle. On le compense
        # ici pour que MIROIR reste un reglage unique, qui ne touche qu'a
        # l'aspect de l'image : sans ca, changer MIROIR obligerait a changer
        # SENS_ROULIS en meme temps, et on ne s'en souvient jamais.
        if cfg.MIROIR:
            roulis = -roulis

        roulis *= cfg.SENS_ROULIS

        return Visage(x=float(np.mean(xs)), y=float(np.mean(ys)),
                      roulis=roulis, formes=formes, boite=boite)

    def arreter(self):
        if self.capture is not None:
            self.capture.release()
        if self.detecteur is not None:
            self.detecteur.close()
