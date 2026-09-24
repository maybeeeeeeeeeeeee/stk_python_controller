# Mode collaboratif — trois personnes, un kart

Le mode performance cherche à piloter le mieux possible, **seul**. Celui-ci
cherche l'inverse : rendre le pilotage **impossible seul**. Deux ou trois
joueurs côte à côte devant **une seule webcam**, et le kart n'obéit que s'ils se
coordonnent.

```
      webcam
        |
  [GAUCHE] [MILIEU] [DROITE]      les joueurs sur un banc
      |        |        |
   tourne   accélère  tourne
   à gauche  (6-7)   à droite
            freine
         (mains sur
          la tête)
```

Il réutilise le serveur d'entrée du mode performance
([`STK_input_server_v2.py`](../STK_input_server_v2.py)) sans rien y changer :
même port, même vocabulaire, même `STEER:` analogique.

Deux ajouts tournent en même temps que la direction, sans rien y changer non
plus :

- **téléphone secoué -> TURBO** : le téléphone est fixé au-dessus de la
  chaise, MultiSense OSC diffuse son accéléromètre par OSC (même app, même
  port 8000 que le volant du volet performance). Voir [`telephone.py`](telephone.py).
- **6 mains levées -> sauvetage collectif (RESCUE)** : les 3 joueurs lèvent
  les deux mains en même temps, tenu un court instant. Réutilise la MÊME
  webcam que la direction. Voir [`mains_levees.py`](mains_levees.py).

Les deux suivent la même règle que le pilotage : **personne ne peut le faire
seul.**

---

## La règle

| Joueur | Ce qu'il peut faire | Ce qu'il ne peut pas |
|---|---|---|
| **gauche** | pencher la tête → le kart tourne à **gauche** | tourner à droite |
| **droite** | pencher la tête → le kart tourne à **droite** | tourner à gauche |
| **milieu** | accélérer en faisant le **geste 6-7**, freiner avec les **mains sur la tête**, tirer en ouvrant la bouche | tourner |

**C'est la place qui décide du sens, pas le geste** : peu importe de quel côté
la tête est penchée, celui de gauche fait tourner à gauche. Et plus il penche,
plus le kart tourne.

Trois conséquences voulues :

- **personne ne peut conduire seul** — il faut deux personnes pour suivre un
  virage ;
- **si les deux extrémités penchent ensemble, leurs intensités se soustraient** :
  à force égale le kart va tout droit, sinon il tourne de la différence. Le tir à
  la corde est l'information, pas un bug ;
- **un joueur qui sort du champ relâche ses commandes** — le kart ne reste jamais
  bloqué en virage parce que quelqu'un s'est levé.

Le **milieu est optionnel** : la partie démarre dès que les deux extrémités sont
vues, et il peut arriver ou repartir en cours de route (il est calibré tout seul
une seconde après son arrivée). Sans lui, un secours fait avancer le kart — par
défaut il suffit qu'une des deux extrémités fasse le geste 6-7
(`ACCELERATION_SANS_MILIEU` dans `config_collab.py`).

---

## Accélérer : le geste 6-7

Les deux mains devant soi, paumes vers le haut, à hauteur de poitrine, qui
montent et descendent **en alternance** (le trend « six seven »). Tant que le
geste continue, le kart accélère ; il s'arrête, le kart lâche l'accélérateur.

Détection dans [`six_sept.py`](six_sept.py), sur les poses que
`mains_levees.py` calcule déjà (aucun modèle en plus). Pour chaque joueur :
`d = (hauteur main gauche − hauteur main droite) / largeur d'épaules`. Le 6-7,
c'est `d` qui bascule de `+SIXSEPT_SEUIL` à `−SIXSEPT_SEUIL` plusieurs fois de
suite. Lever ou baisser les deux mains **ensemble** ne compte pas, et des mains
au-dessus des épaules non plus (c'est le sauvetage).

Réglage : dans la fenêtre de debug, `d=` s'affiche sous chaque joueur. Pendant
le geste il doit passer nettement de + à −, au repos rester proche de 0.

---

## Freiner : les mains sur la tête, façon panique

Le réflexe de quelqu'un qui voit l'accident arriver : les deux mains posées sur
le crâne ou contre les tempes. Tant qu'elles y restent, le kart freine.

Détection dans [`mains_sur_tete.py`](mains_sur_tete.py), sur les mêmes poses :
les deux poignets plus hauts que les épaules **et** à moins de
`FREIN_DISTANCE_TETE` largeurs d'épaules du centre de la tête.

Pour ne pas confondre avec le sauvetage, `mains_levees.py` ne compte plus que
les bras tendus **loin** de la tête : paniquer ne déclenche jamais de sauvetage.

Sans le milieu, une extrémité peut freiner à sa place (`FREIN_SANS_MILIEU`).
Si quelqu'un accélère pendant qu'un autre freine, les deux s'annulent et le kart
roule en roue libre, comme pour la direction.

Réglage : `tete x.xx` s'affiche sous chaque joueur (distance mains → tête, en
largeurs d'épaules). Mains sur la tête : environ 0,3 à 0,5 ; bras levés :
au-dessus de 1.

Son rôle définitif **reste à décider** : tout est isolé dans `role_milieu.py`,
une seule fonction à remplacer, avec quatre pistes listées dans son en-tête.

---

## Lancer

Le modèle Mediapipe (visages) est le même que celui du mode performance
(`models/face_landmarker.task`, voir le [README racine](../README.md)). Le
sauvetage collectif a besoin d'un second modèle, `models/pose_landmarker_lite.task`
(voir la section [Sauvetage collectif](#sauvetage-collectif--6-mains-levées)
ci-dessous pour le lien de téléchargement).

Deux terminaux :

```bash
# Terminal 1 — le serveur d'entrée (celui du mode performance, inchangé)
python3 STK_input_server_v2.py -d

# Terminal 2 — le mode collaboratif (direction + téléphone + mains levées, tout en un)
python3 collaboratif/collaboratif.py
```

Puis SuperTuxKart **en fenêtré**, une course lancée, et cliquer dans sa fenêtre.

Pendant la partie, dans la fenêtre vidéo : **C** recalibre la position de repos
de tout le monde, **Q** quitte.

Pour régler sans rien envoyer au jeu :

```bash
python3 collaboratif/collaboratif.py --simulation
```

### Sous Windows

`STK_input_server_v2.py` a besoin de `/dev/uinput`, donc de Linux. Le jumeau
Windows est [`STK_input_server_win.py`](../STK_input_server_win.py) : même port,
même vocabulaire, manette virtuelle via **ViGEmBus / vgamepad** au lieu de
evdev.

```powershell
pip install vgamepad          # le pilote ViGEmBus doit etre installe
python STK_input_server_win.py -d
```

S'il ne trouve pas `vgamepad`, il ne refuse pas de démarrer : il traduit les
`STEER:` en appuis modulés sur les flèches. Moins fluide, mais le client n'a pas
à le savoir.

---

## Téléphone secoué -> turbo

Le téléphone est fixé au-dessus de la chaise. L'app **MultiSense OSC** diffuse
son accéléromètre par OSC, sur le même port (8000) que le volant du volet
performance — si le téléphone servait déjà au volant, rien à changer côté
app.

Ce module démarre et s'arrête tout seul avec `collaboratif.py` : pas de
troisième terminal.

**L'adresse OSC de l'accéléromètre est une hypothèse à vérifier.** Le volant
utilise et confirme `/multisense/orientation/pitch` ; par analogie, ce module
écoute `/multisense/accelerometer/x`, `/y`, `/z`. Si secouer le téléphone ne
déclenche rien, trouve la bonne adresse avec :

```bash
python3 collaboratif/telephone.py --decouvrir
```

puis secoue le téléphone : le terminal affiche chaque adresse OSC reçue.
Reporte l'adresse correcte dans `ADRESSE_ACCEL_X/Y/Z` de `config_collab.py`.

Réglages dans `config_collab.py` (section « Téléphone secoué ») :
- `SECOUSSE_SEUIL_DELTA` : variation de l'accélération jugée « brusque » —
  monter si de simples mouvements de la chaise déclenchent le turbo à tort.
- `SECOUSSE_PICS_MINIMUM` / `SECOUSSE_FENETRE_S` : il faut ce nombre de
  variations brusques dans cette fenêtre de temps pour que ce soit une vraie
  secousse, et pas un unique choc.
- `SECOUSSE_REPOS_S` : anti-rafale entre deux turbos.

Pour tester le téléphone seul, sans lancer tout `collaboratif.py` :

```bash
python3 collaboratif/telephone.py --simulation   # affiche les secousses sans rien envoyer
python3 collaboratif/telephone.py                # envoie NITRO au serveur STK directement
```

---

## Sauvetage collectif — 6 mains levées

Les 3 joueurs lèvent les deux mains en même temps (6 mains levées au total),
tenu un court instant -> **RESCUE**. Réutilise la **même webcam** que la
direction (`mains_levees.py` analyse la même image que `suivi_visages.py`,
en plus) : pas de deuxième caméra à brancher. Même règle que pour piloter :
personne ne peut se sauver seul.

Modèle Mediapipe nécessaire (en plus de `face_landmarker.task`) :

| Modèle | Rôle | Lien | Destination |
|---|---|---|---|
| `pose_landmarker_lite.task` | Mains levées (Mediapipe Pose) | [Télécharger](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task) | `models/pose_landmarker_lite.task` |

Réglages dans `config_collab.py` (section « Sauvetage collectif ») :
- `MAINS_MARGE` : à augmenter si une main à peine levée compte à tort, à
  diminuer si une main bien levée n'est pas détectée. Se règle en regardant
  le compteur dans la fenêtre de debug pendant le geste.
- `MAINS_MAINTIEN_S` : durée pendant laquelle les 6 mains doivent rester
  levées avant de déclencher — évite qu'un geste furtif (s'étirer, replacer
  ses cheveux) déclenche un sauvetage.
- `RESCUE_REPOS_S` : anti-rafale entre deux sauvetages.

---

---

## Tester sans les joueurs

```bash
python3 collaboratif/faux_joueurs.py            # à trois
python3 collaboratif/faux_joueurs.py --a-deux   # le milieu arrive puis repart
```

Remplace la webcam par un scénario écrit. Tout le reste du programme est le
vrai, du calcul des rôles jusqu'aux commandes envoyées sur le 6006. Pratique
pour vérifier la chaîne avant une séance, quand personne n'est là pour jouer.

Ce que ça **ne** teste pas : la détection Mediapipe elle-même, ni la qualité du
roulis sur un vrai visage. Un scénario rejoué ne remplace pas une mesure.

---

## Ce qui a demandé une mesure

Quatre choses de ce mode n'étaient devinables par personne. Elles sont notées
ici parce qu'elles se dérégleraient silencieusement si quelqu'un y touchait
sans savoir.

### 1. Les rôles sont attribués par zone, pas par classement

Un classement gauche-à-droite se refait à chaque image : trois images sans
détecter le visage du milieu, et le joueur de droite devient le joueur du
milieu, puis redevient celui de droite. **Deux personnes échangent leurs
commandes en pleine course**, sans que rien ne le signale.

Une zone fixe ne peut pas faire ça. Son coût — il faut se placer dans sa zone —
est dessiné dans la fenêtre de debug.

### 2. Le roulis est calculé, et deux corrections sont indispensables

L'angle vient de la droite qui joint les deux coins d'œil (points 33 et 263 du
maillage Mediapipe), comme un angle de volant calculé à partir de deux points
qu'on voit : pas de dérive, pas de blocage de cardan.

- Les coordonnées Mediapipe sont normalisées **chacune par sa dimension**, donc
  il faut les remultiplier par largeur et hauteur avant l'`atan2`. Sans ça, en
  16/9, une inclinaison réelle de 15° est lue **25,5°** — 70 % d'erreur.
- L'angle est ramené dans (−90°, +90°] parce qu'une droite et son opposée sont
  la même droite. Sans ça, **l'image en miroir place le repos pile sur la
  coupure à 180°** d'`atan2` : deux poses écartées de 20° donnaient un écart
  calculé de −340° et le kart braquait à fond.

### 3. La direction analogique, et son repli

`DIRECTION_ANALOGIQUE = True` envoie `STEER:<-1..1>` au serveur, qui l'applique à
l'axe de la manette virtuelle. C'est ce qui rend la direction fluide, exactement
comme dans le mode performance.

À `False`, on retombe sur une **flèche modulée** : elle n'est pas tenue mais
battue en rythme, ce qui donne quand même du proportionnel avec une touche
tout-ou-rien. Mesuré, 3 s à 60 images/s :

| inclinaison | intensité | temps flèche tenue | durée d'un appui |
|---|---|---|---|
| 0 à 6° | 0 % | rien | — |
| 8° | 10 % | 11 % | 35 ms |
| 13° | 25 % | 26 % | 35 ms |
| 16° | 38 % | 39 % | 47 ms |
| 20° | 60 % | 61 % | 73 ms |
| 23° | 79 % | 81 % | 97 ms |
| 26° et + | 100 % | 100 % | flèche tenue |

**Aucun appui ne descend sous 35 ms**, et c'est volontaire : un appui de 8 ms
n'est jamais vu par le jeu, un appui de 16 ms — une image à 60 fps — l'est
toujours. Un appui plus court ne braquerait pas moins, il ne braquerait **pas**.
Pour descendre en intensité on espace les appuis au lieu de les raccourcir.

### 4. Une seule touche modulée pour la résultante

Pas une par joueur : leurs cycles se déphaseraient, ils n'appuieraient presque
jamais au même instant, et au lieu de s'annuler leurs demandes s'alterneraient.
Mesuré avant correction : 5 `P_RIGHT` et 2 `P_LEFT` sur une étape où le kart
devait aller tout droit. Les intensités se soustraient **avant** la modulation.

---

## Les réglages

Tous dans `config_collab.py`, à régler en regardant la **jauge** sous chaque
visage dans la fenêtre de debug — on fait le geste, on lit les degrés, on fixe le
seuil dessus.

| Réglage | Effet | Équivalent côté performance |
|---|---|---|
| `ANGLE_MINI` (6°) | zone morte | `DEAD_ZONE` |
| `ANGLE_MAXI` (26°) | inclinaison pour le braquage complet | `MAX_STEER_ANGLE` |
| `COURBE` (1,6) | douceur près du neutre | `EXPO_GAMMA` |
| `LISSAGE` (0,35) | moyenne glissante sur l'angle | — |
| `ZONE_GAUCHE_FIN` / `ZONE_DROITE_DEBUT` | frontières des zones | — |
| `MIROIR` | aspect de l'image seulement (l'angle est compensé) | — |
| `ACCELERATION_SANS_MILIEU` | qui accélère quand le milieu n'est pas là | — |

---

## Les fichiers

| Fichier | Rôle |
|---|---|
| `collaboratif.py` | point d'entrée : boucle webcam, calibration, fenêtre de debug |
| `equipe.py` | qui est qui (zones), et ce que chacun demande au kart |
| `suivi_visages.py` | Mediapipe multi-visages : position, roulis, expressions |
| `mains_levees.py` | Mediapipe multi-pose sur la même image : sauvetage collectif (mains levées) |
| `six_sept.py` | geste 6-7 (mains en alternance) -> accélérer, sur les mêmes poses |
| `mains_sur_tete.py` | mains sur la tête (panique) -> freiner, sur les mêmes poses |
| `telephone.py` | téléphone secoué (MultiSense OSC) -> turbo ; `--decouvrir` pour trouver l'adresse OSC |
| `role_milieu.py` | **le rôle du milieu — provisoire, à remplacer** |
| `modulation.py` | braquage proportionnel sur une touche tout-ou-rien (repli) |
| `sortie_stk.py` | fusion des sources, arbitrage, envoi des seuls changements |
| `config_collab.py` | tous les réglages |
| `faux_joueurs.py` | scénario scripté, pour tester sans webcam ni figurants |

---

## Quand ça ne marche pas

| Symptôme | Cause la plus fréquente |
|---|---|
| `en attente de : gauche` en boucle | une extrémité est hors zone ou hors champ ; la fenêtre de debug dit laquelle |
| à deux, le kart ne démarre pas | il faut faire le 6-7, ou passer `ACCELERATION_SANS_MILIEU` à `'automatique'` |
| le 6-7 n'est pas reconnu | `d=` ne dépasse pas ±`SIXSEPT_SEUIL` : baisser le seuil, ou faire des balancements plus amples ; vérifier que poignets et épaules sont dans le champ |
| le kart accélère sans le geste | monter `SIXSEPT_SEUIL` ou `SIXSEPT_BASCULES_MINI` |
| les mains sur la tête ne freinent pas | `tete x.xx` au-dessus de `FREIN_DISTANCE_TETE` : monter le seuil ; ou poignets trop cachés, baisser `FREIN_VISIBILITE_MINI` |
| des bras levés freinent à tort | baisser `FREIN_DISTANCE_TETE` |
| la direction est devenue lente | `MAINS_PERIODE_FRAMES` à 2 (et `SIXSEPT_BASCULES_MINI` à 2) |
| le milieu arrivé en cours reste muet | il se calibre une seconde après son arrivée ; s'il reste `NON CALIBRE`, il est hors zone |
| l'étiquette de la zone de gauche dit « DROITE » | `INVERSER_ROLES` |
| pencher la tête ne fait rien | `ANGLE_MINI` trop haut |
| le kart braque par à-coups | `LISSAGE` trop bas, ou direction analogique désactivée |
| le kart ne tourne pas alors que les deux penchent | c'est la règle : leurs demandes se soustraient |
| tout est lent, les visages sautent | baisser la résolution dans `config_collab.py` |
| les touches partent dans le terminal | le focus n'est pas sur le jeu |
| secouer le téléphone ne fait rien | l'adresse OSC ne correspond pas à l'app installée : `python3 telephone.py --decouvrir` |
| le turbo part tout seul, sans secousse | `SECOUSSE_SEUIL_DELTA` trop bas, ou `SECOUSSE_PICS_MINIMUM` trop petit |
| le sauvetage collectif ne se déclenche jamais | `pose_landmarker_lite.task` absent de `models/`, ou les 3 joueurs ne sont pas visibles épaules + poignets compris |
| le sauvetage se déclenche trop facilement | monter `MAINS_MARGE` et/ou `MAINS_MAINTIEN_S` |
