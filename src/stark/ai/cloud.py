"""İnternetteki büyük dil modelleri: Groq → Gemini → OpenRouter, hepsi olmazsa bilgisayardaki Ollama modeli.

Küçük yerel model (4B) Türkçe isteği çoğu zaman tam anlamıyordu. Ayarlardan açılan bu mod, sohbeti ve arama
kararlarını internetteki büyük modellere gönderir. Limit dolarsa (429), anahtar yanlışsa ya da servis yanıt
vermezse sıradakine geçilir; hiçbiri olmazsa bilgisayardaki model cevap verir. Üç servis de OpenAI uyumlu
"chat/completions" arayüzü sunar.
"""
import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import httpx

from ..config import Settings
from . import keys as key_store
from .ollama_client import OllamaClient, OllamaError

GROQ = "https://api.groq.com/openai/v1/chat/completions"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
THINK = re.compile(r"<think>.*?</think>\s*", re.S)


@dataclass
class Provider:
    key: str            # anahtar adı: groq | gemini | openrouter
    label: str          # ekranda gösterilen ad
    url: str
    model: str
    extra: dict = field(default_factory=dict)
    blocked_until: float = 0.0   # limit/hata sonrası bu ana kadar denenmez (monoton saat)


def default_providers(use_gemini: bool) -> list[Provider]:
    chain = [
        Provider("groq", "Groq · Qwen3.8 27B", GROQ, "qwen/qwen3.8-27b", {"reasoning_effort": "none"}),
        Provider("groq", "Groq · GPT-OSS 120B", GROQ, "openai/gpt-oss-120b", {"reasoning_effort": "low"}),
    ]
    if use_gemini:
        chain.append(Provider("gemini", "Gemini Flash-Lite", GEMINI, "gemini-flash-lite-latest"))
    # OpenRouter'ın ücretsiz modelleri sık sık "geçici olarak yoğun" olabiliyor: iki farklı model sırayla denenir
    chain.append(Provider("openrouter", "OpenRouter · Gemma 4 31B", OPENROUTER, "google/gemma-4-31b-it:free"))
    chain.append(Provider("openrouter", "OpenRouter · Nemotron 120B", OPENROUTER,
                          "nvidia/nemotron-3-super-120b-a12b:free"))
    return chain


class CloudError(Exception):
    def __init__(self, message: str, cooldown: float):
        super().__init__(message)
        self.cooldown = cooldown  # saniye; bu sağlayıcı o kadar süre atlanır


def _cooldown_for(status: int, headers, text: str = "") -> float:
    """429: servis "şu kadar bekle" diyorsa o kadar; "geçici yoğunluk" ise 5 dakika; yoksa günlük limit olabilir
    diye 1 saat. 401/403: anahtar yanlış/yetkisiz, ayarlar değişene kadar (12 saat). Diğer hatalar: 2 dakika."""
    if status == 429 and "temporarily" in text.lower() and not headers.get("retry-after"):
        return 300.0
    if status == 429:
        try:
            return max(5.0, float(headers.get("retry-after", "")))
        except ValueError:
            return 3600.0
    if status in (401, 403):
        return 12 * 3600.0
    if status == 400:
        return 600.0
    return 120.0


class HybridLLM:
    """OllamaClient ile aynı arayüz: motor hangisiyle konuştuğunu bilmek zorunda değil."""

    def __init__(self, settings: Settings, local: OllamaClient | None = None, on_error=lambda m: None):
        self.s = settings
        self.local = local or OllamaClient(settings)
        self.on_error = on_error
        self._keys = key_store.load()
        self._providers = default_providers(settings.cloud_use_gemini)
        self._lock = threading.Lock()
        self._active: dict[int, threading.Event] = {}
        self.last_label = ""   # son cevabı veren model (ekranda gösterilir)

    # ---- ayarlar ----
    def reload(self) -> None:
        """Ayarlar/anahtarlar değişince: yeni anahtarlarla bütün sağlayıcılar yeniden denenir."""
        self._keys = key_store.load()
        self._providers = default_providers(self.s.cloud_use_gemini)

    @property
    def cloud_active(self) -> bool:
        return self.s.cloud_enabled and any(self._keys.get(p.key) for p in self._providers)

    def _available(self) -> list[Provider]:
        if not self.s.cloud_enabled:
            return []
        now = time.monotonic()
        return [p for p in self._providers if self._keys.get(p.key) and p.blocked_until <= now]

    # ---- yerel modelle ortak arayüz ----
    @property
    def last_used(self) -> float:
        return self.local.last_used

    @last_used.setter
    def last_used(self, value: float) -> None:
        self.local.last_used = value

    def idle_unloaded(self) -> bool:
        # İnternet modu açıkken yerel model önceden yüklenmez: ekran kartı boş kalır, yalnızca yedek olarak kullanılır
        return False if self.cloud_active else self.local.idle_unloaded()

    def unload(self) -> None:
        self.local.unload()

    def list_models(self) -> list[str]:
        return self.local.list_models()

    def check(self) -> None:
        try:
            self.local.check()
        except OllamaError:
            if not self.cloud_active:
                raise  # internet modu da yoksa Stark cevap veremez

    def warm_up(self) -> None:
        if not self.cloud_active:
            self.local.warm_up()

    # ---- istekler ----
    def _body(self, p: Provider, messages: list[dict], stream: bool, max_tokens: int | None,
              temperature: float) -> dict:
        body = {"model": p.model, "messages": messages, "stream": stream, "temperature": temperature, **p.extra}
        if max_tokens:
            body["max_tokens"] = max_tokens
        return body

    def _headers(self, p: Provider) -> dict:
        h = {"Authorization": f"Bearer {self._keys[p.key]}", "Content-Type": "application/json"}
        if p.key == "openrouter":
            h["X-Title"] = "Stark voice assistant"
        return h

    def _fail(self, p: Provider, e: CloudError) -> None:
        p.blocked_until = time.monotonic() + e.cooldown
        self.on_error(f"{p.label} kullanılamadı, sıradakine geçiliyor: {e}")

    def complete(self, messages: list[dict], num_predict: int = 32, timeout: float = 10) -> str:
        for p in self._available():
            try:
                r = httpx.post(p.url, headers=self._headers(p), timeout=timeout,
                               json=self._body(p, messages, False, max(num_predict, 64), 0))
                if r.status_code != 200:
                    raise CloudError(f"HTTP {r.status_code}: {r.text[:160]}",
                                     _cooldown_for(r.status_code, r.headers, r.text))
                text = r.json()["choices"][0]["message"].get("content") or ""
                self.last_label = p.label
                return THINK.sub("", text).strip()
            except CloudError as e:
                self._fail(p, e)
            except (httpx.HTTPError, ValueError, KeyError, IndexError) as e:
                self._fail(p, CloudError(type(e).__name__, 60))
        self.last_label = f"yerel · {self.s.llm_model}"
        return self.local.complete(messages, num_predict=num_predict, timeout=timeout)

    def chat(self, session: int, messages: list[dict], on_piece: Callable[[str], None],
             on_done: Callable[[str], None], on_error: Callable[[str], None], num_predict: int | None = None) -> None:
        cancel = threading.Event()
        with self._lock:
            self._active[session] = cancel
        threading.Thread(target=self._run, name=f"cloud-{session}", daemon=True,
                         args=(session, messages, cancel, on_piece, on_done, on_error, num_predict)).start()

    def cancel(self, session: int) -> None:
        with self._lock:
            ev = self._active.pop(session, None)
        if ev:
            ev.set()
        self.local.cancel(session)

    def _stream(self, p: Provider, messages, cancel, on_piece, num_predict) -> str | None:
        """Bir sağlayıcıdan akışlı cevap. None: iptal edildi. CloudError: ilk parçadan önce hata (sıradakine geç)."""
        full, started, in_think = "", False, False
        body = self._body(p, messages, True, num_predict or self.s.cloud_max_tokens, self.s.llm_temperature)
        timeout = httpx.Timeout(self.s.llm_timeout_s, connect=6)
        with httpx.stream("POST", p.url, headers=self._headers(p), json=body, timeout=timeout) as r:
            if r.status_code != 200:
                r.read()
                raise CloudError(f"HTTP {r.status_code}: {r.text[:160]}",
                                 _cooldown_for(r.status_code, r.headers, r.text))
            for line in r.iter_lines():
                if cancel.is_set():
                    return None
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    piece = chunk["choices"][0]["delta"].get("content") or ""
                except (ValueError, KeyError, IndexError):
                    continue
                # Düşünme bölümü (<think>…</think>) seslendirilmez
                if "<think>" in piece:
                    in_think = True
                if in_think:
                    if "</think>" in piece:
                        in_think = False
                        piece = piece.split("</think>", 1)[1]
                    else:
                        continue
                if piece:
                    started = True
                    full += piece
                    on_piece(piece)
        if not started:
            raise CloudError("boş cevap", 60)
        return full

    def _run(self, session, messages, cancel, on_piece, on_done, on_error, num_predict):
        try:
            for p in self._available():
                if cancel.is_set():
                    return
                emitted = []
                try:
                    full = self._stream(p, messages, cancel, lambda x: (emitted.append(x), on_piece(x)), num_predict)
                    if full is None:
                        return
                    self.last_label = p.label
                    on_done(full)
                    return
                except CloudError as e:
                    self._fail(p, e)
                except httpx.HTTPError as e:
                    if emitted:  # cevabın ortasında koptu: yarım cevabı başka modelle karıştırmayalım
                        on_error(f"{p.label} bağlantısı koptu")
                        return
                    self._fail(p, CloudError(type(e).__name__, 60))
            # İnternetteki modellerin hiçbiri olmadı: bilgisayardaki model
            self.last_label = f"yerel · {self.s.llm_model}"
            with self.local._lock:
                self.local._active[session] = cancel
            self.local._run(session, messages, cancel, on_piece, on_done, on_error, num_predict)
        finally:
            with self._lock:
                self._active.pop(session, None)
