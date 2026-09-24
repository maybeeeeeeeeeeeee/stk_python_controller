#!/usr/bin/env python3
"""six_sept.py -- Accelerer en faisant le geste "6-7" avec les deux mains.

Le geste
--------
Les deux mains devant soi, paumes vers le haut, a hauteur de poitrine, qui
montent et descendent EN ALTERNANCE -- comme une balance qui hesite :

    main gauche  ^   v   ^   v
    main droite  v   ^   v   ^

Tant que le joueur "fait le 6-7", le kart accelere. Il s'arrete, le kart
n'accelere plus. Plus creatif que de lever les mains, et impossible a faire
par accident.

Comment on le reconnait
-----------------------
On reutilise les poses que mains_levees.py calcule DEJA sur la meme image
(pas de second modele, pas de calcul en plus). Pour chaque joueur :

    d = (hauteur poignet gauche - hauteur poignet droit) / largeur d'epaules

  - Les deux mains a la meme hauteur    -> d ~ 0
  - Gauche en bas, droite en haut       -> d > 0
  - Gauche en haut, droite en bas       -> d < 0

Le 6-7, c'est d qui oscille de part et d'autre de zero. On compte les
BASCULES : d passe au-dessus de +SEUIL puis sous -SEUIL (ou l'inverse). Il en
faut plusieurs dans une fenetre courte pour que ce soit le geste, et pas une
main qu'on replace.

Pourquoi c'est robuste :
  - diviser par la largeur d'epaules rend le seuil independant de la distance
    a la webcam (un joueur recule, ses mains bougent moins en pixels, ses
    epaules aussi) ;
  - lever ou baisser les DEUX mains ensemble ne change pas d : ca ne compte
    pas. Seule l'ALTERNANCE compte ;
  - l'hysteresis (il faut franchir +SEUIL PUIS -SEUIL) ignore le tremblement
    autour de zero ;
  - les mains doivent rester sous les epaules : des mains levees au-dessus de
    la tete, c'est le sauvetage collectif, pas l'acceleration.
"""

import collections

import config_collab as cfg
from equipe import ROLES, centre_de_zone, role_selon_x

# Topologie BlazePose (33 points), la meme que dans mains_levees.py.
EPAULE_GAUCHE, EPAULE_DROITE = 11, 12
POIGNET_GAUCHE, POIGNET_DROIT = 15, 16


class _SuiviGeste:
    """L'etat du geste pour UN joueur."""

    def __init__(self):
        self.signe = 0                   # -1, 0 ou +1 : dernier cote franchi
        self.bascules = collections.deque()
        self.derniere_vue = 0.0
        self.d = 0.0                     # derniere valeur, pour la fenetre de debug
        self.actif = False

    def oublier(self):
        self.signe = 0
        self.bascules.clear()
        self.actif = False
        self.d = 0.0

    def observer(self, d, maintenant):
        self.d = d
        self.derniere_vue = maintenant

        nouveau = 0
        if d > cfg.SIXSEPT_SEUIL:
            nouveau = 1
        elif d < -cfg.SIXSEPT_SEUIL:
            nouveau = -1

        # Une bascule = passer d'un cote franchi au cote oppose. Rester dans
        # la zone morte entre -SEUIL et +SEUIL ne change rien.
        if nouveau != 0 and nouveau != self.signe:
            if self.signe != 0:
                self.bascules.append(maintenant)
            self.signe = nouveau

        while self.bascules and maintenant - self.bascules[0] > cfg.SIXSEPT_FENETRE_S:
            self.bascules.popleft()

        assez = len(self.bascules) >= cfg.SIXSEPT_BASCULES_MINI
        recent = bool(self.bascules) and (
            maintenant - self.bascules[-1] <= cfg.SIXSEPT_MAINTIEN_S)
        self.actif = assez and recent
        return self.actif


def _mesure(pose, largeur, hauteur):
    """d pour une pose, ou None si les points ne sont pas exploitables."""
    points = [pose[i] for i in (EPAULE_GAUCHE, EPAULE_DROITE,
                                POIGNET_GAUCHE, POIGNET_DROIT)]
    if any(p.visibility < cfg.MAINS_VISIBILITE_MINI for p in points):
        return None
    eg, ed, pg, pd = points

    # En pixels : x et y sont normalises chacun par SA dimension, meme piege
    # que pour le roulis dans suivi_visages.py.
    largeur_epaules = abs(eg.x - ed.x) * largeur
    if largeur_epaules < 1.0:
        return None

    # Les mains au-dessus des epaules, c'est le sauvetage, pas le 6-7.
    epaules_y = (eg.y + ed.y) / 2
    if pg.y < epaules_y - cfg.MAINS_MARGE or pd.y < epaules_y - cfg.MAINS_MARGE:
        return None

    return (pg.y - pd.y) * hauteur / largeur_epaules


class SixSept:
    """Qui fait le 6-7, par role (gauche / milieu / droite)."""

    def __init__(self):
        self.suivis = {role: _SuiviGeste() for role in ROLES}

    def mettre_a_jour(self, poses, largeur, hauteur, maintenant):
        """poses : resultat.pose_landmarks de mains_levees.py (image deja en
        miroir si MIROIR). On range chaque pose dans la zone de son role, au
        plus une par zone -- meme regle que pour les visages."""
        meilleures = {}
        for pose in poses:
            x = (pose[EPAULE_GAUCHE].x + pose[EPAULE_DROITE].x) / 2
            role = role_selon_x(x)
            distance = abs(x - centre_de_zone(role))
            if role not in meilleures or distance < meilleures[role][1]:
                meilleures[role] = (pose, distance)

        for role, (pose, _) in meilleures.items():
            d = _mesure(pose, largeur, hauteur)
            if d is not None:
                self.suivis[role].observer(d, maintenant)

        # Un joueur qu'on ne voit plus assez longtemps lache l'accelerateur :
        # le kart ne doit jamais rester bloque a fond parce que quelqu'un est
        # sorti du champ.
        for suivi in self.suivis.values():
            if maintenant - suivi.derniere_vue > cfg.SIXSEPT_MAINTIEN_S:
                suivi.oublier()

    def actif(self, role):
        return self.suivis[role].actif

    def texte(self, role):
        s = self.suivis[role]
        return '6-7%s d=%+.2f' % (' OUI' if s.actif else '', s.d)
