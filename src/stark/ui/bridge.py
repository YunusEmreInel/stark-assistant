"""Motor/işçi thread'lerinden gelen geri çağrıları Qt sinyallerine çevirir (UI yalnızca ana thread'de güncellenir)."""
from PySide6.QtCore import QObject, Signal

from ..core.states import State


class Bridge(QObject):
    state = Signal(object)
    status = Signal(str)
    user_text = Signal(str)
    assistant_text = Signal(str, bool)
    error = Signal(str)
    timing = Signal(dict)

    # EngineListener
    def on_state(self, state: State) -> None:
        self.state.emit(state)

    def on_status(self, text: str) -> None:
        self.status.emit(text)

    def on_user_text(self, text: str) -> None:
        self.user_text.emit(text)

    def on_assistant_text(self, text: str, final: bool) -> None:
        self.assistant_text.emit(text, final)

    def on_error(self, message: str) -> None:
        self.error.emit(message)

    def on_timing(self, timings: dict) -> None:
        self.timing.emit(timings)
