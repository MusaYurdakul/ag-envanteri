import subprocess
import platform
import ipaddress
from concurrent.futures import ThreadPoolExecutor


def ping(ip):
    """Tek bir IP'ye ping atar, cevap verirse True doner."""
    parametre = "-n" if platform.system().lower() == "windows" else "-c"
    zaman_asimi = "-w" if platform.system().lower() == "windows" else "-W"

    komut = ["ping", parametre, "1", zaman_asimi, "500", str(ip)]

    try:
        sonuc = subprocess.run(
            komut,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        return sonuc.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def aralik_tara(ag, is_parcacigi=50):
    """Verilen ag araligindaki ayakta olan cihazlari dondurur."""
    adresler = list(ipaddress.ip_network(ag, strict=False).hosts())
    aktif = []

    with ThreadPoolExecutor(max_workers=is_parcacigi) as havuz:
        sonuclar = havuz.map(ping, adresler)

        for ip, cevap in zip(adresler, sonuclar):
            if cevap:
                aktif.append(str(ip))
                print(f"  aktif: {ip}")

    return aktif


if __name__ == "__main__":
    ag = "127.0.0.1/32"
    print(f"Taraniyor: {ag}")
    bulunanlar = aralik_tara(ag)
    print(f"\nToplam {len(bulunanlar)} cihaz bulundu.")