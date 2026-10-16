"""faster-whisper işçisi: uyandırma kontrolü (tiny) ve asıl konuşma tanıma (ayarlardaki model)."""
import itertools
import os
import queue
import re
import sys
import threading
from pathlib import Path
from typing import Callable

import numpy as np

from ..config import Settings
from ..tools import places

WAKE_RE = re.compile(r"^\W*(?:hey\s+)?(i?s[dt]?[aâe]r[kcgq]|stark|start|şark|sark)\b[\s,.!?]*", re.I)
# Whisper'ın sessizlik/gürültüde uydurduğu bilinen kalıplar
HALLUCINATIONS = re.compile(r"altyaz|abone ol|izlediğiniz için|thanks for watching|subtitles by", re.I)
SAMPLE_RATE = 16000
PROMPTS = {"tr": "Kullanıcı ile Stark arasında Türkçe bir sohbet. Stark.",
           "en": "A conversation in English between the user and Stark. Stark."}
EN_MIN_PROB = 0.6
# Ölçüm (medium, kayıttaki cümleler): doğru metinler ≥ -0.45, anlamsız/uydurma metinler ≤ -0.68
UNSURE_LOGPROB = -0.55
NO_SPEECH_MAX = 0.6


def _add_cuda_dll_paths() -> None:
    """pip ile gelen nvidia-cublas/cudnn DLL'lerini Windows'ta bulunur yapar."""
    for base in sys.path:
        nv = Path(base) / "nvidia"
        if nv.is_dir():
            for bin_dir in nv.glob("*/bin"):
                os.add_dll_directory(str(bin_dir))
                os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]


def is_wake(text: str) -> bool:
    return bool(WAKE_RE.match(text.strip()))


def strip_wake(text: str) -> str:
    return WAKE_RE.sub("", text.strip(), count=1).strip()


class Transcriber:
    def __init__(self, settings: Settings,
                 on_wake: Callable[[np.ndarray | None, str], None],
                 on_transcript: Callable[[int, str, str, bool], None],
                 on_error: Callable[[str], None]):
        self.s = settings
        self.on_wake = on_wake
        self.on_transcript = on_transcript
        self.on_error = on_error
        self._q: queue.PriorityQueue = queue.PriorityQueue(maxsize=20)
        self._seq = itertools.count()
        self.main = None
        self.wake = None
        self.learned_names: Callable[[], list[str]] = lambda: []  # motor hafızaya bağlar

    def load(self) -> None:
        if self.main is not None:
            return  # "Tekrar dene" sonrası ikinci çağrı
        from faster_whisper import WhisperModel
        device = self.s.whisper_device
        if device == "cuda":
            _add_cuda_dll_paths()
        try:
            self.main = WhisperModel(self.s.whisper_model, device=device, compute_type=self.s.whisper_compute,
                                     cpu_threads=4)
            self._run_model(self.main, np.zeros(SAMPLE_RATE, dtype=np.float32), "tr")
        except Exception:  # noqa: BLE001 — CUDA yoksa CPU'ya düş
            if device == "cpu":
                raise
            device = "cpu"
            self.main = WhisperModel(self.s.whisper_model, device="cpu", compute_type="int8", cpu_threads=4)
        # Uyandırma kontrolü de ekran kartındaysa orada: işlemcide ~120 MB, ekran kartında ~20 MB bellek
        self.wake = (WhisperModel("tiny", device="cuda", compute_type="int8_float16") if device == "cuda"
                     else WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=2))
        threading.Thread(target=self._run, name="asr", daemon=True).start()

    def check_wake(self, segment: np.ndarray) -> None:
        try:
            self._q.put_nowait((1, next(self._seq), "wake", 0, segment))
        except queue.Full:
            pass  # zaten birikmiş; bu bölümü atla

    def transcribe(self, session: int, audio: np.ndarray) -> None:
        self._q.put((0, next(self._seq), "main", session, audio))  # öncelikli

    def _run_model(self, model, audio, language, prompt=None) -> tuple[str, str, float]:
        """(metin, dil, güven). Güven = en zayıf bölümün avg_logprob değeri (0'a yakın = emin)."""
        segs, info = model.transcribe(audio, language=language, beam_size=1 if model is self.wake else 5,
                                      without_timestamps=True, condition_on_previous_text=False,
                                      initial_prompt=prompt, vad_filter=False)
        kept = [s for s in segs if s.no_speech_prob < NO_SPEECH_MAX]
        text = " ".join(s.text.strip() for s in kept).strip()
        confidence = min((s.avg_logprob for s in kept), default=0.0)
        return text, info.language, confidence

    def _run(self) -> None:
        while True:
            _, _, kind, session, audio = self._q.get()
            try:
                if kind == "wake":
                    self._handle_wake(audio)
                else:
                    lang = self._pick_language(audio) if self.s.language == "auto" else self.s.language
                    prompt = PROMPTS.get(lang, "")
                    if lang == "tr":
                        # "Bornova" gibi yerel adlar ve öğretilen özel adlar doğru yazılsın
                        prompt += places.whisper_hint(self.s.city, self.learned_names())
                    text, detected, conf = self._run_model(self.main, audio, lang, prompt=prompt or None)
                    text = "" if HALLUCINATIONS.search(text) else strip_wake(text)
                    self.on_transcript(session, text, detected, bool(text) and conf < UNSURE_LOGPROB)
            except Exception as e:  # noqa: BLE001
                if kind == "main":
                    self.on_error(f"Konuşma tanıma hatası: {e}")
                    self.on_transcript(session, "", "", False)

    def _pick_language(self, audio: np.ndarray) -> str:
        """Otomatik dil: yalnızca Türkçe/İngilizce. Kısa cümlelerde tespit yanılabildiği için
        İngilizce ancak yeterince eminse seçilir; aksi halde Türkçe."""
        _, _, probs = self.main.detect_language(audio)
        p = dict(probs)
        return "en" if p.get("en", 0) >= EN_MIN_PROB and p.get("en", 0) > p.get("tr", 0) else "tr"

    def _handle_wake(self, segment: np.ndarray) -> None:
        head = segment[: int(1.6 * SAMPLE_RATE)]
        text, _, _ = self._run_model(self.wake, head, "tr", prompt="Stark.")
        if not is_wake(text):
            return
        # "Stark" sonrası konuşma varsa (uzun bölüm), tamamı komut olarak işlenir
        has_command = len(segment) > 1.3 * SAMPLE_RATE and len(strip_wake(text)) > 0
        self.on_wake(segment if has_command else None, text)  # metin: söz kesmede yankı kontrolü için
