"""Cevabı belli sorular ("kendini tanıt", "neler yapabilirsin?"): model "patron'ın asistanıyım" diyor ve olmayan
yetenekler sayıyordu; doğru cevap güncel ayarlardan kodla üretilir."""
import re

INTRO = re.compile(r"kendini\s+tanıt|sen\s+kimsin|kimsin\s+sen|\badın\s+ne|ismin\s+ne|who\s+are\s+you|"
                   r"introduce\s+yourself|what'?s\s+your\s+name", re.I)
ABILITIES = re.compile(r"ne(ler)?\s+yapabil|yeteneklerin|neler\s+biliyorsun\s+yapmayı|ne\s+işe\s+yarıyorsun|"
                       r"what\s+can\s+you\s+do|your\s+capabilities", re.I)


def reply_for(text: str, language: str, internet: bool) -> str | None:
    intro, abilities = bool(INTRO.search(text)), bool(ABILITIES.search(text))
    if not (intro or abilities):
        return None
    if language == "en":
        web = " I can also check the web, the weather and exchange rates for you." if internet else ""
        if intro:
            return ("I'm Stark, your personal assistant, boss. I run locally on this computer; I can chat, "
                    f"answer questions and remember what you ask me to.{web}")
        return ("I can talk with you in Turkish and English and answer your questions. I remember things when you "
                "say “remember that”, delete them when you say “forget”, and you can teach me facts with “learn "
                f"that”.{web} On this PC I can open apps like Chrome or Word, search in Chrome or YouTube, play a "
                "video, take a screenshot, create desktop files, and control volume and music. I can't delete "
                "files or control your phone.")
    web = " Ayrıca internetten güncel bilgi, hava durumu ve döviz kurlarına bakabilirim." if internet else ""
    if intro:
        return ("Ben Stark, kişisel asistanınızım patron. Bu bilgisayarda yerel olarak çalışıyorum; sohbet "
                f"edebilir, sorularınızı cevaplayabilir ve hatırlamamı istediğiniz bilgileri saklayabilirim.{web}")
    return ("Sizinle Türkçe ve İngilizce sohbet edip sorularınızı cevaplayabilirim. “Bunu hatırla” dediğiniz "
            "bilgileri saklar, “unut” deyince silerim; “şunu öğren” diyerek bana yeni bilgiler de "
            f"öğretebilirsiniz.{web} Bilgisayarda Chrome, Word gibi uygulamaları açabilir, Chrome'da ya da "
            "YouTube'da arama yapıp video açabilir, ekran görüntüsü alabilir, masaüstünde dosya oluşturabilir, "
            "sesi ve müziği kontrol edebilirim. Dosya silemem ve telefonunuzu kontrol edemem.")
