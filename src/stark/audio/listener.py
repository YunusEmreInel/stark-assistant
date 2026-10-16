"""Mikrofon bloklarını mod'a göre yorumlar: WAKE → kısa konuşma bölümleri, VAD → konuşma başı/sonu."""
import threading
import time
from collections import deque
from typing import Callable

import numpy as np
import sherpa_onnx

from ..config import MODELS_DIR, Settings
from ..core.states import MicMode
from .capture import SAMPLE_RATE

PREROLL = int(0.3 * SAMPLE_RATE)


def _vad(settings: Settings, min_silence: float, max_speech: float) -> sherpa_onnx.VoiceActivityDetector:
    cfg = sherpa_onnx.VadModelConfig()
    cfg.silero_vad.model = str(MODELS_DIR / "silero_vad.onnx")
    cfg.silero_vad.threshold = settings.vad_threshold
    cfg.silero_vad.min_silence_duration = min_silence
    cfg.silero_vad.min_speech_duration = settings.vad_min_speech_s
    cfg.silero_vad.max_speech_duration = max_speech
    cfg.sample_rate = SAMPLE_RATE
    cfg.num_threads = 1
    return sherpa_onnx.VoiceActivityDetector(cfg, buffer_size_in_seconds=max_speech + 5)


class Listener:
    """capture thread'inden çağrılır; mod değişimi başka thread'den gelebilir."""

    def __init__(self, settings: Settings,
                 on_wake_segment: Callable[[np.ndarray], None],
                 on_speech_started: Callable[[], None],
                 on_speech_ended: Callable[[np.ndarray], None]):
        self.s = settings
        self.on_wake_segment = on_wake_segment
        self.on_speech_started = on_speech_started
        self.on_speech_ended = on_speech_ended
        # Uyandırma: kısa duraklamada bölümü kapat ki "Stark" çabuk kontrol edilsin
        self.wake_vad = _vad(settings, min_silence=0.35, max_speech=8)
        self.chat_vad = _vad(settings, min_silence=settings.vad_end_silence_s, max_speech=settings.max_record_s)
        self.mode = MicMode.OFF
        self._ignore_until = 0.0
        self._speaking = False
        self._lock = threading.Lock()
        self.echo_guard_s = settings.echo_guard_speaker_s
        self._reset_history()

    def _reset_history(self) -> None:
        # VAD sayaçlarıyla hizalı ham ses geçmişi; bölüm başına ön pay eklemek için
        self._hist: deque[np.ndarray] = deque()
        self._hist_len = 0
        self._hist_offset = 0  # deque'deki ilk örneğin VAD sıfırlamasından beri indeksi

    def _with_preroll(self, start: int, samples) -> np.ndarray:
        """VAD konuşma başını birkaç on ms geç yakalar; ilk hece kaybolmasın diye öncesini ekler."""
        seg = np.asarray(samples, dtype=np.float32)
        begin = max(self._hist_offset, start - PREROLL)
        if begin < start:
            joined = np.concatenate(self._hist)
            pre = joined[begin - self._hist_offset:start - self._hist_offset]
            seg = np.concatenate([pre, seg])
        return seg

    def _trim_history(self) -> None:
        # Bölüm, konuşma bitince gelir; başlangıcı en fazla max_record_s geride olabilir
        keep = int((self.s.max_record_s + 2) * SAMPLE_RATE)
        while self._hist_len - len(self._hist[0]) > keep:
            self._hist_offset += len(self._hist[0])
            self._hist_len -= len(self._hist.popleft())

    def set_mode(self, mode: MicMode) -> None:
        with self._lock:
            prev, self.mode = self.mode, mode
            if mode in (MicMode.WAKE, MicMode.VAD) and prev is not mode:
                self.wake_vad.reset()
                self.chat_vad.reset()
                self._reset_history()
                self._speaking = False
                if prev is MicMode.MUTED or (prev is MicMode.WAKE and mode is MicMode.VAD):
                    # Stark'ın kendi sesinin yankısı/son tamponlar sohbet sayılmasın (konuşma sonrası, söz
                    # kesme dinlemesinden sohbete geçişte de)
                    self._ignore_until = time.monotonic() + self.echo_guard_s

    def feed(self, block: np.ndarray) -> None:
        with self._lock:
            mode = self.mode
            if mode in (MicMode.OFF, MicMode.MUTED) or time.monotonic() < self._ignore_until:
                return
            vad = self.wake_vad if mode is MicMode.WAKE else self.chat_vad
            vad.accept_waveform(block)
            started = False
            if mode is MicMode.VAD and not self._speaking and vad.is_speech_detected():
                self._speaking = started = True
            self._hist.append(block)
            self._hist_len += len(block)
            self._trim_history()
            segments = []
            while not vad.empty():
                segments.append(self._with_preroll(vad.front.start, vad.front.samples))
                vad.pop()
            if segments and mode is MicMode.VAD:
                self._speaking = False
        # geri çağrılar kilit dışında
        if started:
            self.on_speech_started()
        for seg in segments:
            if mode is MicMode.WAKE:
                self.on_wake_segment(seg)
            else:
                self.on_speech_ended(seg)
                break  # bir tur = bir bölüm; denetleyici zaten MUTED'a geçecek
