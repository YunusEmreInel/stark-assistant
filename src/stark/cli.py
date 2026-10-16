"""Arayüzsüz Stark: konsolda durum ve metinleri gösterir. Enter = uyandır, s = yanıtı durdur,
p = duraklat/devam, n = yeni sohbet, q = çıkış."""
import sys

from .config import Settings
from .core.engine import Engine
from .core.states import State

LABELS = {
    State.INITIALIZING: "hazırlanıyor", State.IDLE: "💤 'Stark' bekleniyor", State.LISTENING: "🎙  dinliyorum",
    State.CAPTURING: "🎙  konuşuyorsun…", State.TRANSCRIBING: "✍  yazıya çeviriyorum",
    State.THINKING: "🤔 düşünüyorum", State.SPEAKING: "🔊 konuşuyorum", State.PAUSED: "⏸  duraklatıldı",
    State.ERROR: "⚠  hata", State.STOPPED: "kapandı",
}


class ConsoleUI:
    def on_state(self, state):
        print(f"[{LABELS[state]}]", flush=True)

    def on_status(self, text):
        print(f"… {text}", flush=True)

    def on_user_text(self, text):
        print(f"\nSiz: {text}", flush=True)

    def on_assistant_text(self, text, final):
        if final:
            print(f"Stark: {text}\n", flush=True)

    def on_error(self, message):
        print(f"⚠ {message}", flush=True)

    def on_timing(self, t):
        names = {"asr_done": "yazıya çevirme", "llm_first": "ilk kelime", "first_audio": "ilk ses"}
        print("  ⏱ konuşman bittikten sonra: " + ", ".join(f"{names.get(k, k)} {v:.2f} sn" for k, v in t.items()),
              flush=True)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    engine = Engine(Settings.load(), ConsoleUI())
    engine.start()
    print("Komutlar: Enter = uyandır | s = yanıtı durdur | p = duraklat/devam | n = yeni sohbet | q = çıkış")
    try:
        for line in sys.stdin:
            cmd = line.strip().lower()
            if cmd == "q":
                break
            {"": engine.wake, "s": engine.stop_response, "p": engine.toggle_pause,
             "n": engine.new_conversation}.get(cmd, lambda: None)()
    except KeyboardInterrupt:
        pass
    engine.shutdown()


if __name__ == "__main__":
    main()
