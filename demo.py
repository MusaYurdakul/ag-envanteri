"""
demo.py — README ekran goruntuleri icin ornek rapor uretir.

Hicbir ag taramasi yapmaz. Tamamen uydurma bir ofis agi verisiyle
HTML raporu olusturur; gercek IP, MAC veya hostname icermez.

Calistirma:
    python demo.py
"""

from html_rapor import html_yaz


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


if __name__ == "__main__":
    yol = html_yaz(DEMO_CIHAZLAR, klasor="raporlar", on_ek="demo",
                   ag="192.168.10.0/24 (DEMO VERI)", toner_esigi=20)
    print(f"Demo rapor yazildi: {yol}")
    print("Tarayicida acmak icin:  start " + yol.replace("/", "\\"))