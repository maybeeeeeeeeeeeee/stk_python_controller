"""
Shared keyboard controller between face and voice modules (legacy).

Two types of actions:
- "continuous" (e.g. accelerate, look_back): a source signals "active" or
  "inactive", the key is held down as long as at least one source requests it (OR logic).
- "impulses" (e.g. fire, turbo, rescue): a brief press+release, with a
  per-action cooldown to prevent spam.

Thread-safe: multiple threads (face, voice) can call this controller
concurrently without race conditions.
"""

import threading
import time

from pynput.keyboard import Controller

from config import KEY_MAP, PULSE_HOLD_S


class KeyboardController:
    def __init__(self):
        self._keyboard = Controller()
        self._lock = threading.Lock()
        # For each continuous action, the set of requesting sources
        self._active_sources = {}          # action -> set(source_name)
        self._currently_pressed = set()    # actions whose key is physically pressed down
        self._last_pulse_time = {}         # action -> timestamp of last trigger

    # -- Continuous (held) actions -------------------------------------------------
    def set_continuous(self, action: str, source: str, active: bool):
        """A source (e.g. 'face_smile') indicates whether it requests the action."""
        if action not in KEY_MAP:
            return
        with self._lock:
            sources = self._active_sources.setdefault(action, set())
            if active:
                sources.add(source)
            else:
                sources.discard(source)

            should_be_pressed = len(sources) > 0
            is_pressed = action in self._currently_pressed

            if should_be_pressed and not is_pressed:
                self._keyboard.press(KEY_MAP[action])
                self._currently_pressed.add(action)
            elif not should_be_pressed and is_pressed:
                self._keyboard.release(KEY_MAP[action])
                self._currently_pressed.discard(action)

    # -- One-time (impulse) actions -------------------------------------------------
    def pulse(self, action: str, cooldown_s: float):
        """Triggers a brief press+release, respecting a per-action cooldown."""
        if action not in KEY_MAP:
            return
        now = time.monotonic()
        with self._lock:
            last = self._last_pulse_time.get(action, 0.0)
            if now - last < cooldown_s:
                return  # Too early, ignore (anti-spam)
            self._last_pulse_time[action] = now

        # Actual press/release is done outside the lock to avoid blocking other threads
        key = KEY_MAP[action]
        self._keyboard.press(key)
        threading.Timer(PULSE_HOLD_S, lambda: self._keyboard.release(key)).start()

    def release_all(self):
        """Call on program exit so no keys remain stuck."""
        with self._lock:
            for action in list(self._currently_pressed):
                self._keyboard.release(KEY_MAP[action])
            self._currently_pressed.clear()
            self._active_sources.clear()
