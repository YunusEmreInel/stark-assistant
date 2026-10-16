"""Ayarlar ve veri yolları. Kişisel veri kaynak klasörüne değil kullanıcı klasöründeki .stark altına yazılır.

AppData kullanılmaz: Microsoft Store (MSIX) paketli uygulamalardan (ör. Claude masaüstü) başlatılan süreçlerin
AppData yazıları Windows tarafından pakete özel gizli bir klasöre yönlendirilir. Stark'ın verileri ve modelleri
oraya gitmiş, masaüstünden açılan Stark onları bulamamıştı. Kullanıcı klasörünün kendisi yönlendirilmez.
"""
import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

APP_DIR = Path(os.environ.get("STARK_HOME", Path.home() / ".stark"))
MODELS_DIR = APP_DIR / "models"
LOG_FILE = APP_DIR / "stark_hata.log"
BACKUP_DIR = APP_DIR / "yedekler"
SETTINGS_FILE = APP_DIR / "settings.json"
DB_FILE = APP_DIR / "stark.db"   # sohbet geçmişi + açıkça kaydedilen hafıza
# Whisper modelleri Hugging Face'ten sabit bir sürümden (commit) indirilir: depo sonradan değişse de aynı dosyalar gelir
WHISPER_REVISIONS = {
    "tiny": "d90ca5fe260221311c53c58e660288d3deb8d356",
    "small": "536b0662742c02347bc0e980a01041f333bce120",
    "medium": "08e178d48790749d25932bbc082711ddcfdfbc4f",
}

# Talimat İngilizce: küçük modeller İngilizce talimata daha iyi uyuyor ve "Sen Stark'sın" gibi cümleleri
# cevaba kopyalamıyor ("Ben Sen Stark" hatası). Cevap dili ayrıca her turda belirtilir.
ADDRESS_RULE = (
    "Addressing rule: the user wants to be called '{tr}' in Turkish and '{en}' in English, like a loyal "
    "assistant to his boss. In Turkish always use the respectful formal second person (siz; verb endings "
    "-siniz/-sınız/-iniz, e.g. 'istersiniz', 'misiniz'), never 'sen' or informal -sin endings. Use '{tr}' "
    "naturally, at most once per reply, inside a sentence (e.g. 'Tamam patron, ...'); never as a standalone "
    "one-word sentence like '{tr_cap}.' at the end. '{tr}' is a form "
    "of address, not a name: never use it in third person (no '{tr}'ın', '{tr}'a'). Never end with filler "
    "closers like 'Tamam {tr}, bu kadar', 'bu bilgileri aktardım', 'başka bir şey var mı'. Use first person "
    "only for yourself. Answer directly without stock opening phrases."
)
SYSTEM_PROMPT = (
    "You are Stark, a general-purpose personal voice assistant running locally on the user's computer. "
    "Your replies are spoken aloud: be short, natural and conversational; no lists, tables, Markdown or "
    "emoji. Expand only when asked for detail.\n"
    "{address_rule}\n"
    "Honesty rules: never invent facts. You have no internet or live data of your own; current information "
    "is available only when web results are explicitly given to you in a system message. Without them, for "
    "weather, news, prices, exchange rates or scores say briefly that you can't access that right now. "
    "The user's words come from "
    "speech recognition and may be misheard: if a name, project or term looks meaningless or unknown to "
    "you, do not pretend to know it and do not make up details; ask what they meant. Do not describe "
    "past conversations or shared history that are not in the messages you were given. If the user asks "
    "what you said earlier, rely only on your actual previous replies in this conversation. Do not agree "
    "with false claims just to please him and do not make untrue confessions about yourself; correct "
    "politely. Never claim you searched, opened a file or did an action unless a tool actually did it. "
    "Never say you heard, read, saw or noticed something yourself ('duydum', 'okudum', 'gördüm'); you only "
    "know what is in this conversation and in provided results."
)


@dataclass
class Settings:
    user_name: str = ""                  # Ayarlar'dan; boşsa modele ad verilmez
    address_tr: str = "patron"           # hitap; Türkçe'de resmi "siz" ile
    address_en: str = "boss"
    language: str = "auto"               # "tr" | "en" | "auto" (auto: İngilizce ancak eminse)
    # LLM
    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:4b-instruct"   # uydurma testinde gemma3:4b'den belirgin şekilde dürüst
    llm_num_ctx: int = 4096
    llm_num_gpu: int = 99                # tüm katmanlar GPU'da (ölçüm: 13 → 45 tok/sn)
    llm_idle_unload_min: int = 1         # uykuya geçtikten bu kadar dk sonra dil modeli bellekten çıkar (~1,3 GB);
                                         # "Stark" deyince yeniden yüklenir (~3 sn, konuşurken). 0: hep bellekte
    llm_timeout_s: float = 60.0
    llm_temperature: float = 0.2
    # İnternetteki büyük modeller (Groq → Gemini → OpenRouter → bilgisayardaki model). Açıkken sohbet bu servislere
    # gider; anahtarlar ~/.stark/anahtarlar.bin içinde Windows DPAPI ile şifreli saklanır.
    cloud_enabled: bool = False
    cloud_use_gemini: bool = True
    cloud_max_tokens: int = 700
    history_turns: int = 8
    barge_in: bool = True                # Stark konuşurken "Stark" deyince susup dinler
    auto_learn: bool = True             # konuşmalardan kalıcı bilgi çıkar (yalnızca kullanıcının söyledikleri)
    # İnternet (arama, hava, döviz) — açıkken sorgular dış servislere gider
    internet_enabled: bool = False
    city: str = ""                       # hava durumu için varsayılan şehir
    fact_check: bool = True              # kesin cevaplı bilgi sorularını internetten doğrula (5-10 sn)
    searxng_url: str = ""                # kurulursa ör. http://127.0.0.1:8888
    # ASR
    whisper_model: str = "medium"           # Türkçe doğruluk: small 4/7, medium 6/7 (GPU ~1 sn)
    whisper_device: str = "cuda"             # yoksa otomatik CPU
    whisper_compute: str = "int8_float16"  # ölçüm: CPU 2.06 sn → GPU 0.41 sn
    # Ses
    input_device: str = ""               # boş = Windows varsayılanı
    output_device: str = ""
    listen_timeout_s: float = 10.0
    vad_threshold: float = 0.5
    vad_min_speech_s: float = 0.25
    vad_end_silence_s: float = 0.9
    max_record_s: float = 30.0
    echo_guard_speaker_s: float = 0.5
    echo_guard_headset_s: float = 0.15
    wake_threshold: float = 0.25
    wake_boost: float = 2.0
    tts_voice_tr: str = "vits-piper-tr_TR-fahrettin-medium"
    tts_voice_en: str = "vits-piper-en_US-lessac-medium"
    tts_speed: float = 1.0
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
