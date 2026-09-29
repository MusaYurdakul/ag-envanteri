"""
demo.py — README ekran goruntuleri icin ornek veri uretir.

Hicbir ag taramasi yapmaz, gercek envanter.db'ye dokunmaz. Tamamen uydurma
bir ofis agi verisiyle:
  - raporlar/demo_*.html  -> ornek HTML rapor
  - demo.db               -> 14 gunluk ornek tarama gecmisi (web paneli icin)
  - demo_bilinen_cihazlar.csv -> ornek bilinen cihaz listesi

Calistirma:
    python demo.py
    python panel.py --db demo.db --kayit demo_bilinen_cihazlar.csv
"""

import csv
import os
from datetime import datetime, timedelta

from html_rapor import html_yaz
from veritabani import kaydet


DEMO_AG = "192.168.10.0/24"

DEMO_CIHAZLAR = [
    {"ip": "192.168.10.1", "hostname": "gw-merkez", "mac": "00:1B:54:10:00:01",
     "uretici": "Cisco Systems, Inc", "portlar": "22/SSH, 443/HTTPS",
     "snmp": "Cisco IOS Software, ISR4331", "toner": "-"},
    {"ip": "192.168.10.2", "hostname": "sw-kat1", "mac": "00:1B:54:10:00:02",
     "uretici": "Cisco Systems, Inc", "portlar": "22/SSH, 23/Telnet",
     "snmp": "Cisco IOS Software, C2960X", "toner": "-"},
    {"ip": "192.168.10.10", "hostname": "DC01.demo.local", "mac": "00:0C:29:A1:B2:10",
     "uretici": "VMware, Inc.", "portlar": "53/DNS, 88/Kerberos, 389/LDAP, 445/SMB, 3389/RDP",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.11", "hostname": "SRV-DOSYA", "mac": "00:0C:29:A1:B2:11",
     "uretici": "VMware, Inc.", "portlar": "445/SMB, 3389/RDP",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.21", "hostname": "DESKTOP-MUH01", "mac": "B0:7B:25:3C:11:21",
     "uretici": "Dell Inc.", "portlar": "135/RPC, 445/SMB",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.22", "hostname": "LAPTOP-IT02", "mac": "54:E1:AD:7F:22:22",
     "uretici": "LCFC(HeFei) Electronics Technology", "portlar": "445/SMB, 3389/RDP",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.23", "hostname": "DESKTOP-URT05", "mac": "3C:52:82:19:23:23",
     "uretici": "HP Inc.", "portlar": "445/SMB",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.50", "hostname": "PRN-MUHASEBE", "mac": "A0:D3:C1:50:50:50",
     "uretici": "Hewlett Packard", "portlar": "80/HTTP, 443/HTTPS, 631/IPP, 9100/JetDirect",
     "snmp": "HP LaserJet Pro M404dn", "toner": "Siyah: %12"},
    {"ip": "192.168.10.51", "hostname": "PRN-URETIM", "mac": "00:17:C8:51:51:51",
     "uretici": "Kyocera Document Solutions", "portlar": "80/HTTP, 9100/JetDirect",
     "snmp": "ECOSYS M5526cdw", "toner": "Siyah: %64, Camgobegi: %8, Macenta: %41, Sari: %55"},
    {"ip": "192.168.10.70", "hostname": "CAM-GIRIS", "mac": "BC:AD:28:70:70:70",
     "uretici": "Hangzhou Hikvision Digital Technology", "portlar": "80/HTTP, 554/RTSP, 8000",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.71", "hostname": "-", "mac": "3C:EF:8C:71:71:71",
     "uretici": "Zhejiang Dahua Technology", "portlar": "80/HTTP, 554/RTSP, 37777",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.80", "hostname": "NVR-01", "mac": "BC:AD:28:80:80:80",
     "uretici": "Hangzhou Hikvision Digital Technology", "portlar": "80/HTTP, 554/RTSP, 8000",
     "snmp": "-", "toner": "-"},
    {"ip": "192.168.10.104", "hostname": "-", "mac": "DA:A1:19:5C:3E:77",
     "uretici": "-", "portlar": "-", "snmp": "-", "toner": "-"},
]

# Yalnizca gecmiste gorulen / sonradan gelen cihazlar
ESKI_YAZICI = {"ip": "192.168.10.52", "hostname": "PRN-DEPO", "mac": "00:80:77:52:52:52",
               "uretici": "Brother Industries", "portlar": "80/HTTP, 9100/JetDirect",
               "snmp": "Brother HL-L5100DN", "toner": "Siyah: %35"}
MISAFIR = {"ip": "192.168.10.120", "hostname": "LAPTOP-MISAFIR", "mac": "F4:A4:75:12:01:20",
           "uretici": "Intel Corporate", "portlar": "445/SMB",
           "snmp": "-", "toner": "-"}


def _gun_cihazlari(gun):
    """14 gunluk senaryonun gun'uncu gunundeki cihaz listesi (0 = en eski gun)."""
    cihazlar = []
    for c in DEMO_CIHAZLAR:
        c = dict(c)
        # Dizustu 7. gunde DHCP'den yeni IP aliyor
        if c["hostname"] == "LAPTOP-IT02" and gun >= 7:
            c["ip"] = "192.168.10.35"
        # Dahua kamera 9. gun erisilemiyor
        if c["mac"] == "3C:EF:8C:71:71:71" and gun == 9:
            continue
        # Telefon sadece bazi gunler bagli
        if c["mac"] == "DA:A1:19:5C:3E:77" and gun % 3 != 0 and gun != 13:
            continue
        cihazlar.append(c)
    # Eski depo yazicisi ilk 5 gun var, sonra agdan cikiyor
    if gun < 5:
        cihazlar.append(dict(ESKI_YAZICI))
    # Misafir dizustu son 3 gunde geliyor
    if gun >= 11:
        cihazlar.append(dict(MISAFIR))
    return cihazlar


def demo_veritabani(yol="demo.db", gun_sayisi=14):
    """Her gun 20:00'de bir tarama yapilmis gibi ornek gecmis olusturur."""
    if os.path.exists(yol):
        os.remove(yol)
    bugun = datetime.now().replace(hour=20, minute=0, second=0, microsecond=0)
    if bugun > datetime.now():
        bugun -= timedelta(days=1)
    for gun in range(gun_sayisi):
        zaman = bugun - timedelta(days=gun_sayisi - 1 - gun)
        kaydet(_gun_cihazlari(gun), DEMO_AG, f"demo_{zaman:%Y%m%d_%H%M}.xlsx", zaman, yol)
    return yol


# Bilinen cihaz listesi: telefon ve misafir dizustu bilerek listede yok (tanimsiz gorunsunler)
DEMO_KAYITLAR = [
    ("00:1B:54:10:00:01", "Ana router", "BT", "Sistem odasi"),
    ("00:1B:54:10:00:02", "Kat 1 switch", "BT", "Kat 1 dolap"),
    ("00:0C:29:A1:B2:10", "Etki alani denetleyicisi", "BT", "Sanal sunucu"),
    ("00:0C:29:A1:B2:11", "Dosya sunucusu", "BT", "Sanal sunucu"),
    ("B0:7B:25:3C:11:21", "Muhasebe masaustu", "Muhasebe", "Kat 2"),
    ("54:E1:AD:7F:22:22", "BT dizustu", "BT", "Kat 1"),
    ("3C:52:82:19:23:23", "Uretim masaustu", "Uretim", "Atolye"),
    ("A0:D3:C1:50:50:50", "Muhasebe yazicisi", "Muhasebe", "Kat 2"),
    ("00:17:C8:51:51:51", "Uretim yazicisi", "Uretim", "Atolye"),
    ("00:80:77:52:52:52", "Depo yazicisi", "Depo", "Depo"),
    ("BC:AD:28:70:70:70", "Giris kamerasi", "Guvenlik", "Ana giris"),
    ("3C:EF:8C:71:71:71", "Otopark kamerasi", "Guvenlik", "Otopark"),
    ("BC:AD:28:80:80:80", "Kayit cihazi (NVR)", "Guvenlik", "Sistem odasi"),
]


def demo_liste(yol="demo_bilinen_cihazlar.csv"):
    with open(yol, "w", encoding="utf-8-sig", newline="") as f:
        yazici = csv.writer(f, delimiter=";")
        yazici.writerow(["kimlik", "ad", "sahip", "konum", "not"])
        for kimlik, ad, sahip, konum in DEMO_KAYITLAR:
            yazici.writerow([kimlik, ad, sahip, konum, ""])
    return yol


if __name__ == "__main__":
    yol = html_yaz(DEMO_CIHAZLAR, klasor="raporlar", on_ek="demo",
                   ag=f"{DEMO_AG} (DEMO VERI)", toner_esigi=20)
    print(f"Demo rapor yazildi     : {yol}")
    db = demo_veritabani()
    print(f"Demo veritabani yazildi: {db} (14 gunluk ornek gecmis)")
    print(f"Demo cihaz listesi     : {demo_liste()}")
    print()
    print("Raporu acmak icin : start " + yol.replace("/", "\\"))
    print("Paneli acmak icin : python panel.py --db demo.db --kayit demo_bilinen_cihazlar.csv")