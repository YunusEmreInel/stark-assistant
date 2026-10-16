import numpy as np
import pytest

from stark.core import events as ev
from stark.core.controller import Controller
from stark.core.states import MicMode, State


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class FakeEffects:
    def __init__(self):
        self.calls = []
        self.mic = None

    def __getattr__(self, name):
        def rec(*args):
            self.calls.append((name, *args))
            if name == "set_mic":
                self.mic = args[0]
        return rec

    def names(self, name):
        return [c for c in self.calls if c[0] == name]


AUDIO = np.zeros(1600, dtype=np.float32)


@pytest.fixture
def env():
    clock, fx = FakeClock(), FakeEffects()
    c = Controller(fx, clock)
    c.handle(ev.Ready())

    def tick(seconds):
        # 100 ms'lik adımlarla zamanı ilerlet
        for _ in range(int(round(seconds * 10))):
            clock.advance(0.1)
            c.handle(ev.Tick())
    return c, fx, clock, tick


def wake(c):
    c.handle(ev.WakeDetected())
    c.handle(ev.AckDone(c.session))


def ask(c, text="merhaba"):
    c.handle(ev.SpeechStarted())
    c.handle(ev.SpeechEnded(AUDIO))
    c.handle(ev.TranscriptReady(c.session, text, "tr"))


def test_ready_goes_idle_with_wake_mic(env):
    c, fx, _, _ = env
    assert c.state is State.IDLE and fx.mic is MicMode.WAKE


def test_timer_starts_only_after_ack(env):
    c, fx, _, tick = env
    c.handle(ev.WakeDetected())
    assert fx.mic is MicMode.MUTED and fx.names("play_ack")
    tick(15)  # onay sesi uzun sürse bile uyumaz
    assert c.state is State.LISTENING
    c.handle(ev.AckDone(c.session))
    assert fx.mic is MicMode.VAD


def test_ten_seconds_silence_returns_idle(env):
    c, fx, _, tick = env
    wake(c)
    tick(9.9)
    assert c.state is State.LISTENING
    tick(0.2)
    assert c.state is State.IDLE and fx.mic is MicMode.WAKE


def test_speech_starting_at_nine_seconds_is_not_cut(env):
    c, _, _, tick = env
    wake(c)
    tick(9)
    c.handle(ev.SpeechStarted())
    tick(20)  # uzun soru
    assert c.state is State.CAPTURING
    c.handle(ev.SpeechEnded(AUDIO))
    assert c.state is State.TRANSCRIBING


def test_thinking_and_speaking_longer_than_timeout_do_not_sleep(env):
    c, _, _, tick = env
    wake(c)
    ask(c)
    tick(30)
    assert c.state is State.THINKING
    c.handle(ev.LlmSentence(c.session, "Birinci cümle."))
    tick(30)
    assert c.state is State.SPEAKING


def test_new_window_starts_after_last_tts_sentence(env):
    c, fx, clock, tick = env
    wake(c)
    ask(c)
    s = c.session
    c.handle(ev.LlmSentence(s, "Bir."))
    c.handle(ev.LlmSentence(s, "İki."))
    c.handle(ev.TtsSentenceDone(s))
    assert c.state is State.SPEAKING  # ilk cümle bitti diye dinlemeye geçmez
    c.handle(ev.LlmDone(s))
    assert c.state is State.SPEAKING
    tick(5)
    c.handle(ev.TtsSentenceDone(s))
    assert c.state is State.LISTENING and fx.mic is MicMode.VAD
    assert c.deadline == pytest.approx(clock() + 10)
    tick(9.9)
    assert c.state is State.LISTENING
    tick(0.2)
    assert c.state is State.IDLE


def test_follow_up_without_wake_word_keeps_session_flow(env):
    c, fx, _, tick = env
    wake(c)
    ask(c, "birinci soru")
    c.handle(ev.LlmSentence(c.session, "Cevap."))
    c.handle(ev.LlmDone(c.session))
    c.handle(ev.TtsSentenceDone(c.session))
    tick(4)
    ask(c, "ikinci soru")
    assert c.state is State.THINKING
    assert [x[2] for x in fx.names("ask_llm")] == ["birinci soru", "ikinci soru"]


def test_stop_discards_stale_llm_and_tts(env):
    c, fx, _, _ = env
    wake(c)
    ask(c)
    old = c.session
    c.handle(ev.LlmSentence(old, "Uzun cevap."))
    c.handle(ev.StopResponse())
    assert ("cancel", old) in fx.calls
    assert c.state is State.LISTENING and c.session != old
    spoken_before = len(fx.names("speak"))
    c.handle(ev.LlmSentence(old, "Eski cümle."))
    c.handle(ev.TtsSentenceDone(old))
    c.handle(ev.LlmDone(old))
    assert len(fx.names("speak")) == spoken_before
    assert c.state is State.LISTENING


def test_wake_during_speaking_cancels_old_session(env):
    c, fx, _, _ = env
    wake(c)
    ask(c)
    old = c.session
    c.handle(ev.LlmSentence(old, "Cevap."))
    c.handle(ev.WakeDetected(manual=True))
    assert ("cancel", old) in fx.calls and c.session == old + 1


def test_wake_with_command_goes_straight_to_transcribing(env):
    c, fx, _, _ = env
    c.handle(ev.WakeDetected(command_audio=AUDIO))
    assert c.state is State.TRANSCRIBING and not fx.names("play_ack")
    c.handle(ev.TranscriptReady(c.session, "bugün hava nasıl", "tr"))
    assert c.state is State.THINKING


def test_wake_with_only_wake_word_opens_listening_window(env):
    c, _, _, tick = env
    c.handle(ev.WakeDetected(command_audio=AUDIO))
    c.handle(ev.TranscriptReady(c.session, "", "tr"))
    assert c.state is State.LISTENING
    tick(10.1)
    assert c.state is State.IDLE


def test_unsure_transcript_asks_to_repeat_without_llm(env):
    c, fx, _, _ = env
    wake(c)
    c.handle(ev.SpeechStarted())
    c.handle(ev.SpeechEnded(AUDIO))
    c.handle(ev.TranscriptReady(c.session, "nisabal gırtma", "tr", unsure=True))
    assert not fx.names("ask_llm")
    assert "anlayamadım" in fx.names("speak")[-1][2]
    c.handle(ev.TtsSentenceDone(c.session))
    assert c.state is State.LISTENING  # tekrar söylemesi için dinleme penceresi açılır


def test_thanks_replies_and_sleeps_immediately(env):
    c, fx, _, _ = env
    wake(c)
    ask(c, "Teşekkürler.")
    assert not fx.names("ask_llm") and fx.names("speak")[-1][2] == "Rica ederim patron."
    c.handle(ev.TtsSentenceDone(c.session))
    assert c.state is State.IDLE and fx.mic is MicMode.WAKE  # 10 sn beklemeden


def test_thanks_with_follow_up_question_keeps_talking(env):
    c, fx, _, _ = env
    wake(c)
    ask(c, "Teşekkürler, bir de yarın hava nasıl olacak?")
    assert fx.names("ask_llm")


def test_sleep_flag_does_not_leak_into_next_session(env):
    c, _, _, _ = env
    wake(c)
    ask(c, "Sağ ol.")
    c.handle(ev.WakeDetected(manual=True))  # cevap bitmeden yeniden uyandırıldı
    c.handle(ev.AckDone(c.session))
    ask(c, "Fotosentez nedir?")
    c.handle(ev.LlmSentence(c.session, "Cevap."))
    c.handle(ev.LlmDone(c.session))
    c.handle(ev.TtsSentenceDone(c.session))
    assert c.state is State.LISTENING


def test_barge_in_listens_for_wake_while_speaking(env):
    c, fx, _, _ = env
    wake(c)
    ask(c)
    c.handle(ev.LlmSentence(c.session, "Uzun bir cevap."))
    assert c.state is State.SPEAKING and fx.mic is MicMode.WAKE  # konuşurken "Stark" dinleniyor
    old = c.session
    c.handle(ev.WakeDetected())  # kullanıcı "Stark" dedi
    assert ("cancel", old) in fx.calls and c.session == old + 1 and fx.names("play_ack")


def test_stop_command_returns_to_listening_silently(env):
    c, fx, _, _ = env
    c.handle(ev.WakeDetected(command_audio=AUDIO))
    spoken = len(fx.names("speak"))
    c.handle(ev.TranscriptReady(c.session, "Dur.", "tr"))
    assert c.state is State.LISTENING and len(fx.names("speak")) == spoken and not fx.names("ask_llm")


def test_barge_in_disabled_mutes_mic():
    fx = FakeEffects()
    c = Controller(fx, FakeClock(), barge_in=False)
    c.handle(ev.Ready())
    wake(c)
    ask(c)
    c.handle(ev.LlmSentence(c.session, "Cevap."))
    assert fx.mic is MicMode.MUTED


def test_own_echo_detection():
    from stark.core.engine import is_own_echo
    assert is_own_echo("Stark projesi", "Stark projesi Ekim'de başladı.")    # kendi adını söylüyor
    assert is_own_echo("Start, fotosentez bitkilerin", "Fotosentez bitkilerin besin üretmesidir.")
    assert not is_own_echo("Stark", "Fotosentez bitkilerin besin üretmesidir.")  # gerçek söz kesme
    assert not is_own_echo("Stark dur", "")


def test_empty_transcript_returns_to_listening(env):
    c, _, _, tick = env
    wake(c)
    ask(c, "   ")
    assert c.state is State.LISTENING
    tick(10.1)
    assert c.state is State.IDLE


def test_llm_failure_speaks_error_and_recovers(env):
    c, fx, _, _ = env
    wake(c)
    ask(c)
    c.handle(ev.LlmFailed(c.session, "bağlantı reddedildi"))
    assert fx.names("on_error") and c.state is State.SPEAKING
    c.handle(ev.TtsSentenceDone(c.session))
    assert c.state is State.LISTENING


def test_llm_done_without_sentences_returns_to_listening(env):
    c, _, _, _ = env
    wake(c)
    ask(c)
    c.handle(ev.LlmDone(c.session))
    assert c.state is State.LISTENING


def test_tts_failure_does_not_lock(env):
    c, fx, _, _ = env
    wake(c)
    ask(c)
    c.handle(ev.LlmSentence(c.session, "Bir."))
    c.handle(ev.LlmDone(c.session))
    c.handle(ev.TtsFailed(c.session, "ses aygıtı yok"))
    assert c.state is State.LISTENING and fx.names("on_error")


def test_pause_releases_mic_and_ignores_wake(env):
    c, fx, _, _ = env
    c.handle(ev.TogglePause())
    assert c.state is State.PAUSED and fx.mic is MicMode.OFF
    c.handle(ev.WakeDetected())
    assert c.state is State.PAUSED
    c.handle(ev.TogglePause())
    assert c.state is State.IDLE and fx.mic is MicMode.WAKE


def test_shutdown_is_final(env):
    c, fx, _, _ = env
    wake(c)
    c.handle(ev.Shutdown())
    c.handle(ev.WakeDetected(manual=True))
    assert c.state is State.STOPPED and fx.mic is MicMode.OFF
