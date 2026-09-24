#!/usr/bin/env python3
"""Volet collaboratif : trois personnes, un kart, une webcam.

    python collaboratif.py                 joue pour de vrai
    python collaboratif.py --simulation    n'envoie rien, affiche tout
    python collaboratif.py --sans-fenetre  sans la fenetre de debug

La chaine
---------
    webcam --> collaboratif.py --UDP:6006--> tools/stk_server_maintien.py --> STK
    telephone (secoue) --OSC:8000--> telephone.py --------^

La regle
--------
    joueur de GAUCHE  : penche la tete -> le kart tourne a gauche
    joueur de DROITE  : penche la tete -> le kart tourne a droite
    joueur du MILIEU  : fait le geste 6-7 -> accelere (voir six_sept.py)
                        mains sur la tete -> freine (voir mains_sur_tete.py)

C'est la PLACE qui decide du sens, pas le cote vers lequel on penche.

Personne ne peut conduire seul, et deux joueurs qui se contredisent s'annulent.

Deux ajouts, independants de la direction
------------------------------------------
    telephone secoue (fixe au-dessus de la chaise, MultiSense OSC)
        -> TURBO. Voir telephone.py -- l'adresse OSC de l'accelerometre est a
        verifier une fois avec `python3 telephone.py --decouvrir`.

    6 mains levees (les 3 joueurs, 2 mains chacun, en meme temps)
        -> sauvetage collectif (RESCUE). Voir mains_levees.py -- reutilise la
        MEME webcam que la direction, pas de camera en plus. Meme regle que
        pour piloter : personne ne peut se sauver seul.

A DEUX
------
Le milieu est optionnel : la partie demarre des que les deux extremites sont
la, et il peut arriver ou repartir en cours de route. Sans lui, un secours fait
avancer le kart -- par defaut, il suffit qu'une des deux extremites fasse le
geste 6-7.
Voir ACCELERATION_SANS_MILIEU dans config_collab.py.

Pendant la partie
-----------------
    C   recalibrer la position de repos de tout le monde
    Q   quitter (ou Ctrl+C dans le terminal)

La fenetre de debug montre les zones, le role attribue a chacun, l'angle
mesure, et le compteur de mains levees. C'est l'outil de reglage : on y lit
les chiffres pendant que les joueurs font le geste, et on regle ANGLE_MINI
(ou MAINS_MARGE) dessus.
"""

import argparse
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config_collab as cfg
import role_milieu
import telephone
from equipe import Equipe, ROLES, GAUCHE, MILIEU, DROITE, role_selon_x
from mains_levees import MainsLevees
from six_sept import SixSept
from mains_sur_tete import MainsSurTete
from modulation import ToucheModulee
from suivi_visages import SuiviVisages

# sortie_stk vit dans PILOTE/ : config_collab l'a deja mis dans le chemin.
from sortie_stk import SortieSTK

COULEURS = {GAUCHE: (80, 200, 80), MILIEU: (80, 200, 255), DROITE: (255, 160, 80)}


def dessiner(image, equipe, vus, compte_a_rebours, mains, sixsept, frein,
             maintenant):
    """La fenetre de reglage : zones, roles, angles, mains levees."""
    h, l = image.shape[:2]

    for x in (cfg.ZONE_GAUCHE_FIN, cfg.ZONE_DROITE_DEBUT):
        cv2.line(image, (int(x * l), 0), (int(x * l), h), (60, 60, 60), 2)

    # Les etiquettes sont deduites de l'attribution reelle, pas ecrites en dur :
    # si INVERSER_ROLES change, la fenetre dit toujours la verite.
    for x_texte, x_zone in ((0.02, 0.1), (0.42, 0.5), (0.80, 0.9)):
        role = role_selon_x(x_zone)
        cv2.putText(image, role.upper(), (int(x_texte * l), 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, COULEURS[role], 2)

    for role, (visage, _) in vus.items():
        joueur = equipe.joueurs[role]
        x1, y1, x2, y2 = visage.boite
        cv2.rectangle(image, (x1, y1), (x2, y2), COULEURS[role], 2)

        if not joueur.calibre:
            texte = '%s : non calibre' % role
        else:
            intention = joueur.intention_direction()
            intensite = joueur.intensite_direction()
            fleche = '  %s %d%%' % (intention.upper(), intensite * 100)                 if intention else ''
            texte = '%s %+.0f deg%s' % (role, joueur.ecart, fleche)

            # Jauge de braquage : c'est elle qu'on regarde pour regler
            # ANGLE_MAXI et COURBE. Un chiffre qui monte trop vite se voit
            # tout de suite.
            largeur = x2 - x1
            cv2.rectangle(image, (x1, y2 + 8), (x2, y2 + 22), (60, 60, 60), 1)
            if intensite > 0:
                cv2.rectangle(image, (x1, y2 + 8),
                              (x1 + int(largeur * intensite), y2 + 22),
                              COULEURS[role], -1)
        cv2.putText(image, texte, (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COULEURS[role], 2)

        # Le geste 6-7 : c'est la valeur d qu'on regarde pour regler
        # SIXSEPT_SEUIL. Elle doit passer nettement de + a - a chaque
        # balancement des mains.
        actif = sixsept.actif(role)
        cv2.putText(image, sixsept.texte(role) + ('  -> ACCELERE' if actif else ''),
                    (x1, y2 + 42), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 0, 255) if actif else COULEURS[role], 2)

        # Le frein : "tete x.xx" est la distance mains -> tete en largeurs
        # d'epaules. C'est elle qu'on regarde pour regler FREIN_DISTANCE_TETE.
        freine = frein.actif(role)
        cv2.putText(image, frein.texte(role) + ('  -> FREINE' if freine else ''),
                    (x1, y2 + 64), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                    (0, 0, 255) if freine else COULEURS[role], 2)

    if compte_a_rebours:
        cv2.putText(image, compte_a_rebours, (int(l * 0.3), int(h * 0.55)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3)

    # Un requis manquant bloque la partie (rouge) ; le milieu manquant ne la
    # bloque pas (gris), il est optionnel.
    requis = equipe.manquants_requis()
    if requis:
        cv2.putText(image, 'il manque : ' + ', '.join(requis), (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    elif not equipe.joueurs[MILIEU].vu:
        cv2.putText(image, 'milieu absent (optionnel)', (10, h - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (170, 170, 170), 2)

    # Compteur de mains levees, pour regler MAINS_MARGE et MAINS_MAINTIEN_S en
    # regardant la barre se remplir pendant le geste.
    besoin = cfg.MAINS_REQUISES
    pret = mains.dernier_compte >= besoin
    couleur_mains = (0, 0, 255) if pret else (255, 255, 255)
    cv2.putText(image, 'Mains levees: %d/%d  (%d personnes vues)'
                % (mains.dernier_compte, besoin, mains.dernier_nombre_personnes),
                (10, h - 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur_mains, 2)
    barre_x, barre_y, barre_l, barre_h = 10, h - 35, 200, 12
    cv2.rectangle(image, (barre_x, barre_y), (barre_x + barre_l, barre_y + barre_h),
                  (255, 255, 255), 1)
    remplissage = int(barre_l * mains.progression(maintenant))
    if remplissage > 0:
        cv2.rectangle(image, (barre_x, barre_y), (barre_x + remplissage, barre_y + barre_h),
                      (0, 0, 255), -1)

    cv2.imshow('Collaboratif - C recalibrer, Q quitter', image)


def main():
    p = argparse.ArgumentParser(description='Trois joueurs, un kart.')
    p.add_argument('--simulation', action='store_true',
                   help='affiche les commandes sans les envoyer')
    p.add_argument('--silencieux', action='store_true',
                   help='n affiche plus chaque commande envoyee')
    p.add_argument('--sans-fenetre', action='store_true',
                   help='pas de fenetre de debug')
    args = p.parse_args()

    fenetre = cfg.FENETRE_DEBUG and not args.sans_fenetre

    if not os.path.exists(cfg.MODELE_VISAGE):
        print('Modele introuvable : %s' % cfg.MODELE_VISAGE)
        print('Lance PILOTE\\preparer.ps1 une fois.')
        return 1

    if not os.path.exists(cfg.MODELE_POSE):
        print('Modele de pose introuvable : %s' % cfg.MODELE_POSE)
        print('Telecharge pose_landmarker_lite.task (voir le README racine)')
        print('et place-le a cote de face_landmarker.task dans models/.')
        return 1

    sortie = SortieSTK(serveur=cfg.SERVEUR_STK,
                       envoi_reel=not args.simulation,
                       trace=not args.silencieux)
    equipe = Equipe()
    suivi = SuiviVisages()
    mains = MainsLevees()
    sixsept = SixSept()
    frein = MainsSurTete()

    print()
    print('=== COLLABORATIF : deux ou trois joueurs, un kart ===')
    if args.simulation:
        print('MODE SIMULATION : rien n est envoye au serveur.')
    else:
        print('Commandes envoyees a %s:%d.' % cfg.SERVEUR_STK)
        if cfg.DIRECTION_ANALOGIQUE:
            print('Direction ANALOGIQUE : il faut un serveur qui cree')
            print('une manette -> python tools\\stk_server_manette.py -d')
        else:
            print('Le serveur doit tourner : python tools\\stk_server_maintien.py -d')
    print('Telephone secoue (au-dessus de la chaise) -> TURBO.')
    print('Geste 6-7 (mains en alternance) -> ACCELERER.')
    print('Mains sur la tete (panique) -> FREINER.')
    print('Mains levees (les joueurs, ensemble) -> sauvetage collectif.')
    print()

    try:
        suivi.demarrer()
    except Exception as erreur:
        print('Camera : %s' % erreur)
        return 1

    mains.demarrer()
    arreter_telephone = telephone.demarrer(sortie)

    print('Camera %d ouverte en %dx%d.'
          % (cfg.CAMERA_INDEX, suivi.largeur, suivi.hauteur))
    print()
    print('Installez-vous devant la webcam, chacun dans sa zone.')
    print('Il faut au minimum : %s. Le milieu est optionnel et peut'
          % ' et '.join(cfg.ROLES_REQUIS))
    print('arriver ou partir en cours de partie.')
    print('Sans lui, ce qui fait avancer le kart : %s.'
          % cfg.ACCELERATION_SANS_MILIEU)
    print()

    calibre = False
    debut_attente = None
    prochaine_ligne = 0.0
    compteur_images = 0

    # UNE seule touche modulee, pour la direction resultante. Une par joueur
    # ne marcherait pas : leurs cycles seraient dephases, donc quand les deux
    # penchent ils n'appuieraient presque jamais au meme instant. Au lieu de
    # s'annuler, leurs demandes s'alterneraient et le kart partirait en
    # crabe -- mesure faite, 5 P_RIGHT et 2 P_LEFT sur une etape ou le kart
    # devait aller tout droit.
    modulateur = ToucheModulee(cfg.PERIODE_MODULATION, cfg.APPUI_MINIMUM,
                               cfg.PERIODE_MAXI)

    try:
        while True:
            image, visages = suivi.lire()
            if image is None:
                continue

            vus = equipe.mettre_a_jour(visages)
            maintenant = time.time()
            texte_compte = ''

            # ----------------------------------------------------------------
            # Sauvetage collectif : meme image, un PoseLandmarker en plus.
            # Aucun rapport avec la calibration de la direction -- ca marche
            # meme avant que l'equipe soit calibree, exactement comme il faut
            # pouvoir se sauver a tout moment de la course.
            #
            # Une image sur MAINS_PERIODE_FRAMES seulement : le geste se tient
            # deja MAINS_MAINTIEN_S avant de declencher, donc le verifier a
            # chaque image ne sert a rien et coute du temps de calcul a la
            # direction -- qui, elle, doit rester reactive.
            # ----------------------------------------------------------------
            compteur_images += 1
            if compteur_images % cfg.MAINS_PERIODE_FRAMES == 0:
                if mains.traiter(image, maintenant):
                    sortie.pulse('rescue', cfg.RESCUE_REPOS_S)
                    print('-- SAUVETAGE COLLECTIF (mains levees) --')
                # Meme poses, second geste : le 6-7 pour accelerer.
                sixsept.mettre_a_jour(mains.dernieres_poses, image.shape[1],
                                      image.shape[0], maintenant)
                # Et un troisieme : les mains sur la tete pour freiner.
                frein.mettre_a_jour(mains.dernieres_poses, image.shape[1],
                                    image.shape[0], maintenant)

            # ----------------------------------------------------------------
            # Calibration : on attend que les trois soient vus, puis un compte
            # a rebours. Calibrer avant que quelqu'un soit en place, c'est
            # retenir un repos qui n'est celui de personne -- meme piege qu'au
            # TP1 avec le volant calibre sur des zeros.
            # ----------------------------------------------------------------
            if not calibre:
                if equipe.requis_presents():
                    if debut_attente is None:
                        debut_attente = maintenant
                        # Surtout pas "vus" : ce nom porte deja le dictionnaire
                        # des visages vus, que dessiner() attend plus bas.
                        roles_vus = equipe.presents()
                        print('Joueurs vus : %s. Ne bougez plus.'
                              % ', '.join(roles_vus))
                        if MILIEU not in roles_vus:
                            print('Le milieu n est pas la : on demarre quand meme,')
                            print('il pourra arriver en cours de partie.')
                    restant = cfg.DELAI_CALIBRATION - (maintenant - debut_attente)
                    if restant > 0:
                        texte_compte = 'calibration dans %d' % (int(restant) + 1)
                    else:
                        roles = equipe.calibrer()
                        calibre = True
                        print('Repos retenu pour : %s' % ', '.join(roles))
                        print('C pour recalibrer, Q pour quitter.')
                        print()
                else:
                    debut_attente = None
                    texte_compte = ('en attente de : %s'
                                    % ', '.join(equipe.manquants_requis()))

            # ----------------------------------------------------------------
            # Les demandes. Chaque joueur est une SOURCE nommee : la fusion et
            # l'annulation des demandes opposees sont deja faites par SortieSTK.
            # ----------------------------------------------------------------
            if calibre:
                # groupe() : les trois joueurs sont appliques d'un seul coup.
                # Un par un, la sortie passerait par des etats qui n'ont jamais
                # existe -- par exemple "droite seul demandeur" en quittant une
                # situation ou les deux penchaient.
                # Un joueur arrive apres coup (le milieu, ou une extremite qui
                # etait hors champ) est calibre tout seul une seconde apres son
                # arrivee. Sans ca il resterait sans neutre, donc muet.
                tardifs = equipe.calibrer_les_retardataires()
                if tardifs:
                    print('-- arrive en cours de partie, calibre : %s --'
                          % ', '.join(tardifs))

                # Tir a la corde : les deux demandes se SOUSTRAIENT avant
                # d'etre transformees en appuis. A force egale, resultante
                # nulle et le kart va tout droit ; si l'un tire plus fort, le
                # kart tourne de la difference, proportionnellement. C'est la
                # regle "ils s'annulent", en version continue.
                net = (equipe.joueurs[DROITE].intensite_direction()
                       - equipe.joueurs[GAUCHE].intensite_direction())
                if net > 0:
                    direction = 'right'
                elif net < 0:
                    direction = 'left'
                else:
                    direction = None

                if cfg.DIRECTION_ANALOGIQUE:
                    # Une consigne continue, que le serveur applique a l'axe
                    # d'une manette virtuelle. Rien a moduler : le jeu recoit
                    # directement la valeur.
                    sortie.steer(net)
                    with sortie.groupe():
                        sortie.set_continuous('left', 'equipe', False)
                        sortie.set_continuous('right', 'equipe', False)
                else:
                    # Repli : la fleche n'est pas tenue, elle est battue au
                    # rythme de la resultante. Proportionnel malgre une touche
                    # qui ne connait que tout ou rien.
                    actif = modulateur.etat(abs(net), maintenant)
                    with sortie.groupe():
                        sortie.set_continuous('left', 'equipe',
                                              actif and direction == 'left')
                        sortie.set_continuous('right', 'equipe',
                                              actif and direction == 'right')

                # Hors du if/else : le milieu doit agir QUELLE QUE SOIT la
                # direction. Il etait auparavant dans la branche des fleches
                # seulement -- en direction analogique, le kart n'accelerait
                # jamais et la ligne d'etat plantait (texte_milieu indefini).
                texte_milieu = role_milieu.appliquer(equipe, sortie, sixsept,
                                                    frein)
            else:
                texte_milieu = '-'
                net = 0.0

            if maintenant >= prochaine_ligne:
                prochaine_ligne = maintenant + cfg.PERIODE_ETAT
                resultante = ('%+4.0f%%' % (net * 100)) if calibre else '   -'
                print('touches=[%s]  net=%s   %s   | milieu: %s'
                      % (sortie.etat_texte(), resultante, equipe.etat_texte(),
                         texte_milieu))

            if fenetre:
                dessiner(image, equipe, vus, texte_compte, mains, sixsept,
                         frein, maintenant)
                touche = cv2.waitKey(1) & 0xFF
                if touche == ord('q'):
                    break
                if touche == ord('c'):
                    roles = equipe.calibrer()
                    calibre = bool(roles)
                    print('-- repos recalibre pour : %s --'
                          % (', '.join(roles) if roles else 'personne'))

    except KeyboardInterrupt:
        pass
    finally:
        role_milieu.relacher(sortie)
        sortie.release_all()
        arreter_telephone()
        mains.arreter()
        suivi.arreter()
        if fenetre:
            cv2.destroyAllWindows()
        print()
        print('Arrete, toutes les touches relachees.')
    return 0


if __name__ == '__main__':
    sys.exit(main())