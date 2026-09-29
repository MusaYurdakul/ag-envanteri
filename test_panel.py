"""
test_panel.py — panel.py icin senaryo testleri.

Ag taramasi yapmaz, sunucu baslatmaz, gercek envanter.db'ye dokunmaz.
Gecici bir veritabanina sahte taramalar yazar ve Flask test istemcisiyle
sayfalari kontrol eder.

Calistirma:
    python test_panel.py
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timedelta

import veritabani as vt
from panel import uygulama_olustur


def cihaz(ip, mac="-", hostname="-", uretici="-", portlar="-"):
    return {"ip": ip, "mac": mac, "hostname": hostname, "uretici": uretici,
            "portlar": portlar, "toner": "-"}


def kontrol(ad, kosul):
    print(f"  [{'OK ' if kosul else 'HATA'}] {ad}")
    return kosul


def main():
    sonuclar = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as klasor:
        db = os.path.join(klasor, "test.db")
        liste_yok = os.path.join(klasor, "yok.csv")
        liste = os.path.join(klasor, "bilinen.csv")

        # Veritabani yokken
        istemci = uygulama_olustur(db, liste_yok).test_client()
        r = istemci.get("/")
        sonuclar.append(kontrol("1) Veritabani yokken acilis sayfasi calisiyor",
                                r.status_code == 200 and "Veritabanı yok" in r.get_data(as_text=True)))

        simdi = datetime.now()
        vt.kaydet([cihaz("192.168.1.5", "08:00:27:AA:AA:01", "PC-A", "Dell Inc.", "445/SMB"),
                   cihaz("192.168.1.9", "08:00:27:AA:AA:09", "ESKI-YAZICI", "Kyocera", "9100")],
                  "192.168.1.0/24", "r1.xlsx", simdi - timedelta(days=20), db)
        vt.kaydet([cihaz("192.168.1.23", "08:00:27:AA:AA:01", "PC-A", "Dell Inc.", "445/SMB"),
                   cihaz("192.168.1.50", "08:00:27:BB:BB:50", "<script>alert(1)</script>", "Hikvision", "554")],
                  "192.168.1.0/24", "r2.xlsx", simdi - timedelta(hours=1), db)

        istemci = uygulama_olustur(db, liste_yok).test_client()

        r = istemci.get("/")
        metin = r.get_data(as_text=True)
        sonuclar.append(kontrol("2) Ozet sayfasi: sayilar ve grafik",
                                r.status_code == 200 and "<svg" in metin and "Taramalara göre" in metin))

        r = istemci.get("/cihazlar")
        metin = r.get_data(as_text=True)
        sonuclar.append(kontrol("3) Cihaz listesi: 3 cihaz, tip tahmini var",
                                r.status_code == 200 and metin.count('class="tip"') == 3 and "Kamera" in metin))
        sonuclar.append(kontrol("4) Durum: son taramadaki aktif, eski cihaz 'gundur yok'",
                                "Aktif" in metin and "gündür yok" in metin))
        sonuclar.append(kontrol("5) Zararli hostname kacislanmis (XSS yok)",
                                "<script>alert(1)</script>" not in metin and "&lt;script&gt;" in metin))

        r = istemci.get("/cihaz/MAC:08:00:27:AA:AA:01")
        metin = r.get_data(as_text=True)
        sonuclar.append(kontrol("6) Cihaz detayi: iki farkli IP ve iki tarama",
                                r.status_code == 200 and "192.168.1.5" in metin and "192.168.1.23" in metin))

        r = istemci.get("/ara?q=192.168.1.5")
        metin = r.get_data(as_text=True)
        sonuclar.append(kontrol("7) IP aramasi: IP'yi kullanan cihaz bulundu",
                                r.status_code == 200 and "PC-A" in metin and "1 sonuç" in metin))

        r = istemci.get("/ara?q=08-00-27-aa-aa-01")
        sonuclar.append(kontrol("8) MAC aramasi (farkli yazim) cihaz sayfasina yonlendiriyor",
                                r.status_code == 302 and "MAC:08:00:27:AA:AA:01" in r.headers["Location"]))

        r = istemci.get("/ara?q=hikvision")
        sonuclar.append(kontrol("9) Metin aramasi uretici adinda buluyor",
                                "1 sonuç" in r.get_data(as_text=True)))

        r = istemci.get("/cihaz/MAC:00:00:00:00:00:99")
        sonuclar.append(kontrol("10) Olmayan cihaz 404 donuyor", r.status_code == 404))

        r = istemci.get("/taramalar")
        sonuclar.append(kontrol("11) Tarama listesi 2 kayit gosteriyor",
                                r.status_code == 200 and "2 tarama kaydı" in r.get_data(as_text=True)))

        # Salt okunur: panel veritabanini degistiremez
        with sqlite3.connect(db) as once:
            cihaz_sayisi = once.execute("SELECT COUNT(*) FROM cihazlar").fetchone()[0]
        once.close()
        with uygulama_olustur(db, liste_yok).app_context():
            from panel import _baglan
            baglanti = _baglan()
            try:
                baglanti.execute("DELETE FROM cihazlar")
                yazabildi = True
            except sqlite3.OperationalError:
                yazabildi = False
            finally:
                baglanti.close()
        sonuclar.append(kontrol("12) Panel baglantisi salt okunur (silme reddedildi)",
                                not yazabildi and cihaz_sayisi == 3))

        r = istemci.get("/cihazlar")
        sonuclar.append(kontrol("13) Bilinen cihaz listesi yokken 'Tanimsiz' hic gorunmuyor",
                                "Tanımsız" not in r.get_data(as_text=True)))

        # Bilinen cihaz listesi: PC-A kayitli, kamera kayitsiz
        with open(liste, "w", encoding="utf-8-sig", newline="") as f:
            f.write("kimlik;ad;sahip;konum;not\n08-00-27-aa-aa-01;Muhasebe PC;Ayşe;Kat 2;\n"
                    "08:00:27:AA:AA:09;Depo yazıcısı;BT;Depo;\n")
        istemci = uygulama_olustur(db, liste).test_client()

        metin = istemci.get("/cihazlar").get_data(as_text=True)
        sonuclar.append(kontrol("14) Kayitli cihaz adiyla, kayitsiz kamera 'Tanimsiz' rozetiyle gorunuyor",
                                "Muhasebe PC" in metin and "Ayşe" in metin and metin.count("Tanımsız") == 1))

        metin = istemci.get("/").get_data(as_text=True)
        sonuclar.append(kontrol("15) Ozet: aktif tanimsiz cihaz karti ve listesi",
                                "Aktif tanımsız cihaz" in metin and "192.168.1.50" in metin
                                and "listesinde olmayan" in metin))

        metin = istemci.get("/cihaz/MAC:08:00:27:BB:BB:50").get_data(as_text=True)
        detay_pc = istemci.get("/cihaz/MAC:08:00:27:AA:AA:01").get_data(as_text=True)
        sonuclar.append(kontrol("16) Detay: tanimsizda uyari, kayitlida sahip/konum bilgisi",
                                "Tanımsız cihaz" in metin and "Kayıt bilgisi" in detay_pc and "Kat 2" in detay_pc))

    basarili = sum(sonuclar)
    print(f"\n{basarili}/{len(sonuclar)} senaryo gecti.")
    if basarili != len(sonuclar):
        raise SystemExit(1)


if __name__ == "__main__":
    main()