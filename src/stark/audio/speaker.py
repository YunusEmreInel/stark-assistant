"""Seslendirme: sentez thread'i (Piper/sherpa-onnx) + çalma thread'i (sounddevice).

Sentez bir sonraki cümleyi hazırlarken çalma önceki cümleyi çalar, cümle arası boşluk kısalır.
cancel(session) o oturumun ve öncekilerin kuyruktaki/çalınan seslerini keser.
"""
import queue
import random
import threading
from typing import Callable

import numpy as np
import sherpa_onnx
import sounddevice as sd

from ..ai.text_for_speech import to_speech
from ..config import MODELS_DIR, Settings
from .capture import resolve_device

HEADSET_HINTS = ("kulak", "head", "buds", "hands-free", "airpods", "earphone", "kablosuz")


def output_is_headset(device_name: str = "") -> bool:
    try:
        name = sd.query_devices(resolve_device(device_name, "output"), kind="output")["name"].lower()
    except Exception:  # noqa: BLE001
        return False
    return any(h in name for h in HEADSET_HINTS)


class Speaker:
    def __init__(self, settings: Settings,
                 on_sentence_done: Callable[[int], None],
                 on_ack_done: Callable[[int], None],
                 on_error: Callable[[int, str], None],
                 on_level: Callable[[float], None] = lambda v: None):
        self.s = settings
        self.on_sentence_done = on_sentence_done
        self.on_ack_done = on_ack_done
        self.on_error = on_error
        self.on_level = on_level
        self._text_q: queue.Queue = queue.Queue(maxsize=50)
        self._audio_q: queue.Queue = queue.Queue(maxsize=4)
        self._min_session = 0          # bundan küçük oturumlar iptal edilmiş sayılır
        self._lock = threading.Lock()
        self.voices: dict[str, sherpa_onnx.OfflineTts] = {}
        self._ack_cache: dict[tuple, tuple[np.ndarray, int]] = {}
        self.current_text = ""  # o an çalınan cümle

    def load(self) -> None:
        if self.voices:
            return  # "Tekrar dene" sonrası ikinci çağrı
        # İngilizce ses (~100 MB) ilk İngilizce cevapta yüklenir; çoğu gün hiç gerekmez
        self._voice("tr")
        for text in self._ack_texts("tr"):  # uyanma cevapları önceden üretilir: "Stark" deyince gecikmesiz çalar
            self._ack_audio("tr", text)
        threading.Thread(target=self._synth_loop, name="tts-synth", daemon=True).start()
        threading.Thread(target=self._play_loop, name="tts-play", daemon=True).start()

    def _voice(self, lang: str) -> sherpa_onnx.OfflineTts:
        """Sesi gerekince yükler (yalnızca seslendirme thread'inden ve load()'dan çağrılır)."""
        if lang not in self.voices:
            d = MODELS_DIR / (self.s.tts_voice_en if lang == "en" else self.s.tts_voice_tr)
            onnx = next(d.glob("*.onnx"))
            cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(onnx), tokens=str(d / "tokens.txt"), data_dir=str(d / "espeak-ng-data")),
                num_threads=2))
            self.voices[lang] = sherpa_onnx.OfflineTts(cfg)
        return self.voices[lang]

    def _ack_texts(self, lang: str) -> list[str]:
        if lang == "en":
            a = self.s.address_en
            return [f"Yes, {a}?", f"I'm listening, {a}.", f"Go ahead, {a}."]
        a = self.s.address_tr
        return [f"Efendim {a}.", f"Sizi dinliyorum {a}.", f"Buyurun {a}."]

    def _ack_audio(self, lang: str, text: str) -> tuple[np.ndarray, int]:
        """Önbellekli uyanma sesi (hitap ayardan değişirse yenisi ilk kullanımda üretilir)."""
        key = (lang, text, self.s.tts_speed)
        if key not in self._ack_cache:
            audio = self._voice(lang).generate(text, sid=0, speed=self.s.tts_speed)
            self._ack_cache[key] = (np.asarray(audio.samples, dtype=np.float32), audio.sample_rate)
        return self._ack_cache[key]

    # ---- dış arayüz (denetleyici thread'inden) ----
    def speak(self, session: int, text: str, language: str = "tr") -> None:
        self._text_q.put((session, text, language if language in ("tr", "en") else "tr"))

    def play_ack(self, session: int, language: str = "tr") -> None:
        self._text_q.put((session, language if language in ("tr", "en") else "tr", "ack"))

    def cancel(self, session: int) -> None:
        with self._lock:
            self._min_session = max(self._min_session, session + 1)

    def _stale(self, session: int) -> bool:
        with self._lock:
            return session < self._min_session

    # ---- thread'ler ----
    def _synth_loop(self) -> None:
        while True:
            session, text, lang = self._text_q.get()
            if self._stale(session):
                continue
            try:
                if lang == "ack":  # text alanı burada uyanma cevabının dilini taşır
                    samples, sr = self._ack_audio(text, random.choice(self._ack_texts(text)))
                    self._audio_q.put((session, "ack", samples, sr, ""))
                    continue
                speech = to_speech(text, lang)
                if not speech:
                    self._audio_q.put((session, "text", None, 0, ""))  # sırayı bozmadan "bitti" bildir
                    continue
                audio = self._voice(lang).generate(speech, sid=0, speed=self.s.tts_speed)
                samples = np.asarray(audio.samples, dtype=np.float32)
                self._audio_q.put((session, "text", samples, audio.sample_rate, speech))
            except Exception as e:  # noqa: BLE001
                self.on_error(session, f"Seslendirme hatası: {e}")

    def _play_loop(self) -> None:
        while True:
            session, kind, samples, sr, spoken = self._audio_q.get()
            if self._stale(session):
                continue
            try:
                if samples is not None:
                    self.current_text = spoken  # söz kesmede yankı kontrolü için
                    self._play(session, samples, sr)
            except Exception as e:  # noqa: BLE001
                self.on_level(0.0)
                self.on_error(session, f"Ses çalınamadı: {e}")
                continue
            self.on_level(0.0)
            self.current_text = ""
            if self._stale(session):
                continue
            if kind == "ack":
                self.on_ack_done(session)
            else:
                self.on_sentence_done(session)

    def _play(self, session: int, samples: np.ndarray, sr: int) -> None:
        chunk = sr // 20  # 50 ms: iptal ve küre genliği için yeterince sık
        device = resolve_device(self.s.output_device, "output")
        with sd.OutputStream(samplerate=sr, channels=1, dtype="float32", device=device) as out:
            for i in range(0, len(samples), chunk):
                if self._stale(session):
                    return
                part = samples[i:i + chunk]
                self.on_level(float(np.sqrt(np.mean(part ** 2))))
                out.write(part)
            out.write(np.zeros(sr // 20, dtype=np.float32))  # son parçanın kesilmemesi için
