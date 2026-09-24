#!/usr/bin/env python3
"""Le role du joueur du milieu, et ce qui se passe quand il n'est pas la.

>>> C'est le fichier a remplacer quand le role du milieu sera decide. <<<

Tout tient dans appliquer(). Les deux joueurs des extremites n'en dependent
pas : on peut changer ce fichier entierement sans toucher au reste.

Le milieu est OPTIONNEL
-----------------------
La partie demarre des que les deux extremites sont la. Le milieu peut arriver
en cours de route -- il est calibre tout seul une seconde apres son arrivee --
ou repartir sans que rien ne soit a relancer.

Mais quelqu'un doit faire avancer le kart, sinon une partie a deux se joue avec
un kart a l'arret. D'ou le SECOURS, choisi par ACCELERATION_SANS_MILIEU dans
config_collab.py :

    'sixsept_un'        l'une des deux extremites fait le 6-7 -> on accelere (defaut)
    'sixsept_les_deux'  il faut que les deux fassent le 6-7 ensemble
    'automatique'       le kart avance tout seul, ils ne font que tourner
    'aucune'            personne : le kart n'avance pas a deux

Le secours s'efface des que le milieu revient, et inversement : ce sont deux
sources nommees differentes, la sortie gere le passage de l'une a l'autre.

Ce que fait le milieu quand il est la
-------------------------------------
    geste 6-7 (mains en alternance, voir six_sept.py)  ->  accelerer
    mains sur la tete, facon panique (mains_sur_tete.py) ->  freiner
    bouche grande ouverte ->  lancer un objet

Quelques pistes, pour quand on en parlera
-----------------------------------------
  - l'accelerateur, comme ici : le milieu decide de la vitesse, les cotes de la
    trajectoire. Simple, et la dependance est totale dans les deux sens.
  - le frein et le nitro seulement : les cotes gerent la vitesse autrement, le
    milieu arbitre les moments critiques.
  - les objets et le sauvetage : le milieu ne conduit pas, il assiste -- role
    de copilote, plus social que mecanique.
  - un droit de veto : tant que le milieu ouvre la bouche, les cotes n'ont plus
    la main. Le plus interessant a observer, le plus penible a jouer.
"""

import config_collab as cfg
from equipe import GAUCHE, DROITE, MILIEU

NOM = 'milieu'
SECOURS = 'secours'     # l'acceleration quand le milieu n'est pas la


def _secours(equipe, sixsept):
    """(accelere, explication) selon le mode choisi. Le milieu est absent."""
    mode = cfg.ACCELERATION_SANS_MILIEU

    if mode == 'automatique':
        return True, 'secours automatique'

    if mode == 'aucune':
        return False, 'aucun secours'

    presents = [role for role in (GAUCHE, DROITE) if equipe.joueurs[role].vu]
    if not presents:
        return False, 'secours : personne de vu'

    gestes = [sixsept.actif(role) for role in presents]
    if mode == 'sixsept_les_deux':
        accelere = len(gestes) == 2 and all(gestes)
        detail = 'les deux font le 6-7'
    else:   # 'sixsept_un', le defaut
        accelere = any(gestes)
        detail = 'un des deux fait le 6-7'

    return accelere, 'secours (%s) %s' % (
        detail, '[ACCELERE]' if accelere else
        ' '.join(sixsept.texte(role) for role in presents))


def _frein_secours(equipe, frein):
    """(freine, explication) quand le milieu est absent."""
    mode = cfg.FREIN_SANS_MILIEU
    if mode == 'aucun':
        return False, ''
    presents = [role for role in (GAUCHE, DROITE) if equipe.joueurs[role].vu]
    gestes = [frein.actif(role) for role in presents]
    if mode == 'les_deux':
        freine = len(gestes) == 2 and all(gestes)
    else:   # 'un', le defaut
        freine = any(gestes)
    return freine, ' [FREINE]' if freine else ''


def appliquer(equipe, sortie, sixsept, frein):
    """Traduit le milieu -- ou son absence -- en demandes au kart.

    sixsept : l'objet SixSept de six_sept.py, deja mis a jour pour l'image.
    frein   : l'objet MainsSurTete de mains_sur_tete.py, idem.
    Rend un texte court pour la ligne d'etat.

    Accelerer et freiner en meme temps (par exemple une extremite qui fait le
    6-7 pendant que l'autre panique) s'annulent dans SortieSTK (OPPOSEES) :
    le kart roule en roue libre. Meme regle que pour la direction.
    """
    joueur = equipe.joueurs[MILIEU]

    if not joueur.vu:
        # Absent : on relache ce qu'il tenait, sinon le kart resterait bloque
        # a fond des qu'il sort du champ de la webcam. Puis le secours prend
        # le relais pour que la partie reste jouable a deux.
        accelere, texte = _secours(equipe, sixsept)
        freine, texte_frein = _frein_secours(equipe, frein)
        with sortie.groupe():
            sortie.set_continuous('accelerate', NOM, False)
            sortie.set_continuous('brake', NOM, False)
            sortie.set_continuous('accelerate', SECOURS, accelere)
            sortie.set_continuous('brake', SECOURS, freine)
        return 'absent, ' + texte + texte_frein

    accelere = sixsept.actif(MILIEU)
    freine = frein.actif(MILIEU)
    with sortie.groupe():
        # Il est la : le secours n'a plus rien a demander.
        sortie.set_continuous('accelerate', SECOURS, False)
        sortie.set_continuous('brake', SECOURS, False)
        sortie.set_continuous('accelerate', NOM, accelere)
        sortie.set_continuous('brake', NOM, freine)

    bouche = joueur.visage.forme('jawOpen')
    if bouche > cfg.MILIEU_SEUIL_BOUCHE:
        sortie.pulse('fire', cfg.MILIEU_REPOS_OBJET)

    return '%s%s  %s%s  bouche=%.2f' % (
        sixsept.texte(MILIEU), ' (ACCELERE)' if accelere else '',
        frein.texte(MILIEU), ' (FREINE)' if freine else '', bouche)


def relacher(sortie):
    """A appeler a l'arret du programme."""
    for action in ('accelerate', 'brake'):
        sortie.set_continuous(action, NOM, False)
        sortie.set_continuous(action, SECOURS, False)
