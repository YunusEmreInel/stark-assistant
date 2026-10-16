# Stark mimarisi

## Bileşenler ve iş parçacıkları

```
Mikrofon (sounddevice, 16 kHz) ─► audio-proc thread: Listener (Silero VAD)
        │                              ├─ WAKE modu: kısa bölümler ─► Transcriber.wake (Whisper tiny) ─► "Stark"?
        │                              └─ VAD modu: konuşma başı/sonu ─► Transcriber.main (Whisper medium, GPU)
        ▼
engine thread: Controller (durum makinesi) ◄── tüm olaylar kuyruktan, tek thread
        │  Effects: set_mic, play_ack, transcribe, ask_llm, speak, cancel
        ├─► kod komutları: hafıza/not/öğret, bilgisayar kontrolü, günaydın, kapanış/dur, tanıtım
        ├─► plan thread: arama kararı (LLM, ~0.5 sn) ─► tool thread: hava / döviz / haber RSS / web
        ├─► llm thread: Ollama akışı ─► SentenceStream ─► cümleler
        └─► learn thread: konuşmadan kalıcı bilgi çıkarma (arka planda)
Speaker: tts-synth thread (Piper, sherpa-onnx) ─► tts-play thread (sounddevice) ─► genlik ─► küre
Qt ana thread: MainWindow, OrbWidget, tepsi, ayarlar; Bridge sinyalleriyle motordan güncellenir.
```

## Durum makinesi

`INITIALIZING → IDLE → LISTENING ⇄ CAPTURING → TRANSCRIBING → THINKING → SPEAKING → LISTENING`;
LISTENING'de 10 sn konuşma yoksa `IDLE`. Ayrıca `PAUSED`, `ERROR`, `STOPPED`.

- 10 sn sayaç yalnızca LISTENING'de işler; "Efendim patron" ve son TTS cümlesi bittikten sonra başlar (monoton saat).
- Her uyanma/iptal yeni `session` kimliği üretir; eski oturumdan gelen ASR/LLM/TTS olayları atılır.
- SPEAKING sırasında mikrofon yalnızca uyandırma kelimesini dinler (söz kesme); okunan cümleyle örtüşen duyumlar yankı
  sayılır. Konuşmadan sohbete geçerken kısa yankı koruması uygulanır.
- Kapanış cümleleri ("teşekkürler") doğrudan IDLE'a; "dur/sus" sessizce LISTENING'e döner.

## Uydurmaya karşı katmanlar

1. Konuşma tanıma güveni düşükse (avg_logprob < −0.55) modele sorulmaz, tekrar istenir.
2. Hafıza/not/öğretme, kişisel sorular ("annemin adı?"), tanıtma, hava ve döviz cevapları kodla üretilir.
3. Modele yalnızca soruyla ilgili hafıza kayıtları verilir; konum bağlamı yalnızca yerel sorularda.
4. Arama cevapları akışsız üretilir; kaynaklarda olmayan skor/sayı varsa cevap okunmaz.
5. "Dün/bugün" haberleri tarihe göre süzülür; yayın tarihi olmayan eski sonuçlar "son" diye sunulmaz.
6. Otomatik öğrenilen her bilgi kullanıcının cümlesiyle karşılaştırılır (%75 kelime örtüşmesi), aksi halde kaydedilmez.

## Veri

`%USERPROFILE%\.stark` (AppData değil — MSIX paketli uygulamalardan başlatılan süreçlerde AppData yönlendirilir):
`stark.db` (conversations, messages, memories[kind, source, expires_at], notes), `settings.json`, `models\`,
`yedekler\` (günlük SQLite yedeği, 7 gün), `stark_hata.log`.

## Hata yönetimi

Ollama kapalıysa uygulama açılmaya çalışılır, olmazsa ERROR durumu ve "Tekrar dene". Mikrofon kaybolursa her 2 sn yeniden
açılır. Ağ/arama hataları sohbeti kilitlemez; anlaşılır bir cümleyle bildirilir. Konsolsuz çalışmada Python hataları ve
yerel çökmeler `stark_hata.log`'a yazılır.
