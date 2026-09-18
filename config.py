"""
Configuration centrale du module "visage + tête/corps + voix".

>>> IMPORTANT <<<
Les touches définies ici doivent être EXACTEMENT les mêmes que celles
configurées dans SuperTuxKart (Options > Contrôles), et cohérentes avec
le firmware Arduino de l'équipe hardware, pour éviter tout conflit.
"""

from pynput.keyboard import Key

# ---------------------------------------------------------------------------
# 1. Table de correspondance action -> touche clavier
#    (reprend la table validée dans le plan)
# ---------------------------------------------------------------------------
KEY_MAP = {
    "accelerate": Key.up,
    "brake": Key.down,
    "left": Key.left,
    "right": Key.right,
    "fire": Key.space,
    "turbo": "n",
    "drift": "v",
    "rescue": Key.backspace,
    "look_back": "b",
}

# ---------------------------------------------------------------------------
# 2. Chemins des modèles (à télécharger, voir README.md)
# ---------------------------------------------------------------------------
FACE_MODEL_PATH = "models/face_landmarker.task"
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"

# ---------------------------------------------------------------------------
# 3. Caméra
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0          # webcam du PC (0 = caméra par défaut)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
DEBUG_WINDOW = True        # affiche une fenêtre avec les scores en direct, utile pour calibrer

# ---------------------------------------------------------------------------
# 4. Seuils des expressions du visage
#    Chaque expression "maintenue" (continue) a un seuil d'activation (engage)
#    et un seuil de relâche (release) plus bas -> évite le scintillement
#    (hystérésis) quand le score oscille autour d'une seule valeur.
# ---------------------------------------------------------------------------
SMILE_ENGAGE = 0.50
SMILE_RELEASE = 0.35

WINK_LEFT_ENGAGE = 0.40
WINK_LEFT_RELEASE_OTHER_EYE = 0.30    # l'œil droit doit rester ouvert (score bas)

WINK_RIGHT_ENGAGE = 0.25              # plus bas par défaut : l'œil droit est souvent moins net
WINK_RIGHT_RELEASE_OTHER_EYE = 0.30   # l'œil gauche doit rester ouvert (score bas)

JAW_OPEN_THRESHOLD = 0.60       # action ponctuelle (impulsion) -> Fire
JAW_OPEN_COOLDOWN_S = 0.6       # anti-spam entre deux "Fire" par la bouche

EYEBROW_ENABLED = True          # bonus optionnel: sourcils levés -> Nitro
EYEBROW_THRESHOLD = 0.55
EYEBROW_COOLDOWN_S = 1.0

# ---------------------------------------------------------------------------
# 5. Seuils de la tête (yaw = tourner la tête, pitch = hocher la tête)
#    Ces valeurs sont des points de départ : lance main.py avec
#    DEBUG_WINDOW=True, observe les valeurs affichées en tournant/hochant
#    la tête, puis ajuste-les. Le signe peut être inversé selon la caméra.
# ---------------------------------------------------------------------------
LOOK_BACK_YAW_THRESHOLD_DEG = 35.0   # tête tournée franchement -> Look back (maintenu)

NOD_PITCH_DIP_DEG = 15.0             # hochement de tête vers le bas -> Rescue (impulsion)
NOD_MAX_DURATION_S = 0.8             # le hochement doit être bref
RESCUE_COOLDOWN_S = 1.5

# ---------------------------------------------------------------------------
# 6. Voix (Vosk, grammaire restreinte en anglais)
#    On limite volontairement le vocabulaire reconnu à ces quelques mots :
#    ça rend Vosk beaucoup plus rapide et fiable sur un mot crié.
# ---------------------------------------------------------------------------
VOICE_SAMPLE_RATE = 16000

VOICE_ACTION_MAP = {
    "turbo": "turbo",
    "fire": "fire",
    # Ajoutez d'autres mots ici si l'équipe le décide, par ex. :
    # "brake": "brake",
    # "left": "left",
    # "right": "right",
}

VOICE_COOLDOWN_S = 1.0   # anti-spam: un même mot ne redéclenche pas avant ce délai

# ---------------------------------------------------------------------------
# 7. Durée d'appui pour les actions "impulsion" (Fire, Turbo, Rescue)
#    Un simple press/release trop court n'est pas toujours capté par le jeu.
# ---------------------------------------------------------------------------
PULSE_HOLD_S = 0.15
