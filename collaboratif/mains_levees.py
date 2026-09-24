#!/usr/bin/env python3
"""mains_levees.py -- Sauvetage collectif : 3 joueurs, 6 mains levees.

Reutilise la MEME image que suivi_visages.py -- pas de deuxieme camera a
brancher. Les 3 joueurs sont deja dans le champ pour la direction ; pour le
sauvetage, on y fait tourner en plus un PoseLandmarker (corps entier, jusqu'a
3 personnes) pour compter les mains levees au-dessus des epaules.

    RESCUE se declenche quand les 3 joueurs ont les 2 mains levees EN MEME
    TEMPS (6 mains au total), tenu un court instant. Meme regle que pour la
    direction : personne ne peut se sauver seul.

Pourquoi un maintien, pas un simple seuil instantane
-----------------------------------------------------
Un passage furtif a 6 mains levees (quelqu'un qui s'etire, qui replace ses
cheveux en meme temps qu'un genou qui remonte) ne doit pas declencher un
sauvetage. Exiger que la pose soit tenue force un geste VOULU par les trois.
"""

import time

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

import config_collab as cfg
from mains_sur_tete import main_pres_de_la_tete

# Topologie BlazePose (33 points), la meme que Mediapipe Pose Landmarker.
EPAULE_GAUCHE, EPAULE_DROITE = 11, 12
POIGNET_GAUCHE, POIGNET_DROIT = 15, 16


def _main_levee(poignet, epaule, marge):
    """Une main compte comme levee si son poignet depasse nettement son
    epaule (plus haut dans l'image), et si Mediapipe voit les deux points
    avec assez de confiance."""
    if poignet.visibility < cfg.MAINS_VISIBILITE_MINI:
        return False
    if epaule.visibility < cfg.MAINS_VISIBILITE_MINI:
        return False
    return poignet.y < (epaule.y - marge)


def _mains_levees_une_personne(points, marge, largeur, hauteur):
    """0, 1 ou 2 mains levees pour une personne detectee.

    Une main posee sur la tete est aussi au-dessus de l'epaule, mais c'est le
    geste du FREIN (mains_sur_tete.py), pas celui du sauvetage : sans cette
    exclusion, paniquer declencherait un sauvetage. Seuls comptent les bras
    tendus vers le haut, loin de la tete.
    """
    n = 0
    for idx_poignet, idx_epaule in ((POIGNET_GAUCHE, EPAULE_GAUCHE),
                                    (POIGNET_DROIT, EPAULE_DROITE)):
        poignet = points[idx_poignet]
        if (_main_levee(poignet, points[idx_epaule], marge)
                and not main_pres_de_la_tete(points, poignet, largeur, hauteur)):
            n += 1
    return n


class _DetecteurMaintien:
    """Declenche une seule fois quand une condition reste vraie sans
    interruption pendant `maintien_s`."""

    def __init__(self, maintien_s):
        self.maintien_s = maintien_s
        self._debut = None
        self._declenche = False

    def observer(self, condition, maintenant):
        if not condition:
            self._debut = None
            self._declenche = False
            return False
        if self._debut is None:
            self._debut = maintenant
        if not self._declenche and (maintenant - self._debut) >= self.maintien_s:
            self._declenche = True
            return True
        return False

    def progression(self, maintenant):
        """0.0 a 1.0 : a quel point on est pres de declencher. Pour la
        fenetre de debug."""
        if self._debut is None:
            return 0.0
        return min(1.0, (maintenant - self._debut) / self.maintien_s)


class MainsLevees:
    """Compte les mains levees sur la MEME image que SuiviVisages."""

    def __init__(self):
        self.detecteur = None
        self._maintien = _DetecteurMaintien(cfg.MAINS_MAINTIEN_S)
        self._horodatage = 0
        self.dernier_compte = 0
        self.dernier_nombre_personnes = 0
        # Les poses de la derniere image traitee. six_sept.py les relit pour
        # reconnaitre le geste d'acceleration : un seul PoseLandmarker pour
        # les deux gestes, pas de calcul en double.
        self.dernieres_poses = []

    def demarrer(self):
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=cfg.MODELE_POSE),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=3,
            min_pose_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.detecteur = vision.PoseLandmarker.create_from_options(options)
        return self

    def traiter(self, image_bgr, maintenant):
        """image_bgr : la MEME image (deja retournee en miroir si besoin) que
        rend suivi.lire(). Rend True exactement au moment du declenchement."""
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        self._horodatage += 1
        resultat = self.detecteur.detect_for_video(
            mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
            self._horodatage)

        self.dernieres_poses = list(resultat.pose_landmarks)
        h, l = image_bgr.shape[:2]
        comptes = [_mains_levees_une_personne(pose, cfg.MAINS_MARGE, l, h)
                   for pose in resultat.pose_landmarks]
        total = sum(comptes)
        self.dernier_compte = total
        self.dernier_nombre_personnes = len(comptes)

        condition = total >= cfg.MAINS_REQUISES
        return self._maintien.observer(condition, maintenant)

    def progression(self, maintenant):
        return self._maintien.progression(maintenant)

    def arreter(self):
        if self.detecteur is not None:
            self.detecteur.close()


# --------------------------------------------------------------------- test isole

def _dessiner_debug(image_bgr, resultat, comptes, progression):
    """Squelette + confiance de chaque point, pour voir CE QUE Mediapipe voit
    reellement : combien de personnes, et pourquoi telle main ne compte pas
    (pas assez levee, ou point pas assez visible)."""
    h, l = image_bgr.shape[:2]

    for i, pose in enumerate(resultat.pose_landmarks):
        for idx in (EPAULE_GAUCHE, EPAULE_DROITE):
            p = pose[idx]
            cv2.circle(image_bgr, (int(p.x * l), int(p.y * h)), 6, (255, 200, 0), -1)

        for idx_poignet, idx_epaule in ((POIGNET_GAUCHE, EPAULE_GAUCHE),
                                         (POIGNET_DROIT, EPAULE_DROITE)):
            poignet = pose[idx_poignet]
            levee = _main_levee(poignet, pose[idx_epaule], cfg.MAINS_MARGE)
            couleur = (0, 0, 255) if levee else (0, 255, 0)
            centre = (int(poignet.x * l), int(poignet.y * h))
            cv2.circle(image_bgr, centre, 8, couleur, -1)
            cv2.putText(image_bgr, 'vis=%.2f' % poignet.visibility,
                        (centre[0] + 10, centre[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, couleur, 1)

        cv2.putText(image_bgr, 'personne %d : %d main(s)' % (i + 1, comptes[i]),
                    (10, 25 + i * 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

    total = sum(comptes)
    besoin = cfg.MAINS_REQUISES
    couleur_total = (0, 0, 255) if total >= besoin else (255, 255, 255)
    cv2.putText(image_bgr, 'TOTAL: %d/%d  (%d personne(s) vue(s) sur 3)'
                % (total, besoin, len(comptes)),
                (10, h - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur_total, 2)

    barre_x, barre_y, barre_l, barre_h = 10, h - 35, 200, 12
    cv2.rectangle(image_bgr, (barre_x, barre_y), (barre_x + barre_l, barre_y + barre_h),
                  (255, 255, 255), 1)
    rempli = int(barre_l * progression)
    if rempli > 0:
        cv2.rectangle(image_bgr, (barre_x, barre_y), (barre_x + rempli, barre_y + barre_h),
                      (0, 0, 255), -1)

    cv2.imshow('Mains levees -- test isole (Q quitte)', image_bgr)


def main():
    """Test isole, sans le reste de collaboratif.py : ouvre la webcam seule
    et affiche le squelette + la confiance (visibility) de chaque epaule et
    poignet. Sert a comprendre pourquoi une personne ou une main n'est pas
    comptee -- point bleu = epaule, point vert = main non levee, point rouge
    = main levee, avec sa confiance ecrite a cote."""
    print('Test isole du sauvetage collectif (webcam %d). Q pour quitter.'
          % cfg.CAMERA_INDEX)
    print('Point bleu = epaule. Point vert = main non levee, rouge = main levee.')
    print('"vis=" a cote d un poignet = a quel point Mediapipe est sur de ce point')
    print('(en dessous de MAINS_VISIBILITE_MINI = %.2f, la main ne compte jamais,'
          % cfg.MAINS_VISIBILITE_MINI)
    print('meme si elle est clairement levee).')
    print()

    mains = MainsLevees().demarrer()
    capture = cv2.VideoCapture(cfg.CAMERA_INDEX, cv2.CAP_DSHOW)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.CAMERA_LARGEUR)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.CAMERA_HAUTEUR)
    if not capture.isOpened():
        print('Impossible d ouvrir la camera %d.' % cfg.CAMERA_INDEX)
        return

    try:
        while True:
            ok, image = capture.read()
            if not ok:
                continue
            if cfg.MIROIR:
                image = cv2.flip(image, 1)

            maintenant = time.time()
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            mains._horodatage += 1
            resultat = mains.detecteur.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                mains._horodatage)

            h, l = image.shape[:2]
            comptes = [_mains_levees_une_personne(pose, cfg.MAINS_MARGE, l, h)
                       for pose in resultat.pose_landmarks]
            condition = sum(comptes) >= cfg.MAINS_REQUISES
            mains._maintien.observer(condition, maintenant)

            _dessiner_debug(image, resultat, comptes,
                             mains._maintien.progression(maintenant))
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        capture.release()
        mains.arreter()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()