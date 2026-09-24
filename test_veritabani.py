"""
test_veritabani.py — veritabani.py icin senaryo testleri.

Ag taramasi yapmaz, gercek envanter.db'ye dokunmaz. Gecici bir veritabani
olusturup sahte taramalar yazar ve sonuclari kontrol eder.

Calistirma:
    python test_veritabani.py
"""

import os
import sqlite3
import tempfile
from datetime import datetime

from openpyxl import Workbook

import veritabani as vt


def cihaz(ip, mac="-", hostname="-", uretici="-"):
    return {"ip": ip, "mac": mac, "hostname": hostname, "uretici": uretici,
            "portlar": "-", "toner": "-"}


def kontrol(ad, kosul):
    print(f"  [{'OK ' if kosul else 'HATA'}] {ad}")
    return kosul


def satir(db_yolu, sql, *param):
    db = sqlite3.connect(db_yolu)
    try:
        db.row_factory = sqlite3.Row
        return db.execute(sql, param).fetchone()
    finally:
        db.close()  # Windows'ta acik baglanti gecici klasorun silinmesini engeller


def main():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as klasor:
        db = os.path.join(klasor, "test.db")
        t1 = datetime(2026, 9, 10, 9, 0)
        t2 = datetime(2026, 9, 11, 9, 0)
        t3 = datetime(2026, 9, 12, 9, 0)
        t0 = datetime(2026, 9, 1, 9, 0)

        # Tarama 1: PC-A (.5), MAC'siz yerel makine
        vt.kaydet([cihaz("192.168.1.5", "08-00-27-AA-AA-01", "PC-A", "Dell"),
                   cihaz("127.0.0.1", "-", "LAPTOP")], "test", "r1", t1, db)
        # Tarama 2: PC-A DHCP'den yeni IP almis
        vt.kaydet([cihaz("192.168.1.23", "08:00:27:AA:AA:01", "PC-A", "Dell")],
                  "test", "r2", t2, db)
        # Tarama 3: PC-A ayni, yeni bir cihaz gelmis
        vt.kaydet([cihaz("192.168.1.23", "08:00:27:AA:AA:01", "PC-A", "Dell"),
                   cihaz("192.168.1.99", "08:00:27:CC:CC:09", "MISAFIR", "Samsung")],
                  "test", "r3", t3, db)
        # Eski bir tarama sonradan ice aktarilmis gibi (siralama disi)
        vt.kaydet([cihaz("192.168.1.2", "08:00:27:AA:AA:01", "PC-A-ESKI", "Dell")],
                  "test", "r0", t0, db)

        pc = satir(db, "SELECT * FROM cihazlar WHERE anahtar = 'MAC:08:00:27:AA:AA:01'")
        yerel = satir(db, "SELECT * FROM cihazlar WHERE anahtar = 'IP:127.0.0.1'")
        misafir = satir(db, "SELECT * FROM cihazlar WHERE anahtar = 'MAC:08:00:27:CC:CC:09'")
        ip5 = satir(db, "SELECT COUNT(DISTINCT anahtar) AS n, MIN(anahtar) AS a "
                        "FROM gozlemler WHERE ip = '192.168.1.5'")
        pc_ip_sayisi = satir(db, "SELECT COUNT(DISTINCT ip) AS n FROM gozlemler "
                                 "WHERE anahtar = 'MAC:08:00:27:AA:AA:01'")

        # Ice aktarma: ayni rapor iki kez aktarilirsa ikincisi atlanmali
        xlsx = os.path.join(klasor, "envanter_20260905_1000.xlsx")
        kitap = Workbook()
        kitap.active.append(["IP Adresi", "Hostname", "MAC Adresi", "Uretici", "Acik Portlar"])
        kitap.active.append(["192.168.1.7", "YAZICI", "08:00:27:DD:DD:07", "HP", "80/HTTP"])
        kitap.save(xlsx)
        print("Ice aktarma denemesi:")
        ilk = vt.ice_aktar(os.path.join(klasor, "envanter_*.xlsx"), db)
        ikinci = vt.ice_aktar(os.path.join(klasor, "envanter_*.xlsx"), db)
        yazici = satir(db, "SELECT * FROM cihazlar WHERE anahtar = 'MAC:08:00:27:DD:DD:07'")
        tarama_sayisi = satir(db, "SELECT COUNT(*) AS n FROM taramalar")["n"]

        print("\nSenaryolar:")
        sonuclar = [
        kontrol("1) IP'si degisen cihaz tek kayit olarak tutuldu",
                pc is not None and pc["gorulme_sayisi"] == 4),
        kontrol("2) Son IP en yeni taramadan geldi (.23)",
                pc["son_ip"] == "192.168.1.23"),
        kontrol("3) Sonradan eklenen eski tarama ilk gorulmeyi geriye cekti",
                pc["ilk_gorulme"] == t0.strftime(vt.ZAMAN_BICIMI)),
        kontrol("4) Eski tarama son IP'yi bozmadi",
                pc["son_ip"] == "192.168.1.23" and pc["son_hostname"] == "PC-A"),
        kontrol("5) Cihazin 3 farkli IP kullandigi goruluyor",
                pc_ip_sayisi["n"] == 3),
        kontrol("6) .5 adresinin sahibi dogru cihaz",
                ip5["n"] == 1 and ip5["a"] == "MAC:08:00:27:AA:AA:01"),
        kontrol("7) MAC'siz cihaz IP ile kaydedildi",
                yerel is not None and yerel["gorulme_sayisi"] == 1),
        kontrol("8) Yeni cihazin ilk gorulmesi kendi taramasi",
                misafir["ilk_gorulme"] == t3.strftime(vt.ZAMAN_BICIMI)),
        kontrol("9) Excel raporu ice aktarildi, zaman dosya adindan okundu",
                ilk == 1 and yazici is not None
                and yazici["ilk_gorulme"] == "2026-09-05 10:00:00"),
        kontrol("10) Ayni rapor ikinci kez aktarilmadi",
                ikinci == 0 and tarama_sayisi == 5),
    ]

        basarili = sum(sonuclar)
        print(f"\n{basarili}/{len(sonuclar)} senaryo gecti.")
        if basarili != len(sonuclar):
            raise SystemExit(1)


if __name__ == "__main__":
    main()