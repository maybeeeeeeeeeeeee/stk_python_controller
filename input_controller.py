"""
Contrôleur clavier partagé entre les modules visage et voix.

Deux types d'actions :
- "continues" (ex: accelerate, look_back) : une source dit "actif" ou
  "inactif", la touche est maintenue enfoncée tant qu'au moins une source
  la demande (logique OR).
- "impulsions" (ex: fire, turbo, rescue) : un press+release bref, avec un
  cooldown par action pour éviter le spam.

Thread-safe : plusieurs threads (visage, voix) peuvent appeler ce
contrôleur en même temps sans se marcher dessus.
"""

import threading
import time

from pynput.keyboard import Controller

from config import KEY_MAP, PULSE_HOLD_S


class KeyboardController:
    def __init__(self):
        self._keyboard = Controller()
        self._lock = threading.Lock()
        # pour chaque action continue, l'ensemble des sources qui la demandent
        self._active_sources = {}          # action -> set(source_name)
        self._currently_pressed = set()    # actions dont la touche est physiquement enfoncée
        self._last_pulse_time = {}         # action -> timestamp du dernier déclenchement

    # -- Actions continues (maintenues) -------------------------------------------------
    def set_continuous(self, action: str, source: str, active: bool):
        """Une source (ex: 'face_smile') indique si elle demande l'action ou non."""
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

    # -- Actions ponctuelles (impulsions) -------------------------------------------------
    def pulse(self, action: str, cooldown_s: float):
        """Déclenche un press+release bref, en respectant un cooldown par action."""
        if action not in KEY_MAP:
            return
        now = time.monotonic()
        with self._lock:
            last = self._last_pulse_time.get(action, 0.0)
            if now - last < cooldown_s:
                return  # trop tôt, on ignore (anti-spam)
            self._last_pulse_time[action] = now

        # le press/release réel se fait hors du verrou pour ne pas bloquer
        # les autres threads pendant le petit délai de maintien
        key = KEY_MAP[action]
        self._keyboard.press(key)
        threading.Timer(PULSE_HOLD_S, lambda: self._keyboard.release(key)).start()

    def release_all(self):
        """À appeler en sortie de programme pour ne laisser aucune touche coincée."""
        with self._lock:
            for action in list(self._currently_pressed):
                self._keyboard.release(KEY_MAP[action])
            self._currently_pressed.clear()
            self._active_sources.clear()
