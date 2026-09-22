#!/usr/bin/env python3
"""Reglages du volet collaboratif.

Le volet performance (PILOTE/) cherche a piloter le mieux possible, seul. Ce
volet-ci cherche l'inverse : rendre le pilotage IMPOSSIBLE seul. Trois joueurs
cote a cote devant une webcam, et le kart n'obeit que s'ils se coordonnent.
"""

import os
import sys

DOSSIER_COLLAB = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(DOSSIER_COLLAB)
DOSSIER_PILOTE = os.path.join(RACINE, 'PILOTE')
DOSSIER_TOOLS = os.path.join(RACINE, 'tools')


def _premier_existant(chemins, defaut=None):
    """Le premier chemin qui existe, ou le defaut. Sert a tourner dans deux
    arborescences sans avoir deux versions du fichier.

    Ici : a cote de nous quand le dossier est pose a plat (depot de l'equipe),
    ou dans PILOTE/ quand on est dans l'arborescence du TP.
    """
    for chemin in chemins:
        if os.path.exists(chemin):
            return chemin
    return defaut if defaut is not None else chemins[-1]


# sortie_stk.py fusionne les sources et parle au serveur. Il vit a cote de nous
# dans le depot, et dans PILOTE/ dans l'arborescence du TP -- une seule copie
# dans les deux cas, jamais deux fichiers a maintenir.
_DOSSIER_SORTIE = _premier_existant(
    [os.path.join(DOSSIER_COLLAB, 'sortie_stk.py'),
     os.path.join(DOSSIER_PILOTE, 'sortie_stk.py')])
sys.path.insert(0, os.path.dirname(_DOSSIER_SORTIE))

# Le modele Mediapipe, meme logique : models/ a cote, sinon celui que
# PILOTE\preparer.ps1 a deja telecharge -- pas de second exemplaire de 4 Mo.
MODELE_VISAGE = _premier_existant(
    [os.path.join(DOSSIER_COLLAB, 'models', 'face_landmarker.task'),
     os.path.join(RACINE, 'models', 'face_landmarker.task'),
     os.path.join(DOSSIER_PILOTE, 'models', 'face_landmarker.task')])

SERVEUR_STK = ('localhost', 6006)

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
# Trois visages dans le champ : en 640x480 chacun ne fait plus qu'un tiers de
# l'image, et les yeux deviennent trop petits pour que l'angle soit stable.
# 1280x720 coute un peu de temps de calcul et le rend largement.
CAMERA_INDEX = 0
CAMERA_LARGEUR = 1280
CAMERA_HAUTEUR = 720

FENETRE_DEBUG = True        # indispensable pour regler : elle montre les zones,
                            # les roles attribues et les angles mesures

# ---------------------------------------------------------------------------
# Les roles, par ZONE de l'image
# ---------------------------------------------------------------------------
# On attribue les roles par la position a l'ecran, pas par un classement
# gauche-a-droite. Un classement s'inverse des qu'une detection saute : deux
# joueurs echangent leurs commandes en pleine course, et c'est indebogable.
# Une zone fixe, elle, ne bouge pas -- et elle se dessine dans la fenetre de
# debug, donc chacun voit ou il doit se placer.
#
# Bornes en fraction de la largeur de l'image, de 0 (bord gauche) a 1.
ZONE_GAUCHE_FIN = 0.38      # x < 0.38            -> joueur de gauche
ZONE_DROITE_DEBUT = 0.62    # x > 0.62            -> joueur de droite
                            # entre les deux      -> joueur du milieu

# L'image de la webcam est retournee comme un miroir : chacun se voit comme
# dans une glace. Ce reglage ne change QUE l'aspect de l'image et la zone ou
# chacun apparait ; l'angle mesure, lui, est compense dans suivi_visages.py
# pour ne pas dependre de ce choix.
MIROIR = True

# Qui pilote quoi. False = la zone de gauche de l'image commande la fleche
# gauche, ce qui est le cas sur cette installation (verifie le 2026-09-22 : les
# etiquettes de la fenetre de debug tombent du bon cote).
#
# A ne toucher que si la personne assise a gauche se met a commander la fleche
# droite -- et ca se verifie en regardant les etiquettes, pas en raisonnant.
INVERSER_ROLES = False

# ---------------------------------------------------------------------------
# Le geste de direction
# ---------------------------------------------------------------------------
# On mesure le ROULIS de la tete par l'angle de la droite qui joint les deux
# yeux. C'est le meme raisonnement qu'au TP1 pour le volant du telephone :
# plutot que de prendre un angle qu'on nous donne (et qui derive, ou bloque),
# on le calcule a partir de deux points qu'on voit.
# Braquage PROPORTIONNEL. La fleche ne connait que tout ou rien, donc on la
# module (voir modulation.py) : peu d'inclinaison = appuis brefs et espaces,
# beaucoup = appui continu.
ANGLE_MINI = 6.0            # zone morte : en dessous, le kart ne tourne pas
ANGLE_MAXI = 26.0           # au-dela, braquage complet (fleche tenue)
COURBE = 1.6                # > 1 : plus doux pres du centre, pour corriger fin
DELAI_CALIBRATION = 3       # secondes pour retenir la position de repos

# Lissage de l'angle, entre 0 (aucun) et 1 (fige). Une tete bouge tout le temps
# et Mediapipe rend un angle legerement different a chaque image : sans lissage,
# l'intensite saute et le braquage devient nerveux.
LISSAGE = 0.35

# DIRECTION ANALOGIQUE. True : on envoie une consigne continue (STEER:) a une
# manette virtuelle, ce qui donne une direction vraiment fluide -- c'est ce que
# fait le mode performance de l'equipe. Demande un serveur qui sait la creer :
#   Linux   : STK_input_server_v2.py      (evdev/uinput)
#   Windows : tools/stk_server_manette.py (ViGEmBus/vgamepad)
# False : on retombe sur la modulation des fleches, qui marche avec n'importe
# quel serveur mais reste une suite d'appuis.
DIRECTION_ANALOGIQUE = True

# Rythme de la modulation. L'appui minimum vaut deux images a 60 fps : mesure du
# projet, un appui d'une image passe, un appui plus court n'est jamais vu.
PERIODE_MODULATION = 0.12
APPUI_MINIMUM = 0.034
PERIODE_MAXI = 0.45

# La plus petite intensite que cette modulation sait rendre : un appui minimum
# espace au maximum. En dessous, la touche ne peut pas braquer moins -- la
# plage utile commence donc la, pas a zero.
INTENSITE_MINI = APPUI_MINIMUM / PERIODE_MAXI

# Sens du roulis. A verifier en 10 secondes dans la fenetre de debug : penche
# la tete vers ton epaule gauche, l'angle affiche doit devenir NEGATIF.
SENS_ROULIS = 1

# Faut-il pencher du bon cote ?
#
#   False (defaut) : n'importe quelle inclinaison declenche SA fleche a lui.
#                    Le joueur de gauche penche la tete, le kart tourne a
#                    gauche -- peu importe de quel cote il l'a penchee.
#   True           : il doit pencher vers SON cote. Plus lisible pour un
#                    spectateur, mais ca depend du signe de l'angle mesure,
#                    qui depend de la webcam : si le joueur de gauche doit
#                    pencher a droite pour declencher, c'est SENS_ROULIS
#                    qu'il faut inverser.
#
# Mis a False le 2026-09-22 : le sens exige etait inverse en jeu, et cette
# contrainte n'apporte rien au pilotage. Une exigence de sens qui depend d'un
# signe qu'on ne peut pas deviner, c'est un piege pour rien.
EXIGER_LE_BON_SENS = False

# Au-dela de ce delai sans voir un visage dans une zone, le joueur est declare
# absent et ses commandes sont relachees. Le suivi tourne vers 15-20 Hz a trois
# visages : une demi-seconde de trou est franchement anormale.
TIMEOUT_JOUEUR = 0.5

# ---------------------------------------------------------------------------
# Qui faut-il pour jouer
# ---------------------------------------------------------------------------
# Seules les deux extremites sont indispensables : sans elles, le kart ne peut
# pas tourner du tout. Le milieu est OPTIONNEL -- il peut arriver en cours de
# partie, ou repartir, sans que rien ne soit a relancer.
ROLES_REQUIS = ('gauche', 'droite')

# Un joueur qui arrive apres la calibration generale est calibre tout seul,
# une fois qu'on le voit sans interruption pendant ce delai. Sans ca, un
# retardataire resterait "NON CALIBRE" jusqu'au bout, donc muet.
DELAI_CALIBRATION_TARDIVE = 1.0

# Qui accelere quand le joueur du milieu n'est pas la ? Sans reponse a cette
# question, une partie a deux se joue avec un kart a l'arret.
#
#   'sourire_un'       l'un des deux suffit                      (defaut)
#   'sourire_les_deux' il faut que les deux sourient en meme temps
#   'automatique'      le kart avance tout seul, ils ne font que tourner
#   'aucune'           personne : le kart n'avance pas a deux
ACCELERATION_SANS_MILIEU = 'sourire_un'
SEUIL_SOURIRE_EXTREMITE = 0.45

# ---------------------------------------------------------------------------
# Le joueur du milieu -- PROVISOIRE
# ---------------------------------------------------------------------------
# Son role reste a decider. En attendant, il fait avancer le kart, sinon rien
# n'est jouable : deux personnes qui tournent un kart a l'arret, ca ne se teste
# pas. Tout est regroupe dans role_milieu.py, une seule fonction a remplacer.
MILIEU_SEUIL_SOURIRE = 0.45     # sourire maintenu -> accelerer
MILIEU_SEUIL_BOUCHE = 0.55      # bouche ouverte   -> lancer un objet
MILIEU_REPOS_OBJET = 0.8        # secondes entre deux objets

# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------
PERIODE_ETAT = 0.5
