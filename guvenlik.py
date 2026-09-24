"""
guvenlik.py — Tarama baslamadan once hedef agin taranmasina izin verilip
verilmedigini kontrol eder.

Iki kural:
  1. Hedef ag, config.ini'deki [guvenlik] yasak_aglar listesiyle cakisiyorsa tarama yapilmaz.
  2. Hedef ag, bu bilgisayarin o an dogrudan bagli oldugu bir ag degilse tarama yapilmaz.
     (Ornek: sirketteyken ev agi araligi verilirse, paketler sirketin gateway'i
     uzerinden sirket aginda dolasacagi icin engellenir.)

Tek basina kontrol:
    python guvenlik.py 192.168.1.0/24
"""

import configparser
import ipaddress
import socket
import sys


def yerel_ipler():
    """Bu bilgisayarin IPv4 adreslerini dondurur (yerel dongu dahil)."""
    ipler = {ipaddress.ip_address("127.0.0.1")}

    try:
        for bilgi in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ipler.add(ipaddress.ip_address(bilgi[4][0]))
    except OSError:
        pass

    # Varsayilan cikis arayuzunun IP'si. UDP connect paket gondermez.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ipler.add(ipaddress.ip_address(s.getsockname()[0]))
    except OSError:
        pass

    return ipler


def yasak_aglari_oku(config_yolu="config.ini"):
    """config.ini -> [guvenlik] yasak_aglar = 10.20.30.0/24, 172.16.0.0/12"""
    config = configparser.ConfigParser()
    config.read(config_yolu, encoding="utf-8")
    metin = config.get("guvenlik", "yasak_aglar", fallback="")

    aglar = []
    for parca in metin.replace(";", ",").split(","):
        parca = parca.strip()
        if not parca:
            continue
        try:
            aglar.append(ipaddress.ip_network(parca, strict=False))
        except ValueError:
            print(f"UYARI: config.ini'de gecersiz yasak ag atlandi: {parca}")
    return aglar


def tarama_izinli_mi(hedef, yasak_aglar=None, yerel=None):
    """(izin_var_mi, aciklama) dondurur."""
    try:
        ag = ipaddress.ip_network(str(hedef).strip(), strict=False)
    except ValueError:
        return False, f"gecersiz ag araligi: {hedef}"

    if yasak_aglar is None:
        yasak_aglar = yasak_aglari_oku()
    for yasak in yasak_aglar:
        if ag.overlaps(yasak):
            return False, f"{ag} yasakli ag {yasak} ile cakisiyor"

    if yerel is None:
        yerel = yerel_ipler()
    if not any(ip in ag for ip in yerel):
        liste = ", ".join(sorted(str(ip) for ip in yerel))
        return False, (f"{ag} bu bilgisayarin bagli oldugu bir ag degil "
                       f"(bu bilgisayarin IP'leri: {liste})")

    return True, f"{ag} yerel ag, tarama izinli"


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Kullanim: python guvenlik.py <ag_araligi>")
        sys.exit(1)
    print("Bu bilgisayarin IP'leri :", ", ".join(sorted(str(i) for i in yerel_ipler())))
    print("Yasakli aglar           :", ", ".join(str(a) for a in yasak_aglari_oku()) or "(yok)")
    izin, sebep = tarama_izinli_mi(sys.argv[1])
    print(f"Sonuc                   : {'IZINLI' if izin else 'ENGELLENDI'} - {sebep}")
    sys.exit(0 if izin else 2)