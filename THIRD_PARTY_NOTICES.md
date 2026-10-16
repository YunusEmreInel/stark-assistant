# Third-party components and licenses

Licenses were read from the installed packages' metadata and from each model's own model card (16 Oct 2026).

## Python libraries

| Component | Version | License |
|---|---|---|
| PySide6 (Qt) | 6.12.0 | LGPL-3.0 (or GPL-2.0/3.0) |
| sounddevice | 0.5.6 | MIT |
| NumPy | 2.4.6 | BSD-3-Clause and others |
| sherpa-onnx | 1.13.8 | Apache-2.0 |
| onnxruntime | 1.31.0 | MIT |
| faster-whisper | 1.2.1 | MIT |
| CTranslate2 | 4.8.3 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| trafilatura | 2.3.1 | Apache-2.0 |
| ddgs | 9.16.0 | MIT |
| tokenizers / huggingface-hub | 0.23.3 / 2.2.0 | Apache-2.0 |
| pywinrt (winrt-*) | 3.2.1 | MIT |
| nvidia-cublas-cu12, nvidia-cudnn-cu12 (optional) | 12.9 / 9.27 | NVIDIA proprietary license |

## Models and data

| Model | Used for | License |
|---|---|---|
| Qwen3 4B Instruct (Ollama `qwen3:4b-instruct`) | Language model | Apache-2.0 |
| Whisper medium / tiny (OpenAI, Systran CTranslate2 conversion) | Speech recognition, wake word | MIT |
| Silero VAD | Speech detection | MIT |
| Piper `tr_TR-fahrettin-medium` (default Turkish voice) | Text-to-speech | CC0 |
| Piper `tr_TR-fettah-medium` | Text-to-speech (option) | CC0 |
| Piper `tr_TR-dfki-medium` | Text-to-speech (option) | CC BY-NC-SA 4.0 — non-commercial use |
| Piper `en_US-lessac-medium` | English text-to-speech | Blizzard 2013 / Lessac license — non-commercial use |
| Wiktionary (Turkish and English, via kaikki.org Wiktextract) → `models\sozluk.db` | English–Turkish dictionary | CC BY-SA 4.0 |

Ollama (MIT) is installed as a separate application. The models and data are downloaded during setup; none of
them are included in this repository. Integrity checks:

- Speech-detection and voice models: the SHA-256 of every file is verified (`scripts/download_models.py`);
  a file that doesn't match is deleted, not installed.
- Whisper models: downloaded from a fixed Hugging Face commit (`WHISPER_REVISIONS` in `src/stark/config.py`).
- Language model: Ollama verifies the SHA-256 digest of every model layer it downloads.
- Dictionary: Wiktionary data is plain text parsed into a SQLite database; it is never executed.

## Online services (only when internet access is on)

- **Open-Meteo** — weather data, CC BY 4.0 (answers say "Kaynak: Open-Meteo").
- **Frankfurter** — European Central Bank reference exchange rates.
- **Kandilli Observatory (Boğaziçi University)** — list of recent earthquakes, personal use; credited in answers.
- **ESPN** — public fixture/result data (site.api.espn.com), personal use; answers say "Kaynak: ESPN fikstürü".
- **Google News / Bing News RSS**, **DuckDuckGo and the search engines used by ddgs**, **AA, TRT Haber, NTV,
  Hürriyet RSS feeds** — personal use; answers link to the original sources.
- **YouTube** — only to open a search page or video when the user asks.
