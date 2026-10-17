# Stark — a local, Turkish-speaking voice assistant for Windows

**Stark** is a voice assistant that runs **entirely on your own Windows PC, for free**. It speaks Turkish (and
English): say "Stark", ask your question, and it answers out loud. Speech recognition, the language model and the
voice all run locally — no subscription, no API key, no cloud account. By default your conversations and memory
never leave your computer.

Internet access is optional and only used for questions that need current information (news, weather, exchange
rates, football fixtures, earthquakes). There is also an optional **smart mode** that sends the conversation to a
larger online model on free tiers (Groq → Gemini → OpenRouter) for much better understanding; see
[Smart mode](#smart-mode-optional-online-models).

<table>
  <tr>
    <td align="center" width="55%"><img src="docs/images/main-panel.png" alt="Stark main panel" width="420"></td>
    <td align="center" width="45%"><img src="docs/images/corner-panel.png" alt="Mini panel shown in the bottom-right corner when the main window is closed" width="380"></td>
  </tr>
  <tr>
    <td align="center"><b>Main panel</b> — the golden orb shows Stark's state (listening, thinking, speaking) and reacts to its voice; the conversation is also shown as text.</td>
    <td align="center"><b>Mini panel</b> — when the main window is closed, saying "Stark" brings up this small panel in the bottom-right corner without stealing focus from the app you are using.</td>
  </tr>
</table>

<sub>Window labels in these screenshots are shown in English for this README; the app's own interface is in Turkish.</sub>

> This is a personal project and is not claimed to be error-free. Because it uses a small local language model,
> some answers can be wrong — the code has several safeguards against this (see
> [How it tries to stay accurate](#how-it-tries-to-stay-accurate)).

> **Language note:** Stark talks to you in Turkish, and its interface is in Turkish. The voice commands below are
> the Turkish phrases you actually say, with their meaning in parentheses. If you speak English to it, it answers
> in English, but the built-in commands are Turkish.

---

## Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation (step by step)](#installation-step-by-step)
- [First launch and settings](#first-launch-and-settings)
- [Usage and commands](#usage-and-commands)
- [Data and privacy](#data-and-privacy)
- [Security](#security)
- [Smart mode (optional online models)](#smart-mode-optional-online-models)
  - [Getting the free API keys](#getting-the-free-api-keys)
- [How it tries to stay accurate](#how-it-tries-to-stay-accurate)
- [Performance and memory](#performance-and-memory)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Development](#development)
- [License](#license)

---

## Features

| Feature | Example (what you say) |
|---|---|
| **Voice conversation** | "Stark, fotosentez nedir?" (*what is photosynthesis?*) — keep talking within 10 s without saying "Stark" again |
| **Interrupting** | Say "Stark" while it is speaking; "Stark, dur" (*stop*) just silences it |
| **Current information** | "Hava nasıl?" (*how's the weather?*), "Dolar kaç lira?" (*USD to TRY?*), "Gündemde neler var?" (*what's in the news?*) |
| **Football fixtures and results** | "Galatasaray'ın yarınki maçı saat kaçta?" (*what time is Galatasaray's match tomorrow?*), "Fenerbahçe'nin sonraki 5 maçı" (*Fenerbahçe's next 5 matches*) — Turkish Süper Lig and major European leagues |
| **Earthquakes** | "Son deprem nerede oldu?" (*where was the last earthquake?*) — from Kandilli Observatory data |
| **Morning briefing** | "Günaydın" (*good morning*) → date, weather, today's/tomorrow's plans, notes, headlines |
| **Memory** | "Bunu hatırla: en sevdiğim renk mavi" (*remember: my favourite colour is blue*), "Neleri hatırlıyorsun?" |
| **Learns by itself** | Picks up things like "yarın sınavım var" (*I have an exam tomorrow*) from conversation (can be turned off) |
| **Teaching by voice** | "Şunu öğren: …" (*learn this: …*), "Hayır, doğrusu şu: …" (*no, the correct answer is: …*) |
| **Notes** | "Not al: Cuma kitap iade et" (*note: return the book on Friday*), "Notlarımı oku" (*read my notes*) |
| **Computer control** | "Chrome'u aç" (*open Chrome*), "YouTube'da … aç" (*play … on YouTube*), "Ekran görüntüsü al" (*take a screenshot*), "Sesi kıs" (*volume down*) |
| **Files** | "Masaüstündeki ödev dosyasını aç" (*open the homework file on my desktop*) — executables are never run |
| **Exact calculations** | "345 çarpı 27 kaç?" (*345 times 27?*), "1000 liraya yüzde 20 KDV ekle" (*add 20% VAT*), unit conversion — computed by code |
| **English–Turkish dictionary** | "According kelimesinin Türkçesi ne?" (*what is "according" in Turkish?*) — offline, Wiktionary data |
| **Screen reading** | "Ekranda ne yazıyor?" (*what's on the screen?*), "Bunu özetle" (*summarise this*), "Bunu İngilizceye çevir" (*translate this to English*) |

The full command list is in the app under the **ⓘ** button in the title bar (hover for a summary, click for the guide).

---

## Requirements

| | Minimum | Recommended |
|---|---|---|
| Operating system | Windows 10 (64-bit) | Windows 11 |
| RAM | 8 GB | 16 GB |
| Graphics card | Not required (runs on the CPU, slower) | NVIDIA with 4 GB VRAM or more |
| Disk space | ~8 GB free | |
| Microphone | Laptop microphone or headset | Headset (interrupting works more reliably) |
| Internet | Only during installation | For current-information questions |

You need these installed first (both free):

1. **Python 3.11** — [python.org/downloads/release/python-3119](https://www.python.org/downloads/release/python-3119/)
   (tick **"Add python.exe to PATH"** during setup). Python 3.12 and newer are not supported.
2. **Ollama** (runs the local language model) — [ollama.com/download](https://ollama.com/download),
   or in PowerShell: `winget install Ollama.Ollama`

---

## Installation (step by step)

### 1. Download the project

**Without Git:** click the green **Code** button at the top of this page → **Download ZIP**, then extract it, e.g.
to `Documents\stark-assistant`.

**With Git:**

```powershell
git clone https://github.com/YunusEmreInel/stark-assistant.git
cd stark-assistant
```

### 2. Run the setup script

In the project folder, type `powershell` in the File Explorer address bar and press Enter (or right-click →
"Open in Terminal"), then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
```

The script does the following (no administrator rights needed, your system Python is not touched):

| Step | What it does | Size |
|---|---|---|
| Virtual environment | Installs the Python libraries into `.venv`; also installs CUDA libraries if you have an NVIDIA card | ~1–2 GB |
| Language model | `ollama pull qwen3:4b-instruct` | ~2.5 GB |
| Voice models | Speech detection, Turkish/English voices (Piper) | ~330 MB |
| Speech recognition | Whisper medium and tiny | ~1.6 GB |
| Dictionary | Builds the English–Turkish dictionary from Wiktionary (once; data is streamed, not saved) | downloads ~570 MB, keeps ~90 MB; 3–20 min |
| Launcher | Compiles `launcher\Stark.exe` and adds a **Stark** shortcut to the desktop and Start menu | |
| Tests | Runs the automated tests | |

It takes 15–60 minutes depending on your connection. If a step fails, just run the script again — finished
steps are not downloaded twice. (The script's messages are in Turkish.)

### 3. Start it

Double-click **Stark** on your desktop. It is ready when the orb turns gold (first start takes 15–30 s).

### 4. (Optional, recommended) Turn on smart mode

Stark works without this, using the small model on your PC. For much better understanding, get free API keys from
Groq (required for smart mode), Gemini and OpenRouter (optional backups) — about 5 minutes, no credit card — and
paste them into Settings. Step-by-step: [Getting the free API keys](#getting-the-free-api-keys).

---

## First launch and settings

Open Settings with the **gear** button at the bottom of the window ("Ayarlar"):

| Setting | Description |
|---|---|
| **Adınız** (*your name*) | Optional; Stark will know your name |
| **Hitap** (*form of address*) | Default "patron" (*boss*), with the formal "siz". Change it to whatever you like |
| **Mikrofon / Hoparlör** | "Windows varsayılanı" (*Windows default*) is usually right. The input level bar should move when you speak |
| **Uyandırma testi** (*wake test*) | Say "Stark"; it shows up here when detected |
| **İnternet erişimi** (*internet access*) | **Off** by default. Turn it on for news, weather, exchange rates, fixtures and earthquakes |
| **Varsayılan şehir** (*default city*) | Used for weather and local questions |
| **İnternetteki model** (*smart mode*) | Off by default. Paste free Groq / Gemini / OpenRouter keys to use larger online models — see [Smart mode](#smart-mode-optional-online-models) |
| **Bilgi sorularını doğrula** (*verify factual questions*) | Questions with precise answers ("how many, who, when") are checked online (5–15 s) |
| **Uykudan sonra bellekten çıkar** (*unload after sleep*) | Minutes after Stark goes to sleep before the models are removed from memory and the GPU (default 1) |
| **Windows açılınca başlat** (*start with Windows*) | Launch Stark automatically |

**Optional — district names:** speech recognition sometimes misspells local district names. If you list your
city's districts in `%USERPROFILE%\.stark\yerler.json`, they are recognised correctly:

```json
{ "İzmir": ["Bornova", "Karşıyaka", "Buca", "Konak"] }
```

You can also teach them one by one: "Şunu öğren: Bornova, İzmir'in bir ilçesidir" (*learn: Bornova is a district of İzmir*).

---

## Usage and commands

1. Say **"Stark"** → it answers "Efendim patron". Then ask your question. Or in one breath: "Stark, hava nasıl?"
2. If you speak again within **10 seconds** after the answer, the conversation continues; otherwise it goes back to sleep.
3. **"Teşekkürler" / "Sağ ol" / "Bu kadar"** (*thanks / that's all*) → it goes back to sleep right away.

| Shortcut | Action |
|---|---|
| **Ctrl + Alt + W** | Wake Stark (also when it is in the background) |
| **Ctrl + Alt + S** | Stop Stark while it is speaking |
| Window **X** | Does not quit; hides Stark to the system tray |
| **Power button** / tray → "Tamamen çık" | Quits Stark completely |

If you doubt an answer, say **"internetten araştır"** (*look it up online*): your previous question is searched on
the web. To search a specific site: "Vikipedi'den bak" (*check Wikipedia*), "Maçkolik sitesine bak".

All commands with examples are in the app's **ⓘ guide**.

---

## Data and privacy

- All personal data stays **on your computer only**, in `%USERPROFILE%\.stark`:

  | File | Contents |
  |---|---|
  | `settings.json` | Your settings |
  | `stark.db` | Conversation history, memory, notes (SQLite; deleted records are wiped from the file too) |
  | `yerler.json` | (Optional) your city's districts |
  | `models\` | Voice, speech recognition and dictionary models |
  | `yedekler\` | Daily backups (last 7 days) |
  | `stark_hata.log` | Technical error log only |

- **Audio is never written to disk.** Microphone audio is processed in memory and discarded.
- **Screen-reading images are never written to disk**; text is recognised locally with Windows' built-in OCR.
- **Your conversations, memory and notes are never sent to the internet** — unless you turn on smart mode (below).
- With internet access on, only current-information questions go out: search keywords (DuckDuckGo, Google/Bing
  News RSS), the city name for weather (Open-Meteo), currency codes (Frankfurter / European Central Bank), the team
  for fixtures (ESPN), and the earthquake list request (Kandilli). No personal information is added to these requests.
- Self-learning is not model training; it only extracts short notes from what you say. You can review and delete
  them in the history and memory window.
- Deleted information can remain in the daily backups for up to 7 days; Settings → **"Yedekleri sil"** (*delete
  backups*) removes them immediately.

---

## Security

- **The language model cannot run anything.** Computer commands (opening apps, searching, creating files…) are
  recognised only by fixed patterns in the code and limited to an allow-list; text generated by the model is never
  executed as a command.
- **It never deletes or overwrites files.** If a file with the same name already exists on the desktop, a new name
  is used.
- **Executables are not opened:** types such as `.exe`, `.bat`, `.ps1`, `.msi`, `.lnk`, `.iso` are only shown
  selected in their folder.
- **Content from the internet is treated as data:** web pages, news and text read from the screen are given to
  the model as "data, not instructions"; instructions inside them are ignored.
- **Numbers not found in the sources are rejected:** scores, dates, prices and times in an internet-based answer
  are checked against the sources; if they don't match, the answer is not spoken.
- The calculator does not use `eval`; it only evaluates expressions made of numbers and arithmetic operators.
- The single-instance check uses a local channel that only the same Windows user can connect to; no network port
  is opened.

If you find a security issue, please report it privately via
[GitHub security advisories](https://github.com/YunusEmreInel/stark-assistant/security/advisories/new) instead of
opening a public issue.

---

## Smart mode (optional online models)

The local 4B model is small: it often misunderstands Turkish and invents details. Smart mode sends the conversation
to larger models on free tiers, in this order, moving on when one hits its limit or fails:

| Order | Service | Model | Free limit (Oct 2026, may change) |
|---|---|---|---|
| 1–2 | [Groq](https://console.groq.com) | GPT-OSS 120B, then Qwen3.8 27B | ~1,000 requests and 200K tokens per day per model, 8K tokens per minute |
| 3 | [Gemini](https://aistudio.google.com) (optional) | Gemini Flash-Lite | Not published; roughly 500 requests per day |
| 4–5 | [OpenRouter](https://openrouter.ai) | Gemma 4 31B, then Nemotron 120B (`:free`) | 50 requests per day |
| last | This PC | qwen3:4b-instruct via Ollama | Unlimited |

- Turn it on in **Settings → İnternetteki model** and paste your own free API keys. Keys are stored only on this PC
  in `%USERPROFILE%\.stark\anahtarlar.bin`, encrypted with Windows DPAPI (bound to your Windows account); they are
  never written to the settings file, logs or this repository.
- **Privacy:** with smart mode on, your messages, the recent conversation and relevant memory entries go to these
  services. Gemini's free tier may use prompts to improve Google's products, and free OpenRouter providers may log
  prompts. Commands, calculations, fixtures, earthquakes, weather and exchange rates are still handled on the PC.
- **The model researches by itself.** When internet access is on, the online model gets read-only tools —
  web search, news search (Turkish or English sources), reading a page, football fixtures (ESPN), earthquakes
  (Kandilli), weather (Open-Meteo), exchange rates and a calculator — and decides what to look up, reads the results,
  searches again if they're weak (up to 5 rounds) and then answers. For time-bound questions ("what happened",
  "when is", news, prices, weather, matches) it must use a tool before answering, so it can't answer from memory.
  The tools only fetch data; opening apps, files and other commands are still recognised by code, never by the model.
  OpenRouter's free models are used only for plain chat, not for tool use (they tended to invent results instead).
- The model that answered is shown at the bottom of the window (e.g. "Groq · Qwen3.8 27B"). In smart mode the local
  model isn't loaded at all unless every service fails, so the GPU stays free.

Measured on the same Turkish questions: the local model took 5.7–16.8 s per answer and sometimes invented details
(it guessed a university for "I'm a new graduate"); smart mode answered in 1–5 s (≈10 s when it decides to search
the web) and kept the context of follow-up questions.

### Getting the free API keys

An API key is a password that lets Stark use a service on **your** account. All three services have a free tier
and none of them asks for a credit card for it. You only need **Groq**; Gemini and OpenRouter are backups for when
Groq's daily limit runs out. Website menus change from time to time — if a button has a slightly different name,
look for "API keys".

> **Keep keys secret.** Don't post them in chats, screenshots, GitHub issues or code. Anyone with your key can use
> your quota. If one leaks, delete it on the same page and create a new one.

**1. Groq (main service)**

1. Go to [console.groq.com](https://console.groq.com) and sign in (Google account, GitHub or e-mail).
2. Open **API Keys** in the menu ([console.groq.com/keys](https://console.groq.com/keys)).
3. Click **Create API Key**, give it a name such as `Stark`, and confirm.
4. Copy the key right away (it starts with `gsk_`). Groq shows it **only once**; if you lose it, create a new one.

**2. Gemini (optional backup, Google)**

1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in with your Google account. On first visit,
   accept Google AI Studio's terms.
2. Click **Get API key** (left menu or top right), then **Create API key**. If it asks for a Google Cloud project,
   let it create one for you.
3. Copy the key (it starts with `AIza`).

Note: on the free tier Google may use what you send to improve its products. If you don't want that, leave this
key empty or untick **"Gemini'yi yedek olarak kullan"** in Settings.

**3. OpenRouter (optional, last backup)**

1. Go to [openrouter.ai](https://openrouter.ai) and click **Sign in** (Google, GitHub or e-mail).
2. Open **Keys** from the account menu ([openrouter.ai/settings/keys](https://openrouter.ai/settings/keys)).
3. Click **Create API Key**, name it `Stark`. You can leave the credit limit empty — Stark only uses the free
   (`:free`) models, which cost nothing.
4. Copy the key (it starts with `sk-or-`). It is shown only once.

Free OpenRouter models allow about 50 requests per day (more if you ever buy credits). Stark uses them only for
plain chat, as a last resort.

**4. Put the keys into Stark**

1. Open Stark and click the **gear** button at the bottom of the window (*Ayarlar* — Settings).
2. Make sure **"İnternet erişimi"** (*internet access*) is ticked — without it Stark can't search for answers.
3. Scroll to the **"İnternetteki model"** group and tick **"İnternetteki büyük modeli kullan"** (*use the large
   online model*).
4. Paste each key into its field: **Groq anahtarı**, **Gemini anahtarı**, **OpenRouter anahtarı**
   (*anahtar* = key). Empty fields are simply skipped. The fields show dots — that's normal.
5. Click **Kaydet** (*Save*). The keys are encrypted and stored only on this PC.

**5. Check that it works**

Say "Stark" and ask something like *"Bugün dünyada neler oldu?"* (What happened in the world today?). Under the
answer, the bottom of the window shows which model replied, e.g. **"Groq · GPT-OSS 120B"**. If it says the local
model (`qwen3:4b-instruct`), see the troubleshooting table below.

To stop using the online models, untick **"İnternetteki büyük modeli kullan"**; to remove a key, clear its field and
save.

## How it tries to stay accurate

The local 4B language model is small, so its own knowledge is not trusted. Instead, Stark:

- **Handles precise tasks with code:** calculation, unit conversion, the dictionary, football fixtures (ESPN),
  earthquakes (Kandilli), weather (Open-Meteo) and exchange rates (European Central Bank) — none of these answers
  are produced by the language model.
- **Verifies factual questions online** ("how many, who, when") and shows the sources on screen.
- **Catches invented numbers:** every number in an answer is looked up in the sources.
- **Asks when it misheard:** if speech recognition is unsure, it asks you to repeat.
- **Doesn't invent personal facts:** if you ask about something not in its memory, it says it doesn't know.

---

## Performance and memory

<p align="center"><img src="docs/images/resource-usage.png" alt="Measured resource usage, sleep cycle and response times" width="640"></p>

Stark is meant to be used alongside other work — including games and GPU-heavy apps — so it gives the hardware
back while it waits:

- **Sleep cycle:** 10 s of silence after an answer → sleep. One minute later both the language model and the
  speech-recognition model are removed from the GPU, and Stark's memory pages are returned to Windows
  (`llama-server` disappears from Task Manager).
- **While sleeping (window in the background):** ~15–85 MB RAM, ~0.2% CPU, 60–100 MB GPU memory, 0% GPU use.
  Only a tiny CPU model listens for "Stark"; the orb animation stops while the window isn't in front.
- **When you say "Stark":** both models reload while you are speaking (~4–5 s), so the first answer after a
  long pause can be a few seconds slower; later answers are not affected.
- **Measured times** (entry-level NVIDIA card with 4 GB): speech-to-text ~1 s, first spoken words of a normal
  answer ~2.5–3 s, answers that need a web search 7–20 s, fixtures/earthquakes/calculation/dictionary ~1 s.
- Without an NVIDIA card everything runs on the CPU; choosing **small** under Settings → speech recognition
  ("Konuşma tanıma") is recommended.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **It won't start** | Check `%USERPROFILE%\.stark\stark_hata.log`; every start writes a line there |
| **"Dil modeline ulaşamadım"** (*can't reach the language model*) | Make sure Ollama is installed and running (Stark tries to start it). `ollama list` should show `qwen3:4b-instruct` |
| **It doesn't hear "Stark"** | Settings → Ses (*audio*): does the input level bar move? Try the wake test; pick the right microphone |
| **It hears itself and interrupts itself** | Use a headset or lower the speaker volume |
| **Smart mode is on but the local model answers** | Check the key was copied completely (no space at the start or end) and saved. A deleted or mistyped key is skipped for 12 h — paste the correct one and save again to retry at once. The reason (e.g. HTTP 401 = wrong key) is shown in the Stark window |
| **Answers get slow after many questions in a row** | Groq's free tier allows a limited number of words per minute; Stark waits a few seconds or moves to the next service. It recovers by itself within a minute |
| **Internet questions get no answer** | Is internet access on in Settings? Free search engines may briefly return nothing after many queries |
| **Screen reading doesn't work** | The Turkish language pack must be installed: Windows Settings → Time & language → Language |
| **Python icon on the taskbar** | Unpin the old pin, then pin Stark again while it is running |
| **Setup script "cannot be loaded"** | Run it exactly as shown above, with `-ExecutionPolicy Bypass` |

---

## Known limitations

- The local 4B language model has limited general knowledge and occasionally makes Turkish grammar mistakes.
  There are safeguards against made-up answers, but correctness is not guaranteed — verify important information
  at its source.
- The wake word does not recognise who is speaking; anyone nearby can say "Stark".
- Interrupting is less reliable with speakers than with a headset.
- Free search engines may occasionally return nothing; very local events may not be in the news yet.
- Structured fixture data only covers teams in the Turkish Süper Lig and major European leagues; other teams are
  searched in the news.
- Windows only.

---

## Development

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # automated tests
.\.venv\Scripts\python.exe -m stark --cli        # console version without the UI
powershell -File scripts\build_launcher.ps1      # rebuild Stark.exe and the shortcuts
.\.venv\Scripts\python.exe scripts\make_screenshots.py   # regenerate the README images
```

- Measurement and experiment scripts used during development: [scripts/dev](scripts/dev/README.md)
- Dependencies are pinned to the tested versions in `requirements.lock` (and `requirements-cuda.lock` for NVIDIA
  cards); the setup script installs exactly these.
- Architecture and the anti-hallucination layers: [docs/architecture.md](docs/architecture.md)
- When adding a new voice command, update `src/stark/ui/help_text.py` (the ⓘ guide) and this README;
  `tests/test_help.py` fails for command types missing from the guide.
- Data lives in `%USERPROFILE%\.stark` instead of AppData: processes started from Microsoft Store (MSIX) packaged
  apps have their AppData writes redirected to a package-private folder.
- Code comments are mostly in Turkish.

**Open-source components used:** PySide6 (UI), faster-whisper (speech recognition), sherpa-onnx (speech detection
and Piper voices), Ollama + Qwen3 (language model), trafilatura (web page extraction), Wiktionary (dictionary).
Details and licenses: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

---

## License

Stark's own code is released under the [MIT License](LICENSE). The downloaded models and data have their own
licenses (some Piper voices are for non-commercial use only) — see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
