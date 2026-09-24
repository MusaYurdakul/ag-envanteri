"""
test_karsilastir.py — MAC tabanli karsilastirmanin senaryo testleri.

Ag taramasi yapmaz. Gecici klasorde iki sahte Excel raporu olusturur,
karsilastir() fonksiyonunu calistirir ve her senaryonun sonucunu kontrol eder.

Calistirma:
    python test_karsilastir.py
"""

import os
import tempfile

from openpyxl import Workbook

from karsilastir import karsilastir

BASLIKLAR = ["IP Adresi", "Hostname", "MAC Adresi", "Uretici", "Acik Portlar"]


def rapor_yaz(yol, satirlar):
    kitap = Workbook()
    sayfa = kitap.active
    sayfa.append(BASLIKLAR)
    for s in satirlar:
        sayfa.append(s)
    kitap.save(yol)


ESKI = [
    # 1) DHCP ile IP'si degisecek cihaz
    ["192.168.1.5",  "PC-AHMET",  "08-00-27-AA-AA-01", "Dell",   "445/SMB"],
    # 2) Aglardan cikacak cihaz
    ["192.168.1.30", "TEL-ESKI",  "08:00:27:AA:AA:02", "Apple",  "-"],
    # 3) MAC'i hic bilinmeyen cihaz (kendi makine / yerel dongu)
    ["127.0.0.1",    "LAPTOP",    "-",                 "-",      "445/SMB"],
    # 4) Bu taramada MAC'i bos, sonraki taramada dolu gelecek
    ["192.168.1.40", "YAZICI",    "-",                 "-",      "80/HTTP"],
    # 5) Ayni IP, sonraki taramada BASKA bir cihaz alacak
    ["192.168.1.50", "KAMERA-1",  "08:00:27:AA:AA:05", "Hikvision", "80/HTTP"],
    # 6) Proxy ARP: iki farkli IP ayni MAC'i gosteriyor
    ["192.168.1.60", "-",         "08:00:27:AA:AA:06", "Cisco",  "-"],
    ["192.168.1.61", "-",         "08:00:27:AA:AA:06", "Cisco",  "-"],
    # 7) Yazim bicimi degisecek (tire -> iki nokta), gercekte ayni cihaz
    ["192.168.1.70", "SUNUCU",    "08-00-27-aa-aa-07", "HP",     "3389/RDP"],
]

YENI = [
    ["192.168.1.23", "PC-AHMET",  "08:00:27:AA:AA:01", "Dell",   "445/SMB"],
    ["127.0.0.1",    "LAPTOP",    "-",                 "-",      "445/SMB"],
    ["192.168.1.40", "YAZICI",    "08:00:27:AA:AA:04", "HP",     "80/HTTP"],
    ["192.168.1.50", "KAMERA-2",  "08:00:27:BB:BB:05", "Dahua",  "80/HTTP"],
    ["192.168.1.60", "-",         "08:00:27:AA:AA:06", "Cisco",  "-"],
    ["192.168.1.61", "-",         "08:00:27:AA:AA:06", "Cisco",  "-"],
    ["192.168.1.70", "SUNUCU",    "08:00:27:AA:AA:07", "HP",     "3389/RDP"],
    # 8) Tamamen yeni cihaz
    ["192.168.1.99", "MISAFIR",   "08:00:27:CC:CC:09", "Samsung", "-"],
]


def kontrol(ad, kosul):
    print(f"  [{'OK ' if kosul else 'HATA'}] {ad}")
    return kosul


def main():
    with tempfile.TemporaryDirectory() as klasor:
        eski_yol = os.path.join(klasor, "eski.xlsx")
        yeni_yol = os.path.join(klasor, "yeni.xlsx")
        rapor_yaz(eski_yol, ESKI)
        rapor_yaz(yeni_yol, YENI)
        sonuc = karsilastir(eski_yol, yeni_yol)

    yeni_ipler = sorted(c["IP Adresi"] for c in sonuc["yeni"])
    kayip_ipler = sorted(c["IP Adresi"] for c in sonuc["kaybolan"])
    degisen = {d["ip"]: d["farklar"] for d in sonuc["degisen"]}

    print("\nSonuc:")
    print(f"  yeni     : {yeni_ipler}")
    print(f"  kaybolan : {kayip_ipler}")
    print(f"  degisen  : {sorted(degisen)}\n")

    print("Senaryolar:")
    sonuclar = [
        kontrol("1) IP'si degisen cihaz 'degisen' sayildi, yeni/kayip degil",
                "192.168.1.23" in degisen
                and any("IP Adresi" in f for f in degisen["192.168.1.23"])
                and "192.168.1.5" not in kayip_ipler),
        kontrol("2) Agdan cikan cihaz 'kaybolan'",
                "192.168.1.30" in kayip_ipler),
        kontrol("3) MAC'i bilinmeyen cihaz IP ile eslesti, degisiklik yok",
                "127.0.0.1" not in yeni_ipler + kayip_ipler and "127.0.0.1" not in degisen),
        kontrol("4) MAC'i sonradan gelen cihaz 'degisen', yeni/kayip degil",
                "192.168.1.40" in degisen and "192.168.1.40" not in yeni_ipler + kayip_ipler),
        kontrol("5) Ayni IP'ye gelen baska cihaz: eskisi kayip, yenisi yeni",
                yeni_ipler.count("192.168.1.50") == 1 and kayip_ipler.count("192.168.1.50") == 1),
        kontrol("6) Ayni MAC'i paylasan IP'ler karismadi",
                not any(ip.startswith("192.168.1.6") for ip in yeni_ipler + kayip_ipler + list(degisen))),
        kontrol("7) MAC yazim bicimi farki degisiklik sayilmadi",
                "192.168.1.70" not in degisen),
        kontrol("8) Tamamen yeni cihaz 'yeni'",
                "192.168.1.99" in yeni_ipler),
    ]

    basarili = sum(sonuclar)
    print(f"\n{basarili}/{len(sonuclar)} senaryo gecti.")
    if basarili != len(sonuclar):
        raise SystemExit(1)


if __name__ == "__main__":
    main()