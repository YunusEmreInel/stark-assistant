"""Ollama /api/chat akışı. Her istek kendi thread'inde; iptal oturum kimliğiyle yapılır."""
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

import httpx

from ..config import Settings


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._lock = threading.Lock()
        self._active: dict[int, threading.Event] = {}
        self.last_used = 0.0

    @property
    def keep_alive(self) -> str | int:
        # Kullanım sırasında yedek süre; asıl boşaltma Stark uykuya geçince unload() ile yapılır
        n = self.s.llm_idle_unload_min
        return f"{max(n, 10)}m" if n > 0 else -1

    def idle_unloaded(self) -> bool:
        """Model bellekten çıkarıldı mı (uykuda boşaltıldı ya da yedek süre doldu)?"""
        n = self.s.llm_idle_unload_min
        return n > 0 and (self.last_used == 0.0 or time.monotonic() - self.last_used > max(n, 10) * 60 - 20)

    def unload(self) -> None:
        """Modeli hemen bellekten çıkarır (llama-server süreci kapanır, ~1,3 GB boşalır)."""
        try:
            httpx.post(f"{self.s.ollama_url}/api/generate", json={"model": self.s.llm_model, "keep_alive": 0},
                       timeout=10)
            self.last_used = 0.0
        except httpx.HTTPError:
            pass

    def _body(self, messages: list[dict], stream: bool = True) -> dict:
        self.last_used = time.monotonic()
        body = {
            "model": self.s.llm_model, "messages": messages, "stream": stream,
            "keep_alive": self.keep_alive,
            # Düşük sıcaklık: daha az yaratıcı ama daha az uydurma
            "options": {"num_ctx": self.s.llm_num_ctx, "num_gpu": self.s.llm_num_gpu,
                        "temperature": self.s.llm_temperature},
        }
        if self.s.llm_model.startswith("qwen3"):
            body["think"] = False
        return body

    def list_models(self) -> list[str]:
        try:
            tags = httpx.get(f"{self.s.ollama_url}/api/tags", timeout=3).json()
        except (httpx.HTTPError, ValueError):
            return []
        return sorted(m["name"] for m in tags.get("models", []))

    def _start_ollama_app(self) -> bool:
        """Ollama kapalıysa kullanıcının kurulu Ollama uygulamasını başlatır (kapatmaz, port açmaz)."""
        app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama app.exe"
        if not app.exists():
            return False
        subprocess.Popen([str(app)], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        for _ in range(30):
            time.sleep(0.5)
            try:
                httpx.get(f"{self.s.ollama_url}/api/tags", timeout=1)
                return True
            except httpx.HTTPError:
                pass
        return False

    def check(self) -> None:
        """Ollama açık mı ve model kurulu mu? Değilse anlaşılır OllamaError."""
        try:
            tags = httpx.get(f"{self.s.ollama_url}/api/tags", timeout=5).json()
        except httpx.HTTPError as e:
            if not self._start_ollama_app():
                raise OllamaError("Ollama'ya bağlanılamadı. Ollama uygulamasını başlatıp tekrar deneyin.") from e
            tags = httpx.get(f"{self.s.ollama_url}/api/tags", timeout=5).json()
        names = {m["name"] for m in tags.get("models", [])}
        if self.s.llm_model not in names and f"{self.s.llm_model}:latest" not in names:
            raise OllamaError(f"'{self.s.llm_model}' modeli kurulu değil: ollama pull {self.s.llm_model}")

    def warm_up(self) -> None:
        """Modeli belleğe yükler (ilk sorunun beklemesini önler)."""
        httpx.post(f"{self.s.ollama_url}/api/chat", timeout=300,
                   json={**self._body([{"role": "user", "content": "merhaba"}], stream=False),
                         "options": {**self._body([])["options"], "num_predict": 1}})

    def complete(self, messages: list[dict], num_predict: int = 32, timeout: float = 10) -> str:
        """Kısa, akışsız, deterministik çağrı (ör. arama kararı). Hata OllamaError olarak döner."""
        body = self._body(messages, stream=False)
        body["options"].update({"temperature": 0, "num_predict": num_predict})
        try:
            r = httpx.post(f"{self.s.ollama_url}/api/chat", json=body, timeout=timeout)
            data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise OllamaError(str(e)) from e
        if "error" in data:
            raise OllamaError(data["error"])
        return data.get("message", {}).get("content", "").strip()

    def chat(self, session: int, messages: list[dict],
             on_piece: Callable[[str], None], on_done: Callable[[str], None],
             on_error: Callable[[str], None], num_predict: int | None = None) -> None:
        """Arka planda akış başlatır. Geri çağrılar işçi thread'inden gelir.
        num_predict: cevap uzunluğu sınırı (token); araştırma cevapları kısa tutulur."""
        cancel = threading.Event()
        with self._lock:
            self._active[session] = cancel
        threading.Thread(target=self._run, name=f"llm-{session}", daemon=True,
                         args=(session, messages, cancel, on_piece, on_done, on_error, num_predict)).start()

    def cancel(self, session: int) -> None:
        with self._lock:
            ev = self._active.pop(session, None)
        if ev:
            ev.set()

    def _run(self, session, messages, cancel, on_piece, on_done, on_error, num_predict=None):
        full = ""
        timeout = httpx.Timeout(self.s.llm_timeout_s, connect=5)
        body = self._body(messages)
        if num_predict:
            body["options"]["num_predict"] = num_predict
        try:
            with httpx.stream("POST", f"{self.s.ollama_url}/api/chat", json=body, timeout=timeout) as r:
                if r.status_code != 200:
                    r.read()
                    raise OllamaError(f"Ollama hatası {r.status_code}: {r.text[:200]}")
                for line in r.iter_lines():
                    if cancel.is_set():
                        return
                    if not line:
                        continue
                    data = json.loads(line)
                    if "error" in data:
                        raise OllamaError(data["error"])
                    piece = data.get("message", {}).get("content", "")
                    if piece:
                        full += piece
                        on_piece(piece)
                    if data.get("done"):
                        break
            if not cancel.is_set():
                on_done(full)
        except (httpx.HTTPError, OllamaError, ValueError) as e:
            if not cancel.is_set():
                on_error(str(e) or type(e).__name__)
        finally:
            with self._lock:
                self._active.pop(session, None)
