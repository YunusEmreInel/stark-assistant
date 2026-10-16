"""İnternetteki modeller: sıralı geçiş, limit/hata sonrası bekleme, en sonda bilgisayardaki model."""
import threading

import httpx
import pytest

from stark.ai import cloud
from stark.ai.cloud import HybridLLM
from stark.config import Settings


class FakeLocal:
    def __init__(self):
        self.last_used = 0.0
        self._lock = threading.Lock()
        self._active = {}
        self.calls = []

    def complete(self, messages, num_predict=32, timeout=10):
        self.calls.append("complete")
        return "yerel cevap"

    def _run(self, session, messages, cancel, on_piece, on_done, on_error, num_predict=None):
        self.calls.append("chat")
        on_piece("yerel")
        on_done("yerel")

    def cancel(self, session):
        pass

    def idle_unloaded(self):
        return True

    def check(self):
        from stark.ai.ollama_client import OllamaError
        raise OllamaError("ollama yok")

    def warm_up(self):
        self.calls.append("warm")


class Resp:
    def __init__(self, status, payload=None, headers=None, lines=None):
        self.status_code, self._payload, self.headers = status, payload, headers or {}
        self.text = str(payload)
        self._lines = lines or []

    def json(self):
        return self._payload

    def read(self):
        return b""

    def iter_lines(self):
        yield from self._lines

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def make(monkeypatch, responses, keys=None, enabled=True):
    monkeypatch.setattr(cloud.key_store, "load", lambda: keys if keys is not None else
                        {"groq": "k1", "gemini": "k2", "openrouter": "k3"})
    seen = []

    def post(url, headers=None, json=None, timeout=None):
        seen.append(json["model"])
        return responses.pop(0)

    def stream(method, url, headers=None, json=None, timeout=None):
        seen.append(json["model"])
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(cloud.httpx, "post", post)
    monkeypatch.setattr(cloud.httpx, "stream", stream)
    llm = HybridLLM(Settings(cloud_enabled=enabled), local=FakeLocal())
    return llm, seen


def ok(text):
    return Resp(200, {"choices": [{"message": {"content": text}}]})


def test_rate_limited_provider_is_skipped_until_cooldown(monkeypatch):
    llm, seen = make(monkeypatch, [Resp(429, {}, {"retry-after": "30"}), ok("merhaba"), ok("yine")])
    assert llm.complete([{"role": "user", "content": "x"}]) == "merhaba"
    assert seen == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"] and llm.last_label == "Groq · Qwen3.8 27B"
    assert llm.complete([{"role": "user", "content": "x"}]) == "yine"
    assert seen[-1] == "qwen/qwen3.8-27b"  # limit dolan model 30 sn boyunca atlanır


def test_falls_back_to_local_when_all_fail(monkeypatch):
    llm, seen = make(monkeypatch, [Resp(401, {}), Resp(500, {}), Resp(429, {}), Resp(503, {}), Resp(429, {})])
    assert llm.complete([{"role": "user", "content": "x"}]) == "yerel cevap"
    assert len(seen) == 5 and llm.last_label.startswith("yerel")


def test_disabled_or_no_keys_uses_local_only(monkeypatch):
    llm, seen = make(monkeypatch, [], enabled=False)
    assert llm.complete([{"role": "user", "content": "x"}]) == "yerel cevap" and seen == []
    llm, seen = make(monkeypatch, [], keys={})
    assert llm.complete([{"role": "user", "content": "x"}]) == "yerel cevap" and seen == []


def test_streaming_hides_think_block_and_falls_back(monkeypatch):
    lines = ['data: {"choices":[{"delta":{"content":"<think>plan"}}]}',
             'data: {"choices":[{"delta":{"content":"ediyorum</think>Merhaba"}}]}',
             'data: {"choices":[{"delta":{"content":" patron."}}]}', "data: [DONE]"]
    llm, seen = make(monkeypatch, [httpx.ConnectError("yok"), Resp(200, lines=lines)])
    pieces, done = [], []
    finished = threading.Event()
    llm.chat(1, [{"role": "user", "content": "x"}], pieces.append,
             lambda full: (done.append(full), finished.set()), lambda m: finished.set())
    finished.wait(5)
    assert done == ["Merhaba patron."] and "".join(pieces) == "Merhaba patron."
    assert llm.last_label == "Groq · Qwen3.8 27B"


def test_cloud_mode_keeps_gpu_free(monkeypatch):
    llm, _ = make(monkeypatch, [])
    llm.warm_up()
    llm.check()  # Ollama yoksa bile internet modu varsa açılış durmaz
    assert llm.idle_unloaded() is False and llm.local.calls == []


def test_gemini_can_be_left_out():
    names = [p.model for p in cloud.default_providers(use_gemini=False)]
    assert "gemini-flash-lite-latest" not in names and names[-2:] == ["google/gemma-4-31b-it:free",
                                                                       "nvidia/nemotron-3-super-120b-a12b:free"]


def test_temporary_upstream_overload_is_short():
    assert cloud._cooldown_for(429, {}, '{"raw":"... is temporarily rate-limited upstream"}') == 300.0


@pytest.mark.parametrize("status, expected", [(429, 60.0), (401, 43200.0), (400, 600.0), (500, 120.0)])
def test_cooldowns(status, expected):
    assert cloud._cooldown_for(status, {}) == expected


@pytest.mark.parametrize("text, expected", [
    ("Rate limit reached ... tokens per minute (TPM). Please try again in 7.5s.", 8.5),   # dakikalık: saniyeler
    ("Rate limit reached ... tokens per day (TPD). Please try again in 12m3s.", 724.0),  # günlük: söylenen süre
    ("Limit reached for tokens per day (TPD).", 3600.0),
    ("google/gemma-4-31b-it:free is temporarily rate-limited upstream", 300.0),
])
def test_rate_limit_waits_only_as_long_as_needed(text, expected):
    assert cloud._cooldown_for(429, {}, text) == expected


def test_tool_steps_from_another_model_become_plain_text():
    msgs = [{"role": "user", "content": "x"},
            {"role": "assistant", "content": None, "_by": "Groq · GPT-OSS 120B",
             "tool_calls": [{"id": "1", "function": {"name": "web_search", "arguments": '{"query": "a"}'}}]},
            {"role": "tool", "tool_call_id": "1", "content": "sonuç"}]
    same = cloud._for_provider(msgs, "Groq · GPT-OSS 120B")
    assert same[1]["tool_calls"] and "_by" not in same[1] and same[2]["role"] == "tool"
    other = cloud._for_provider(msgs, "Gemini Flash-Lite")
    # Taklit edilecek "[araç çağırdım]" metni yok: yalnızca kullanıcı mesajı ve bulunanlar notu
    assert len(other) == 2 and other[0] == {"role": "user", "content": "x"}
    assert other[1]["role"] == "system" and other[1]["content"].endswith("sonuç")
    assert not any(m.get("tool_calls") or m["role"] == "tool" for m in other)


class _FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.choices = []

    def complete_tools(self, messages, tools, tool_choice="auto", **kw):
        self.choices.append(tool_choice)
        return self.replies.pop(0)


def _agent(replies):
    from stark.ai import agent as agent_mod
    from stark.config import Settings
    llm = _FakeLLM(replies)
    a = agent_mod.Agent(llm, Settings())
    a.run_tool = lambda name, args, out: "Ankara: 18°C, yağmurlu"
    return a, llm


def test_agent_must_use_a_tool_for_current_questions():
    call = {"id": "1", "function": {"name": "weather", "arguments": '{"city": "Ankara"}'}}
    a, llm = _agent([{"content": "Hava 22 derece.", "tool_calls": []},       # uydurma: kabul edilmez
                     {"content": "", "tool_calls": [call], "by": "x"},
                     {"content": "Ankara'da 18 derece, yağmurlu.", "tool_calls": []}])
    r = a.run([{"role": "user", "content": "Ankara'da hava nasıl?"}], require_tool=True)
    assert r.answer == "Ankara'da 18 derece, yağmurlu." and r.used_tools == ["weather"]
    assert llm.choices[:2] == ["required", "required"] and llm.choices[2] == "auto"


def test_agent_rejects_tool_call_written_as_text():
    a, _ = _agent([{"content": '[I called tools: web_search({"query": "yds"})]', "tool_calls": []},
                   {"content": "YDS 2 Kasım'da.", "tool_calls": []}])
    assert a.run([{"role": "user", "content": "selam"}]).answer == "YDS 2 Kasım'da."
