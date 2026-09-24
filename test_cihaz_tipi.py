"""
test_cihaz_tipi.py — cihaz_tipi.py icin senaryo testleri. Ag taramasi yapmaz.

Calistirma:
    python test_cihaz_tipi.py
"""

from cihaz_tipi import tip_tahmin

SENARYOLAR = [
    ("Toner verisi olan cihaz",
     {"ip": "10.0.0.20", "uretici": "Hewlett Packard", "portlar": "80/HTTP",
      "snmp": "HP LaserJet M404", "toner": "Siyah: %40"},
     "Yazici"),
    ("9100 portu acik cihaz",
     {"ip": "10.0.0.21", "uretici": "Kyocera", "portlar": "80/HTTP, 9100/JetDirect"},
     "Yazici"),
    ("Hikvision + RTSP",
     {"ip": "10.0.0.30", "uretici": "Hangzhou Hikvision Digital Technology",
      "portlar": "80/HTTP, 554/RTSP, 8000"},
     "Kamera"),
    ("Etki alani denetleyicisi (VirtualBox)",
     {"ip": "192.168.56.10", "hostname": "DC01.yurdakul.local", "mac": "08:00:27:AA:BB:CC",
      "uretici": "PCS Systemtechnik GmbH", "portlar": "88, 389, 445, 3389"},
     "Sunucu (sanal)"),
    ("Windows dizustu",
     {"ip": "192.168.56.1", "hostname": "LAPTOP-ORNEK01", "portlar": "445/SMB"},
     "Bilgisayar"),
    ("ISP modemi (gateway)",
     {"ip": "192.168.1.1", "uretici": "Arcadyan Corporation", "portlar": "80/HTTP, 443/HTTPS"},
     "Ag cihazi"),
    ("Cisco switch (SNMP)",
     {"ip": "10.0.0.2", "uretici": "Cisco Systems, Inc", "portlar": "22/SSH, 23/Telnet",
      "snmp": "Cisco IOS Software, C2960"},
     "Ag cihazi"),
    ("Rastgele MAC'li telefon",
     {"ip": "192.168.1.44", "mac": "DA:A1:19:5C:3E:77", "portlar": "-"},
     "Mobil"),
    ("Yerel dongu",
     {"ip": "127.0.0.1", "hostname": "LAPTOP", "portlar": "445/SMB"},
     "Yerel makine"),
    ("Hicbir ipucu yok",
     {"ip": "10.0.0.99", "mac": "-", "uretici": "-", "portlar": "-"},
     "Bilinmiyor"),
]


def main():
    gecen = 0
    for ad, cihaz, beklenen in SENARYOLAR:
        sonuc = tip_tahmin(cihaz)
        tamam = sonuc["tip"] == beklenen
        gecen += tamam
        print(f"  [{'OK ' if tamam else 'HATA'}] {ad:<38} -> {sonuc['tip']:<16} "
              f"({sonuc['guven']}) {sonuc['gerekce']}")
        if not tamam:
            print(f"         beklenen: {beklenen}")

    print(f"\n{gecen}/{len(SENARYOLAR)} senaryo gecti.")
    if gecen != len(SENARYOLAR):
        raise SystemExit(1)


if __name__ == "__main__":
    main()