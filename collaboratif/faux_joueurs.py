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
import sys
import time

import numpy as np

import collaboratif
import config_collab as cfg
from equipe import GAUCHE, MILIEU, DROITE, centre_de_zone
from suivi_visages import Visage

# Un joueur absent s'ecrit None. Sinon (roulis en degres, sourire de 0 a 1).
ABSENT = None

SCENARIO_A_TROIS = [
    # (duree, gauche, milieu, droite, commentaire)
    (4.0, (0, 0.0), (0, 0.0), (0, 0.0), 'les trois en place, calibration'),
    (2.5, (-25, 0.0), (0, 0.0), (0, 0.0), 'gauche penche vers sa gauche'),
    (2.5, (0, 0.0), (0, 0.0), (0, 0.0), 'repos'),
    (2.5, (0, 0.0), (0, 0.0), (25, 0.0), 'droite penche vers sa droite'),
    (2.5, (-25, 0.0), (0, 0.0), (25, 0.0), 'les deux : leurs demandes s annulent'),
    (2.5, (0, 0.0), (0, 0.8), (0, 0.0), 'le milieu sourit -> accelere'),
    (1.5, (0, 0.0), (0, 0.0), (0, 0.0), 'repos'),
]

SCENARIO_A_DEUX = [
    (4.0, (0, 0.0), ABSENT, (0, 0.0), 'a DEUX : le milieu n est pas la'),
    (2.5, (-25, 0.0), ABSENT, (0, 0.0), 'gauche penche -> le kart tourne quand meme'),
    (2.5, (0, 0.8), ABSENT, (0, 0.0), 'gauche sourit -> secours, le kart avance'),
    (2.0, (0, 0.0), ABSENT, (0, 0.0), 'plus de sourire -> le kart n avance plus'),
    (3.0, (0, 0.0), (0, 0.0), (0, 0.0), 'le milieu ARRIVE (calibre tout seul)'),
    (2.5, (0, 0.8), (0, 0.0), (0, 0.0), 'gauche sourit -> plus rien : le milieu est la'),
    (2.5, (0, 0.0), (0, 0.8), (0, 0.0), 'le milieu sourit -> accelere'),
    (3.0, (0, 0.0), ABSENT, (0, 0.8), 'le milieu REPART, droite sourit -> secours'),
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

        image = np.zeros((self.hauteur, self.largeur, 3), dtype=np.uint8)
        visages = []
        for role, etat in zip(ROLES_DU_SCENARIO, (gauche, milieu, droite)):
            if etat is ABSENT:
                continue
            x = centre_de_zone(role)
            roulis, sourire = etat
            cx = int(x * self.largeur)
            cy = self.hauteur // 2
            visages.append(Visage(
                x=x, y=0.5, roulis=float(roulis),
                formes={'mouthSmileLeft': sourire, 'mouthSmileRight': sourire,
                        'jawOpen': 0.0},
                boite=(cx - 90, cy - 110, cx + 90, cy + 110)))

        # 30 Hz, comme une webcam : sans cette pause le scenario defile a
        # plusieurs milliers d'images par seconde et les durees ne veulent
        # plus rien dire.
        time.sleep(1 / 30)
        return image, visages

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
    sys.argv = [sys.argv[0]] + restant
    sys.exit(collaboratif.main())
