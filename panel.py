"""
panel.py — Tarama gecmisini gosteren yerel, salt okunur web paneli.

envanter.db'deki verileri tarayicida gosterir: ozet ve grafikler, tum cihazlar,
cihaz bazinda IP ve tarama gecmisi, tarama listesi, IP / MAC / hostname aramasi.

Guvenlik:
  - Yalnizca 127.0.0.1 uzerinde dinler; agdaki baska bilgisayarlar erisemez.
  - Veritabani salt okunur modda acilir; panelden veri degistirilemez.

Calistirma:
    python panel.py                  # http://127.0.0.1:5000 adresini tarayicida acar
    python panel.py --port 8080
    python panel.py --tarayici-acma
"""

import argparse
import ipaddress
import os
import sqlite3
import webbrowser
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, abort, current_app, redirect, render_template, request, url_for
from jinja2 import DictLoader

from cihaz_tipi import tip_tahmin
from karsilastir import mac_normallestir
from veritabani import VARSAYILAN_DB, ZAMAN_BICIMI


# --- veri erisimi ----------------------------------------------------------


def _baglan():
    """Veritabanini salt okunur acar. Dosya yoksa None dondurur."""
    yol = current_app.config["DB_YOLU"]
    if not os.path.exists(yol):
        return None
    uri = Path(yol).resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.row_factory = sqlite3.Row
    return db


def _zaman(metin):
    try:
        return datetime.strptime(metin, ZAMAN_BICIMI)
    except (TypeError, ValueError):
        return None


def _son_tarama_zamani(db):
    satir = db.execute("SELECT MAX(zaman) FROM taramalar").fetchone()
    return satir[0] if satir else None


def cihaz_listesi(db):
    """Tum cihazlari son gozlemleriyle birlikte, tip ve durum bilgisiyle dondurur."""
    son_zaman = _son_tarama_zamani(db)
    simdi = datetime.now()

    satirlar = db.execute(
        """
        SELECT c.*, g.portlar, g.toner
        FROM cihazlar c
        LEFT JOIN gozlemler g ON g.rowid = (
            SELECT g2.rowid FROM gozlemler g2
            JOIN taramalar t2 ON t2.id = g2.tarama_id
            WHERE g2.anahtar = c.anahtar
            ORDER BY t2.zaman DESC LIMIT 1
        )
        ORDER BY c.son_gorulme DESC
        """
    ).fetchall()

    cihazlar = []
    for s in satirlar:
        c = dict(s)
        tahmin = tip_tahmin({
            "ip": c["son_ip"], "hostname": c["son_hostname"], "mac": c["mac"],
            "uretici": c["uretici"], "portlar": c["portlar"], "toner": c["toner"],
        })
        c["tip"] = tahmin["tip"]
        c["tip_gerekce"] = f"{tahmin['guven']} guven: {tahmin['gerekce']}"

        if c["son_gorulme"] == son_zaman:
            c["durum"], c["aktif"] = "Aktif", True
        else:
            son = _zaman(c["son_gorulme"])
            gun = (simdi - son).days if son else None
            c["durum"] = f"{gun} gündür yok" if gun else "Son taramada yok"
            c["aktif"] = False
        cihazlar.append(c)
    return cihazlar


def _grafik(seri, genislik=640, yukseklik=170, bosluk=28):
    """Tarama basina cihaz sayisi icin SVG nokta/cizgi koordinatlari uretir."""
    if not seri:
        return None
    en_cok = max(s["cihaz_sayisi"] or 0 for s in seri) or 1
    adim = (genislik - 2 * bosluk) / max(len(seri) - 1, 1)
    noktalar = []
    for i, s in enumerate(seri):
        x = bosluk + i * adim if len(seri) > 1 else genislik / 2
        y = yukseklik - bosluk - ((s["cihaz_sayisi"] or 0) / en_cok) * (yukseklik - 2 * bosluk)
        noktalar.append({"x": round(x, 1), "y": round(y, 1),
                         "sayi": s["cihaz_sayisi"], "zaman": s["zaman"], "ag": s["ag"]})
    return {
        "genislik": genislik, "yukseklik": yukseklik, "en_cok": en_cok, "bosluk": bosluk,
        "noktalar": noktalar,
        "cizgi": " ".join(f"{n['x']},{n['y']}" for n in noktalar),
    }


# --- uygulama --------------------------------------------------------------


def uygulama_olustur(db_yolu=VARSAYILAN_DB):
    app = Flask(__name__)
    app.config["DB_YOLU"] = db_yolu
    app.jinja_env.loader = DictLoader(SABLONLAR)

    @app.template_filter("tarih")
    def tarih_bicimle(metin):
        z = _zaman(metin)
        return z.strftime("%d.%m.%Y %H:%M") if z else (metin or "-")

    @app.context_processor
    def genel_degiskenler():
        return {"db_adi": os.path.basename(current_app.config["DB_YOLU"])}

    @app.route("/")
    def ozet():
        db = _baglan()
        if db is None:
            return render_template("bos.html", baslik="Veritabanı yok")
        with closing(db):
            t = db.execute(
                "SELECT COUNT(*) AS sayi, MIN(zaman) AS ilk, MAX(zaman) AS son FROM taramalar"
            ).fetchone()
            if not t["sayi"]:
                return render_template("bos.html", baslik="Henüz tarama yok")

            son_tarama = db.execute(
                "SELECT * FROM taramalar ORDER BY zaman DESC, id DESC LIMIT 1"
            ).fetchone()
            seri = list(reversed(db.execute(
                "SELECT zaman, cihaz_sayisi, ag FROM taramalar ORDER BY zaman DESC, id DESC LIMIT 30"
            ).fetchall()))
            cihazlar = cihaz_listesi(db)

        esik = (datetime.now() - timedelta(days=7)).strftime(ZAMAN_BICIMI)
        yeniler = [c for c in cihazlar if c["ilk_gorulme"] >= esik][:10]
        kayiplar = sorted((c for c in cihazlar if c["son_gorulme"] < esik),
                          key=lambda c: c["son_gorulme"])[:10]

        tipler = {}
        for c in cihazlar:
            ana_tip = c["tip"].replace(" (sanal)", "")
            tipler[ana_tip] = tipler.get(ana_tip, 0) + 1
        tip_dagilimi = sorted(tipler.items(), key=lambda x: -x[1])
        en_cok_tip = tip_dagilimi[0][1] if tip_dagilimi else 1

        return render_template(
            "ozet.html", baslik="Özet", t=t, son_tarama=son_tarama,
            toplam_cihaz=len(cihazlar), aktif=sum(c["aktif"] for c in cihazlar),
            grafik=_grafik(seri), yeniler=yeniler, kayiplar=kayiplar,
            tip_dagilimi=tip_dagilimi, en_cok_tip=en_cok_tip,
        )

    @app.route("/cihazlar")
    def cihazlar():
        db = _baglan()
        if db is None:
            return render_template("bos.html", baslik="Veritabanı yok")
        with closing(db):
            liste = cihaz_listesi(db)
        return render_template("cihazlar.html", baslik="Cihazlar", cihazlar=liste)

    @app.route("/cihaz/<path:anahtar>")
    def cihaz(anahtar):
        db = _baglan()
        if db is None:
            abort(404)
        with closing(db):
            c = next((x for x in cihaz_listesi(db) if x["anahtar"] == anahtar), None)
            if c is None:
                abort(404)
            gecmis = db.execute(
                """SELECT t.zaman, t.ag, g.ip, g.hostname, g.portlar, g.toner
                   FROM gozlemler g JOIN taramalar t ON t.id = g.tarama_id
                   WHERE g.anahtar = ? ORDER BY t.zaman DESC""",
                (anahtar,),
            ).fetchall()
            ipler = db.execute(
                """SELECT g.ip, MIN(t.zaman) AS ilk, MAX(t.zaman) AS son, COUNT(*) AS sayi
                   FROM gozlemler g JOIN taramalar t ON t.id = g.tarama_id
                   WHERE g.anahtar = ? GROUP BY g.ip ORDER BY son DESC""",
                (anahtar,),
            ).fetchall()
        return render_template("cihaz.html", baslik=c["son_hostname"] if c["son_hostname"] != "-" else c["son_ip"],
                               c=c, gecmis=gecmis, ipler=ipler)

    @app.route("/taramalar")
    def taramalar():
        db = _baglan()
        if db is None:
            return render_template("bos.html", baslik="Veritabanı yok")
        with closing(db):
            liste = db.execute("SELECT * FROM taramalar ORDER BY zaman DESC, id DESC").fetchall()
        return render_template("taramalar.html", baslik="Taramalar", taramalar=liste)

    @app.route("/ara")
    def ara():
        q = (request.args.get("q") or "").strip()
        if not q:
            return redirect(url_for("cihazlar"))

        mac = mac_normallestir(q)
        if mac:
            return redirect(url_for("cihaz", anahtar=f"MAC:{mac}"))

        db = _baglan()
        if db is None:
            return render_template("bos.html", baslik="Veritabanı yok")
        with closing(db):
            try:
                ipaddress.ip_address(q)
                ip_mi = True
            except ValueError:
                ip_mi = False

            if ip_mi:
                sonuclar = db.execute(
                    """SELECT g.anahtar, c.mac, c.uretici, c.son_hostname,
                              MIN(t.zaman) AS ilk, MAX(t.zaman) AS son, COUNT(*) AS sayi
                       FROM gozlemler g
                       JOIN taramalar t ON t.id = g.tarama_id
                       JOIN cihazlar  c ON c.anahtar = g.anahtar
                       WHERE g.ip = ? GROUP BY g.anahtar ORDER BY son DESC""",
                    (q,),
                ).fetchall()
            else:
                desen = f"%{q}%"
                sonuclar = db.execute(
                    """SELECT anahtar, mac, uretici, son_hostname,
                              ilk_gorulme AS ilk, son_gorulme AS son, gorulme_sayisi AS sayi
                       FROM cihazlar
                       WHERE son_hostname LIKE ? OR uretici LIKE ? OR son_ip LIKE ?
                       ORDER BY son_gorulme DESC""",
                    (desen, desen, desen),
                ).fetchall()
        return render_template("ara.html", baslik=f"Arama: {q}", q=q, ip_mi=ip_mi, sonuclar=sonuclar)

    @app.errorhandler(404)
    def bulunamadi(_):
        return render_template("bos.html", baslik="Bulunamadı", bulunamadi=True), 404

    return app


# --- sablonlar -------------------------------------------------------------

SABLONLAR = {
    "temel.html": """<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ baslik }} · Ağ Envanteri</title>
<style>
  :root {
    --zemin:#f5f7fa; --kart:#fff; --yazi:#1f2933; --soluk:#6b7785; --cizgi:#e1e6ec;
    --vurgu:#1f5fa8; --vurgu-acik:#e6eef8; --yesil:#1a7f37; --yesil-acik:#e6f4ea;
    --kirmizi:#c62828; --kirmizi-acik:#fdecea; --satir:#f9fbfd;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --zemin:#14181d; --kart:#1c2229; --yazi:#e4e8ec; --soluk:#8b96a3; --cizgi:#2c343d;
      --vurgu:#6aa6ec; --vurgu-acik:#1e2d40; --yesil:#4cc26b; --yesil-acik:#17301f;
      --kirmizi:#ef6b6b; --kirmizi-acik:#3a1f1f; --satir:#20272f;
    }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--zemin); color:var(--yazi);
    font:14px/1.5 "Segoe UI", system-ui, -apple-system, Arial, sans-serif; }
  a { color:var(--vurgu); text-decoration:none; } a:hover { text-decoration:underline; }
  .kap { max-width:1200px; margin:0 auto; padding:0 24px; }
  .ust { background:var(--kart); border-bottom:1px solid var(--cizgi); margin-bottom:24px; }
  .ust .kap { display:flex; align-items:center; gap:24px; height:56px; flex-wrap:wrap; }
  .logo { font-weight:700; font-size:16px; color:var(--yazi); }
  nav { display:flex; gap:4px; flex:1; }
  nav a { padding:6px 12px; border-radius:6px; color:var(--soluk); }
  nav a.secili, nav a:hover { background:var(--vurgu-acik); color:var(--vurgu); text-decoration:none; }
  .ust form input { padding:7px 12px; width:240px; font:inherit; color:var(--yazi);
    background:var(--zemin); border:1px solid var(--cizgi); border-radius:6px; }
  h1 { font-size:22px; margin:0 0 4px; } .alt { color:var(--soluk); margin:0 0 20px; }
  h2 { font-size:15px; margin:0 0 12px; }
  .kartlar { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px,1fr)); gap:12px; margin-bottom:16px; }
  .kart { background:var(--kart); border:1px solid var(--cizgi); border-radius:10px; padding:16px; }
  .kart b { display:block; font-size:26px; line-height:1.2; } .kart span { color:var(--soluk); font-size:13px; }
  .izgara { display:grid; grid-template-columns:2fr 1fr; gap:16px; margin-bottom:16px; }
  .izgara-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  @media (max-width:860px) { .izgara, .izgara-2 { grid-template-columns:1fr; } }
  .tablo-kap { overflow-x:auto; background:var(--kart); border:1px solid var(--cizgi); border-radius:10px; }
  table { width:100%; border-collapse:collapse; }
  th, td { padding:9px 12px; text-align:left; border-bottom:1px solid var(--cizgi); white-space:nowrap; }
  th { background:var(--vurgu); color:#fff; font-weight:600; cursor:pointer; user-select:none; }
  tbody tr:nth-child(even) { background:var(--satir); } tbody tr:hover { background:var(--vurgu-acik); }
  .kart table th { background:none; color:var(--soluk); cursor:default; font-weight:600; font-size:12px; }
  .mono { font-family:Consolas, "Courier New", monospace; }
  .rozet { display:inline-block; padding:1px 8px; border-radius:10px; font-size:12px; }
  .rozet.aktif { background:var(--yesil-acik); color:var(--yesil); }
  .rozet.pasif { background:var(--kirmizi-acik); color:var(--kirmizi); }
  .tip { font-weight:600; cursor:help; border-bottom:1px dotted var(--soluk); }
  .soluk { color:var(--soluk); }
  .cubuk { display:flex; align-items:center; gap:8px; margin:6px 0; font-size:13px; }
  .cubuk .ad { width:110px; } .cubuk .dolgu { height:10px; background:var(--vurgu); border-radius:5px; }
  #ara { width:100%; padding:9px 12px; margin-bottom:10px; font:inherit; color:var(--yazi);
    background:var(--kart); border:1px solid var(--cizgi); border-radius:8px; }
  svg text { fill:var(--soluk); font-size:11px; }
  footer { color:var(--soluk); font-size:12px; margin:28px auto; }
</style>
</head>
<body>
<header class="ust"><div class="kap">
  <a class="logo" href="{{ url_for('ozet') }}">Ağ Envanteri</a>
  <nav>
    <a href="{{ url_for('ozet') }}" class="{{ 'secili' if request.endpoint == 'ozet' }}">Özet</a>
    <a href="{{ url_for('cihazlar') }}" class="{{ 'secili' if request.endpoint in ('cihazlar', 'cihaz') }}">Cihazlar</a>
    <a href="{{ url_for('taramalar') }}" class="{{ 'secili' if request.endpoint == 'taramalar' }}">Taramalar</a>
  </nav>
  <form action="{{ url_for('ara') }}"><input name="q" placeholder="IP, MAC veya hostname ara" value="{{ q or '' }}"></form>
</div></header>
<main class="kap">{% block icerik %}{% endblock %}</main>
<footer class="kap">Salt okunur panel · {{ db_adi }} · yalnızca bu bilgisayardan erişilebilir</footer>
<script>
document.querySelectorAll("table.siralanir").forEach(function (tablo) {
  var govde = tablo.tBodies[0], satirlar = Array.prototype.slice.call(govde.rows);
  Array.prototype.forEach.call(tablo.tHead.rows[0].cells, function (th, i) {
    th.addEventListener("click", function () {
      var artan = th.dataset.yon !== "artan"; th.dataset.yon = artan ? "artan" : "azalan";
      satirlar.sort(function (a, b) {
        var x = a.cells[i].dataset.sirala || a.cells[i].textContent.trim().toLowerCase();
        var y = b.cells[i].dataset.sirala || b.cells[i].textContent.trim().toLowerCase();
        return (x < y ? -1 : x > y ? 1 : 0) * (artan ? 1 : -1);
      });
      satirlar.forEach(function (s) { govde.appendChild(s); });
    });
  });
});
var kutu = document.getElementById("ara");
if (kutu) kutu.addEventListener("input", function () {
  var a = kutu.value.trim().toLowerCase();
  document.querySelectorAll("#cihaz-tablosu tbody tr").forEach(function (s) {
    s.style.display = s.textContent.toLowerCase().indexOf(a) === -1 ? "none" : "";
  });
});
</script>
</body>
</html>""",

    "ozet.html": """{% extends "temel.html" %}{% block icerik %}
<h1>Özet</h1>
<p class="alt">Son tarama: {{ son_tarama.zaman|tarih }} · {{ son_tarama.ag }}</p>
<div class="kartlar">
  <div class="kart"><b>{{ toplam_cihaz }}</b><span>Bugüne kadar görülen cihaz</span></div>
  <div class="kart"><b>{{ aktif }}</b><span>Son taramada aktif</span></div>
  <div class="kart"><b>{{ t.sayi }}</b><span>Tarama</span></div>
  <div class="kart"><b>{{ yeniler|length }}</b><span>Son 7 günde yeni cihaz</span></div>
</div>
<div class="izgara">
  <div class="kart">
    <h2>Taramalara göre cihaz sayısı</h2>
    {% if grafik %}
    <svg viewBox="0 0 {{ grafik.genislik }} {{ grafik.yukseklik }}" width="100%" role="img" aria-label="Cihaz sayısı grafiği">
      <line x1="{{ grafik.bosluk }}" y1="{{ grafik.yukseklik - grafik.bosluk }}" x2="{{ grafik.genislik - grafik.bosluk }}" y2="{{ grafik.yukseklik - grafik.bosluk }}" stroke="var(--cizgi)"/>
      <text x="4" y="{{ grafik.bosluk + 4 }}">{{ grafik.en_cok }}</text>
      <text x="4" y="{{ grafik.yukseklik - grafik.bosluk + 4 }}">0</text>
      <polyline points="{{ grafik.cizgi }}" fill="none" stroke="var(--vurgu)" stroke-width="2"/>
      {% for n in grafik.noktalar %}
      <circle cx="{{ n.x }}" cy="{{ n.y }}" r="4" fill="var(--vurgu)"><title>{{ n.zaman|tarih }} · {{ n.ag }} · {{ n.sayi }} cihaz</title></circle>
      {% endfor %}
    </svg>
    <p class="soluk" style="margin:4px 0 0;font-size:12px">Son {{ grafik.noktalar|length }} tarama · noktaların üzerine gelince ayrıntı görünür</p>
    {% endif %}
  </div>
  <div class="kart">
    <h2>Cihaz tipleri</h2>
    {% for tip, sayi in tip_dagilimi %}
    <div class="cubuk"><span class="ad">{{ tip }}</span>
      <span class="dolgu" style="width:{{ (sayi / en_cok_tip * 120)|round|int }}px"></span><span class="soluk">{{ sayi }}</span></div>
    {% endfor %}
  </div>
</div>
<div class="izgara-2">
  <div class="kart"><h2>Son 7 günde ilk kez görülenler</h2>
    {% if yeniler %}<table><thead><tr><th>Cihaz</th><th>Tip</th><th>İlk görülme</th></tr></thead><tbody>
    {% for c in yeniler %}<tr><td><a href="{{ url_for('cihaz', anahtar=c.anahtar) }}">{{ c.son_hostname if c.son_hostname != '-' else c.son_ip }}</a></td>
      <td>{{ c.tip }}</td><td>{{ c.ilk_gorulme|tarih }}</td></tr>{% endfor %}
    </tbody></table>{% else %}<p class="soluk">Yok.</p>{% endif %}
  </div>
  <div class="kart"><h2>7 günden uzun süredir görülmeyenler</h2>
    {% if kayiplar %}<table><thead><tr><th>Cihaz</th><th>Tip</th><th>Son görülme</th></tr></thead><tbody>
    {% for c in kayiplar %}<tr><td><a href="{{ url_for('cihaz', anahtar=c.anahtar) }}">{{ c.son_hostname if c.son_hostname != '-' else c.son_ip }}</a></td>
      <td>{{ c.tip }}</td><td>{{ c.son_gorulme|tarih }}</td></tr>{% endfor %}
    </tbody></table>{% else %}<p class="soluk">Yok.</p>{% endif %}
  </div>
</div>
{% endblock %}""",

    "cihazlar.html": """{% extends "temel.html" %}{% block icerik %}
<h1>Cihazlar</h1>
<p class="alt">Bugüne kadar görülen {{ cihazlar|length }} cihaz · başlığa tıklayarak sırala</p>
<input id="ara" type="search" placeholder="Listede ara: IP, hostname, MAC, üretici, tip...">
<div class="tablo-kap"><table id="cihaz-tablosu" class="siralanir">
<thead><tr><th>Durum</th><th>Son IP</th><th>Tip</th><th>Hostname</th><th>MAC</th><th>Üretici</th><th>İlk görülme</th><th>Son görülme</th><th>Tarama</th></tr></thead>
<tbody>
{% for c in cihazlar %}
<tr>
  <td data-sirala="{{ '0' if c.aktif else '1' }}"><span class="rozet {{ 'aktif' if c.aktif else 'pasif' }}">{{ c.durum }}</span></td>
  <td class="mono"><a href="{{ url_for('cihaz', anahtar=c.anahtar) }}">{{ c.son_ip }}</a></td>
  <td><span class="tip" title="{{ c.tip_gerekce }}">{{ c.tip }}</span></td>
  <td>{{ c.son_hostname }}</td>
  <td class="mono">{{ c.mac or '-' }}</td>
  <td>{{ c.uretici }}</td>
  <td data-sirala="{{ c.ilk_gorulme }}">{{ c.ilk_gorulme|tarih }}</td>
  <td data-sirala="{{ c.son_gorulme }}">{{ c.son_gorulme|tarih }}</td>
  <td data-sirala="{{ '%06d' % c.gorulme_sayisi }}">{{ c.gorulme_sayisi }}</td>
</tr>
{% endfor %}
</tbody></table></div>
{% endblock %}""",

    "cihaz.html": """{% extends "temel.html" %}{% block icerik %}
<p class="alt" style="margin-bottom:6px"><a href="{{ url_for('cihazlar') }}">← Cihazlar</a></p>
<h1>{{ baslik }} <span class="rozet {{ 'aktif' if c.aktif else 'pasif' }}" style="font-size:13px;vertical-align:middle">{{ c.durum }}</span></h1>
<p class="alt"><span class="tip" title="{{ c.tip_gerekce }}">{{ c.tip }}</span> · {{ c.uretici }}</p>
<div class="kartlar">
  <div class="kart"><b class="mono" style="font-size:18px">{{ c.son_ip }}</b><span>Son IP</span></div>
  <div class="kart"><b class="mono" style="font-size:18px">{{ c.mac or '-' }}</b><span>MAC adresi</span></div>
  <div class="kart"><b style="font-size:18px">{{ c.ilk_gorulme|tarih }}</b><span>İlk görülme</span></div>
  <div class="kart"><b style="font-size:18px">{{ c.son_gorulme|tarih }}</b><span>Son görülme · {{ c.gorulme_sayisi }} taramada</span></div>
</div>
<div class="izgara-2" style="margin-bottom:16px">
  <div class="kart"><h2>Kullandığı IP adresleri ({{ ipler|length }})</h2>
    <table><thead><tr><th>IP</th><th>İlk</th><th>Son</th><th>Tarama</th></tr></thead><tbody>
    {% for i in ipler %}<tr><td class="mono"><a href="{{ url_for('ara', q=i.ip) }}">{{ i.ip }}</a></td>
      <td>{{ i.ilk|tarih }}</td><td>{{ i.son|tarih }}</td><td>{{ i.sayi }}</td></tr>{% endfor %}
    </tbody></table>
  </div>
  <div class="kart"><h2>Tip tahmininin gerekçesi</h2><p>{{ c.tip_gerekce }}</p>
    <p class="soluk" style="font-size:12px">Tahmin, son gözlemdeki port, üretici, hostname ve MAC bilgisine dayanır.</p></div>
</div>
<h2>Tarama geçmişi</h2>
<div class="tablo-kap"><table>
<thead><tr><th>Zaman</th><th>Ağ</th><th>IP</th><th>Hostname</th><th>Açık portlar</th><th>Sarf malzeme</th></tr></thead>
<tbody>{% for g in gecmis %}
<tr><td>{{ g.zaman|tarih }}</td><td class="mono">{{ g.ag }}</td><td class="mono">{{ g.ip }}</td>
  <td>{{ g.hostname }}</td><td>{{ g.portlar }}</td><td>{{ g.toner }}</td></tr>
{% endfor %}</tbody></table></div>
{% endblock %}""",

    "taramalar.html": """{% extends "temel.html" %}{% block icerik %}
<h1>Taramalar</h1>
<p class="alt">{{ taramalar|length }} tarama kaydı</p>
<div class="tablo-kap"><table class="siralanir">
<thead><tr><th>#</th><th>Zaman</th><th>Ağ</th><th>Cihaz sayısı</th><th>Rapor dosyası</th></tr></thead>
<tbody>{% for t in taramalar %}
<tr><td data-sirala="{{ '%06d' % t.id }}">{{ t.id }}</td><td data-sirala="{{ t.zaman }}">{{ t.zaman|tarih }}</td>
  <td class="mono">{{ t.ag }}</td><td data-sirala="{{ '%06d' % t.cihaz_sayisi }}">{{ t.cihaz_sayisi }}</td><td>{{ t.rapor }}</td></tr>
{% endfor %}</tbody></table></div>
{% endblock %}""",

    "ara.html": """{% extends "temel.html" %}{% block icerik %}
<h1>{{ 'Bu IP adresini kullanan cihazlar' if ip_mi else 'Arama sonuçları' }}</h1>
<p class="alt mono">{{ q }} · {{ sonuclar|length }} sonuç</p>
{% if sonuclar %}
<div class="tablo-kap"><table>
<thead><tr><th>Cihaz</th><th>MAC</th><th>Üretici</th><th>{{ 'Bu IP ile ilk' if ip_mi else 'İlk görülme' }}</th><th>{{ 'Bu IP ile son' if ip_mi else 'Son görülme' }}</th><th>Tarama</th></tr></thead>
<tbody>{% for s in sonuclar %}
<tr><td><a href="{{ url_for('cihaz', anahtar=s.anahtar) }}">{{ s.son_hostname if s.son_hostname != '-' else s.anahtar }}</a></td>
  <td class="mono">{{ s.mac or '(bilinmiyor)' }}</td><td>{{ s.uretici }}</td>
  <td>{{ s.ilk|tarih }}</td><td>{{ s.son|tarih }}</td><td>{{ s.sayi }}</td></tr>
{% endfor %}</tbody></table></div>
{% else %}<div class="kart"><p class="soluk">Eşleşen kayıt yok.</p></div>{% endif %}
{% endblock %}""",

    "bos.html": """{% extends "temel.html" %}{% block icerik %}
<div class="kart" style="max-width:560px;margin:40px auto;text-align:center">
{% if bulunamadi %}
  <h1>Bulunamadı</h1><p class="soluk">Aradığın sayfa ya da cihaz kaydı yok.</p>
  <p><a href="{{ url_for('ozet') }}">Özete dön</a></p>
{% else %}
  <h1>{{ baslik }}</h1>
  <p class="soluk">Panel, taramaların kaydedildiği <span class="mono">{{ db_adi }}</span> dosyasını okur.
  Önce en az bir tarama yap:</p>
  <p class="mono">python main.py 192.168.1.0/24</p>
{% endif %}
</div>
{% endblock %}""",
}


if __name__ == "__main__":
    ayristirici = argparse.ArgumentParser(description="Ag envanteri web paneli (salt okunur, yerel)")
    ayristirici.add_argument("--db", default=VARSAYILAN_DB, help="Veritabani dosyasi")
    ayristirici.add_argument("--port", type=int, default=5000)
    ayristirici.add_argument("--tarayici-acma", action="store_true", help="Tarayiciyi otomatik acma")
    arg = ayristirici.parse_args()

    adres = f"http://127.0.0.1:{arg.port}"
    print(f"Panel: {adres}   (kapatmak icin Ctrl+C)")
    if not arg.tarayici_acma:
        webbrowser.open(adres)
    uygulama_olustur(arg.db).run(host="127.0.0.1", port=arg.port, debug=False)