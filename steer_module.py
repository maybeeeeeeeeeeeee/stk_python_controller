"""
steer_module.py — Analog steering module for SuperTuxKart (via virtual Xbox 360 Controller).

Advanced Proportional Controller:
- Continuous Analog Axis (virtual gamepad ABS_X)
- Exponential Sensitivity Curve (x^1.4)
- Zero-Lag Adaptive Filter
- Automatic Calibration and Recalibration with 2 Fingers / Terminal
- Acceleration and Brake via Touchpad (sent as keyboard keys via UDP)

Sends:
- Steering: "STEER:X.XXXX" (-1.0 to 1.0)
- Acceleration / Brake: "P_ACCELERATE" / "R_ACCELERATE" and "P_BRAKE" / "R_BRAKE"
"""

import sys
import math
import threading
import time

from oscpy.server import OSCThreadServer

# ---------------------------------------------------------------------------
# Acceleration / Brake Command Table (via Keyboard)
# ---------------------------------------------------------------------------
COMMANDS = {
    "ACCELERATE": ("P_ACCELERATE", "R_ACCELERATE"),
    "BRAKE":      ("P_BRAKE",      "R_BRAKE"),
}

# ---------------------------------------------------------------------------
# Fine-tuning parameters
# ---------------------------------------------------------------------------
DEAD_ZONE           = 4.5    # Neutral tilt dead zone in degrees (straight line stability)
MAX_STEER_ANGLE     = 30.0   # Max tilt angle for 100% steering
EXPO_GAMMA          = 1.4    # Exponential curve (1.4: smooth center, aggressive edges)

# Steering and calibration
STEER_SIGN          = 1      # Change to -1 if left/right are inverted
TOUCH_TIMEOUT       = 0.20   # Seconds without touch message before releasing gas/brake
RECAL_COOLDOWN      = 0.8    # Minimum seconds between recalibrations

DEBUG_STEER         = False  # Display real-time angle and intensity telemetry
DEBUG_LOGS          = False  # Display sent UDP commands in console

# ---------------------------------------------------------------------------
# Shared State (Thread-Safe)
# ---------------------------------------------------------------------------
lock = threading.Lock()

pitch_origin            = None   # Calibrated neutral position
smoothed_pitch          = None   # Dynamically filtered angle
current_vertical        = None   # "ACCELERATE" | "BRAKE" | None
last_touch_time         = 0.0

# Two-finger detection
last_left_touch         = 0.0
last_right_touch        = 0.0
last_touch_x            = None
last_recal_time         = 0.0

# Send function injected by run_all.py
_send_fn = None


def _module_send_command(command: str):
    """Sends the command using the provided UDP callback."""
    if _send_fn is not None:
        _send_fn(command)
        if DEBUG_LOGS:
            print(f"[steer] Sent: {command}")


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def normalize_angle(angle):
    """Keeps angle difference within (-180, 180]."""
    while angle > 180:
        angle -= 360
    while angle <= -180:
        angle += 360
    return angle


def trigger_recalibrate(reason=""):
    """Resets the center (steering zero) to current orientation."""
    global pitch_origin, smoothed_pitch, last_recal_time
    global current_vertical

    now = time.time()
    if now - last_recal_time < RECAL_COOLDOWN:
        return

    with lock:
        last_recal_time = now
        if smoothed_pitch is not None:
            pitch_origin = smoothed_pitch

        # Temporarily release any active vertical command for safety
        if current_vertical is not None:
            _module_send_command(COMMANDS[current_vertical][1])
            current_vertical = None

    # Recenter analog steering immediately
    _module_send_command("STEER:0.0000")

    print("\n" + "=" * 55)
    print("🎯 CENTER RECALIBRATED! (New neutral: {:.1f}°) [{}]".format(
        pitch_origin if pitch_origin is not None else 0.0, reason))
    print("=" * 55 + "\n")


# ---------------------------------------------------------------------------
# Watchdog Thread: Releases Gas / Brake when finger is lifted
# ---------------------------------------------------------------------------
def release_watchdog():
    global current_vertical
    while True:
        time.sleep(0.04)
        with lock:
            if current_vertical is not None:
                if time.time() - last_touch_time > TOUCH_TIMEOUT:
                    _module_send_command(COMMANDS[current_vertical][1])
                    current_vertical = None


# ---------------------------------------------------------------------------
# Thread to recalibrate via Terminal Keyboard (Enter / Space / 'c')
# ---------------------------------------------------------------------------
def keyboard_listener_thread():
    while True:
        try:
            line = sys.stdin.readline()
            if line:
                trigger_recalibrate("PC terminal command")
        except Exception:
            break


# ---------------------------------------------------------------------------
# OSC Callbacks (Sensor and Touch Processing)
# ---------------------------------------------------------------------------
def on_pitch(*values):
    global pitch_origin, smoothed_pitch

    if not values:
        return
    value = float(values[0])

    # Automatic initial calibration on first received value
    if pitch_origin is None:
        pitch_origin   = value
        smoothed_pitch = value
        print("\n🎮 Initial steering calibration complete! Neutral center at {:.1f}°.".format(pitch_origin))
        print("💡 Tip: Tap with 2 fingers on the screen at any time to recalibrate the center.\n")
        return

    # Zero-Lag Adaptive Filter
    diff = abs(value - smoothed_pitch)
    adaptive_alpha = min(0.85, max(0.35, 0.35 + (diff / 12.0) * 0.50))
    smoothed_pitch = adaptive_alpha * value + (1.0 - adaptive_alpha) * smoothed_pitch

    # Delta relative to calibrated center
    delta = normalize_angle(smoothed_pitch - pitch_origin) * STEER_SIGN
    adelta = abs(delta)

    # Compute continuous analog value (-1.0 to 1.0)
    if adelta <= DEAD_ZONE:
        steer_value = 0.0
    else:
        norm = min(1.0, (adelta - DEAD_ZONE) / (MAX_STEER_ANGLE - DEAD_ZONE))
        intensity = norm ** EXPO_GAMMA
        steer_value = intensity if delta > 0 else -intensity

    # Immediate transmission of continuous value to analog axis ABS_X
    _module_send_command(f"STEER:{steer_value:.4f}")

    if DEBUG_STEER:
        bar_len = int(abs(steer_value) * 20)
        side = "R" if steer_value > 0 else "L" if steer_value < 0 else "C"
        bar = "[" + "=" * bar_len + " " * (20 - bar_len) + "]"
        print(f"delta={delta:+5.1f}° | {side} | steer={steer_value:+.4f} {bar}")


def on_pad_x(*values):
    global current_vertical, last_touch_time, last_left_touch, last_right_touch, last_touch_x

    if not values:
        return

    if len(values) >= 2:
        trigger_recalibrate("Multi-touch detected (2 fingers)")
        return

    val = float(values[0])
    now = time.time()

    if val < -0.2:
        last_left_touch = now
    elif val > 0.2:
        last_right_touch = now

    is_bilateral = (abs(last_left_touch - last_right_touch) < 0.12 and
                    (now - min(last_left_touch, last_right_touch)) < 0.25)
    is_jump = (last_touch_x is not None and
               ((last_touch_x < -0.3 and val > 0.3) or (last_touch_x > 0.3 and val < -0.3)) and
               (now - last_touch_time < 0.08))

    last_touch_x    = val
    last_touch_time = now

    if is_bilateral or is_jump:
        trigger_recalibrate("2 fingers on screen (left + right)")
        return

    new_cmd = None
    if val < -0.15:
        new_cmd = "BRAKE"
    elif val > 0.15:
        new_cmd = "ACCELERATE"

    with lock:
        if new_cmd != current_vertical:
            if current_vertical is not None:
                _module_send_command(COMMANDS[current_vertical][1])
            if new_cmd is not None:
                _module_send_command(COMMANDS[new_cmd][0])
            current_vertical = new_cmd


def on_multitouch_event(*values):
    trigger_recalibrate("Multi-touch detected")


# ---------------------------------------------------------------------------
# Module Entry Point
# ---------------------------------------------------------------------------
def start_steer(send_fn):
    """
    Starts the analog steering module.

    Args:
        send_fn: Callable that receives a string and sends via UDP.

    Returns:
        stop: Function that safely shuts down threads and OSC server.
    """
    global _send_fn
    _send_fn = send_fn

    # Start background threads (watchdog and keyboard listener)
    threading.Thread(target=release_watchdog, daemon=True).start()
    threading.Thread(target=keyboard_listener_thread, daemon=True).start()

    PITCH_ADDRESS = b'/multisense/orientation/pitch'
    PAD_ADDRESS_X = b'/multisense/pad/x'

    osc = OSCThreadServer()
    osc.listen(address='0.0.0.0', port=8000, default=True)

    osc.bind(PITCH_ADDRESS, on_pitch)
    osc.bind(PAD_ADDRESS_X, on_pad_x)
    osc.bind(b'/multisense/pad/touches', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/x', on_multitouch_event)
    osc.bind(b'/multisense/pad/2/y', on_multitouch_event)
    osc.bind(b'/multisense/multitouch', on_multitouch_event)

    print()
    print("=" * 65)
    print("🏎️  ANALOG STEER MODULE STARTED (OSC port 8000)")
    print("=" * 65)
    print("  * Mobile Phone (MultiSense OSC):")
    print("    - Orientation (pitch)  -> Continuous Analog Wheel (STEER:float)")
    print("    - Touch Pad (X)        -> Accelerate (right) / Brake (left)")
    print("    - 2 Fingers / Terminal -> Recalibrate center")
    print("=" * 65)
    print()

    def stop():
        global current_vertical
        with lock:
            if current_vertical is not None:
                _module_send_command(COMMANDS[current_vertical][1])
                current_vertical = None
        # Recenter analog wheel
        _module_send_command("STEER:0.0000")
        time.sleep(0.05)
        try:
            osc.stop()
        except Exception as e:
            print(f"[steer] Warning while stopping OSC: {e}")
        print("[steer] Steer module stopped.")

    return stop
