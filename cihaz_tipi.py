"""
cihaz_tipi.py — Tarama verisine bakarak cihaz tipi tahmini yapar.

Kural tabanli puanlama: her ipucu (acik port, MAC ureticisi, hostname,
SNMP aciklamasi, toner verisi) bir tipe puan ekler. En yuksek puanli tip
secilir; guven seviyesi ve hangi kurallarin tetiklendigi de dondurulur.

Kullanim:
    from cihaz_tipi import tip_tahmin
    sonuc = tip_tahmin(cihaz)   # {"tip": "Yazici", "guven": "yuksek", "gerekce": "..."}
"""

import re

from karsilastir import mac_normallestir


# Esitlik durumunda soldaki (daha belirgin) tip tercih edilir.
ONCELIK = ["Yazici", "Kamera", "Sunucu", "Ag cihazi", "Bilgisayar", "IoT", "Mobil"]

# (anahtar kelimeler, tip, puan) — uretici adi kucuk harfe cevrilip aranir
URETICI_KURALLARI = [
    (("kyocera", "brother", "canon", "xerox", "ricoh", "lexmark", "epson",
      "konica", "oki data", "toshiba tec", "zebra"), "Yazici", 3),
    (("hikvision", "dahua", "axis communications", "hanwha", "uniview",
      "bosch security", "vivotek"), "Kamera", 3),
    (("cisco", "juniper", "aruba", "mikrotik", "routerboard", "ubiquiti",
      "tp-link", "zyxel", "fortinet", "d-link", "netgear", "ruckus",
      "arcadyan", "sagemcom", "technicolor", "zte", "sophos",
      "extreme networks", "allied telesis"), "Ag cihazi", 3),
    (("espressif", "tuya", "shelly", "sonoff", "raspberry",
      "amazon technologies"), "IoT", 2),
    (("dell", "lenovo", "lcfc", "asustek", "acer", "micro-star", "gigabyte",
      "intel corporate", "realtek", "liteon", "azurewave", "hon hai",
      "wistron", "quanta", "compal", "microsoft", "hewlett packard", "hp inc"),
     "Bilgisayar", 1),
    (("hewlett packard", "hp inc"), "Yazici", 1),
    (("apple", "samsung", "xiaomi", "oppo", "vivo mobile", "oneplus",
      "realme", "motorola"), "Mobil", 1),
    (("huawei",), "Ag cihazi", 1),
    (("huawei",), "Mobil", 1),
]

SANAL_URETICILER = ("pcs systemtechnik", "vmware", "qemu", "xensource", "parallels")
SANAL_MAC_ONEKLERI = ("00:15:5D",)  # Hyper-V

# (port, tip, puan, aciklama)
PORT_KURALLARI = [
    (9100, "Yazici", 3, "9100/JetDirect"),
    (631,  "Yazici", 3, "631/IPP"),
    (515,  "Yazici", 3, "515/LPD"),
    (37777, "Kamera", 3, "37777/Dahua"),
    (554,  "Kamera", 2, "554/RTSP"),
    (8000, "Kamera", 1, "8000/Hikvision"),
    (88,   "Sunucu", 3, "88/Kerberos (etki alani denetleyicisi)"),
    (389,  "Sunucu", 2, "389/LDAP"),
    (636,  "Sunucu", 2, "636/LDAPS"),
    (1433, "Sunucu", 2, "1433/MSSQL"),
    (3306, "Sunucu", 2, "3306/MySQL"),
    (5432, "Sunucu", 2, "5432/PostgreSQL"),
    (53,   "Sunucu", 1, "53/DNS"),
    (53,   "Ag cihazi", 1, "53/DNS"),
    (23,   "Ag cihazi", 2, "23/Telnet"),
    (22,   "Sunucu", 1, "22/SSH"),
    (22,   "Ag cihazi", 1, "22/SSH"),
    (3389, "Bilgisayar", 1, "3389/RDP"),
    (3389, "Sunucu", 1, "3389/RDP"),
    (445,  "Bilgisayar", 1, "445/SMB"),
    (445,  "Sunucu", 1, "445/SMB"),
    (135,  "Bilgisayar", 1, "135/RPC"),
    (139,  "Bilgisayar", 1, "139/NetBIOS"),
]

WEB_PORTLARI = {80, 443, 8080}
BILGISAYAR_PORTLARI = {22, 135, 139, 445, 3389}

# (regex, tip, puan) — hostname buyuk harfe cevrilip aranir
HOSTNAME_KURALLARI = [
    (r"^(DESKTOP|LAPTOP|PC|NB|WS)[-_]", "Bilgisayar", 3),
    (r"(^DC\d|^SRV|SERVER|SUNUCU|^SQL|^ESX|VCENTER|^NAS)", "Sunucu", 3),
    (r"(PRN|PRINTER|YAZICI|MFP|LASERJET|OFFICEJET|ECOSYS)", "Yazici", 3),
    (r"(CAM|KAMERA|NVR|DVR|^IPC)", "Kamera", 3),
    (r"(IPHONE|IPAD|ANDROID|GALAXY|REDMI)", "Mobil", 3),
    (r"(^SW[-_\d]|SWITCH|ROUTER|^AP[-_]|^FW[-_]|^GW[-_]|MODEM)", "Ag cihazi", 3),
]

SNMP_KURALLARI = [
    (("laserjet", "printer", "mfp", "ecosys", "imagerunner", "workcentre",
      "bizhub", "officejet", "jetdirect"), "Yazici", 4),
    (("cisco ios", "routeros", "junos", "procurve", "fortigate", "switch",
      "aruba", "edgeos"), "Ag cihazi", 4),
]


def _metin(deger):
    if deger is None:
        return ""
    metin = str(deger).strip()
    return "" if metin == "-" else metin


def _portlar(deger):
    return {int(p) for p in re.findall(r"\b(\d{1,5})\b", _metin(deger))}


def tip_tahmin(cihaz):
    """Cihaz sozlugunden tip tahmini yapar.

    Beklenen anahtarlar (eksik olabilir): ip, hostname, mac, uretici, portlar, snmp, toner
    Donus: {"tip": str, "guven": "yuksek" | "orta" | "dusuk", "gerekce": str}
    """
    ip = _metin(cihaz.get("ip"))
    if ip.startswith("127."):
        return {"tip": "Yerel makine", "guven": "yuksek", "gerekce": "yerel dongu adresi"}

    hostname = _metin(cihaz.get("hostname")).upper()
    uretici = _metin(cihaz.get("uretici")).lower()
    snmp = _metin(cihaz.get("snmp")).lower()
    toner = _metin(cihaz.get("toner"))
    mac = mac_normallestir(cihaz.get("mac"))
    portlar = _portlar(cihaz.get("portlar"))

    puan = {tip: 0 for tip in ONCELIK}
    neden = {tip: [] for tip in ONCELIK}

    def ekle(tip, deger, aciklama):
        puan[tip] += deger
        neden[tip].append(aciklama)

    # Toner verisi varsa neredeyse kesin yazicidir
    if toner:
        ekle("Yazici", 5, "toner verisi var")

    for kelimeler, tip, deger in SNMP_KURALLARI:
        if any(k in snmp for k in kelimeler):
            ekle(tip, deger, "SNMP aciklamasi")

    for kelimeler, tip, deger in URETICI_KURALLARI:
        if any(k in uretici for k in kelimeler):
            ekle(tip, deger, f"uretici: {cihaz.get('uretici')}")

    for port, tip, deger, aciklama in PORT_KURALLARI:
        if port in portlar:
            ekle(tip, deger, aciklama)

    # Sadece web paneli acik, bilgisayar portu yok -> gomulu cihaz
    if portlar & WEB_PORTLARI and not portlar & BILGISAYAR_PORTLARI:
        ekle("Ag cihazi", 1, "yalnizca web paneli")
        ekle("Kamera", 1, "yalnizca web paneli")

    for desen, tip, deger in HOSTNAME_KURALLARI:
        if hostname and re.search(desen, hostname):
            ekle(tip, deger, f"hostname: {cihaz.get('hostname')}")

    # Gateway adresleri genelde modem/router
    if ip.endswith(".1") or ip.endswith(".254"):
        ekle("Ag cihazi", 1, "gateway adresi")

    # Rastgele (yerel yonetimli) MAC + acik port yok -> buyuk ihtimalle telefon
    if mac and int(mac[:2], 16) & 0x02 and not portlar:
        ekle("Mobil", 2, "rastgele MAC adresi")

    sanal = (any(k in uretici for k in SANAL_URETICILER)
             or (mac is not None and mac.startswith(SANAL_MAC_ONEKLERI)))

    sirali = sorted(ONCELIK, key=lambda t: (-puan[t], ONCELIK.index(t)))
    en_iyi, ikinci = sirali[0], sirali[1]

    if puan[en_iyi] == 0:
        if sanal:
            return {"tip": "Sanal makine", "guven": "orta",
                    "gerekce": f"uretici: {cihaz.get('uretici')}"}
        return {"tip": "Bilinmiyor", "guven": "dusuk", "gerekce": "yeterli ipucu yok"}

    fark = puan[en_iyi] - puan[ikinci]
    if puan[en_iyi] >= 4 and fark >= 2:
        guven = "yuksek"
    elif puan[en_iyi] >= 2 and fark >= 1:
        guven = "orta"
    else:
        guven = "dusuk"

    tip = f"{en_iyi} (sanal)" if sanal else en_iyi
    gerekce = ", ".join(dict.fromkeys(neden[en_iyi]))  # tekrarlari at, sirayi koru
    if sanal:
        gerekce += ", sanal makine ureticisi"

    return {"tip": tip, "guven": guven, "gerekce": gerekce}


if __name__ == "__main__":
    ornekler = [
        {"ip": "192.168.56.1", "hostname": "LAPTOP-ORNEK01", "portlar": "445/SMB"},
        {"ip": "192.168.56.10", "hostname": "DC01.yurdakul.local", "mac": "08:00:27:AA:BB:CC",
         "uretici": "PCS Systemtechnik GmbH", "portlar": "88/Kerberos, 389/LDAP, 445/SMB"},
        {"ip": "192.168.1.1", "uretici": "Arcadyan Corporation", "portlar": "80/HTTP, 443/HTTPS"},
    ]
    for c in ornekler:
        s = tip_tahmin(c)
        print(f"{c['ip']:<16} {s['tip']:<20} {s['guven']:<7} {s['gerekce']}")