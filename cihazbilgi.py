import subprocess
import socket
import re
from mac_vendor_lookup import MacLookup


def hostname_bul(ip):
    """IP adresinden ters DNS sorgusu ile isim bulmaya calisir."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except (socket.herror, socket.gaierror):
        return "-"


def mac_tablosu():
    """Sistemin ARP tablosunu okuyup {ip: mac} sozlugu dondurur."""
    tablo = {}
    try:
        cikti = subprocess.run(
            ["arp", "-a"],
            capture_output=True,
            text=True,
            timeout=5
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return tablo

    desen = re.compile(
        r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}"
        r"[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2}[-:][0-9a-fA-F]{2})"
    )

    for satir in cikti.splitlines():
        eslesme = desen.search(satir)
        if eslesme:
            ip, mac = eslesme.groups()
            tablo[ip] = mac.replace("-", ":").lower()

    return tablo


def uretici_bul(mac, arayici):
    """MAC adresinin ilk uc baytindan uretici firmayi cozer."""
    if not mac or mac == "-":
        return "-"
    try:
        return arayici.lookup(mac)
    except Exception:
        return "Bilinmiyor"


def port_kontrol(ip, port, zaman_asimi=0.5):
    """Belirtilen portun acik olup olmadigini kontrol eder."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(zaman_asimi)
        return s.connect_ex((ip, port)) == 0

from ayarlar import Ayarlar

_ayar = Ayarlar()
ILGINC_PORTLAR = _ayar.portlar


def acik_portlar(ip):
    """Cihazda acik olan bilinen portlari listeler."""
    acik = []
    for port, isim in ILGINC_PORTLAR.items():
        if port_kontrol(ip, port):
            acik.append(f"{port}/{isim}")
    return ", ".join(acik) if acik else "-"


if __name__ == "__main__":
    arayici = MacLookup()
    tablo = mac_tablosu()

    print("ARP tablosu:")
    for ip, mac in list(tablo.items())[:5]:
        print(f"  {ip}  {mac}  {uretici_bul(mac, arayici)}")
        