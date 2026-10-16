# Development scripts

Measurement and experiment scripts used while building Stark. They are **not needed to install or run it**.
Most of them expect the models to be installed (`scripts\setup_windows.ps1`) and some need a microphone, Ollama
or an internet connection. Run them from the project root, e.g.:

```powershell
.\.venv\Scripts\python.exe scripts\dev\debug_search.py "Gündemde neler var?"
```

| Script | Purpose |
|---|---|
| `bench_asr.py`, `bench_asr_gpu.py`, `asr_confidence.py`, `test_language.py` | Speech-recognition speed, accuracy and confidence thresholds |
| `bench_llm.py`, `bench_gpu.py` | Language-model speed and GPU usage |
| `bench_voice.py`, `voice_samples.py` | Compare text-to-speech voices |
| `analyze_wake_whisper.py`, `test_mics.py` | Wake-word detection and microphone checks |
| `smoke_*.py` | End-to-end checks of the engine, memory, search and barge-in |
| `test_grammar.py`, `test_hallucination.py`, `test_learning_llm.py`, `test_memory_llm.py`, `test_planner.py` | Behaviour checks against the real language model |
| `debug_search.py` | Shows sources, the raw model answer and rejected numbers for a web question |
| `capture_window.py` | Captures only the Stark window |
| `run_console.ps1` | Starts Stark with a console window for debugging |

The automated test suite lives in `tests/` and runs with `.\.venv\Scripts\python.exe -m pytest -q`.
