# Stark architecture

## Components and threads

```
Microphone (sounddevice, 16 kHz) ─► audio-proc thread: Listener (Silero VAD)
        │                              ├─ WAKE mode: short segments ─► Transcriber.wake (Whisper tiny) ─► "Stark"?
        │                              └─ VAD mode: speech start/end ─► Transcriber.main (Whisper medium, GPU)
        ▼
engine thread: Controller (state machine) ◄── all events through one queue, one thread
        │  Effects: set_mic, play_ack, transcribe, ask_llm, speak, cancel
        ├─► code-handled commands: memory/notes/teaching, computer control, morning briefing, dismiss/stop,
        │   introduction, calculator, dictionary, files, screen reading
        ├─► structured data: football fixtures (ESPN), earthquakes (Kandilli), weather, exchange rates
        ├─► plan thread: search decision (LLM, ~0.5 s) ─► tool thread: news RSS / web search
        ├─► llm thread: Ollama stream ─► SentenceStream ─► sentences
        └─► learn thread: extracts durable facts from the conversation (in the background)
Speaker: tts-synth thread (Piper, sherpa-onnx) ─► tts-play thread (sounddevice) ─► amplitude ─► orb
Qt main thread: MainWindow, OrbWidget, tray, settings; updated from the engine through Bridge signals.
```

## State machine

`INITIALIZING → IDLE → LISTENING ⇄ CAPTURING → TRANSCRIBING → THINKING → SPEAKING → LISTENING`;
back to `IDLE` after 10 s without speech in LISTENING. Also `PAUSED`, `ERROR`, `STOPPED`.

- The 10 s timer only runs in LISTENING; it starts after the wake acknowledgement and the last spoken sentence
  have finished (monotonic clock).
- Every wake/cancel creates a new `session` id; ASR/LLM/TTS events from an older session are dropped.
- While SPEAKING, the microphone only listens for the wake word (barge-in); detections that overlap the sentence
  being spoken are treated as echo. A short echo guard is applied when switching from speaking to listening.
- Closing phrases ("teşekkürler", *thanks*) go straight to IDLE; "dur/sus" (*stop/quiet*) silently returns to
  LISTENING.
- One minute after entering IDLE, the language model is unloaded from Ollama and the process working set is
  trimmed; the model is preloaded again as soon as the wake word is heard.

## Layers against hallucination

1. If speech-recognition confidence is low (avg_logprob < −0.55), the model is not asked; the user is asked to repeat.
2. Memory/notes/teaching, personal questions ("what is my mother's name?"), the introduction, calculation,
   dictionary, fixtures, earthquakes, weather and exchange rates are answered by code.
3. Only memory entries relevant to the question are given to the model; location context only for local questions.
4. Search answers are generated without streaming; if they contain a score/number/time/date not present in the
   sources, the answer is not spoken. Upcoming-event answers that mention a past date are rejected.
5. "Yesterday/today" news is filtered by publication date; old results without a date are not presented as "latest".
6. Every automatically learned fact is compared with the user's sentence (75% word overlap), otherwise it is not saved.

## Data

`%USERPROFILE%\.stark` (not AppData — AppData writes are redirected for processes started from MSIX-packaged apps):
`stark.db` (conversations, messages, memories[kind, source, expires_at], notes), `settings.json`, `yerler.json`
(optional district names), `models\`, `yedekler\` (daily SQLite backup, 7 days), `stark_hata.log`.

## Error handling

If Ollama is not running, Stark tries to start it; otherwise it enters the ERROR state with a "retry" button. If
the microphone disappears it is reopened every 2 s. Network/search errors never block the conversation; they are
reported in a plain sentence. When running without a console, Python errors and native crashes are written to
`stark_hata.log`.
