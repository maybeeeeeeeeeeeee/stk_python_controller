# SuperTuxKart — Contrôleur visage / tête / voix

Module Python qui pilote SuperTuxKart via des expressions du visage, des
mouvements de tête et des mots-clés vocaux, en émulant les touches du
clavier.

Ce module fait partie d'un projet collaboratif plus large qui inclut
également un contrôleur Arduino (chaise roulante, volant, frein à main,
bonbonne à gaz). Il constitue le canal de contrôle **mains libres** :
accélération, tir et nitro pilotés par le visage et la voix, en
complément des commandes physiques gérées par l'Arduino.

## Sommaire

- [Fonctionnement](#fonctionnement)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration de SuperTuxKart](#configuration-de-supertuxkart)
- [Lancement](#lancement)
- [Structure du dépôt](#structure-du-dépôt)
- [Réglages et calibration](#réglages-et-calibration)
- [Dépannage](#dépannage)

## Fonctionnement

| Geste / voix | Type | Action | Touche |
|---|---|---|---|
| Sourire (maintenu) | continu | Accélérer | Haut |
| Bouche grande ouverte | impulsion | Tirer | Espace |
| Sourcils levés | impulsion | Nitro | N |
| Clin d'œil gauche | continu | Tourner à gauche | Gauche |
| Clin d'œil droit | continu | Tourner à droite | Droit |
| Tête tournée (maintenue) | continu | Regarder en arrière | B |
| Hochement de tête bref | impulsion | Sauvetage | Retour arrière |
| Crier « turbo » | impulsion | Nitro | N |
| Crier « fire » | impulsion | Tirer | Espace |

**Impulsion** : l'action se déclenche une fois par geste détecté.
**Continu** : la touche reste enfoncée tant que le geste est maintenu.

## Prérequis

- Python 3.9 ou supérieur
- Une webcam fonctionnelle (pour la détection visage/tête)
- Un microphone fonctionnel (pour la détection vocale)
- SuperTuxKart installé
- ~60 Mo d'espace disque pour les modèles (voir ci-dessous)

## Installation

1. Cloner le dépôt puis installer les dépendances Python :

   ```bash
   pip install -r requirements.txt
   ```

2. Télécharger les deux modèles nécessaires (non inclus dans le dépôt
   car trop volumineux pour Git) :

   | Modèle | Rôle | Taille | Lien | Destination |
   |---|---|---|---|---|
   | `face_landmarker.task` | Visage / tête (Mediapipe) | ~4 Mo | [Télécharger](https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task) | `models/face_landmarker.task` |
   | `vosk-model-small-en-us-0.15` | Reconnaissance vocale (Vosk) | ~50 Mo | [Télécharger](https://alphacephei.com/vosk/models) | `models/vosk-model-small-en-us-0.15/` (dézippé) |

   Après téléchargement, l'arborescence `models/` doit ressembler à :

   ```
   models/
   ├── face_landmarker.task
   └── vosk-model-small-en-us-0.15/
       └── ... (fichiers du modèle)
   ```

## Configuration de SuperTuxKart

Dans **Options > Contrôles**, assigner les touches exactement comme
indiqué dans le tableau de la section [Fonctionnement](#fonctionnement)
(et dans `config.py`). Un décalage entre les touches configurées dans
le jeu et celles définies dans `config.py` empêchera les gestes de
fonctionner correctement.

## Lancement

```bash
python main.py
```

Pour arrêter proprement :
- `Ctrl+C` dans le terminal, ou
- `q` dans la fenêtre de debug (si affichée)

## Structure du dépôt

```
.
├── main.py                # point d'entrée
├── config.py               # touches, seuils, chemins des modèles
├── input_controller.py     # gestion clavier thread-safe
├── face_module.py          # webcam + Mediapipe (visage, tête)
├── voice_module.py         # micro + Vosk (mots-clés)
├── requirements.txt
├── models/                 # modèles téléchargés (non versionnés)
└── docs/                   # documentation complémentaire
```

## Réglages et calibration

Les seuils de détection (durée de maintien, sensibilité des clins
d'œil, sensibilité du sourire, etc.) se règlent dans `config.py`. Il
est recommandé de calibrer ces valeurs en fonction :
- de l'éclairage de la pièce,
- de la distance webcam/visage,
- de la morphologie du visage de l'utilisateur.

## Dépannage

- **Aucune détection du visage** : vérifier que la webcam est bien
  détectée par le système et que `face_landmarker.task` est présent
  dans `models/`.
- **Aucune détection vocale** : vérifier les permissions du
  microphone et que le dossier `vosk-model-small-en-us-0.15/` est
  bien dézippé (et non resté en `.zip`).
- **Gestes mal reconnus** : ajuster les seuils dans `config.py` (voir
  [Réglages et calibration](#réglages-et-calibration)).
- **Les touches ne font rien dans le jeu** : vérifier que les touches
  assignées dans SuperTuxKart correspondent exactement à celles de
  `config.py`.
