"""
kayitli_cihazlar.py — Bilinen (kayitli) cihaz listesi ve tanimsiz cihaz tespiti.

bilinen_cihazlar.csv dosyasindaki her satir bir cihazi tanimlar:
    kimlik;ad;sahip;konum;not;son_ip;hostname;uretici

  - kimlik : MAC adresi (tercih edilir) veya IP adresi
  - ad, sahip, konum, not : serbest metin, bos birakilabilir
  - son_ip, hostname, uretici : yalnizca bilgi amacli; --olustur doldurur, okurken kullanilmaz

Listede olmayan cihazlar "tanimsiz" sayilir. Dosya yoksa ozellik kapalidir
ve hicbir cihaz tanimsiz sayilmaz.

Dosya Excel ile duzenlenebilir: Turkce Excel icin ";" ayiraci ve UTF-8 BOM kullanilir.
Okurken "," ayiracli dosyalar da kabul edilir.

Kullanim:
    python kayitli_cihazlar.py --olustur   # envanter.db'deki cihazlarla listeyi olusturur / eksikleri ekler
    python kayitli_cihazlar.py             # son taramadaki tanimsiz cihazlari gosterir
"""

import argparse
import csv
import ipaddress
import os
import sqlite3
from contextlib import closing

from karsilastir import mac_normallestir


VARSAYILAN_YOL = "bilinen_cihazlar.csv"
ALANLAR = ["kimlik", "ad", "sahip", "konum", "not", "son_ip", "hostname", "uretici"]
KAYIT_ALANLARI = ["ad", "sahip", "konum", "not"]


def kimlik_anahtari(metin):
    """MAC veya IP metnini veritabanindaki anahtar bicimine cevirir: 'MAC:..' / 'IP:..'."""
    if metin is None:
        return None
    metin = str(metin).strip()
    mac = mac_normallestir(metin)
    if mac:
        return f"MAC:{mac}"
    try:
        return f"IP:{ipaddress.ip_address(metin)}"
    except ValueError:
        return None


def _ayirici(ilk_satir):
    return ";" if ilk_satir.count(";") >= ilk_satir.count(",") else ","


def oku(yol=VARSAYILAN_YOL):
    """{anahtar: {ad, sahip, konum, not}} dondurur. Dosya yoksa None (ozellik kapali)."""
    if not yol or not os.path.exists(yol):
        return None

    with open(yol, encoding="utf-8-sig", newline="") as f:
        ilk = f.readline()
        f.seek(0)
        okuyucu = csv.DictReader(f, delimiter=_ayirici(ilk))
        kayitlar = {}
        for satir in okuyucu:
            satir = {(k or "").strip().lower(): (v or "").strip() for k, v in satir.items()}
            anahtar = kimlik_anahtari(satir.get("kimlik"))
            if anahtar is None:
                continue  # bos veya gecersiz kimlik
            kayitlar[anahtar] = {alan: satir.get(alan, "") for alan in KAYIT_ALANLARI}
    return kayitlar


def bul(kayitlar, mac=None, ip=None):
    """Cihazin kaydini dondurur: once MAC ile, bulamazsa IP ile arar. Yoksa None."""
    if not kayitlar:
        return None
    for aday in (mac, ip):
        anahtar = kimlik_anahtari(aday)
        if anahtar and anahtar in kayitlar:
            return kayitlar[anahtar]
    return None


def tanimsiz_mi(kayitlar, mac=None, ip=None):
    """Liste kullaniliyorsa ve cihaz listede yoksa True."""
    return kayitlar is not None and bul(kayitlar, mac, ip) is None


def _mevcut_satirlar(yol):
    if not os.path.exists(yol):
        return []
    with open(yol, encoding="utf-8-sig", newline="") as f:
        ilk = f.readline()
        f.seek(0)
        return [
            {(k or "").strip().lower(): (v or "").strip() for k, v in satir.items()}
            for satir in csv.DictReader(f, delimiter=_ayirici(ilk))
        ]


def olustur(db_yolu="envanter.db", yol=VARSAYILAN_YOL):
    """Veritabanindaki cihazlardan listeyi olusturur veya eksik cihazlari ekler.

    Mevcut satirlara (kullanicinin yazdigi ad, sahip vb.) dokunmaz.
    Donus: (eklenen_sayisi, toplam_satir)
    """
    if not os.path.exists(db_yolu):
        raise FileNotFoundError(f"Veritabani bulunamadi: {db_yolu}")

    satirlar = _mevcut_satirlar(yol)
    bilinen = {kimlik_anahtari(s.get("kimlik")) for s in satirlar}

    with closing(sqlite3.connect(db_yolu)) as db:
        db.row_factory = sqlite3.Row
        cihazlar = db.execute(
            "SELECT anahtar, mac, son_ip, son_hostname, uretici FROM cihazlar ORDER BY son_ip"
        ).fetchall()

    eklenen = 0
    for c in cihazlar:
        if c["anahtar"] in bilinen:
            continue
        if c["mac"] is None and f"IP:{c['son_ip']}" in bilinen:
            continue
        satirlar.append({
            "kimlik": c["mac"] or c["son_ip"],
            "ad": "", "sahip": "", "konum": "", "not": "",
            "son_ip": c["son_ip"], "hostname": c["son_hostname"], "uretici": c["uretici"],
        })
        bilinen.add(c["anahtar"])
        eklenen += 1

    try:
        with open(yol, "w", encoding="utf-8-sig", newline="") as f:
            yazici = csv.DictWriter(f, fieldnames=ALANLAR, delimiter=";", extrasaction="ignore")
            yazici.writeheader()
            for s in satirlar:
                yazici.writerow({alan: s.get(alan, "") for alan in ALANLAR})
    except PermissionError:
        raise PermissionError(f"{yol} yazilamadi. Dosya Excel'de aciksa kapatip tekrar deneyin.")

    return eklenen, len(satirlar)


def _son_tarama_tanimsizlari(db_yolu, kayitlar):
    with closing(sqlite3.connect(db_yolu)) as db:
        db.row_factory = sqlite3.Row
        son = db.execute("SELECT id, zaman, ag FROM taramalar ORDER BY zaman DESC, id DESC LIMIT 1").fetchone()
        if son is None:
            return None, []
        gozlemler = db.execute(
            """SELECT g.ip, g.hostname, c.mac, c.uretici FROM gozlemler g
               JOIN cihazlar c ON c.anahtar = g.anahtar WHERE g.tarama_id = ?""",
            (son["id"],),
        ).fetchall()
    return son, [g for g in gozlemler if tanimsiz_mi(kayitlar, g["mac"], g["ip"])]


if __name__ == "__main__":
    ayristirici = argparse.ArgumentParser(description="Bilinen cihaz listesi")
    ayristirici.add_argument("--olustur", action="store_true",
                             help="Veritabanindaki cihazlarla listeyi olustur / eksikleri ekle")
    ayristirici.add_argument("--liste", default=VARSAYILAN_YOL, help="Liste dosyasi")
    ayristirici.add_argument("--db", default="envanter.db", help="Veritabani dosyasi")
    arg = ayristirici.parse_args()

    if arg.olustur:
        eklenen, toplam = olustur(arg.db, arg.liste)
        print(f"{arg.liste}: {eklenen} cihaz eklendi, toplam {toplam} satir.")
        print("Excel'de acip ad / sahip / konum sutunlarini doldurabilirsin.")
    else:
        kayitlar = oku(arg.liste)
        if kayitlar is None:
            print(f"{arg.liste} yok. Olusturmak icin: python kayitli_cihazlar.py --olustur")
        else:
            son, tanimsizlar = _son_tarama_tanimsizlari(arg.db, kayitlar)
            print(f"Kayitli cihaz: {len(kayitlar)}")
            if son is None:
                print("Veritabaninda tarama yok.")
            else:
                print(f"Son tarama: {son['zaman']} ({son['ag']})")
                print(f"Tanimsiz cihaz: {len(tanimsizlar)}")
                for g in tanimsizlar:
                    print(f"  {g['ip']:<16} {g['mac'] or '-':<18} {g['uretici']:<25} {g['hostname']}")