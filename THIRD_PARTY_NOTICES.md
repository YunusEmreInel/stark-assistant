# Üçüncü taraf bileşenler ve lisanslar

Lisanslar kurulu paketlerin üst verisinden ve model dosyalarının kendi model kartlarından okunmuştur (16.10.2026).

## Python kütüphaneleri

| Bileşen | Sürüm | Lisans |
|---|---|---|
| PySide6 (Qt) | 6.12.0 | LGPL-3.0 (ya da GPL-2.0/3.0) |
| sounddevice | 0.5.6 | MIT |
| NumPy | 2.4.6 | BSD-3-Clause ve diğerleri |
| sherpa-onnx | 1.13.8 | Apache-2.0 |
| onnxruntime | 1.31.0 | MIT |
| faster-whisper | 1.2.1 | MIT |
| CTranslate2 | 4.8.3 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| trafilatura | 2.3.1 | Apache-2.0 |
| ddgs | 9.16.0 | MIT |
| tokenizers / huggingface-hub | 0.23.3 / 2.2.0 | Apache-2.0 |
| nvidia-cublas-cu12, nvidia-cudnn-cu12 (isteğe bağlı) | 12.9 / 9.27 | NVIDIA özel lisansı |

## Modeller

| Model | Kullanım | Lisans |
|---|---|---|
| Qwen3 4B Instruct (Ollama `qwen3:4b-instruct`) | Dil modeli | Apache-2.0 |
| Whisper medium / tiny (OpenAI, Systran CTranslate2 dönüşümü) | Konuşma tanıma, uyandırma | MIT |
| Silero VAD | Konuşma algılama | MIT |
| Piper `tr_TR-fahrettin-medium` (varsayılan Türkçe ses) | Seslendirme | CC0 |
| Piper `tr_TR-fettah-medium` | Seslendirme (seçenek) | CC0 |
| Piper `tr_TR-dfki-medium` | Seslendirme (seçenek) | CC BY-NC-SA 4.0 — ticari olmayan kullanım |
| Piper `en_US-lessac-medium` | İngilizce seslendirme | Blizzard 2013 / Lessac lisansı — ticari olmayan kullanım |
| sherpa-onnx KWS zipformer gigaspeech | Denendi, kullanılmıyor | Apache-2.0 |
| Vikisözlük / Wiktionary (kaikki.org Wiktextract çıktısı) → `models\sozluk.db` | İngilizce-Türkçe sözlük | CC BY-SA 4.0 |

Ollama (MIT) ayrı bir uygulama olarak kurulur.

## Çevrimiçi servisler (yalnızca internet açıkken)

- **Open-Meteo** — hava durumu verisi, CC BY 4.0 (cevaplarda "Kaynak: Open-Meteo" diye belirtilir).
- **Frankfurter** — Avrupa Merkez Bankası referans kurları.
- **Kandilli Rasathanesi (Boğaziçi Üniversitesi)** — son depremler listesi, kişisel kullanım; cevaplarda kaynak
  olarak belirtilir.
- **ESPN** — herkese açık fikstür/sonuç verisi (site.api.espn.com), kişisel kullanım; cevaplarda "Kaynak: ESPN
  fikstürü" diye belirtilir.
- **Google Haberler / Bing Haberler RSS**, **DuckDuckGo ve ddgs'nin kullandığı arama motorları**, **AA, TRT Haber, NTV,
  Hürriyet RSS akışları** — kişisel kullanım; içerik kaynaklarına bağlantı verilir.
- **YouTube** — yalnızca kullanıcı istediğinde arama sayfası/video açmak için.
