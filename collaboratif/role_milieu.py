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

    'sourire_un'        l'une des deux extremites sourit  -> on accelere (defaut)
    'sourire_les_deux'  il faut que les deux sourient
    'automatique'       le kart avance tout seul, ils ne font que tourner
    'aucune'            personne : le kart n'avance pas a deux

Le secours s'efface des que le milieu revient, et inversement : ce sont deux
sources nommees differentes, la sortie gere le passage de l'une a l'autre.

Ce que fait le milieu quand il est la
-------------------------------------
    sourire maintenu      ->  accelerer
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


def _secours(equipe):
    """(accelere, explication) selon le mode choisi. Le milieu est absent."""
    mode = cfg.ACCELERATION_SANS_MILIEU
    extremites = [equipe.joueurs[GAUCHE], equipe.joueurs[DROITE]]
    sourires = [j.sourire for j in extremites if j.vu]

    if mode == 'automatique':
        return True, 'secours automatique'

    if mode == 'aucune':
        return False, 'aucun secours'

    if not sourires:
        return False, 'secours : personne de vu'

    seuil = cfg.SEUIL_SOURIRE_EXTREMITE
    if mode == 'sourire_les_deux':
        accelere = len(sourires) == 2 and all(s > seuil for s in sourires)
        detail = 'les deux sourient'
    else:   # 'sourire_un', le defaut
        accelere = any(s > seuil for s in sourires)
        detail = 'un des deux sourit'

    return accelere, 'secours (%s) %s' % (
        detail, '[ACCELERE]' if accelere else ' '.join(
            '%.2f' % s for s in sourires))


def appliquer(equipe, sortie):
    """Traduit le milieu -- ou son absence -- en demandes au kart.

    Rend un texte court pour la ligne d'etat.
    """
    joueur = equipe.joueurs[MILIEU]

    if not joueur.vu:
        # Absent : on relache ce qu'il tenait, sinon le kart resterait bloque
        # a fond des qu'il sort du champ de la webcam. Puis le secours prend
        # le relais pour que la partie reste jouable a deux.
        sortie.set_continuous('accelerate', NOM, False)
        accelere, texte = _secours(equipe)
        sortie.set_continuous('accelerate', SECOURS, accelere)
        return 'absent, ' + texte

    # Il est la : le secours n'a plus rien a demander.
    sortie.set_continuous('accelerate', SECOURS, False)

    sourire = joueur.sourire
    bouche = joueur.visage.forme('jawOpen')

    accelere = sourire > cfg.MILIEU_SEUIL_SOURIRE
    sortie.set_continuous('accelerate', NOM, accelere)

    if bouche > cfg.MILIEU_SEUIL_BOUCHE:
        sortie.pulse('fire', cfg.MILIEU_REPOS_OBJET)

    return 'sourire=%.2f%s  bouche=%.2f' % (
        sourire, ' (ACCELERE)' if accelere else '', bouche)


def relacher(sortie):
    """A appeler a l'arret du programme."""
    sortie.set_continuous('accelerate', NOM, False)
    sortie.set_continuous('accelerate', SECOURS, False)
