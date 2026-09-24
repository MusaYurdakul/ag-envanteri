import argparse
import glob
import importlib
import os
import re
import sys
from mac_vendor_lookup import MacLookup

from veritabani import kaydet as veritabani_kaydet
from guvenlik import tarama_izinli_mi
from ayarlar import Ayarlar
from gunluk import gunluk_kur
from tarayici import aralik_tara
from cihazbilgi import hostname_bul, mac_tablosu, uretici_bul, acik_portlar
from snmp_bilgi import snmp_ozet
from rapor import excel_yaz
from karsilastir import karsilastir
from bildirim import ozet_olustur, gonder
from html_rapor import html_yaz

log = gunluk_kur()


def envanter_cikar(ag, port_tara=True, snmp_tara=True, is_parcacigi=50):
    """Verilen agi tarar, bulunan cihazlar icin bilgi toplar."""
    log.info(f"Tarama baslatildi: {ag}")
    aktif_ipler = aralik_tara(ag, is_parcacigi)

    if not aktif_ipler:
        log.warning("Hicbir cihaz bulunamadi.")
        return []

    log.info(f"{len(aktif_ipler)} cihaz bulundu, bilgiler toplaniyor.")

    arp = mac_tablosu()
    arayici = MacLookup()
    cihazlar = []

    for ip in aktif_ipler:
        mac = arp.get(ip, "-")
        cihaz = {
            "ip": ip,
            "hostname": hostname_bul(ip),
            "mac": mac,
            "uretici": uretici_bul(mac, arayici),
            "portlar": acik_portlar(ip) if port_tara else "-",
        }

        if snmp_tara:
            try:
                cihaz.update(snmp_ozet(ip))
            except Exception as hata:
                log.error(f"{ip} SNMP sorgusu basarisiz: {hata}")
                cihaz.update({"snmp": "-", "toner": "-"})
        else:
            cihaz.update({"snmp": "-", "toner": "-"})

        cihazlar.append(cihaz)
        log.info(f"  {ip:<16} {cihaz['uretici']}")

    return cihazlar


def dusuk_tonerleri_bul(cihazlar, esik):
    """Toner seviyesi esigin altinda olanlari liste olarak dondurur."""
    sonuc = []
    for cihaz in cihazlar:
        toner = cihaz.get("toner", "-")
        if toner == "-":
            continue
        for eslesme in re.finditer(r"([^,:]+):\s*%(\d+)", toner):
            yuzde = int(eslesme.group(2))
            if yuzde < esik:
                kayit = {
                    "ip": cihaz["ip"],
                    "cihaz": cihaz.get("snmp", "-"),
                    "ad": eslesme.group(1).strip(),
                    "yuzde": yuzde,
                }
                sonuc.append(kayit)
                log.warning(f"DUSUK TONER: {kayit['ip']} ({kayit['cihaz']}) {kayit['ad']}: %{yuzde}")
    return sonuc


def son_raporu_bul(klasor, on_ek):
    """Klasordeki en son envanter raporunun yolunu dondurur, yoksa None."""
    dosyalar = glob.glob(os.path.join(klasor, f"{on_ek}_*.xlsx"))
    # Excel acikken olusan ~$ kilit dosyalarini atla
    dosyalar = [d for d in dosyalar if not os.path.basename(d).startswith("~$")]
    if not dosyalar:
        return None
    return max(dosyalar, key=os.path.getmtime)


def main():
    ayar = Ayarlar()

    ayristirici = argparse.ArgumentParser(description="Ag envanteri cikarma araci")
    ayristirici.add_argument("ag", nargs="?", default=None,
                             help="Taranacak ag araligi (bos birakilirsa config.ini kullanilir)")
    ayristirici.add_argument("-o", "--cikti", help="Excel dosya adi (varsayilan: otomatik)")
    ayristirici.add_argument("--port-tarama-yok", action="store_true",
                             help="Port taramasini atla, daha hizli calisir")
    ayristirici.add_argument("--snmp-yok", action="store_true", help="SNMP sorgusunu atla")

    arg = ayristirici.parse_args()
    hedef_ag = arg.ag or ayar.varsayilan_ag

    izin, sebep = tarama_izinli_mi(hedef_ag)
    if not izin:
        log.error(f"TARAMA ENGELLENDI: {sebep}")
        sys.exit(2)

    try:
        cihazlar = envanter_cikar(
            hedef_ag,
            port_tara=not arg.port_tarama_yok,
            snmp_tara=(not arg.snmp_yok) and ayar.snmp_etkin,
            is_parcacigi=ayar.is_parcacigi
        )
    except ValueError as hata:
        log.error(f"Gecersiz ag araligi: {hata}")
        sys.exit(1)
    except Exception as hata:
        log.error(f"Beklenmeyen hata: {hata}")
        sys.exit(1)

    if not cihazlar:
        return

    dusuk_tonerler = dusuk_tonerleri_bul(cihazlar, ayar.toner_esigi)

    # Yeni raporu yazmadan ONCE bir onceki raporu bul
    onceki_rapor = son_raporu_bul(ayar.cikti_klasoru, ayar.dosya_on_eki)

    try:
        dosya = excel_yaz(cihazlar, arg.cikti)
        if arg.cikti is None:
            yeni_yol = os.path.join(ayar.cikti_klasoru, os.path.basename(dosya))
            os.replace(dosya, yeni_yol)
            dosya = yeni_yol
        log.info(f"Rapor olusturuldu: {dosya}")
    except Exception as hata:
        log.error(f"Rapor yazilamadi: {hata}")
        sys.exit(1)
    try:
        html_dosya = html_yaz(cihazlar, ayar.cikti_klasoru, ayar.dosya_on_eki,
                              hedef_ag, ayar.toner_esigi)
        log.info(f"HTML rapor olusturuldu: {html_dosya}")
    except Exception as hata:
        log.error(f"HTML rapor yazilamadi: {hata}")

    try:
        veritabani_kaydet(cihazlar, hedef_ag, os.path.basename(dosya))
        log.info("Tarama gecmisi veritabanina kaydedildi.")
    except Exception as hata:
        log.error(f"Veritabanina yazilamadi: {hata}")

        yeni_cihazlar, kaybolanlar, degisenler = [], [], []
    if onceki_rapor:
        try:
            fark = karsilastir(onceki_rapor, dosya)
            yeni_cihazlar = fark["yeni"]
            kaybolanlar = fark["kaybolan"]
            degisenler = fark["degisen"]
            log.info(f"Onceki raporla karsilastirildi: {len(yeni_cihazlar)} yeni, {len(kaybolanlar)} kaybolan.")
        except Exception as hata:
            log.error(f"Karsilastirma yapilamadi: {hata}")
    else:
        log.info("Onceki rapor bulunamadi, karsilastirma atlandi.")

    if ayar.eposta_etkin:
        govde = ozet_olustur(dusuk_tonerler, yeni_cihazlar, kaybolanlar, degisenler)
        if govde:
            gonder(ayar, f"[Envanter] {hedef_ag} bildirimi", govde)
        else:
            log.info("Bildirilecek degisiklik yok, e-posta gonderilmedi.")


if __name__ == "__main__":
    main()
