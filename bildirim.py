import os
import smtplib
import ssl
from email.message import EmailMessage
from datetime import datetime

from gunluk import gunluk_kur

log = gunluk_kur()

SIFRE_DEGISKENI = "ENVANTER_SMTP_SIFRE"


def ozet_olustur(dusuk_tonerler, yeni_cihazlar, kaybolanlar, degisenler=None):
    """Bildirilecek bir sey varsa e-posta metnini dondurur, yoksa None."""
    degisenler = degisenler or []
    if not (dusuk_tonerler or yeni_cihazlar or kaybolanlar or degisenler):
        return None

    satirlar = [f"Ag envanteri bildirimi - {datetime.now():%d.%m.%Y %H:%M}", ""]

    if dusuk_tonerler:
        satirlar.append(f"DUSUK TONER ({len(dusuk_tonerler)})")
        for t in dusuk_tonerler:
            satirlar.append(f"  - {t['ip']} ({t['cihaz']}): {t['ad']} %{t['yuzde']}")
        satirlar.append("")

    if yeni_cihazlar:
        satirlar.append(f"YENI CIHAZ ({len(yeni_cihazlar)})")
        for c in yeni_cihazlar:
                        satirlar.append(f"  - {c.get('IP Adresi')}  {c.get('Tip') or '-'}  {c.get('MAC Adresi', '-')}  {c.get('Uretici', '-')}")
        satirlar.append("")

    if kaybolanlar:
        satirlar.append(f"ERISILEMEYEN CIHAZ ({len(kaybolanlar)})")
        for c in kaybolanlar:
                        satirlar.append(f"  - {c.get('IP Adresi')}  {c.get('Tip') or '-'}  {c.get('Uretici', '-')}")
        satirlar.append("")

    if degisenler:
        satirlar.append(f"DEGISEN CIHAZ ({len(degisenler)})")
        for d in degisenler:
            satirlar.append(f"  - {d['ip']}")
            for fark in d["farklar"]:
                satirlar.append(f"      {fark}")
        satirlar.append("")

    satirlar.append("Bu mesaj envanter araci tarafindan otomatik olusturulmustur.")
    return "\n".join(satirlar)


def gonder(ayar, konu, govde):
    """E-postayi gonderir. Deneme modunda gondermek yerine dosyaya yazar."""
    mesaj = EmailMessage()
    mesaj["Subject"] = konu
    mesaj["From"] = ayar.eposta_gonderen
    mesaj["To"] = ", ".join(ayar.eposta_alicilar)
    mesaj.set_content(govde)

    if ayar.eposta_deneme_modu:
        os.makedirs("loglar", exist_ok=True)
        yol = os.path.join("loglar", "son_bildirim.txt")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(mesaj.as_string())
        log.info(f"Deneme modu: e-posta gonderilmedi, icerik {yol} dosyasina yazildi.")
        return True

    sifre = os.environ.get(SIFRE_DEGISKENI)
    if not sifre:
        log.error(f"{SIFRE_DEGISKENI} ortam degiskeni tanimli degil, e-posta gonderilemedi.")
        return False

    if not ayar.eposta_gonderen or not ayar.eposta_alicilar:
        log.error("Gonderen veya alici adresi eksik (config.ini [eposta]).")
        return False

    try:
        baglam = ssl.create_default_context()
        with smtplib.SMTP(ayar.smtp_sunucu, ayar.smtp_port, timeout=15) as sunucu:
            sunucu.starttls(context=baglam)
            sunucu.login(ayar.eposta_gonderen, sifre)
            sunucu.send_message(mesaj)
        log.info(f"E-posta gonderildi: {', '.join(ayar.eposta_alicilar)}")
        return True
    except smtplib.SMTPAuthenticationError:
        log.error("SMTP kimlik dogrulama basarisiz. Gmail icin uygulama sifresi gerekir.")
    except (smtplib.SMTPException, OSError) as hata:
        log.error(f"E-posta gonderilemedi: {hata}")
    return False