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

# Meme logique pour le modele de pose (mains_levees.py, sauvetage collectif) :
# pas de second exemplaire si le volet performance l'a deja telecharge.
MODELE_POSE = _premier_existant(
    [os.path.join(DOSSIER_COLLAB, 'models', 'pose_landmarker_lite.task'),
     os.path.join(RACINE, 'models', 'pose_landmarker_lite.task'),
     os.path.join(DOSSIER_PILOTE, 'models', 'pose_landmarker_lite.task')])

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
ANGLE_MINI = 4.0            # zone morte : en dessous, le kart ne tourne pas -- baisse
                            # de 6 a 4 pour demarrer le virage sur un tout petit mouvement
ANGLE_MAXI = 22.0           # au-dela, braquage complet (fleche tenue) -- remonte de 18 a
                            # 22 : a 18, le moindre tremblement ou petite perte de suivi
                            # se traduisait en gros pourcentage de braquage (mesure faite
                            # le 2026-09-22 : des -100%/+100% en rafale alors que personne
                            # ne braquait vraiment a fond)
COURBE = 1.4                # > 1 : plus doux pres du centre, pour corriger fin -- baisse
                            # de 1.6 a 1.4 pour une reaction un peu plus directe
DELAI_CALIBRATION = 3       # secondes pour retenir la position de repos

# Lissage de l'angle, entre 0 (aucun) et 1 (fige). Une tete bouge tout le temps
# et Mediapipe rend un angle legerement different a chaque image : sans lissage,
# l'intensite saute et le braquage devient nerveux.
LISSAGE = 0.32              # remonte de 0.25 a 0.32 : la latence venait surtout du repli
                            # sans vgamepad (regle a part), pas du lissage -- on peut se
                            # permettre un peu plus de stabilite sans perdre le gain de
                            # reactivite de la vraie direction analogique

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
#
# Remonte de 0.5 a 0.8 le 2026-09-22 : a 0.5, une tres breve perte de suivi
# (la tete qui sort un instant de la zone, un clignement de detection) faisait
# declarer le joueur absent -- son intensite retombe alors a 0 sans etre
# annulee par l'autre cote, et le kart partait plein braquage du cote oppose.
# 0.8 laisse le temps a une perte courte de se resorber sans rien changer a la
# securite : un joueur qui se leve vraiment reste tout de meme declare absent
# en moins d'une seconde.
TIMEOUT_JOUEUR = 0.8

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
#   'sixsept_un'       l'un des deux fait le 6-7                  (defaut)
#   'sixsept_les_deux' il faut que les deux fassent le 6-7 ensemble
#   'automatique'      le kart avance tout seul, ils ne font que tourner
#   'aucune'           personne : le kart n'avance pas a deux
ACCELERATION_SANS_MILIEU = 'sixsept_un'

# ---------------------------------------------------------------------------
# Le joueur du milieu -- PROVISOIRE
# ---------------------------------------------------------------------------
# Il fait avancer le kart avec le geste "6-7" (voir six_sept.py) et lance un
# objet en ouvrant grand la bouche. Tout est regroupe dans role_milieu.py.
MILIEU_SEUIL_BOUCHE = 0.55      # bouche ouverte   -> lancer un objet
MILIEU_REPOS_OBJET = 0.8        # secondes entre deux objets

# ---------------------------------------------------------------------------
# Le geste 6-7 -> ACCELERER (six_sept.py)
# ---------------------------------------------------------------------------
# Les deux mains paumes vers le haut, qui montent et descendent en alternance.
# On mesure d = (hauteur main gauche - hauteur main droite) / largeur
# d'epaules, et on compte combien de fois d bascule d'un cote a l'autre.
#
# A regler en regardant "d=" sous chaque joueur dans la fenetre de debug :
# pendant le geste, d doit depasser nettement +SEUIL puis -SEUIL a chaque
# balancement. Au repos, mains immobiles, il doit rester entre les deux.
SIXSEPT_SEUIL = 0.15            # amplitude a franchir de chaque cote -- monter si
                                 # une main qui bouge un peu suffit a accelerer,
                                 # baisser si un vrai 6-7 n'est pas reconnu
SIXSEPT_FENETRE_S = 1.5         # fenetre dans laquelle on compte les bascules
SIXSEPT_BASCULES_MINI = 3       # bascules necessaires dans la fenetre pour que ce
                                 # soit le geste (3 = un aller-retour et demi)
SIXSEPT_MAINTIEN_S = 0.6        # sans nouvelle bascule depuis ce delai, on arrete
                                 # d'accelerer : le kart lache des que le geste s'arrete

# ---------------------------------------------------------------------------
# Les mains sur la tete, facon panique -> FREINER (mains_sur_tete.py)
# ---------------------------------------------------------------------------
# Les deux poignets au-dessus des epaules ET pres du centre de la tete.
# A regler en regardant "tete x.xx" sous chaque joueur dans la fenetre de
# debug : c'est la distance de la main la plus eloignee, en largeurs
# d'epaules. Mains sur la tete -> petite valeur ; bras leves -> grande.
FREIN_DISTANCE_TETE = 0.9       # monter si des mains bien posees ne freinent pas,
                                 # baisser si des bras leves freinent a tort
FREIN_VISIBILITE_MINI = 0.3     # plus tolerant que MAINS_VISIBILITE_MINI : une main sur
                                 # la tete est souvent a moitie cachee
FREIN_MAINTIEN_S = 0.15         # le geste doit tenir ce temps avant de freiner --
                                 # court, un frein doit etre reactif
FREIN_TOLERANCE_S = 0.25        # une image ratee ne relache pas le frein

# Qui freine quand le joueur du milieu n'est pas la ?
#   'un'        l'une des deux extremites met les mains sur la tete   (defaut)
#   'les_deux'  il faut que les deux paniquent ensemble
#   'aucun'     pas de frein a deux
FREIN_SANS_MILIEU = 'un'

# ---------------------------------------------------------------------------
# Affichage
# ---------------------------------------------------------------------------
PERIODE_ETAT = 0.5

# ---------------------------------------------------------------------------
# Telephone secoue -> TURBO (MultiSense OSC)
# ---------------------------------------------------------------------------
# Le telephone est fixe au-dessus de la chaise. MultiSense OSC diffuse ses
# capteurs par OSC sur ce port -- le meme que le volant du volet performance
# (voir PILOTE/steer_module.py), donc pas de reglage cote app a changer si le
# telephone servait deja au volant.
TELEPHONE_PORT = 8000

# Adresse OSC de l'accelerometre. Devinee par analogie avec
# /multisense/orientation/pitch (deja utilisee et confirmee pour le volant) :
# a VERIFIER sur l'app installee avec `python3 telephone.py --decouvrir`,
# qui affiche l'adresse exacte des qu'on secoue le telephone.
ADRESSE_ACCEL_X = b'/multisense/accelerometer/x'
ADRESSE_ACCEL_Y = b'/multisense/accelerometer/y'
ADRESSE_ACCEL_Z = b'/multisense/accelerometer/z'
ADRESSE_ACCEL_XYZ = b'/multisense/accelerometer'   # au cas ou les 3 valeurs arrivent groupees

# Detection de la secousse : on suit la NORME du vecteur acceleration et on
# compte ses variations brusques ("jerk") plutot qu'un seuil absolu -- ca
# marche pareil que le telephone soit a plat ou incline sur la chaise, sans
# calibration de la gravite.
SECOUSSE_SEUIL_DELTA = 8.0     # variation de norme (m/s^2 ou g, selon l'app) jugee brusque
SECOUSSE_FENETRE_S = 0.6       # fenetre dans laquelle on compte les variations brusques
SECOUSSE_PICS_MINIMUM = 3      # il en faut au moins ca dans la fenetre pour que ce soit une VRAIE secousse
SECOUSSE_REPOS_S = 1.2         # anti-rafale : temps mort apres un turbo declenche

# ---------------------------------------------------------------------------
# Sauvetage collectif -- 3 joueurs, 6 mains levees (mains_levees.py)
# ---------------------------------------------------------------------------
# Reutilise la MEME webcam que suivi_visages.py (pas de deuxieme camera) :
# les 3 joueurs sont deja dans le champ pour la direction, donc pour le
# sauvetage aussi. Personne ne peut se sauver seul, meme regle que pour le
# pilotage.
MAINS_REQUISES = 3              # au moins 3 mains levees au total (peu importe qui) --
                                 # baisse de 6 (3 joueurs x 2 mains) car la detection
                                 # des 6 en meme temps etait peu fiable en pratique
MAINS_MARGE = 0.03              # le poignet doit depasser l'epaule d'au moins ca (coord. normalisees 0-1)
MAINS_VISIBILITE_MINI = 0.5     # ignore un point que Mediapipe voit mal (occlusion, hors cadre)
MAINS_MAINTIEN_S = 0.6          # les 6 mains doivent rester levees ce temps avant de declencher
RESCUE_REPOS_S = 1.5            # anti-rafale entre deux sauvetages
MAINS_PERIODE_FRAMES = 1        # analyse de pose une image sur N. Passe de 3 a 1 pour le
                                 # geste 6-7 : un balancement dure ~0,2 s, et a une image sur
                                 # trois (5-7 analyses/s) on rate des bascules. Si la direction
                                 # devient trop lente, essayer 2 et baisser SIXSEPT_BASCULES_MINI