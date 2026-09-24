import configparser
import os
import sys


VARSAYILAN_DOSYA = "config.ini"


class Ayarlar:
    """config.ini dosyasini okur ve ayarlara erisim saglar."""

    def __init__(self, dosya=VARSAYILAN_DOSYA):
        self.dosya = dosya
        self._cfg = configparser.ConfigParser()

        if not os.path.exists(dosya):
            print(f"[!] Ayar dosyasi bulunamadi: {dosya}")
            sys.exit(1)

        self._cfg.read(dosya, encoding="utf-8")

    # --- tarama ---
    @property
    def varsayilan_ag(self):
        return self._cfg.get("tarama", "varsayilan_ag", fallback="192.168.1.0/24")

    @property
    def is_parcacigi(self):
        return self._cfg.getint("tarama", "is_parcacigi", fallback=50)

    @property
    def ping_zaman_asimi(self):
        return self._cfg.getint("tarama", "ping_zaman_asimi", fallback=500)

    # --- portlar ---
    @property
    def portlar(self):
        if not self._cfg.has_section("portlar"):
            return {}
        return {
            int(anahtar): deger
            for anahtar, deger in self._cfg.items("portlar")
            if anahtar.isdigit()
        }

    # --- snmp ---
    @property
    def snmp_etkin(self):
        return self._cfg.getboolean("snmp", "etkin", fallback=True)

    @property
    def snmp_community(self):
        return self._cfg.get("snmp", "community", fallback="public")

    @property
    def snmp_zaman_asimi(self):
        return self._cfg.getint("snmp", "zaman_asimi", fallback=1)

    @property
    def toner_esigi(self):
        return self._cfg.getint("snmp", "toner_esigi", fallback=20)

    # --- rapor ---
    @property
    def cikti_klasoru(self):
        klasor = self._cfg.get("rapor", "cikti_klasoru", fallback="raporlar")
        os.makedirs(klasor, exist_ok=True)
        return klasor

    @property
    def dosya_on_eki(self):
        return self._cfg.get("rapor", "dosya_on_eki", fallback="envanter")

    # --- eposta ---
    @property
    def eposta_etkin(self):
        return self._cfg.getboolean("eposta", "etkin", fallback=False)

    @property
    def eposta_deneme_modu(self):
        return self._cfg.getboolean("eposta", "deneme_modu", fallback=True)

    @property
    def smtp_sunucu(self):
        return self._cfg.get("eposta", "sunucu", fallback="smtp.gmail.com")

    @property
    def smtp_port(self):
        return self._cfg.getint("eposta", "port", fallback=587)

    @property
    def eposta_gonderen(self):
        return self._cfg.get("eposta", "gonderen", fallback="")

    @property
    def eposta_alicilar(self):
        ham = self._cfg.get("eposta", "alicilar", fallback="")
        return [a.strip() for a in ham.split(",") if a.strip()]


if __name__ == "__main__":
    ayar = Ayarlar()
    print(f"Varsayilan ag    : {ayar.varsayilan_ag}")
    print(f"Portlar          : {ayar.portlar}")
    print(f"SNMP etkin       : {ayar.snmp_etkin}")
    print(f"Toner esigi      : %{ayar.toner_esigi}")
    print(f"Cikti klasoru    : {ayar.cikti_klasoru}")
    print(f"E-posta etkin    : {ayar.eposta_etkin}")
    print(f"Deneme modu      : {ayar.eposta_deneme_modu}")
    print(f"Alicilar         : {ayar.eposta_alicilar}")