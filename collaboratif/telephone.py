#!/usr/bin/env python3
"""telephone.py -- Turbo au telephone secoue (MultiSense OSC).

Le telephone est fixe au-dessus de la chaise. MultiSense OSC diffuse son
accelerometre par OSC, sur le meme port que le volant du volet performance
(PILOTE/steer_module.py) : 8000, adresses "/multisense/...". Secouer la
chaise -> TURBO.

    telephone (accelerometre) --OSC:8000--> telephone.py --> sortie.pulse('turbo')

Detection de la secousse
-------------------------
Pas besoin de connaitre l'orientation du telephone ni de soustraire la
gravite : on suit uniquement la NORME du vecteur acceleration (x, y, z) et on
compte a quelle vitesse elle varie d'un echantillon au suivant (le "jerk").
Une vraie secousse produit plusieurs grandes variations rapprochees ; pousser
ou tourner la chaise normalement en produit au plus une ou deux, isolees.
D'ou la regle : il faut plusieurs depassements de seuil dans une petite
fenetre de temps, pas un seul pic, avant de déclencher.

Adresse OSC de l'accelerometre : A VERIFIER
--------------------------------------------
Le volant du volet performance utilise deja et confirme
"/multisense/orientation/pitch". Par analogie, ce module ecoute
"/multisense/accelerometer/x", "/y", "/z" (et, au cas ou l'app envoie les
trois valeurs groupees, "/multisense/accelerometer"). Si l'app installee
utilise une autre adresse, rien ne se declenchera : lancer

    python3 telephone.py --decouvrir

et secouer le telephone. Le terminal affiche alors l'adresse OSC exacte
recue, a copier dans ADRESSE_ACCEL_* de config_collab.py.
"""

import argparse
import collections
import math
import socket
import threading
import time

from oscpy.server import OSCThreadServer

import config_collab as cfg


class DetecteurSecousse:
    """Declenche quand la norme de l'acceleration varie brusquement,
    plusieurs fois de suite, dans une petite fenetre de temps.

    Compter les PICS plutot que comparer a un seuil absolu evite deux faux
    departs : un unique choc (poser le telephone, une bosse) qui ne fait rien
    a la conduite, et une secousse molle qui franchirait un seuil absolu bas
    mais correspondrait juste a la chaise qu'on pousse.
    """

    def __init__(self, seuil_delta, fenetre_s, minimum_pics, repos_s):
        self.seuil_delta = seuil_delta
        self.fenetre_s = fenetre_s
        self.minimum_pics = minimum_pics
        self.repos_s = repos_s
        self._derniere_norme = None
        self._pics = collections.deque()
        self._dernier_declenchement = 0.0

    def observer(self, x, y, z):
        """A appeler a chaque nouvel echantillon. Rend True au moment exact
        ou la secousse est reconnue (une seule fois par secousse)."""
        norme = math.sqrt(x * x + y * y + z * z)
        maintenant = time.monotonic()

        if self._derniere_norme is not None:
            delta = abs(norme - self._derniere_norme)
            if delta > self.seuil_delta:
                self._pics.append(maintenant)
        self._derniere_norme = norme

        while self._pics and maintenant - self._pics[0] > self.fenetre_s:
            self._pics.popleft()

        if (len(self._pics) >= self.minimum_pics
                and maintenant - self._dernier_declenchement >= self.repos_s):
            self._dernier_declenchement = maintenant
            self._pics.clear()
            return True
        return False


def _lire_adresse_osc(paquet):
    """Extrait le pattern d'adresse (chaine C terminee par \\0) du debut d'un
    paquet OSC brut. Ne depend d'aucune bibliotheque : sert au mode
    --decouvrir, justement pour trouver la bonne adresse sans la supposer."""
    fin = paquet.find(b'\x00')
    if fin <= 0:
        return None
    return paquet[:fin].decode('utf-8', errors='replace')


def decouvrir(port):
    """Affiche chaque adresse OSC recue (une seule fois), pour trouver
    l'adresse exacte de l'accelerometre sur l'app installee."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    print('Ecoute sur le port %d -- secoue le telephone (Ctrl+C pour arreter).' % port)
    print('Adresses vues :')
    vues = set()
    try:
        while True:
            paquet, expediteur = sock.recvfrom(4096)
            adresse = _lire_adresse_osc(paquet)
            if adresse and adresse not in vues:
                vues.add(adresse)
                print('  %s   (depuis %s)' % (adresse, expediteur[0]))
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()


def demarrer(sortie):
    """Demarre l'ecoute OSC du telephone dans ce process.

    Args:
        sortie: un SortieSTK (ou tout objet avec une methode
            pulse(action, cooldown_s)).

    Rend une fonction stop() a appeler a l'arret.
    """
    detecteur = DetecteurSecousse(
        seuil_delta=cfg.SECOUSSE_SEUIL_DELTA,
        fenetre_s=cfg.SECOUSSE_FENETRE_S,
        minimum_pics=cfg.SECOUSSE_PICS_MINIMUM,
        repos_s=cfg.SECOUSSE_REPOS_S,
    )
    dernier = {'x': 0.0, 'y': 0.0, 'z': 0.0}
    verrou = threading.Lock()

    def _traiter_echantillon():
        with verrou:
            x, y, z = dernier['x'], dernier['y'], dernier['z']
        if detecteur.observer(x, y, z):
            sortie.pulse('turbo', cfg.SECOUSSE_REPOS_S)
            print('[telephone] SECOUSSE -> TURBO')

    def on_x(*valeurs):
        if not valeurs:
            return
        with verrou:
            dernier['x'] = float(valeurs[0])
        _traiter_echantillon()

    def on_y(*valeurs):
        if not valeurs:
            return
        with verrou:
            dernier['y'] = float(valeurs[0])
        _traiter_echantillon()

    def on_z(*valeurs):
        if not valeurs:
            return
        with verrou:
            dernier['z'] = float(valeurs[0])
        _traiter_echantillon()

    def on_xyz(*valeurs):
        if len(valeurs) < 3:
            return
        with verrou:
            dernier['x'], dernier['y'], dernier['z'] = (
                float(valeurs[0]), float(valeurs[1]), float(valeurs[2]))
        _traiter_echantillon()

    osc = OSCThreadServer()
    osc.listen(address='0.0.0.0', port=cfg.TELEPHONE_PORT, default=True)
    osc.bind(cfg.ADRESSE_ACCEL_X, on_x)
    osc.bind(cfg.ADRESSE_ACCEL_Y, on_y)
    osc.bind(cfg.ADRESSE_ACCEL_Z, on_z)
    osc.bind(cfg.ADRESSE_ACCEL_XYZ, on_xyz)

    print()
    print('=' * 55)
    print('TELEPHONE (MultiSense OSC, port %d) : secouer -> TURBO' % cfg.TELEPHONE_PORT)
    print('Rien ne se passe en secouant ? Verifie l adresse OSC avec :')
    print('    python3 telephone.py --decouvrir')
    print('=' * 55)
    print()

    def stop():
        try:
            osc.stop()
        except Exception as e:
            print('[telephone] avertissement a l arret : %s' % e)

    return stop


def main():
    p = argparse.ArgumentParser(description='Turbo au telephone secoue (test independant).')
    p.add_argument('--decouvrir', action='store_true',
                   help='affiche les adresses OSC recues, pour trouver celle de l accelerometre')
    p.add_argument('--simulation', action='store_true',
                   help='affiche les secousses detectees sans rien envoyer au serveur')
    args = p.parse_args()

    if args.decouvrir:
        decouvrir(cfg.TELEPHONE_PORT)
        return

    if args.simulation:
        class _SortieFactice:
            def pulse(self, action, cooldown_s=0.0):
                print('[simulation] pulse(%r)' % action)
        sortie = _SortieFactice()
    else:
        # Test independant de collaboratif.py : envoie directement au serveur STK.
        _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        class _SortieDirecte:
            def pulse(self, action, cooldown_s=0.0):
                mot = {'turbo': 'NITRO', 'rescue': 'RESCUE'}.get(action)
                if mot:
                    _sock.sendto(mot.encode(), cfg.SERVEUR_STK)
        sortie = _SortieDirecte()

    stop = demarrer(sortie)
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        stop()


if __name__ == '__main__':
    main()
