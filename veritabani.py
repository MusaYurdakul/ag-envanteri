"""
veritabani.py — Tarama gecmisini SQLite veritabaninda tutar.

Her tarama kaydedilir; cihazlar MAC adresine (yoksa IP'ye) gore tanimlanir.
Boylece bir cihazin ilk/son gorulme zamani, kullandigi IP'ler ve bir IP'yi
zaman icinde hangi cihazlarin kullandigi sorgulanabilir.

Kullanim:
    python veritabani.py                         # genel ozet
    python veritabani.py --gun 3                 # ozet, son 3 gun
    python veritabani.py --cihaz 192.168.56.1    # bu IP'yi kullanan cihazlar
    python veritabani.py --cihaz 08:00:27:AA:BB:CC   # bu cihazin gecmisi
    python veritabani.py --ice-aktar "raporlar/envanter_*.xlsx"
"""

import argparse
import glob
import os
import re
import sqlite3
from collections import Counter
from contextlib import closing
from datetime import datetime, timedelta

from karsilastir import mac_normallestir, rapor_oku


VARSAYILAN_DB = "envanter.db"
ZAMAN_BICIMI = "%Y-%m-%d %H:%M:%S"

SEMA = """
CREATE TABLE IF NOT EXISTS taramalar (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman         TEXT NOT NULL,
    ag            TEXT,
    cihaz_sayisi  INTEGER,
    rapor         TEXT
);

CREATE TABLE IF NOT EXISTS cihazlar (
    anahtar         TEXT PRIMARY KEY,
    mac             TEXT,
    uretici         TEXT,
    ilk_gorulme     TEXT NOT NULL,
    son_gorulme     TEXT NOT NULL,
    son_ip          TEXT,
    son_hostname    TEXT,
    gorulme_sayisi  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS gozlemler (
    tarama_id  INTEGER NOT NULL REFERENCES taramalar(id),
    anahtar    TEXT NOT NULL REFERENCES cihazlar(anahtar),
    ip         TEXT,
    hostname   TEXT,
    portlar    TEXT,
    toner      TEXT
);

CREATE INDEX IF NOT EXISTS ix_gozlem_anahtar ON gozlemler(anahtar);
CREATE INDEX IF NOT EXISTS ix_gozlem_ip      ON gozlemler(ip);
"""

# Eski taramalar ice aktarilirken de dogru sonuc versin diye:
# ilk gorulme en eskiye, son gorulme en yeniye gore guncellenir;
# son IP / hostname yalnizca daha yeni bir gozlemden gelirse degisir.
CIHAZ_YAZ = """
INSERT INTO cihazlar (anahtar, mac, uretici, ilk_gorulme, son_gorulme,
                      son_ip, son_hostname, gorulme_sayisi)
VALUES (?, ?, ?, ?, ?, ?, ?, 1)
ON CONFLICT(anahtar) DO UPDATE SET
    mac            = COALESCE(cihazlar.mac, excluded.mac),
    uretici        = CASE WHEN cihazlar.uretici IN ('-', '') OR cihazlar.uretici IS NULL
                          THEN excluded.uretici ELSE cihazlar.uretici END,
    ilk_gorulme    = MIN(cihazlar.ilk_gorulme, excluded.ilk_gorulme),
    son_gorulme    = MAX(cihazlar.son_gorulme, excluded.son_gorulme),
    son_ip         = CASE WHEN excluded.son_gorulme >= cihazlar.son_gorulme
                          THEN excluded.son_ip ELSE cihazlar.son_ip END,
    son_hostname   = CASE WHEN excluded.son_gorulme >= cihazlar.son_gorulme
                          THEN excluded.son_hostname ELSE cihazlar.son_hostname END,
    gorulme_sayisi = cihazlar.gorulme_sayisi + 1
"""


# --- temel islemler -------------------------------------------------------


def baglan(db_yolu=VARSAYILAN_DB):
    db = sqlite3.connect(db_yolu)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SEMA)
    return db


def _temiz(deger):
    if deger is None:
        return "-"
    metin = str(deger).strip()
    return metin or "-"


def anahtarlar_uret(cihazlar):
    """Her cihaz icin (anahtar, mac) dondurur.

    Gecerli ve bu taramada tekil MAC varsa anahtar MAC'tir, yoksa IP.
    """
    macler = [mac_normallestir(c.get("mac")) for c in cihazlar]
    sayac = Counter(m for m in macler if m)
    sonuc = []
    for cihaz, mac in zip(cihazlar, macler):
        if mac and sayac[mac] == 1:
            sonuc.append((f"MAC:{mac}", mac))
        else:
            sonuc.append((f"IP:{_temiz(cihaz.get('ip'))}", mac))
    return sonuc


def kaydet(cihazlar, ag="-", rapor="-", zaman=None, db_yolu=VARSAYILAN_DB):
    """Bir taramayi veritabanina yazar, tarama kimligini dondurur.

    cihazlar: main.py'deki yapi -> [{"ip", "hostname", "mac", "uretici", "portlar", "toner"}, ...]
    """
    zaman_metni = (zaman or datetime.now()).strftime(ZAMAN_BICIMI)

    with closing(baglan(db_yolu)) as db:
        with db:  # hata olursa hepsi geri alinir, olmazsa tek seferde kaydedilir
            imlec = db.execute(
                "INSERT INTO taramalar (zaman, ag, cihaz_sayisi, rapor) VALUES (?, ?, ?, ?)",
                (zaman_metni, ag, len(cihazlar), rapor),
            )
            tarama_id = imlec.lastrowid

            for cihaz, (anahtar, mac) in zip(cihazlar, anahtarlar_uret(cihazlar)):
                ip = _temiz(cihaz.get("ip"))
                hostname = _temiz(cihaz.get("hostname"))
                db.execute(CIHAZ_YAZ, (
                    anahtar, mac, _temiz(cihaz.get("uretici")),
                    zaman_metni, zaman_metni, ip, hostname,
                ))
                db.execute(
                    "INSERT INTO gozlemler (tarama_id, anahtar, ip, hostname, portlar, toner) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (tarama_id, anahtar, ip, hostname,
                     _temiz(cihaz.get("portlar")), _temiz(cihaz.get("toner"))),
                )
    return tarama_id


# --- eski Excel raporlarini ice aktarma ------------------------------------


DAMGA_DESENI = re.compile(r"(\d{8}_\d{4})")


def _rapor_zamani(yol):
    eslesme = DAMGA_DESENI.search(os.path.basename(yol))
    if eslesme:
        return datetime.strptime(eslesme.group(1), "%Y%m%d_%H%M")
    return datetime.fromtimestamp(os.path.getmtime(yol))


def ice_aktar(desen, db_yolu=VARSAYILAN_DB):
    """Eski Excel raporlarini gecmise ekler. Daha once aktarilan rapor atlanir."""
    dosyalar = sorted(
        d for d in glob.glob(desen)
        if not os.path.basename(d).startswith(("~$", "fark_"))
    )

    with closing(baglan(db_yolu)) as db:
        onceki = {r["rapor"] for r in db.execute("SELECT rapor FROM taramalar")}

    aktarilan = 0
    for yol in dosyalar:
        ad = os.path.basename(yol)
        if ad in onceki:
            print(f"  atlandi (zaten var): {ad}")
            continue

        kayitlar = rapor_oku(yol)
        cihazlar = [
            {
                "ip": k.get("IP Adresi"),
                "hostname": k.get("Hostname"),
                "mac": k.get("MAC Adresi"),
                "uretici": k.get("Uretici"),
                "portlar": k.get("Acik Portlar"),
                                "toner": k.get("Sarf Malzeme") or k.get("Toner"),
            }
            for k in kayitlar.values()
        ]
        kaydet(cihazlar, ag="(ice aktarildi)", rapor=ad,
               zaman=_rapor_zamani(yol), db_yolu=db_yolu)
        print(f"  aktarildi: {ad} ({len(cihazlar)} cihaz)")
        aktarilan += 1

    return aktarilan


# --- sorgular --------------------------------------------------------------


def ozet(gun=7, db_yolu=VARSAYILAN_DB):
    esik = (datetime.now() - timedelta(days=gun)).strftime(ZAMAN_BICIMI)

    with closing(baglan(db_yolu)) as db:
        t = db.execute(
            "SELECT COUNT(*) AS sayi, MIN(zaman) AS ilk, MAX(zaman) AS son FROM taramalar"
        ).fetchone()
        toplam_cihaz = db.execute("SELECT COUNT(*) FROM cihazlar").fetchone()[0]

        if not t["sayi"]:
            print("Veritabaninda henuz tarama yok.")
            return

        print(f"\nTarama sayisi   : {t['sayi']}  ({t['ilk']} -> {t['son']})")
        print(f"Benzersiz cihaz : {toplam_cihaz}")

        yeniler = db.execute(
            "SELECT * FROM cihazlar WHERE ilk_gorulme >= ? ORDER BY ilk_gorulme DESC", (esik,)
        ).fetchall()
        print(f"\n[+] Son {gun} gunde ilk kez gorulen cihazlar: {len(yeniler)}")
        for c in yeniler:
            print(f"      {c['son_ip']:<16} {c['mac'] or '-':<18} {c['uretici']:<25} ilk: {c['ilk_gorulme']}")

        eskiler = db.execute(
            "SELECT * FROM cihazlar WHERE son_gorulme < ? ORDER BY son_gorulme ASC LIMIT 10", (esik,)
        ).fetchall()
        print(f"\n[-] {gun} gunden uzun suredir gorulmeyen cihazlar: {len(eskiler)}")
        for c in eskiler:
            print(f"      {c['son_ip']:<16} {c['mac'] or '-':<18} {c['uretici']:<25} son: {c['son_gorulme']}")

        cok_ipli = db.execute(
            """SELECT c.anahtar, c.mac, c.uretici, COUNT(DISTINCT g.ip) AS ip_sayisi
               FROM cihazlar c JOIN gozlemler g ON g.anahtar = c.anahtar
               WHERE c.mac IS NOT NULL
               GROUP BY c.anahtar HAVING ip_sayisi > 1
               ORDER BY ip_sayisi DESC LIMIT 10"""
        ).fetchall()
        print(f"\n[!] Birden fazla IP kullanmis cihazlar: {len(cok_ipli)}")
        for c in cok_ipli:
            print(f"      {c['mac']:<18} {c['uretici']:<25} {c['ip_sayisi']} farkli IP")
    print()


def cihaz_gecmisi(sorgu, db_yolu=VARSAYILAN_DB):
    """MAC verilirse o cihazin gecmisini, IP verilirse o IP'yi kullanan cihazlari gosterir."""
    mac = mac_normallestir(sorgu)

    with closing(baglan(db_yolu)) as db:
        if mac:
            cihaz = db.execute(
                "SELECT * FROM cihazlar WHERE anahtar = ?", (f"MAC:{mac}",)
            ).fetchone()
            if not cihaz:
                print(f"Kayit bulunamadi: {mac}")
                return
            print(f"\nCihaz     : {mac}  ({cihaz['uretici']})")
            print(f"Ilk gorme : {cihaz['ilk_gorulme']}")
            print(f"Son gorme : {cihaz['son_gorulme']}  ({cihaz['gorulme_sayisi']} taramada)")
            print(f"Son IP    : {cihaz['son_ip']}  /  {cihaz['son_hostname']}\n")
            satirlar = db.execute(
                """SELECT t.zaman, g.ip, g.hostname, g.portlar
                   FROM gozlemler g JOIN taramalar t ON t.id = g.tarama_id
                   WHERE g.anahtar = ? ORDER BY t.zaman""",
                (f"MAC:{mac}",),
            ).fetchall()
            for s in satirlar:
                print(f"  {s['zaman']}  {s['ip']:<16} {s['hostname']:<25} {s['portlar']}")
        else:
            satirlar = db.execute(
                """SELECT g.anahtar, c.mac, c.uretici,
                          MIN(t.zaman) AS ilk, MAX(t.zaman) AS son, COUNT(*) AS sayi
                   FROM gozlemler g
                   JOIN taramalar t ON t.id = g.tarama_id
                   JOIN cihazlar  c ON c.anahtar = g.anahtar
                   WHERE g.ip = ?
                   GROUP BY g.anahtar ORDER BY son DESC""",
                (sorgu.strip(),),
            ).fetchall()
            if not satirlar:
                print(f"Bu IP hic gorulmemis: {sorgu}")
                return
            print(f"\n{sorgu} adresini kullanan cihazlar ({len(satirlar)}):\n")
            for s in satirlar:
                print(f"  {s['mac'] or '(MAC bilinmiyor)':<18} {s['uretici']:<25} "
                      f"{s['ilk']} -> {s['son']}  ({s['sayi']} tarama)")
    print()


if __name__ == "__main__":
    ayristirici = argparse.ArgumentParser(description="Envanter tarama gecmisi")
    ayristirici.add_argument("--db", default=VARSAYILAN_DB, help="Veritabani dosyasi")
    ayristirici.add_argument("--gun", type=int, default=7, help="Ozet icin gun sayisi")
    ayristirici.add_argument("--cihaz", help="MAC veya IP adresi")
    ayristirici.add_argument("--ice-aktar", help='Excel raporlari, orn. "raporlar/envanter_*.xlsx"')
    arg = ayristirici.parse_args()

    if arg.ice_aktar:
        sayi = ice_aktar(arg.ice_aktar, arg.db)
        print(f"\n{sayi} rapor ice aktarildi.")
    elif arg.cihaz:
        cihaz_gecmisi(arg.cihaz, arg.db)
    else:
        ozet(arg.gun, arg.db)