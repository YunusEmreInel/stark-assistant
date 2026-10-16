"""Denetleyiciye gelen olaylar. Oturuma bağlı olaylar session ile gelir; eski oturumunkiler atılır."""
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Ready:
    pass


@dataclass(frozen=True)
class InitFailed:
    message: str


@dataclass(frozen=True, eq=False)
class WakeDetected:
    manual: bool = False
    # "Stark, bugün hava nasıl?" gibi tek nefeste söylenen komutun sesi; varsa onay sesi atlanır
    command_audio: np.ndarray | None = field(default=None, repr=False)


@dataclass(frozen=True)
class AckDone:
    session: int


@dataclass(frozen=True)
class SpeechStarted:
    pass


@dataclass(frozen=True, eq=False)
class SpeechEnded:
    audio: np.ndarray = field(repr=False)


@dataclass(frozen=True)
class TranscriptReady:
    session: int
    text: str
    language: str = ""
    unsure: bool = False   # konuşma tanıma emin değil → modele sormadan tekrar iste


@dataclass(frozen=True)
class LlmSentence:
    session: int
    text: str


@dataclass(frozen=True)
class LlmDone:
    session: int


@dataclass(frozen=True)
class LlmFailed:
    session: int
    message: str


@dataclass(frozen=True)
class TtsSentenceDone:
    session: int


@dataclass(frozen=True)
class TtsFailed:
    session: int
    message: str


@dataclass(frozen=True)
class StopResponse:
    pass


@dataclass(frozen=True)
class TogglePause:
    pass


@dataclass(frozen=True)
class Shutdown:
    pass


@dataclass(frozen=True)
class Tick:
    pass
