from pysnmp.hlapi import (
    getCmd, SnmpEngine, CommunityData, UdpTransportTarget,
    ContextData, ObjectType, ObjectIdentity
)


# Standart OID'ler (RFC 1213 - MIB-II)
OID_SISTEM_ADI = "1.3.6.1.2.1.1.5.0"
OID_SISTEM_ACIKLAMA = "1.3.6.1.2.1.1.1.0"
OID_CALISMA_SURESI = "1.3.6.1.2.1.1.3.0"
OID_KONUM = "1.3.6.1.2.1.1.6.0"

# Yazici OID'leri (RFC 3805 - Printer MIB)
OID_SARF_ACIKLAMA = "1.3.6.1.2.1.43.11.1.1.6.1"
OID_SARF_MAKSIMUM = "1.3.6.1.2.1.43.11.1.1.8.1"
OID_SARF_MEVCUT = "1.3.6.1.2.1.43.11.1.1.9.1"


def snmp_sorgu(ip, oid, community="public", zaman_asimi=1, deneme=0):
    """Tek bir OID icin SNMP sorgusu yapar, deger doner."""
    try:
        motor = getCmd(
            SnmpEngine(),
            CommunityData(community, mpModel=1),
            UdpTransportTarget((ip, 161), timeout=zaman_asimi, retries=deneme),
            ContextData(),
            ObjectType(ObjectIdentity(oid))
        )
        hata_belirtisi, hata_durumu, _, degiskenler = next(motor)

        if hata_belirtisi or hata_durumu:
            return None

        for _, deger in degiskenler:
            return str(deger)
    except Exception:
        return None

    return None


def snmp_acik_mi(ip, community="public"):
    """Cihazin SNMP'ye cevap verip vermedigini kontrol eder."""
    return snmp_sorgu(ip, OID_SISTEM_ADI, community) is not None


def cihaz_kimligi(ip, community="public"):
    """SNMP destekleyen cihazdan temel bilgileri toplar."""
    bilgi = {}

    ad = snmp_sorgu(ip, OID_SISTEM_ADI, community)
    if ad is None:
        return None

    bilgi["snmp_ad"] = ad
    bilgi["snmp_aciklama"] = snmp_sorgu(ip, OID_SISTEM_ACIKLAMA, community) or "-"
    bilgi["snmp_konum"] = snmp_sorgu(ip, OID_KONUM, community) or "-"

    return bilgi


def toner_seviyeleri(ip, community="public", kanal_sayisi=6):
    """Yazicidan sarf malzeme seviyelerini yuzde olarak okur."""
    sonuc = []

    for i in range(1, kanal_sayisi + 1):
        aciklama = snmp_sorgu(ip, f"{OID_SARF_ACIKLAMA}.{i}", community)
        if not aciklama:
            break

        maksimum = snmp_sorgu(ip, f"{OID_SARF_MAKSIMUM}.{i}", community)
        mevcut = snmp_sorgu(ip, f"{OID_SARF_MEVCUT}.{i}", community)

        try:
            maksimum = int(maksimum)
            mevcut = int(mevcut)
        except (TypeError, ValueError):
            continue

        if maksimum > 0 and mevcut >= 0:
            yuzde = round(mevcut / maksimum * 100)
            sonuc.append({"ad": aciklama, "yuzde": yuzde})

    return sonuc


def snmp_ozet(ip, community="public"):
    """Bir cihaz icin SNMP bilgilerini tek satirlik ozet olarak dondurur."""
    kimlik = cihaz_kimligi(ip, community)
    if kimlik is None:
        return {"snmp": "-", "toner": "-"}

    toner = toner_seviyeleri(ip, community)
    if toner:
        toner_metin = ", ".join(f"{t['ad']}: %{t['yuzde']}" for t in toner)
    else:
        toner_metin = "-"

    return {
        "snmp": kimlik["snmp_ad"],
        "toner": toner_metin,
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Kullanim: python snmp_bilgi.py <ip> [community]")
        sys.exit(1)

    ip = sys.argv[1]
    community = sys.argv[2] if len(sys.argv) > 2 else "public"

    print(f"[*] {ip} sorgulaniyor (community: {community})")

    kimlik = cihaz_kimligi(ip, community)
    if kimlik is None:
        print("[!] Cihaz SNMP'ye cevap vermedi.")
        sys.exit(0)

    print(f"    Ad       : {kimlik['snmp_ad']}")
    print(f"    Aciklama : {kimlik['snmp_aciklama']}")
    print(f"    Konum    : {kimlik['snmp_konum']}")

    toner = toner_seviyeleri(ip, community)
    if toner:
        print("    Sarf malzemeler:")
        for t in toner:
            print(f"      {t['ad']}: %{t['yuzde']}")