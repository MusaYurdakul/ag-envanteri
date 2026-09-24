"""
html_rapor.py — Tarama sonucunu tarayicida acilan tek dosyalik HTML rapora yazar.

Harici kutuphane veya internet baglantisi gerektirmez. Rapor icinde:
  - ozet kartlari (cihaz sayisi, acik portlu cihaz, dusuk toner)
  - canli arama kutusu
  - basliga tiklayarak siralama (IP adresleri sayisal siralanir)
  - esik altindaki toner degerleri kirmizi vurgulu
  - tahmini cihaz tipi (uzerine gelince gerekcesi gorunur)
"""

import html
import os
import re
from datetime import datetime

from cihaz_tipi import tip_tahmin


SUTUNLAR = [
    ("ip", "IP Adresi"),
    ("tip", "Tip"),
    ("hostname", "Hostname"),
    ("mac", "MAC Adresi"),
    ("uretici", "Uretici"),
    ("portlar", "Acik Portlar"),
    ("snmp", "SNMP"),
    ("toner", "Toner"),
]

TONER_DESENI = re.compile(r"([^,:]+):\s*%(\d+)")


def _kacis(deger):
    """Degeri HTML icin guvenli metne cevirir."""
    if deger is None or deger == "":
        return "-"
    return html.escape(str(deger))


def _ip_sirasi(ip):
    """192.168.1.5 -> '192168001005' gibi, sayisal siralama icin anahtar."""
    try:
        return "".join(f"{int(parca):03d}" for parca in str(ip).split("."))
    except ValueError:
        return str(ip)


def _portlar_hucresi(portlar):
    metin = str(portlar or "-").strip()
    if metin in ("-", "", "[]"):
        return '<span class="bos">-</span>'
    parcalar = [p.strip(" []'\"") for p in metin.split(",") if p.strip(" []'\"")]
    return "".join(f'<span class="etiket">{_kacis(p)}</span>' for p in parcalar)


def _toner_hucresi(toner, esik):
    metin = str(toner or "-").strip()
    if metin in ("-", ""):
        return '<span class="bos">-</span>', False

    dusuk_var = False
    parcalar = []
    for eslesme in TONER_DESENI.finditer(metin):
        ad = eslesme.group(1).strip()
        yuzde = int(eslesme.group(2))
        sinif = "toner dusuk" if yuzde < esik else "toner"
        dusuk_var = dusuk_var or yuzde < esik
        parcalar.append(f'<span class="{sinif}">{_kacis(ad)} %{yuzde}</span>')

    if not parcalar:
        return _kacis(metin), False
    return "".join(parcalar), dusuk_var


def html_yaz(cihazlar, klasor="raporlar", on_ek="envanter", ag="-", toner_esigi=20):
    """Cihaz listesini HTML rapora yazar ve dosya yolunu dondurur."""
    os.makedirs(klasor, exist_ok=True)
    simdi = datetime.now()
    dosya = os.path.join(klasor, f"{on_ek}_{simdi:%Y%m%d_%H%M}.html")

    satirlar = []
    portlu = 0
    dusuk_tonerli = 0

    for cihaz in cihazlar:
        if not cihaz.get("tip"):
            tahmin = tip_tahmin(cihaz)
            cihaz = {**cihaz, "tip": tahmin["tip"],
                     "tip_gerekce": f"{tahmin['guven']} guven: {tahmin['gerekce']}"}

        hucreler = []
        for anahtar, _ in SUTUNLAR:
            deger = cihaz.get(anahtar, "-")

            if anahtar == "ip":
                hucreler.append(
                    f'<td data-sirala="{_ip_sirasi(deger)}" class="ip">{_kacis(deger)}</td>'
                )
            elif anahtar == "tip":
                hucreler.append(
                    f'<td title="{_kacis(cihaz.get("tip_gerekce", ""))}">'
                    f'<span class="tip">{_kacis(deger)}</span></td>'
                )
            elif anahtar == "portlar":
                if str(deger).strip() not in ("-", "", "[]"):
                    portlu += 1
                hucreler.append(f"<td>{_portlar_hucresi(deger)}</td>")
            elif anahtar == "toner":
                icerik, dusuk = _toner_hucresi(deger, toner_esigi)
                if dusuk:
                    dusuk_tonerli += 1
                hucreler.append(f"<td>{icerik}</td>")
            else:
                hucreler.append(f"<td>{_kacis(deger)}</td>")

        satirlar.append("<tr>" + "".join(hucreler) + "</tr>")

    basliklar = "".join(
        f'<th data-sutun="{i}">{baslik}<span class="ok"></span></th>'
        for i, (_, baslik) in enumerate(SUTUNLAR)
    )

    icerik = SABLON.format(
        baslik=f"Ag Envanteri - {_kacis(ag)}",
        ag=_kacis(ag),
        tarih=f"{simdi:%d.%m.%Y %H:%M}",
        toplam=len(cihazlar),
        portlu=portlu,
        dusuk_tonerli=dusuk_tonerli,
        esik=toner_esigi,
        basliklar=basliklar,
        satirlar="\n".join(satirlar) or
            f'<tr><td colspan="{len(SUTUNLAR)}" class="bos">Cihaz bulunamadi</td></tr>',
    )

    with open(dosya, "w", encoding="utf-8") as f:
        f.write(icerik)

    return dosya


SABLON = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{baslik}</title>
<style>
  :root {{
    --zemin: #f5f7fa; --kart: #ffffff; --yazi: #1f2933; --soluk: #6b7785;
    --cizgi: #e1e6ec; --vurgu: #1f5fa8; --vurgu-acik: #e6eef8;
    --kirmizi: #c62828; --kirmizi-acik: #fdecea; --satir: #f9fbfd;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --zemin: #14181d; --kart: #1c2229; --yazi: #e4e8ec; --soluk: #8b96a3;
      --cizgi: #2c343d; --vurgu: #6aa6ec; --vurgu-acik: #1e2d40;
      --kirmizi: #ef6b6b; --kirmizi-acik: #3a1f1f; --satir: #20272f;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 28px; background: var(--zemin); color: var(--yazi);
    font: 14px/1.5 "Segoe UI", system-ui, -apple-system, Arial, sans-serif;
  }}
  .kap {{ max-width: 1200px; margin: 0 auto; }}
  header h1 {{ margin: 0; font-size: 22px; }}
  header p {{ margin: 4px 0 20px; color: var(--soluk); }}
  .kartlar {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px; margin-bottom: 18px; }}
  .kart {{ background: var(--kart); border: 1px solid var(--cizgi); border-radius: 10px;
    padding: 14px 16px; }}
  .kart b {{ display: block; font-size: 26px; line-height: 1.2; }}
  .kart span {{ color: var(--soluk); font-size: 13px; }}
  .kart.uyari b {{ color: var(--kirmizi); }}
  .arac {{ display: flex; gap: 12px; align-items: center; margin-bottom: 10px; flex-wrap: wrap; }}
  #ara {{ flex: 1; min-width: 220px; padding: 9px 12px; font: inherit; color: var(--yazi);
    background: var(--kart); border: 1px solid var(--cizgi); border-radius: 8px; }}
  #ara:focus {{ outline: 2px solid var(--vurgu); outline-offset: -1px; }}
  #sayac {{ color: var(--soluk); font-size: 13px; }}
  .tablo-kap {{ overflow-x: auto; background: var(--kart); border: 1px solid var(--cizgi);
    border-radius: 10px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th, td {{ padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--cizgi);
    white-space: nowrap; }}
  th {{ position: sticky; top: 0; background: var(--vurgu); color: #fff; cursor: pointer;
    user-select: none; font-weight: 600; }}
  th .ok::after {{ content: ""; margin-left: 6px; opacity: .8; }}
  th.artan .ok::after {{ content: "\\25B2"; }}
  th.azalan .ok::after {{ content: "\\25BC"; }}
  tbody tr:nth-child(even) {{ background: var(--satir); }}
  tbody tr:hover {{ background: var(--vurgu-acik); }}
  td.ip {{ font-family: Consolas, "Courier New", monospace; }}
  .etiket {{ display: inline-block; padding: 1px 7px; margin: 1px 4px 1px 0; border-radius: 10px;
    background: var(--vurgu-acik); color: var(--vurgu); font-size: 12px; }}
  .toner {{ display: inline-block; margin-right: 8px; }}
  .toner.dusuk {{ color: var(--kirmizi); background: var(--kirmizi-acik); padding: 0 6px;
    border-radius: 6px; font-weight: 600; }}
  .tip {{ font-weight: 600; cursor: help; border-bottom: 1px dotted var(--soluk); }}
  .bos {{ color: var(--soluk); }}
  footer {{ margin-top: 16px; color: var(--soluk); font-size: 12px; }}
  @media print {{
    body {{ background: #fff; padding: 0; }} .arac {{ display: none; }}
    th {{ background: #1f5fa8 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<div class="kap">
  <header>
    <h1>Ag Envanteri Raporu</h1>
    <p>Taranan ag: <b>{ag}</b> &middot; Olusturulma: {tarih}</p>
  </header>

  <div class="kartlar">
    <div class="kart"><b>{toplam}</b><span>Bulunan cihaz</span></div>
    <div class="kart"><b>{portlu}</b><span>Acik portu olan cihaz</span></div>
    <div class="kart uyari"><b>{dusuk_tonerli}</b><span>Toneri %{esik} altinda</span></div>
  </div>

  <div class="arac">
    <input id="ara" type="search" placeholder="IP, hostname, MAC, uretici, port ara..." autofocus>
    <span id="sayac"></span>
  </div>

  <div class="tablo-kap">
    <table id="tablo">
      <thead><tr>{basliklar}</tr></thead>
      <tbody>
{satirlar}
      </tbody>
    </table>
  </div>

  <footer>Bu rapor Ag Envanteri araci tarafindan otomatik olusturulmustur.</footer>
</div>

<script>
(function () {{
  var tablo = document.getElementById("tablo");
  var govde = tablo.tBodies[0];
  var satirlar = Array.prototype.slice.call(govde.rows);
  var ara = document.getElementById("ara");
  var sayac = document.getElementById("sayac");

  function sayaciGuncelle() {{
    var gorunen = satirlar.filter(function (s) {{ return s.style.display !== "none"; }}).length;
    sayac.textContent = gorunen + " / " + satirlar.length + " cihaz";
  }}

  ara.addEventListener("input", function () {{
    var aranan = ara.value.trim().toLowerCase();
    satirlar.forEach(function (s) {{
      s.style.display = s.textContent.toLowerCase().indexOf(aranan) === -1 ? "none" : "";
    }});
    sayaciGuncelle();
  }});

  var basliklar = tablo.tHead.rows[0].cells;
  Array.prototype.forEach.call(basliklar, function (th, i) {{
    th.addEventListener("click", function () {{
      var artan = !th.classList.contains("artan");
      Array.prototype.forEach.call(basliklar, function (b) {{ b.classList.remove("artan", "azalan"); }});
      th.classList.add(artan ? "artan" : "azalan");

      satirlar.sort(function (a, b) {{
        var x = a.cells[i].getAttribute("data-sirala") || a.cells[i].textContent.trim().toLowerCase();
        var y = b.cells[i].getAttribute("data-sirala") || b.cells[i].textContent.trim().toLowerCase();
        if (x === y) return 0;
        return (x < y ? -1 : 1) * (artan ? 1 : -1);
      }});
      satirlar.forEach(function (s) {{ govde.appendChild(s); }});
    }});
  }});

  sayaciGuncelle();
}})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    ornek = [
        {"ip": "192.168.56.10", "hostname": "DC01.yurdakul.local", "mac": "08:00:27:AA:BB:CC",
         "uretici": "PCS Systemtechnik (VirtualBox)", "portlar": "445 (SMB), 3389 (RDP)",
         "snmp": "-", "toner": "-"},
        {"ip": "192.168.56.2", "hostname": "-", "mac": "08:00:27:11:22:33",
         "uretici": "PCS Systemtechnik (VirtualBox)", "portlar": "-", "snmp": "-", "toner": "-"},
        {"ip": "192.168.56.50", "hostname": "YAZICI-ORNEK", "mac": "00:11:22:33:44:55",
         "uretici": "HP", "portlar": "80 (HTTP), 443 (HTTPS)", "snmp": "HP LaserJet (ornek)",
         "toner": "Siyah: %8, Mavi: %64"},
    ]
    yol = html_yaz(ornek, klasor="raporlar", on_ek="ornek", ag="192.168.56.0/24 (ORNEK VERI)")
    print(f"Ornek rapor yazildi: {yol}")