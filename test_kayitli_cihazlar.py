"""
test_kayitli_cihazlar.py — kayitli_cihazlar.py senaryo testleri. Ag taramasi yapmaz.

Calistirma:
    python test_kayitli_cihazlar.py
"""

import os
import tempfile
from datetime import datetime

import kayitli_cihazlar as kc
import veritabani as vt


def kontrol(ad, kosul):
    print(f"  [{'OK ' if kosul else 'HATA'}] {ad}")
    return kosul


def yaz(yol, metin, kodlama="utf-8-sig"):
    with open(yol, "w", encoding=kodlama, newline="") as f:
        f.write(metin)


def main():
    sonuclar = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as klasor:
        liste = os.path.join(klasor, "bilinen.csv")

        # 1) Dosya yoksa ozellik kapali
        k = kc.oku(liste)
        sonuclar.append(kontrol("1) Liste dosyasi yoksa ozellik kapali, kimse tanimsiz degil",
                                k is None and not kc.tanimsiz_mi(k, "08:00:27:AA:AA:01", "10.0.0.5")))

        # 2) Turkce Excel bicimi: ; ayiraci, BOM, Turkce karakter, farkli MAC yazimi
        yaz(liste, "kimlik;ad;sahip;konum;not\n"
                   "08-00-27-aa-aa-01;Muhasebe yazıcısı;Şükrü Öztürk;Kat 2;\n"
                   "192.168.1.1;Modem;BT;Sunucu odası;ISP cihazı\n"
                   ";Boş satır;;;\n"
                   "gecersiz;Hatalı;;;\n")
        k = kc.oku(liste)
        kayit = kc.bul(k, "08:00:27:AA:AA:01", "10.0.0.99")
        sonuclar.append(kontrol("2) ; ayiracli, BOM'lu dosya okundu, Turkce karakter korundu",
                                kayit is not None and kayit["ad"] == "Muhasebe yazıcısı"
                                and kayit["sahip"] == "Şükrü Öztürk"))
        sonuclar.append(kontrol("3) Bos ve gecersiz kimlikli satirlar atlandi",
                                len(k) == 2))

        # 4) MAC'i olan ama listede IP ile kayitli cihaz eslesir
        sonuclar.append(kontrol("4) Listede IP ile kayitli cihaz, MAC'i olsa da eslesti",
                                kc.bul(k, "AA:BB:CC:00:00:01", "192.168.1.1")["ad"] == "Modem"))

        # 5) Listede olmayan cihaz tanimsiz
        sonuclar.append(kontrol("5) Listede olmayan cihaz tanimsiz",
                                kc.tanimsiz_mi(k, "DA:A1:19:5C:3E:77", "192.168.1.44")))

        # 6) Virgul ayiracli dosya da okunur
        yaz(liste, "kimlik,ad\n08:00:27:BB:BB:02,Kamera\n", kodlama="utf-8")
        k = kc.oku(liste)
        sonuclar.append(kontrol("6) Virgul ayiracli, BOM'suz dosya da okundu",
                                kc.bul(k, "08:00:27:BB:BB:02")["ad"] == "Kamera"))

        # 7-9) --olustur: veritabanindan liste uretme ve guncelleme
        db = os.path.join(klasor, "test.db")
        liste2 = os.path.join(klasor, "liste2.csv")
        vt.kaydet([
            {"ip": "192.168.1.5", "mac": "08:00:27:AA:AA:01", "hostname": "PC-A", "uretici": "Dell"},
            {"ip": "127.0.0.1", "mac": "-", "hostname": "LAPTOP", "uretici": "-"},
        ], "test", "r1", datetime(2026, 9, 1, 20, 0), db)

        eklenen, toplam = kc.olustur(db, liste2)
        k = kc.oku(liste2)
        sonuclar.append(kontrol("7) Olusturulan listede tum cihazlar var (MAC'li ve MAC'siz)",
                                eklenen == 2 and toplam == 2
                                and not kc.tanimsiz_mi(k, "08:00:27:AA:AA:01", "192.168.1.5")
                                and not kc.tanimsiz_mi(k, None, "127.0.0.1")))

        # Kullanici Excel'de ad yaziyor
        with open(liste2, encoding="utf-8-sig") as f:
            metin = f.read()
        yaz(liste2, metin.replace("08:00:27:AA:AA:01;;", "08:00:27:AA:AA:01;Ahmet'in bilgisayarı;"))

        # Yeni cihaz geliyor, liste tekrar olusturuluyor
        vt.kaydet([
            {"ip": "192.168.1.5", "mac": "08:00:27:AA:AA:01", "hostname": "PC-A", "uretici": "Dell"},
            {"ip": "192.168.1.99", "mac": "08:00:27:CC:CC:09", "hostname": "MISAFIR", "uretici": "Samsung"},
        ], "test", "r2", datetime(2026, 9, 2, 20, 0), db)
        eklenen, toplam = kc.olustur(db, liste2)
        k = kc.oku(liste2)
        sonuclar.append(kontrol("8) Tekrar calistirinca sadece yeni cihaz eklendi",
                                eklenen == 1 and toplam == 3))
        sonuclar.append(kontrol("9) Kullanicinin yazdigi ad korundu",
                                kc.bul(k, "08:00:27:AA:AA:01")["ad"] == "Ahmet'in bilgisayarı"))

    basarili = sum(sonuclar)
    print(f"\n{basarili}/{len(sonuclar)} senaryo gecti.")
    if basarili != len(sonuclar):
        raise SystemExit(1)


if __name__ == "__main__":
    main()