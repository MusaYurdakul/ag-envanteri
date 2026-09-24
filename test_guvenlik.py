"""
test_guvenlik.py — guvenlik.py senaryo testleri. Ag taramasi yapmaz.

Sirkette ve evde olma durumlarini sahte yerel IP'lerle canlandirir.

Calistirma:
    python test_guvenlik.py
"""

import ipaddress

from guvenlik import tarama_izinli_mi


def ipler(*adresler):
    return {ipaddress.ip_address(a) for a in adresler}


SIRKET_IP = ipler("127.0.0.1", "10.20.30.4", "192.168.56.1")
EV_IP = ipler("127.0.0.1", "192.168.1.34", "192.168.56.1")
YASAK = [ipaddress.ip_network("10.20.30.0/24")]

SENARYOLAR = [
    # (aciklama, hedef, yerel IP'ler, izin bekleniyor mu)
    ("Sirkette: VirtualBox sanal agi",           "192.168.56.0/24", SIRKET_IP, True),
    ("Sirkette: yerel dongu",                    "127.0.0.1/32",    SIRKET_IP, True),
    ("Sirkette: ev agi araligi (unutulmus .bat)", "192.168.1.0/24",  SIRKET_IP, False),
    ("Sirkette: sirket agi",                     "10.20.30.0/24", SIRKET_IP, False),
    ("Sirkette: sirket agini kapsayan genis ag", "10.0.0.0/8",      SIRKET_IP, False),
    ("Sirkette: sirketin komsu alt agi",         "10.20.31.0/24", SIRKET_IP, False),
    ("Evde: ev agi",                             "192.168.1.0/24",  EV_IP, True),
    ("Evde: sirket agi araligi",                 "10.20.30.0/24", EV_IP, False),
    ("Gecersiz giris",                           "abc",             SIRKET_IP, False),
]


def main():
    gecen = 0
    for ad, hedef, yerel, beklenen in SENARYOLAR:
        izin, sebep = tarama_izinli_mi(hedef, YASAK, yerel)
        tamam = izin == beklenen
        gecen += tamam
        durum = "IZINLI    " if izin else "ENGELLENDI"
        print(f"  [{'OK ' if tamam else 'HATA'}] {ad:<42} {durum}  {sebep}")

    print(f"\n{gecen}/{len(SENARYOLAR)} senaryo gecti.")
    if gecen != len(SENARYOLAR):
        raise SystemExit(1)


if __name__ == "__main__":
    main()