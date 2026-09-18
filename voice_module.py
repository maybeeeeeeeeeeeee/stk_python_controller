"""
Module "voix" : reconnaissance vocale hors-ligne (Vosk) avec un vocabulaire
volontairement restreint (grammaire) pour être rapide et fiable sur des mots
criés en pleine partie ("turbo", "fire"...).
"""

import json
import queue
import threading

import sounddevice as sd
import vosk

import config
from config import VOICE_ACTION_MAP, VOICE_COOLDOWN_S, VOICE_SAMPLE_RATE


class VoiceWorker(threading.Thread):
    def __init__(self, controller):
        super().__init__(daemon=True)
        self._controller = controller
        self._stop_event = threading.Event()
        self._audio_queue = queue.Queue()

    def stop(self):
        self._stop_event.set()

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            # Sur-utilisation du buffer, sous-échantillonnage, etc.
            # On log mais on ne bloque pas la capture.
            print(f"[voice] statut audio: {status}")
        self._audio_queue.put(bytes(indata))

    def run(self):
        vosk.SetLogLevel(-1)  # silencieux
        model = vosk.Model(config.VOSK_MODEL_PATH)

        # Grammaire restreinte : seuls ces mots (+ "[unk]" pour le reste) sont
        # reconnus, ce qui rend Vosk beaucoup plus rapide et précis ici.
        grammar_words = list(VOICE_ACTION_MAP.keys()) + ["[unk]"]
        grammar = json.dumps(grammar_words)
        recognizer = vosk.KaldiRecognizer(model, VOICE_SAMPLE_RATE, grammar)

        with sd.RawInputStream(
            samplerate=VOICE_SAMPLE_RATE,
            blocksize=4000,
            dtype="int16",
            channels=1,
            callback=self._audio_callback,
        ):
            while not self._stop_event.is_set():
                try:
                    data = self._audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    text = json.loads(recognizer.Result()).get("text", "")
                else:
                    text = json.loads(recognizer.PartialResult()).get("partial", "")

                self._check_keywords(text)

    def _check_keywords(self, text: str):
        if not text:
            return
        words = text.lower().split()
        for word in words:
            action = VOICE_ACTION_MAP.get(word)
            if action:
                self._controller.pulse(action, VOICE_COOLDOWN_S)
