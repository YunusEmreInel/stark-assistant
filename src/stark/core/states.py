from enum import Enum


class State(Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"                  # yalnızca "Stark" aranır
    LISTENING = "listening"        # yeni konuşma bekleniyor; 10 sn sayaç burada işler
    CAPTURING = "capturing"        # başlamış konuşmanın bitişi bekleniyor
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class MicMode(Enum):
    OFF = "off"        # aygıt serbest
    WAKE = "wake"      # uyandırma algılayıcı
    VAD = "vad"        # konuşma algılama (sohbet)
    MUTED = "muted"    # akış açık ama veri yorumlanmıyor (TTS/ASR sırasında)


# Kullanıcı sessizliği sayılmayan, işin sürdüğü durumlar
BUSY_STATES = {State.TRANSCRIBING, State.THINKING, State.SPEAKING}
