"""Stark'ın yapabildikleri: başlıktaki ⓘ düğmesinin ipucu ve "Kullanım kılavuzu" penceresi buradan üretilir.

Yeni bir özellik eklenince BURASI güncellenmeli. tests/test_help.py, kodun tanıdığı her komut türünün burada
anlatıldığını denetler.
"""
import html

# (başlık, kısa özet, [(söylenecek örnek, açıklama), ...])
SECTIONS = [
    ("Uyandırma ve konuşma", "“Stark” deyin; cevaptan sonra 10 sn içinde konuşursanız sohbet sürer.", [
        ("Stark", "Uyandırır → “Efendim patron”. Sorunuzu sonra söyleyin."),
        ("Stark, fotosentez nedir?", "Tek nefeste uyandırıp sorabilirsiniz."),
        ("(cevaptan sonra 10 sn içinde)", "“Stark” demeden devam edin; 10 sn sessizlikte beklemeye döner."),
        ("Teşekkürler / Sağ ol / Bu kadar", "Kısa cevap verip hemen beklemeye döner."),
        ("Stark (o konuşurken)", "Sözünü keser ve sizi dinler. “Stark, dur” yalnızca susturur."),
        ("Kendini tanıt / Neler yapabilirsin?", "Kendini ve yeteneklerini anlatır."),
        ("What is photosynthesis?", "İngilizce konuşursanız İngilizce cevap verir."),
    ]),
    ("Güncel bilgi (internet)", "Hava, döviz, haber, maç sonucu ve web araması; kaynakları ekranda gösterir.", [
        ("Hava nasıl? / Yarın İzmir'de yağmur var mı?", "Open-Meteo'dan; şehir söylenmezse Ayarlar'daki şehir."),
        ("Dolar kaç lira? / Euro kaç dolar?", "Avrupa Merkez Bankası referans kuru."),
        ("Gündemde neler var?", "AA, TRT Haber, NTV, Hürriyet manşetlerinden özet."),
        ("Fenerbahçe'nin son maçı kaç kaç bitti?", "Süper Lig takımları için fikstürden: skor, tarih, turnuva."),
        ("Fenerbahçe'nin yarınki maçı saat kaçta? / GS'nin sonraki maçı ne zaman?", "Rakip, gün, saat (Türkiye "
                                                                                     "saati) ve turnuva."),
        ("Maçkolik sitesine bak / Vikipedi'den bak", "Önceki soruyu o sitede arar."),
        ("Dün Bornova'da ne oldu?", "Yerel haberler, o güne ait olanlar."),
        ("Son deprem nerede oldu? / İzmir'de deprem mi oldu?", "Kandilli Rasathanesi listesinden: yer, saat, büyüklük."),
        ("Dolar neden yükseldi?", "“Neden” soruları kur yerine haberlerden cevaplanır."),
        ("İnternette ara: Python 3.14 yenilikleri", "Web araması; “internetten araştır” önceki soruyu arar."),
        ("Güneş sisteminde kaç gezegen var?", "Kesin cevaplı bilgi soruları (kaç, hangisi, kim, ne zaman) internetten "
                                               "doğrulanır; Ayarlar'dan kapatılabilir."),
    ]),
    ("Günaydın özeti", "Tarih, hava, bugünkü/yarınki planlar, notlar ve gündem tek seferde.", [
        ("Günaydın / Günün özeti / Bugün neler var?", "Hafızadaki “yarın sınavım var” gibi planlar da söylenir."),
    ]),
    ("Hafıza", "Söylediklerinizi saklar, ilgili sorularda kullanır; Geçmiş ve hafıza ekranından görülür.", [
        ("Bunu hatırla: en sevdiğim renk mavi", "Kişisel bilgi kaydeder."),
        ("Neleri hatırlıyorsun? / Hakkımda ne biliyorsun?", "Kayıtlı bilgileri sayar."),
        ("Unut: en sevdiğim renk / Bunu unut", "Siler (“bunu unut” yalnızca bu oturumdaki son kaydı)."),
        ("(sohbet ederken)", "Kendiliğinden öğrenir: “yarın sınavım var”, “daha kısa konuş” gibi. Kapatılabilir."),
    ]),
    ("Öğretme", "Genel bilgileri ve düzeltmeleri kalıcı olarak öğrenir.", [
        ("Şunu öğren: Bornova, İzmir'in bir ilçesidir", "Modelin kendi bilgisinin önüne geçer."),
        ("Hayır, doğrusu şu: …", "Yanlışını düzeltir ve öğrenir."),
        ("Neleri öğrendin?", "Öğrettiklerinizi sayar."),
    ]),
    ("Notlar", "Hafızadan ayrı not defteri; Geçmiş ekranında “Notlar” sekmesi.", [
        ("Not al: Cuma kitap iade et", "Not ekler."),
        ("Notlarımı oku", "Son notları okur."),
        ("Son notu sil", "En son notu siler."),
        ("Notlarımı masaüstüne aktar", "Masaüstüne “Stark notları.txt” yazar."),
    ]),
    ("Bilgisayar kontrolü", "Yalnızca izinli komutlar; dosya silmez, üzerine yazmaz.", [
        ("Chrome'u aç / Word'ü başlat / Not defterini aç", "Chrome, Edge, Word, Excel, PowerPoint, VS Code, Not Defteri, "
                                                          "Hesap Makinesi, Dosya Gezgini, Paint, Görev Yöneticisi, Ayarlar."),
        ("Chrome'da Python dersleri ara", "Google aramasını Chrome'da açar."),
        ("YouTube'da Barış Manço şarkıları ara", "YouTube arama sonuçlarını açar."),
        ("YouTube'da Tarkan Kuzu Kuzu'yu aç", "Videoyu adıyla bulup açar."),
        ("Ekran görüntüsü al", "Resimler\\Stark klasörüne kaydeder."),
        ("Masaüstünde alışveriş adında bir dosya oluştur, içine süt yaz", "Dosya ya da klasör oluşturur."),
        ("Sesi aç / kıs / kapat", "Bilgisayarın ses düzeyi."),
        ("Müziği durdur / Sonraki şarkı / Önceki şarkı", "Medya tuşları (YouTube, Spotify…)."),
        ("Ekranı kilitle", "Windows'u kilitler."),
    ]),
    ("Dosyalar", "Masaüstü, Belgeler, İndirilenler ve Resimler'de adıyla bulup açar; program dosyalarını çalıştırmaz.", [
        ("Masaüstündeki ödev dosyasını aç", "Adıyla arar, en uygun ve en yeni dosyayı açar."),
        ("Veri yapıları ödevimi aç / Bütçe tablosunu aç", "“tablo, sunum, pdf, fotoğraf” türe göre süzer."),
        ("Son indirdiğim dosyayı aç", "İndirilenler'deki en yeni dosya (.exe gibi programlar yalnızca klasörde gösterilir)."),
        ("İndirilenler klasörünü aç / Belgelerimi aç", "Klasörü açar."),
    ]),
    ("Sözlük", "İngilizce kelimelerin Türkçe anlamları, Vikisözlük'ten; tüm anlamlar ve örnekler ekranda.", [
        ("According kelimesinin Türkçesi ne?", "Türüne göre (isim, fiil, zarf…) tüm anlamlarını söyler."),
        ("Serendipity ne demek? / What does eventually mean?", "İngilizce kelimeyi tanır; Türkçe kelimeleri sohbet "
                                                               "olarak cevaplar."),
        ("Went'in Türkçesi ne?", "Çekimli biçimleri tanır: “went, go fiilinin çekimi”."),
        ("Kitap kelimesinin İngilizcesi ne?", "Türkçeden İngilizceye karşılıkları söyler."),
    ]),
    ("Ekranı okuma", "Öndeki pencereyi okur; özetler, açıklar ya da çevirir. Görüntü kaydedilmez.", [
        ("Ekranda ne yazıyor?", "Öndeki pencerenin (Stark hariç) ne olduğunu ve ana içeriğini kısaca söyler."),
        ("Bunu özetle / Bu sayfayı kısaca özetle", "Öndeki pencerenin yazısını özetler."),
        ("Ekrandakini açıkla", "Basitçe anlatır."),
        ("Bunu İngilizceye çevir / Bu yazıyı Türkçeye çevir", "Çevirir; yabancı dildeki çeviri ekrana yazılır."),
        ("Kopyaladığımı özetle / Panodakini İngilizceye çevir", "Ctrl+C ile kopyaladığınız metni kullanır."),
    ]),
    ("Hesaplama", "Hesapları model değil kod yapar; sonuç kesindir.", [
        ("345 çarpı 27 kaç?", "Dört işlem, üs (“2 üzeri 10”), karekök (“144'ün karekökü”)."),
        ("200'ün yüzde 18'i kaç? / 1000 liraya yüzde 20 KDV ekle", "Yüzde, KDV, indirim; “yüzde 20 KDV dahil 1200 lira”."),
        ("5 mil kaç kilometre? / 30 derece kaç Fahrenheit?", "Uzunluk, ağırlık, hacim ve sıcaklık çevirme."),
    ]),
    ("Kısayollar ve pencere", "Klavye ve pencere davranışları.", [
        ("Ctrl + Alt + W", "Uyandırır (Stark arka plandayken de)."),
        ("Ctrl + Alt + S", "Konuşan Stark'ı durdurur."),
        ("Pencerenin X'i", "Kapatmaz, saatin yanındaki tepsiye gizler."),
        ("Güç düğmesi / tepsi → Tamamen çık", "Stark'ı tamamen kapatır."),
    ]),
]

# Kodun tanıdığı komut türleri → kılavuzda geçmesi gereken anahtar ifade (tests/test_help.py denetler)
COVERAGE = {
    "desktop:open_app": "Chrome'u aç", "desktop:web_search": "Chrome'da", "desktop:youtube_search": "YouTube'da",
    "desktop:youtube_play": "Kuzu Kuzu", "desktop:screenshot": "Ekran görüntüsü", "desktop:create": "Masaüstünde",
    "desktop:volume_up": "Sesi aç", "desktop:volume_down": "kıs", "desktop:mute": "kapat",
    "desktop:media_pause": "Müziği durdur", "desktop:media_play": "Müziği", "desktop:media_next": "Sonraki şarkı",
    "desktop:media_prev": "Önceki şarkı", "desktop:lock": "Ekranı kilitle",
    "memory:remember": "Bunu hatırla", "memory:learn": "Şunu öğren", "memory:forget": "Unut",
    "memory:forget_last": "Bunu unut", "memory:list": "Neleri hatırlıyorsun", "memory:list_learned": "Neleri öğrendin",
    "memory:note": "Not al", "memory:note_list": "Notlarımı oku", "memory:note_delete_last": "Son notu sil",
    "memory:note_export": "masaüstüne aktar",
    "dictionary:en_tr": "Türkçesi ne", "dictionary:meaning": "ne demek", "dictionary:tr_en": "İngilizcesi ne",
    "screen:read": "Ekranda ne yazıyor", "screen:summarize": "Bunu özetle", "screen:explain": "Ekrandakini açıkla",
    "screen:translate": "İngilizceye çevir", "screen:clipboard": "Kopyaladığımı",
    "files:file": "ödev dosyasını aç", "files:folder": "klasörünü aç", "files:latest_download": "Son indirdiğim",
}


def all_text() -> str:
    return "\n".join(f"{t} {s} " + " ".join(f"{a} {b}" for a, b in items) for t, s, items in SECTIONS)


def tooltip_html() -> str:
    rows = "".join(f"<tr><td style='color:#E8A23A;padding:2px 10px 2px 0'><b>{html.escape(t)}</b></td>"
                   f"<td style='padding:2px 0'>{html.escape(s)}</td></tr>" for t, s, _ in SECTIONS)
    return (f"<div style='font-size:9pt'><b>Stark neler yapabilir?</b><table>{rows}</table>"
            f"<div style='color:#8A8A94;margin-top:4px'>Tüm komutlar ve örnekler için tıklayın.</div></div>")


def guide_html() -> str:
    out = ["<h2 style='color:#E8A23A;margin:0 0 4px 0'>Stark kullanım kılavuzu</h2>",
           "<p style='color:#8A8A94'>Örnekleri olduğu gibi söyleyebilirsiniz; “patron” hitabı ve dil Ayarlar'dan "
           "değiştirilebilir.</p>"]
    for title, summary, items in SECTIONS:
        out.append(f"<h3 style='color:#F2F2F4;margin:14px 0 2px 0'>{html.escape(title)}</h3>"
                   f"<div style='color:#8A8A94;margin-bottom:4px'>{html.escape(summary)}</div><table width='100%'>")
        for say, what in items:
            out.append(f"<tr><td width='45%' style='color:#E8A23A;padding:3px 12px 3px 0'>“{html.escape(say)}”</td>"
                       f"<td style='color:#D0D0D6;padding:3px 0'>{html.escape(what)}</td></tr>")
        out.append("</table>")
    return "".join(out)
