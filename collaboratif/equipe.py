#!/usr/bin/env python3
"""Qui est qui, et ce que chacun demande au kart.

Attribution des roles
---------------------
Par ZONE de l'image, pas par classement gauche-a-droite. La difference compte :
un classement se refait a chaque image, donc si le visage du milieu n'est pas
detecte pendant trois images, le joueur de droite devient le joueur du milieu,
puis redevient le joueur de droite. Deux personnes echangent leurs commandes en
pleine course, sans que rien ne le signale.

Une zone fixe ne peut pas faire ca. Elle a un cout : il faut se placer dans sa
zone. La fenetre de debug les dessine, donc ce cout est visible et se corrige
en se decalant de vingt centimetres.

La regle de direction
---------------------
    joueur de gauche  ->  penche la tete  ->  le kart tourne a GAUCHE
    joueur de droite  ->  penche la tete  ->  le kart tourne a DROITE

Peu importe de quel cote la tete est penchee : c'est la PLACE qui decide du
sens, pas le geste. Pour exiger en plus de pencher du bon cote, mettre
EXIGER_LE_BON_SENS a True -- mais il faut alors que SENS_ROULIS soit juste, et
ce signe depend de la webcam.

Personne ne peut donc conduire seul. Et si les deux penchent en meme temps,
leurs demandes s'annulent dans SortieSTK (regle OPPOSEES) : le kart va tout
droit. C'est voulu -- l'annulation est une information, pas un bug : elle dit
aux joueurs qu'ils se contredisent.
"""

import time

import config_collab as cfg
from modulation import intensite_depuis_angle

GAUCHE = 'gauche'
MILIEU = 'milieu'
DROITE = 'droite'
ROLES = (GAUCHE, MILIEU, DROITE)


def ecart_angulaire(a, b):
    """a - b, ramene dans (-90, +90].

    Indispensable des qu'on soustrait deux angles : sans ca, deux poses
    voisines de part et d'autre d'une coupure donnent un ecart absurde. Meme
    precaution que dans tools/source.py pour le volant du telephone.
    """
    d = a - b
    while d > 90.0:
        d -= 180.0
    while d <= -90.0:
        d += 180.0
    return d


def role_selon_x(x):
    """La zone de l'image ou se trouve ce visage, traduite en role.

    INVERSER_ROLES echange les deux extremites. Ce n'est pas un detail de
    confort : c'est le seul reglage qui decide qui commande quelle fleche, et
    il depend de la disposition reelle du banc face a la webcam. Il se verifie
    en dix secondes, il ne se devine pas.
    """
    if x < cfg.ZONE_GAUCHE_FIN:
        return DROITE if cfg.INVERSER_ROLES else GAUCHE
    if x > cfg.ZONE_DROITE_DEBUT:
        return GAUCHE if cfg.INVERSER_ROLES else DROITE
    return MILIEU


def centre_de_zone(role):
    """Milieu de la zone occupee par ce role, pour departager deux visages."""
    if role == MILIEU:
        return (cfg.ZONE_GAUCHE_FIN + cfg.ZONE_DROITE_DEBUT) / 2
    a_gauche = (role == DROITE) if cfg.INVERSER_ROLES else (role == GAUCHE)
    if a_gauche:
        return cfg.ZONE_GAUCHE_FIN / 2
    return (cfg.ZONE_DROITE_DEBUT + 1.0) / 2


class Joueur:
    def __init__(self, role):
        self.role = role
        self.neutre = None        # roulis de repos, retenu a la calibration
        self.roulis = 0.0         # roulis brut mesure
        self.ecart = 0.0          # roulis - neutre, lisse : la mesure qui decide
        self.ecart_brut = 0.0     # avant lissage, pour comparer en reglage
        self.visage = None
        self.derniere_vue = 0.0
        self.vu_depuis = None     # instant ou il est apparu, pour le calibrer

    @property
    def vu(self):
        return (time.time() - self.derniere_vue) < cfg.TIMEOUT_JOUEUR

    @property
    def calibre(self):
        return self.neutre is not None

    @property
    def sourire(self):
        if self.visage is None or not self.vu:
            return 0.0
        return (self.visage.forme('mouthSmileLeft')
                + self.visage.forme('mouthSmileRight')) / 2

    def calibrer(self):
        """Retient la position actuelle comme repos. False si on ne le voit pas."""
        if not self.vu:
            return False
        self.neutre = self.roulis
        return True

    def intensite_direction(self):
        """De 0 a 1 : a quel point CE joueur demande sa fleche.

        0 = rien, 1 = braquage complet. C'est ce qui remplace l'ancien
        tout-ou-rien : la modulation transforme ensuite ce nombre en appuis.
        """
        if self.role == MILIEU or not self.vu or not self.calibre:
            return 0.0

        if cfg.EXIGER_LE_BON_SENS:
            if self.role == GAUCHE and self.ecart > 0:
                return 0.0
            if self.role == DROITE and self.ecart < 0:
                return 0.0

        return intensite_depuis_angle(self.ecart, cfg.ANGLE_MINI,
                                      cfg.ANGLE_MAXI, cfg.COURBE,
                                      cfg.INTENSITE_MINI)

    def intention_direction(self):
        """'left', 'right' ou None -- ce que CE joueur demande.

        Un joueur absent ou non calibre ne demande rien : sans neutre, l'ecart
        se compte depuis zero degre, qui ne correspond a la position de repos
        de personne, et le kart braquerait en permanence. Meme piege qu'au TP1
        avec le volant calibre avant l'arrivee des donnees.
        """
        if self.intensite_direction() <= 0.0:
            return None

        if cfg.EXIGER_LE_BON_SENS:
            # Suppose que pencher vers son epaule gauche donne un ecart
            # negatif. Si ce n'est pas le cas en jeu, c'est SENS_ROULIS qui est
            # a inverser, pas ce test.
            if self.role == GAUCHE and self.ecart > 0:
                return None
            if self.role == DROITE and self.ecart < 0:
                return None

        return 'left' if self.role == GAUCHE else 'right'


class Equipe:
    def __init__(self):
        self.joueurs = {role: Joueur(role) for role in ROLES}

    def mettre_a_jour(self, visages):
        """Range les visages vus dans les zones, au plus un par zone."""
        maintenant = time.time()
        meilleurs = {}
        for visage in visages:
            role = role_selon_x(visage.x)
            distance = abs(visage.x - centre_de_zone(role))
            # Deux visages dans la meme zone : on garde le plus proche du
            # centre. Ca arrive quand quelqu'un passe derriere, ou quand deux
            # joueurs se serrent trop.
            if role not in meilleurs or distance < meilleurs[role][1]:
                meilleurs[role] = (visage, distance)

        for role, (visage, _) in meilleurs.items():
            joueur = self.joueurs[role]
            if not joueur.vu:
                # Il vient d'apparaitre (ou de reapparaitre).
                joueur.vu_depuis = maintenant
            joueur.visage = visage
            joueur.roulis = visage.roulis
            brut = (ecart_angulaire(visage.roulis, joueur.neutre)
                    if joueur.calibre else 0.0)
            joueur.ecart_brut = brut
            # Moyenne glissante : l'angle d'une image a l'autre bouge de
            # quelques dixiemes de degre meme tete immobile, et ce bruit se
            # voyait directement dans le braquage.
            joueur.ecart += (brut - joueur.ecart) * (1.0 - cfg.LISSAGE)
            joueur.derniere_vue = maintenant

        for role in ROLES:
            if not self.joueurs[role].vu:
                self.joueurs[role].vu_depuis = None

        return meilleurs

    def calibrer_les_retardataires(self):
        """Calibre tout seul ceux qui sont arrives apres la calibration generale.

        Le milieu est optionnel et peut arriver en cours de partie ; une
        extremite peut aussi avoir ete hors champ au demarrage. Sans ca, ils
        resteraient sans neutre, donc muets, sans que rien ne l'explique.
        Rend la liste des roles calibres a cet instant.
        """
        maintenant = time.time()
        tardifs = []
        for role in ROLES:
            joueur = self.joueurs[role]
            if joueur.calibre or not joueur.vu or joueur.vu_depuis is None:
                continue
            if maintenant - joueur.vu_depuis >= cfg.DELAI_CALIBRATION_TARDIVE:
                if joueur.calibrer():
                    tardifs.append(role)
        return tardifs

    def requis_presents(self):
        """Les joueurs sans qui la partie ne peut pas commencer sont-ils la ?"""
        return all(self.joueurs[role].vu for role in cfg.ROLES_REQUIS)

    def manquants_requis(self):
        return [role for role in cfg.ROLES_REQUIS if not self.joueurs[role].vu]

    def calibrer(self):
        """Retient le repos de chacun. Rend la liste des roles calibres."""
        return [role for role in ROLES if self.joueurs[role].calibrer()]

    def presents(self):
        return [role for role in ROLES if self.joueurs[role].vu]

    def etat_texte(self):
        morceaux = []
        for role in ROLES:
            j = self.joueurs[role]
            if not j.vu:
                morceaux.append('%s: absent' % role)
            elif not j.calibre:
                morceaux.append('%s: NON CALIBRE' % role)
            else:
                morceaux.append('%s: %+5.1f (%3d%%)'
                                % (role, j.ecart, j.intensite_direction() * 100))
        return '   '.join(morceaux)
