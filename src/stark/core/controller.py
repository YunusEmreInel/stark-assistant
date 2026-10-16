"""Stark'ın durum makinesi. Qt, ses ve AI bağımlılığı yoktur; yan etkiler Effects üzerinden istenir.

Tüm olaylar tek iş parçacığından (Qt ana thread) handle() ile verilmelidir.
"""
import time
from typing import Callable, Protocol

import numpy as np

from . import dismissal
from . import events as ev
from .states import BUSY_STATES, MicMode, State

CLARIFY = {"tr": "Sizi tam anlayamadım patron, tekrar söyler misiniz?",
           "en": "Sorry boss, I didn't catch that. Could you say it again?"}
ERROR_SPEECH = {
    "llm": "Dil modeline ulaşamadım patron. Ollama açık mı, kontrol eder misiniz?",
}


class Effects(Protocol):
    def set_mic(self, mode: MicMode) -> None: ...
    def play_ack(self, session: int) -> None: ...
    def transcribe(self, session: int, audio: np.ndarray) -> None: ...
    def ask_llm(self, session: int, text: str, language: str) -> None: ...
    def speak(self, session: int, text: str) -> None: ...
    def cancel(self, session: int) -> None: ...
    def on_state(self, state: State) -> None: ...
    def on_user_text(self, text: str) -> None: ...
    def on_error(self, message: str) -> None: ...


class Controller:
    def __init__(self, effects: Effects, clock: Callable[[], float] = time.monotonic,
                 listen_timeout: float = 10.0, barge_in: bool = True):
        self.fx = effects
        self.clock = clock
        self.listen_timeout = listen_timeout
        self.barge_in = barge_in
        self.state = State.INITIALIZING
        self.session = 0
        self.deadline: float | None = None   # LISTENING bitiş zamanı (monoton)
        self._pending_tts = 0
        self._llm_done = False
        self._sleep_after = False   # kapanış cümlesinden sonra dinleme yerine uykuya dön

    # ---- yardımcılar -------------------------------------------------
    def _set(self, state: State) -> None:
        if state is not self.state:
            self.state = state
            self.fx.on_state(state)

    def _new_session(self) -> int:
        if self.state in BUSY_STATES or self._pending_tts:
            self.fx.cancel(self.session)
        self.session += 1
        self._pending_tts = 0
        self._llm_done = False
        self._sleep_after = False
        return self.session

    def _go_idle(self) -> None:
        self.deadline = None
        self._set(State.IDLE)
        self.fx.set_mic(MicMode.WAKE)

    def _go_listening(self) -> None:
        """Dinleme penceresini açar; 10 sn bu andan itibaren sayılır."""
        self.deadline = self.clock() + self.listen_timeout
        self._set(State.LISTENING)
        self.fx.set_mic(MicMode.VAD)

    def _maybe_finish_turn(self) -> None:
        if self._llm_done and self._pending_tts == 0:
            if self._sleep_after:
                self._sleep_after = False
                self._go_idle()
            else:
                self._go_listening()

    def _current(self, e) -> bool:
        return getattr(e, "session", self.session) == self.session

    # ---- olay girişi -------------------------------------------------
    def handle(self, e) -> None:
        if self.state is State.STOPPED:
            return
        if not self._current(e):
            return  # eski oturumdan kalan sonuç
        method = getattr(self, f"_on_{type(e).__name__}", None)
        if method:
            method(e)

    def _on_Ready(self, e: ev.Ready) -> None:
        if self.state in (State.INITIALIZING, State.ERROR):
            self._go_idle()

    def _on_InitFailed(self, e: ev.InitFailed) -> None:
        self._set(State.ERROR)
        self.fx.set_mic(MicMode.OFF)
        self.fx.on_error(e.message)

    def _on_WakeDetected(self, e: ev.WakeDetected) -> None:
        if self.state in (State.INITIALIZING, State.PAUSED, State.ERROR):
            if not (e.manual and self.state is State.PAUSED):
                return
        if self.state in (State.LISTENING, State.CAPTURING) and not e.manual:
            return
        session = self._new_session()
        self.deadline = None  # sayaç onay sesi bitince başlar
        if e.command_audio is not None:
            self._set(State.TRANSCRIBING)
            self.fx.set_mic(MicMode.MUTED)
            self.fx.transcribe(session, e.command_audio)
            return
        self._set(State.LISTENING)
        self.fx.set_mic(MicMode.MUTED)
        self.fx.play_ack(session)

    def _on_AckDone(self, e: ev.AckDone) -> None:
        if self.state is State.LISTENING and self.deadline is None:
            self._go_listening()

    def _on_SpeechStarted(self, e: ev.SpeechStarted) -> None:
        if self.state is State.LISTENING and self.deadline is not None:
            self.deadline = None
            self._set(State.CAPTURING)

    def _on_SpeechEnded(self, e: ev.SpeechEnded) -> None:
        if self.state is State.CAPTURING:
            self._set(State.TRANSCRIBING)
            self.fx.set_mic(MicMode.MUTED)
            self.fx.transcribe(self.session, e.audio)

    def _on_TranscriptReady(self, e: ev.TranscriptReady) -> None:
        if self.state is not State.TRANSCRIBING:
            return
        text = e.text.strip()
        if not text:
            self._go_listening()
            return
        self._llm_done = False
        self._pending_tts = 0
        if e.unsure:
            # Yanlış duyulmuş metni modele vermek uydurma cevaba yol açar; tekrar sor
            self.fx.on_user_text(text + " (?)")
            self._set(State.THINKING)
            self._on_LlmSentence(ev.LlmSentence(self.session, CLARIFY.get(e.language, CLARIFY["tr"])))
            self._llm_done = True
            return
        self.fx.on_user_text(text)
        if dismissal.is_stop(text):
            # "Stark, dur" / "sus": cevap kesildi; yeni bir şey söylemeden dinlemeye dön
            self._go_listening()
            return
        self._set(State.THINKING)
        farewell = dismissal.reply_for(text)
        if farewell:
            # "Teşekkürler/sağ ol": kısa cevap ver ve 10 sn beklemeden uykuya dön
            self._sleep_after = True
            self._on_LlmSentence(ev.LlmSentence(self.session, farewell))
            self._llm_done = True
            return
        self.fx.ask_llm(self.session, text, e.language)

    def _on_LlmSentence(self, e: ev.LlmSentence) -> None:
        if self.state not in (State.THINKING, State.SPEAKING):
            return
        self._pending_tts += 1
        if self.state is not State.SPEAKING:
            self._set(State.SPEAKING)
            # Söz kesme: konuşurken yalnızca "Stark" dinlenir (sohbet VAD'i değil); kapalıysa mikrofon susturulur
            self.fx.set_mic(MicMode.WAKE if self.barge_in else MicMode.MUTED)
        self.fx.speak(self.session, e.text)

    def _on_LlmDone(self, e: ev.LlmDone) -> None:
        if self.state in (State.THINKING, State.SPEAKING):
            self._llm_done = True
            self._maybe_finish_turn()

    def _on_LlmFailed(self, e: ev.LlmFailed) -> None:
        if self.state not in (State.THINKING, State.SPEAKING):
            return
        self.fx.on_error(e.message)
        self._on_LlmSentence(ev.LlmSentence(self.session, ERROR_SPEECH["llm"]))
        self._llm_done = True

    def _on_TtsSentenceDone(self, e: ev.TtsSentenceDone) -> None:
        if self.state is State.SPEAKING and self._pending_tts > 0:
            self._pending_tts -= 1
            self._maybe_finish_turn()

    def _on_TtsFailed(self, e: ev.TtsFailed) -> None:
        self.fx.on_error(e.message)
        self._on_TtsSentenceDone(ev.TtsSentenceDone(e.session))

    def _on_StopResponse(self, e: ev.StopResponse) -> None:
        if self.state in BUSY_STATES:
            self._new_session()
            self._go_listening()

    def _on_TogglePause(self, e: ev.TogglePause) -> None:
        if self.state is State.PAUSED:
            self._go_idle()
        elif self.state not in (State.INITIALIZING, State.ERROR):
            self._new_session()
            self.deadline = None
            self._set(State.PAUSED)
            self.fx.set_mic(MicMode.OFF)

    def _on_Shutdown(self, e: ev.Shutdown) -> None:
        self._new_session()
        self.deadline = None
        self.fx.set_mic(MicMode.OFF)
        self._set(State.STOPPED)

    def _on_Tick(self, e: ev.Tick) -> None:
        if self.state is State.LISTENING and self.deadline is not None and self.clock() >= self.deadline:
            self._go_idle()
