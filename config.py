"""
Central configuration module for "face + head + voice".

>>> IMPORTANT <<<
The keys defined here must be EXACTLY the same as those
configured in SuperTuxKart (Options > Controls), and consistent with
the hardware team's Arduino firmware, to avoid any conflicts.
"""

from pynput.keyboard import Key

# ---------------------------------------------------------------------------
# 0. UDP server address (STK_input_server_v2.py)
# ---------------------------------------------------------------------------
STK_SERVER_ADDRESS = ('localhost', 6006)

# ---------------------------------------------------------------------------
# 1. Action -> keyboard key mapping table
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
# 2. Model paths (to download, see README.md)
# ---------------------------------------------------------------------------
FACE_MODEL_PATH = "models/face_landmarker.task"
VOSK_MODEL_PATH = "models/vosk-model-small-en-us-0.15"

# ---------------------------------------------------------------------------
# 3. Camera
# ---------------------------------------------------------------------------
CAMERA_INDEX = 0          # PC webcam (0 = default camera)
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
DEBUG_WINDOW = True       # Displays a window with live scores, useful for calibration

# ---------------------------------------------------------------------------
# 4. Facial expression thresholds
#    Each "held" (continuous) expression has an engage threshold
#    and a lower release threshold -> avoids flickering (hysteresis)
#    when the score oscillates around a single value.
# ---------------------------------------------------------------------------
SMILE_ENGAGE = 0.50
SMILE_RELEASE = 0.35

WINK_LEFT_ENGAGE = 0.40
WINK_LEFT_RELEASE_OTHER_EYE = 0.30    # Right eye must stay open (low score)

WINK_RIGHT_ENGAGE = 0.25              # Lower by default: right eye is often less sharp
WINK_RIGHT_RELEASE_OTHER_EYE = 0.30   # Left eye must stay open (low score)

JAW_OPEN_THRESHOLD = 0.60       # One-time action (impulse) -> Fire
JAW_OPEN_COOLDOWN_S = 0.6       # Anti-spam cooldown between mouth "Fire" actions

EYEBROW_ENGAGE = 0.45          # Raised eyebrows -> Look Back (activation)
EYEBROW_RELEASE = 0.30         # Relaxed eyebrows -> Look Back (deactivation with hysteresis)

DRIFT_ROLL_ENGAGE = 18.0       # Lateral tilt (ear to shoulder) in degrees -> Drift (activation)
DRIFT_ROLL_RELEASE = 10.0      # Head returning to upright in degrees -> Drift (deactivation with hysteresis)

# ---------------------------------------------------------------------------
# 5. Head thresholds (yaw = turn head, pitch = nod head)
# ---------------------------------------------------------------------------
LOOK_BACK_YAW_THRESHOLD_DEG = 35.0   # Clear head turn -> Look back (held)

NOD_PITCH_DIP_DEG = 15.0             # Downward head nod -> Rescue (impulse)
NOD_MAX_DURATION_S = 0.8             # Nod must be brief
RESCUE_COOLDOWN_S = 1.5

# ---------------------------------------------------------------------------
# 6. Voice (Vosk, restricted English grammar)
#    Restricting the recognized vocabulary to these few words makes Vosk
#    much faster and more reliable when shouting keywords during gameplay.
# ---------------------------------------------------------------------------
VOICE_SAMPLE_RATE = 16000

VOICE_ACTION_MAP = {
    "turbo": "NITRO",    # UDP command sent to server
    "fire": "FIRE",      # UDP command sent to server
    # Add other commands if needed
}

VOICE_COOLDOWN_S = 1.0   # Anti-spam: same keyword cannot re-trigger before this delay

# ---------------------------------------------------------------------------
# 7. Press duration for "impulse" actions (Fire, Turbo, Rescue)
#    A press/release that is too brief is not always registered by the game.
# ---------------------------------------------------------------------------
PULSE_HOLD_S = 0.15
