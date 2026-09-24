#!/usr/bin/env python3
"""mains_sur_tete.py -- Freiner en mettant les deux mains sur la tete, facon panique.

Le geste
--------
Le reflexe de quelqu'un qui voit l'accident arriver : les deux mains posees
sur le crane (ou contre les tempes). Tant qu'elles y restent, le kart freine.
On les enleve, il arrete de freiner.

C'est le pendant du 6-7 : un geste de mains pour accelerer, un geste de mains
pour freiner, sur les memes poses et avec le meme code de zones. Les deux ne
peuvent pas se faire en meme temps -- les mains sont soit devant la poitrine,
soit sur la tete.

Comment on le reconnait
-----------------------
On reutilise les poses que mains_levees.py calcule deja (aucun modele en
plus). Pour chaque joueur, les deux mains sont "sur la tete" si :

  - les deux poignets sont PLUS HAUTS que les epaules ;
  - chaque poignet est PRES de la tete : a moins de FREIN_DISTANCE_TETE
    largeurs d'epaules du centre de la tete (milieu des deux oreilles).

Diviser par la largeur d'epaules rend le reglage independant de la distance a
la webcam, comme pour le 6-7.

Et le sauvetage collectif ?
---------------------------
Des mains sur la tete sont aussi des mains "au-dessus des epaules" : sans
precaution, paniquer compterait pour le sauvetage. mains_levees.py utilise
donc main_pres_de_la_tete() ci-dessous pour ne compter que les bras vraiment
tendus vers le haut, loin de la tete.
"""

import math

import config_collab as cfg
from equipe import ROLES, centre_de_zone, role_selon_x

# Topologie BlazePose (33 points).
NEZ = 0
OREILLE_GAUCHE, OREILLE_DROITE = 7, 8
EPAULE_GAUCHE, EPAULE_DROITE = 11, 12
POIGNET_GAUCHE, POIGNET_DROIT = 15, 16


def _centre_tete(pose):
    """Milieu des deux oreilles, ou le nez si les oreilles sont cachees
    (les mains sur les tempes les masquent souvent)."""
    og, od = pose[OREILLE_GAUCHE], pose[OREILLE_DROITE]
    if min(og.visibility, od.visibility) >= cfg.FREIN_VISIBILITE_MINI:
        return (og.x + od.x) / 2, (og.y + od.y) / 2
    nez = pose[NEZ]
    return nez.x, nez.y


def distance_a_la_tete(pose, poignet, largeur, hauteur):
    """Distance poignet -> centre de la tete, en largeurs d'epaules.
    None si les epaules ne sont pas exploitables."""
    eg, ed = pose[EPAULE_GAUCHE], pose[EPAULE_DROITE]
    largeur_epaules = abs(eg.x - ed.x) * largeur
    if largeur_epaules < 1.0:
        return None
    tx, ty = _centre_tete(pose)
    # En pixels : x et y sont normalises chacun par SA dimension.
    dx = (poignet.x - tx) * largeur
    dy = (poignet.y - ty) * hauteur
    return math.hypot(dx, dy) / largeur_epaules


def main_pres_de_la_tete(pose, poignet, largeur, hauteur):
    """Utilise aussi par mains_levees.py pour exclure ces mains du sauvetage."""
    d = distance_a_la_tete(pose, poignet, largeur, hauteur)
    return d is not None and d < cfg.FREIN_DISTANCE_TETE


def _mains_sur_la_tete(pose, largeur, hauteur):
    """(oui/non, distance la plus grande des deux mains) pour une pose."""
    eg, ed = pose[EPAULE_GAUCHE], pose[EPAULE_DROITE]
    pg, pd = pose[POIGNET_GAUCHE], pose[POIGNET_DROIT]

    # Seuil de visibilite plus bas que pour le reste : une main posee sur la
    # tete est souvent a moitie cachee par les cheveux ou le bras, et
    # Mediapipe en est moins sur.
    if min(eg.visibility, ed.visibility) < cfg.MAINS_VISIBILITE_MINI:
        return False, None
    if min(pg.visibility, pd.visibility) < cfg.FREIN_VISIBILITE_MINI:
        return False, None

    epaules_y = (eg.y + ed.y) / 2
    if pg.y >= epaules_y or pd.y >= epaules_y:
        return False, None

    dg = distance_a_la_tete(pose, pg, largeur, hauteur)
    dd = distance_a_la_tete(pose, pd, largeur, hauteur)
    if dg is None or dd is None:
        return False, None
    pire = max(dg, dd)
    return pire < cfg.FREIN_DISTANCE_TETE, pire


class _SuiviFrein:
    def __init__(self):
        self.depuis = None        # debut du geste en cours
        self.derniere_vue = 0.0   # dernier instant ou les mains etaient sur la tete
        self.distance = None      # pour la fenetre de debug
        self.actif = False

    def observer(self, sur_tete, distance, maintenant):
        self.distance = distance
        if sur_tete:
            if self.depuis is None:
                self.depuis = maintenant
            self.derniere_vue = maintenant
        elif maintenant - self.derniere_vue > cfg.FREIN_TOLERANCE_S:
            # Une image ratee (main un instant moins visible) ne doit pas
            # relacher le frein ; un vrai retrait des mains, si.
            self.depuis = None

        self.actif = (self.depuis is not None
                      and maintenant - self.depuis >= cfg.FREIN_MAINTIEN_S)
        return self.actif


class MainsSurTete:
    """Qui a les mains sur la tete, par role (gauche / milieu / droite)."""

    def __init__(self):
        self.suivis = {role: _SuiviFrein() for role in ROLES}

    def mettre_a_jour(self, poses, largeur, hauteur, maintenant):
        meilleures = {}
        for pose in poses:
            x = (pose[EPAULE_GAUCHE].x + pose[EPAULE_DROITE].x) / 2
            role = role_selon_x(x)
            distance = abs(x - centre_de_zone(role))
            if role not in meilleures or distance < meilleures[role][1]:
                meilleures[role] = (pose, distance)

        for role in ROLES:
            if role in meilleures:
                oui, dist = _mains_sur_la_tete(meilleures[role][0], largeur, hauteur)
            else:
                # Plus personne dans la zone : on relache, le kart ne doit
                # jamais rester bloque au frein.
                oui, dist = False, None
            self.suivis[role].observer(oui, dist, maintenant)

    def actif(self, role):
        return self.suivis[role].actif

    def texte(self, role):
        s = self.suivis[role]
        if s.distance is None:
            return 'tete -'
        return 'tete%s %.2f' % (' OUI' if s.actif else '', s.distance)
