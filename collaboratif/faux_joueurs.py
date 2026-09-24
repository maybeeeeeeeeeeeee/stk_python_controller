#!/usr/bin/env python3
"""Des faux joueurs, pour tester toute la chaine tout seul.

    python faux_joueurs.py                 scenario a trois
    python faux_joueurs.py --a-deux        scenario a deux, le milieu arrive en cours
    python faux_joueurs.py --simulation    sans rien envoyer au serveur
    python faux_joueurs.py --sans-fenetre  sans la fenetre video

Remplace la webcam par un scenario ecrit : des visages qui se placent, se
calibrent, penchent la tete, sourient, arrivent et repartent. Aucun materiel,
aucun figurant -- mais tout le reste du programme est le vrai, du calcul des
roles jusqu'aux commandes envoyees sur le 6006.

C'est le pendant de PILOTE\\faux_telephone.py. Meme raison d'etre : pouvoir
verifier la chaine avant la seance, quand personne n'est la pour jouer.

Ce qu'il ne teste PAS : la detection Mediapipe elle-meme, ni la qualite du
roulis mesure sur un vrai visage. Pour ca il faut de vraies tetes devant la
vraie webcam -- un scenario rejoue ne remplace pas une mesure.
"""

import argparse
import math
import sys
import time

import numpy as np

import collaboratif
import config_collab as cfg
from equipe import GAUCHE, MILIEU, DROITE, centre_de_zone
from suivi_visages import Visage

# Un joueur absent s'ecrit None. Sinon (roulis en degres, geste des mains) :
#   0 = mains immobiles, 1 = 6-7 (accelere), 2 = mains sur la tete (freine).
FREIN = 2
ABSENT = None

SCENARIO_A_TROIS = [
    # (duree, gauche, milieu, droite, commentaire)
    (4.0, (0, 0.0), (0, 0.0), (0, 0.0), 'les trois en place, calibration'),
    (2.5, (-25, 0.0), (0, 0.0), (0, 0.0), 'gauche penche vers sa gauche'),
    (2.5, (0, 0.0), (0, 0.0), (0, 0.0), 'repos'),
    (2.5, (0, 0.0), (0, 0.0), (25, 0.0), 'droite penche vers sa droite'),
    (2.5, (-25, 0.0), (0, 0.0), (25, 0.0), 'les deux : leurs demandes s annulent'),
    (2.5, (0, 0.0), (0, 1), (0, 0.0), 'le milieu fait le 6-7 -> accelere'),
    (2.0, (0, 0.0), (0, FREIN), (0, 0.0), 'le milieu panique -> freine'),
    (1.5, (0, 0.0), (0, 0.0), (0, 0.0), 'repos'),
]

SCENARIO_A_DEUX = [
    (4.0, (0, 0.0), ABSENT, (0, 0.0), 'a DEUX : le milieu n est pas la'),
    (2.5, (-25, 0.0), ABSENT, (0, 0.0), 'gauche penche -> le kart tourne quand meme'),
    (2.5, (0, 1), ABSENT, (0, 0.0), 'gauche fait le 6-7 -> secours, le kart avance'),
    (2.0, (0, 0.0), ABSENT, (0, 0.0), 'plus de 6-7 -> le kart n avance plus'),
    (3.0, (0, 0.0), (0, 0.0), (0, 0.0), 'le milieu ARRIVE (calibre tout seul)'),
    (2.5, (0, 1), (0, 0.0), (0, 0.0), 'gauche fait le 6-7 -> plus rien : le milieu est la'),
    (2.5, (0, 0.0), (0, 1), (0, 0.0), 'le milieu fait le 6-7 -> accelere'),
    (3.0, (0, 0.0), ABSENT, (0, 1), 'le milieu REPART, droite fait le 6-7 -> secours'),
    (2.0, (0, FREIN), ABSENT, (0, 0.0), 'gauche panique -> frein de secours'),
    (1.5, (0, 0.0), ABSENT, (0, 0.0), 'repos'),
]

# On place chaque faux joueur au centre de la zone de SON ROLE, au lieu de x
# fixes. Sans ca, le scenario ne dit plus la verite des que INVERSER_ROLES
# change : le visage pose a gauche de l'image se retrouve etiquete "droite" et
# on lit un resultat qui ne correspond plus aux commentaires.
ROLES_DU_SCENARIO = (GAUCHE, MILIEU, DROITE)


class FauxSuivi:
    """Meme interface que SuiviVisages, mais nourri par le scenario."""

    scenario = SCENARIO_A_TROIS

    # L'etape en cours, partagee avec FauxMains pour que les mains suivent
    # le meme scenario que les visages.
    etat_courant = (ABSENT, ABSENT, ABSENT)

    def __init__(self):
        self.largeur = cfg.CAMERA_LARGEUR
        self.hauteur = cfg.CAMERA_HAUTEUR
        self._etape = 0
        self._fin_etape = None

    def demarrer(self):
        print('[faux] webcam remplacee par un scenario de %d etapes.'
              % len(self.scenario))
        return self

    def _avancer(self, maintenant):
        if self._fin_etape is None:
            self._fin_etape = maintenant + self.scenario[0][0]
            print('[faux] --- %s' % self.scenario[0][4])
            return
        if maintenant < self._fin_etape:
            return
        self._etape += 1
        if self._etape >= len(self.scenario):
            print('[faux] scenario termine.')
            raise KeyboardInterrupt
        etape = self.scenario[self._etape]
        self._fin_etape = maintenant + etape[0]
        print('[faux] --- %s' % etape[4])

    def lire(self):
        maintenant = time.time()
        self._avancer(maintenant)
        _, gauche, milieu, droite, _ = self.scenario[self._etape]
        FauxSuivi.etat_courant = (gauche, milieu, droite)

        image = np.zeros((self.hauteur, self.largeur, 3), dtype=np.uint8)
        visages = []
        for role, etat in zip(ROLES_DU_SCENARIO, (gauche, milieu, droite)):
            if etat is ABSENT:
                continue
            x = centre_de_zone(role)
            roulis, _ = etat
            cx = int(x * self.largeur)
            cy = self.hauteur // 2
            visages.append(Visage(
                x=x, y=0.5, roulis=float(roulis),
                formes={'jawOpen': 0.0},
                boite=(cx - 90, cy - 110, cx + 90, cy + 110)))

        # 30 Hz, comme une webcam : sans cette pause le scenario defile a
        # plusieurs milliers d'images par seconde et les durees ne veulent
        # plus rien dire.
        time.sleep(1 / 30)
        return image, visages

    def arreter(self):
        pass


class _Point:
    def __init__(self, x, y):
        self.x, self.y, self.visibility = x, y, 1.0


class FauxMains:
    """Meme interface que MainsLevees : fabrique des poses a partir du
    scenario. Un joueur qui "fait le 6-7" a les poignets qui oscillent en
    opposition a 2,5 Hz, comme dans le vrai geste ; sinon ils sont immobiles
    a hauteur de ventre."""

    def __init__(self):
        self.dernier_compte = 0
        self.dernier_nombre_personnes = 0
        self.dernieres_poses = []

    def demarrer(self):
        return self

    def traiter(self, image, maintenant):
        poses = []
        for role, etat in zip(ROLES_DU_SCENARIO, FauxSuivi.etat_courant):
            if etat is ABSENT:
                continue
            x = centre_de_zone(role)
            fait = etat[1] == 1
            balance = 0.06 * math.sin(2 * math.pi * 2.5 * maintenant) if fait else 0.0
            pose = [_Point(x, 0.9) for _ in range(33)]
            pose[0] = _Point(x, 0.28)             # nez
            pose[7] = _Point(x - 0.025, 0.27)     # oreille gauche
            pose[8] = _Point(x + 0.025, 0.27)     # oreille droite
            pose[11] = _Point(x - 0.06, 0.45)     # epaule gauche
            pose[12] = _Point(x + 0.06, 0.45)     # epaule droite
            if etat[1] == FREIN:
                pose[15] = _Point(x - 0.03, 0.18)     # mains sur le crane
                pose[16] = _Point(x + 0.03, 0.18)
            else:
                pose[15] = _Point(x - 0.05, 0.65 + balance)   # poignet gauche
                pose[16] = _Point(x + 0.05, 0.65 - balance)   # poignet droit
            poses.append(pose)
        self.dernieres_poses = poses
        self.dernier_nombre_personnes = len(poses)
        return False

    def progression(self, maintenant):
        return 0.0

    def arreter(self):
        pass


if __name__ == '__main__':
    # --a-deux nous appartient ; tout le reste part a collaboratif.py.
    choix = argparse.ArgumentParser(add_help=False)
    choix.add_argument('--a-deux', action='store_true')
    args, restant = choix.parse_known_args()

    FauxSuivi.scenario = SCENARIO_A_DEUX if args.a_deux else SCENARIO_A_TROIS

    # On remplace la classe DANS le module collaboratif : c'est le nom qu'il a
    # importe, donc c'est celui-la qu'il utilisera.
    collaboratif.SuiviVisages = FauxSuivi
    collaboratif.MainsLevees = FauxMains
    sys.argv = [sys.argv[0]] + restant
    sys.exit(collaboratif.main())
