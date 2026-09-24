from bildirim import ozet_olustur

metin = ozet_olustur(
    dusuk_tonerler=[],
    yeni_cihazlar=[],
    kaybolanlar=[],
    degisenler=[{"ip": "192.168.1.23",
                 "farklar": ["IP Adresi: '192.168.1.5' -> '192.168.1.23'"]}],
)
print(metin)