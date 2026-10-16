"""Tek mikrofon akışı. Bütün bileşenler (uyandırma, VAD, ASR) bu akıştan beslenir."""
import queue
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
BLOCK = 512  # 32 ms, Silero VAD pencere boyu


def list_devices(kind: str) -> list[str]:
    """Windows varsayılan ses API'sindeki (MME) giriş/çıkış aygıt adları."""
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    api = sd.default.hostapi
    names = []
    for d in sd.query_devices():
        if d["hostapi"] == api and d[key] > 0 and d["name"] not in names and "Eşleştirici" not in d["name"] \
                and "Mapper" not in d["name"]:
            names.append(d["name"])
    return names


def resolve_device(name: str, kind: str) -> int | None:
    """Kayıtlı aygıt adını şu anki indekse çevirir; bulunamazsa None (= Windows varsayılanı)."""
    if not name:
        return None
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    for i, d in enumerate(sd.query_devices()):
        if d["hostapi"] == sd.default.hostapi and d[key] > 0 and d["name"] == name:
            return i
    return None


class AudioCapture:
    def __init__(self, on_block: Callable[[np.ndarray], None], on_error: Callable[[str], None],
                 device: str | int | None = None):
        self.on_block = on_block
        self.on_error = on_error
        self.device = device or None
        self._q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)  # ~6 sn; dolarsa eski bloklar atılır
        self._stream: sd.InputStream | None = None
        self._want_open = False
        self._lock = threading.Lock()
        self._worker = threading.Thread(target=self._run, name="audio-proc", daemon=True)
        self._worker.start()
        self.level = 0.0

    def open(self) -> None:
        with self._lock:
            self._want_open = True
            if self._stream is None:
                self._open_locked()

    def close(self) -> None:
        with self._lock:
            self._want_open = False
            self._close_locked()

    def flush(self) -> None:
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return

    def _open_locked(self) -> None:
        try:
            device = resolve_device(self.device, "input") if isinstance(self.device, str) else self.device
            self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32",
                                          blocksize=BLOCK, device=device, callback=self._callback)
            self._stream.start()
        except Exception as e:  # noqa: BLE001 — aygıt yok/meşgul
            self._stream = None
            self.on_error(f"Mikrofon açılamadı: {e}")

    def _close_locked(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:  # noqa: BLE001
                pass
            self._stream = None

    def _callback(self, indata, frames, time_info, status) -> None:
        block = indata[:, 0].copy()
        try:
            self._q.put_nowait(block)
        except queue.Full:
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            self._q.put_nowait(block)

    def _run(self) -> None:
        last_check = time.monotonic()
        while True:
            try:
                block = self._q.get(timeout=0.5)
            except queue.Empty:
                block = None
            if block is not None:
                self.level = float(np.sqrt(np.mean(block ** 2)))
                try:
                    self.on_block(block)
                except Exception as e:  # noqa: BLE001
                    self.on_error(f"Ses işleme hatası: {e}")
            # Aygıt kaybolduysa (kulaklık çıkarıldı vb.) yeniden açmayı dene
            now = time.monotonic()
            if now - last_check > 2:
                last_check = now
                with self._lock:
                    if self._want_open and (self._stream is None or not self._stream.active):
                        self._close_locked()
                        self._open_locked()
