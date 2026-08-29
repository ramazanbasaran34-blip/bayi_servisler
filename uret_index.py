#!/usr/bin/env python3
"""index.html üretir — MOTOSİKLET BAYİ VE SERVİS AĞI.

Tek sayfa, üç kaynak:
  1. Veritabanındaki toplanmış kayıtlar (satış / servis / ikisi rolleriyle)
  2. Excel'deki resmi sayfa linkleri — henüz taranmamış markalar için
  3. Her kayıt için markanın kendi sayfasına doğrudan giriş bağlantısı

Kullanım:  python uret_index.py [cikti_yolu]
"""

import base64
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from bayiradar.normalize import ILLER, fold, phone_display

PLAKA = {ad: f"{i+1:02d}" for i, ad in enumerate(ILLER)}
ROL_ADI = {"satis": "Satış", "servis": "Servis", "satis_servis": "Satış + Servis"}


def _logo(yol: str) -> str:
    """Logoyu dosyaya gömer — tek dosya kalsın, internet gerekmesin."""
    p = Path(yol)
    if not p.exists():
        return ""
    return "data:image/png;base64," + p.read_text(encoding="utf-8").strip()


def markalari_oku(yol="markalar.json"):
    return json.load(open(yol, encoding="utf-8"))


def veritabanindan_oku(db_yolu="bayiler.db"):
    if not Path(db_yolu).exists():
        return [], {}
    from bayiradar.store import db, marka_durumu, sorgula
    with db(db_yolu) as con:
        kayitlar = sorgula(con)
        durum = {m["marka"]: m for m in marka_durumu(con)}
    return kayitlar, durum


def uret(cikti="index.html", markalar_json="markalar.json", db_yolu="bayiler.db",
         logo_dizin="logolar"):
    markalar = markalari_oku(markalar_json)
    kayitlar, durum = veritabanindan_oku(db_yolu)

    # Marka → resmi sayfa adresleri (doğrudan giriş sütunu için)
    link = {m["ad"]: m for m in markalar}

    # Kompakt dizi: [marka, ad, il, ilce, adres, tel, durum, rol, giris_url]
    satirlar = []
    for k in kayitlar:
        m = link.get(k["marka"], {})
        giris = (k.get("kaynak_servis") or k.get("kaynak_satis")
                 or k.get("kaynak_url") or m.get("bayi") or m.get("site") or "")
        satirlar.append([
            k["marka"], k["bayi_adi"], k["il"], k["ilce"], k["adres"],
            phone_display(k.get("telefon", "")), k.get("veri_durumu", "Güncel"),
            k.get("rol") or "satis", giris,
        ])

    say = defaultdict(lambda: {"satis": 0, "servis": 0, "ikisi": 0, "toplam": 0})
    for k in kayitlar:
        r = k.get("rol") or "satis"
        s = say[k["marka"]]
        s["toplam"] += 1
        s["ikisi" if r == "satis_servis" else r] += 1

    for m in markalar:
        s = say.get(m["ad"])
        m["sayi"] = s["toplam"] if s else None
        m["rol_sayi"] = (s or {"satis": 0, "servis": 0, "ikisi": 0})
        d = durum.get(m["ad"])
        m["tazelik"] = d["etiket"] if d else ""

    veri = {
        "olusturma": datetime.now().astimezone().isoformat(timespec="minutes"),
        "iller": sorted([{"ad": i, "plaka": PLAKA[i], "slug": fold(i).replace(" ", "")}
                         for i in ILLER], key=lambda x: fold(x["ad"])),
        "markalar": sorted(markalar, key=lambda m: fold(m["ad"])),
        "bayiler": satirlar,
        "rol_adi": ROL_ADI,
    }

    html = (SABLON
            .replace("__VERI__", json.dumps(veri, ensure_ascii=False,
                                            separators=(",", ":")))
            .replace("__LOGO_SOL__", _logo(f"{logo_dizin}/kuralkan.b64"))
            .replace("__LOGO_SAG__", _logo(f"{logo_dizin}/dayanisma.b64")))
    Path(cikti).parent.mkdir(parents=True, exist_ok=True)
    Path(cikti).write_text(html, encoding="utf-8")
    return cikti, len(satirlar), sum(1 for m in markalar if m["sayi"])


SABLON = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motosiklet Bayi ve Servis Ağı</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --zemin:#F4F6FA; --kart:#FFFFFF; --murekkep:#122036; --celik:#5A6B84;
  --hat:#DEE4EE; --hat2:#C3CDDD;
  --satis:#D9480F;   --satis-z:#FFF0E6;   /* turuncu  */
  --servis:#0B7285;  --servis-z:#E3F6F9;  /* turkuaz  */
  --ikisi:#5F3DC4;   --ikisi-z:#EFEAFB;   /* mor      */
  --vurgu:#1864AB;   --vurgu-z:#E7F1FC;   /* mavi     */
  --uyari:#B54708;   --uyari-z:#FFF6E5;
  --mavi:#1B4B9E;
  --golge:0 1px 2px rgba(18,32,54,.05), 0 10px 28px -18px rgba(18,32,54,.35);
  --d:"Familjen Grotesk",system-ui,sans-serif; --m:"DM Mono",ui-monospace,monospace;
}
*{box-sizing:border-box} html,body{margin:0}
body{background:var(--zemin);color:var(--murekkep);font-family:var(--d);
  font-size:14px;line-height:1.45;-webkit-font-smoothing:antialiased}
button,input,select{font:inherit;color:inherit}
a{color:var(--vurgu)}

/* ================= BAŞLIK ================= */
.tepe{background:#fff;border-bottom:3px solid var(--murekkep);padding:14px 22px;
  display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:18px}
.tepe img{display:block;height:42px;width:auto}
.tepe .sag-logo{height:56px;justify-self:end}
.tepe .orta{text-align:center}
.tepe h1{margin:0;font-size:26px;font-weight:700;letter-spacing:-.02em;line-height:1.05}
.tepe .alt{margin:3px 0 0;font-family:var(--m);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--celik)}
@media (max-width:760px){
  .tepe{grid-template-columns:auto 1fr auto;gap:10px;padding:10px 14px}
  .tepe h1{font-size:17px} .tepe img{height:28px} .tepe .sag-logo{height:36px}
  .tepe .alt{font-size:9px;letter-spacing:.1em}
}

/* ================= ŞERİT ================= */
.serit{background:var(--murekkep);color:#DCE5F2;padding:8px 22px;display:flex;
  gap:16px;align-items:center;flex-wrap:wrap;font-family:var(--m);font-size:11.5px;
  position:sticky;top:0;z-index:40}
.serit b{color:#fff;font-weight:500}
.sek{margin-left:auto;display:flex;gap:6px}
.sek button{background:none;border:1px solid #35455E;color:#9DB0CA;border-radius:5px;
  padding:5px 12px;cursor:pointer;font-size:12px;font-family:var(--d)}
.sek button:hover{border-color:#5E7characters}
.sek button:hover{border-color:#5E708C;color:#fff}
.sek button.aktif{background:#fff;border-color:#fff;color:var(--murekkep);font-weight:600}

.sar{max-width:1100px;margin:0 auto;padding:20px 18px 70px}
h2{font-size:17px;font-weight:600;margin:0 0 4px}
.notm{color:var(--celik);font-size:12.5px;margin:0 0 14px}

.ara{width:100%;border:1px solid var(--hat2);background:#fff;border-radius:7px;
  padding:9px 12px;outline:none;margin-bottom:12px;font-size:13.5px}
.ara:focus{border-color:var(--vurgu);box-shadow:0 0 0 3px rgba(24,100,171,.15)}

/* ================= PLAKA ================= */
.plaka{display:inline-flex;align-items:stretch;height:20px;border-radius:3px;
  overflow:hidden;border:1.5px solid var(--murekkep);background:#fff;
  font-family:var(--m);line-height:1;flex:none}
.plaka .tr{background:var(--mavi);color:#fff;font-size:6px;display:flex;
  align-items:flex-end;justify-content:center;width:12px;padding-bottom:2px}
.plaka .kod{display:flex;align-items:center;padding:0 6px;font-size:12px;font-weight:500}

/* ================= ROL ROZETİ ================= */
.rol{display:inline-flex;align-items:center;gap:4px;font-family:var(--m);
  font-size:9.5px;padding:2px 7px;border-radius:11px;white-space:nowrap;
  letter-spacing:.03em;font-weight:500;border:1px solid transparent}
.rol.satis {background:var(--satis-z); color:var(--satis); border-color:#F5C9AE}
.rol.servis{background:var(--servis-z);color:var(--servis);border-color:#A9DDE6}
.rol.ikisi {background:var(--ikisi-z); color:var(--ikisi); border-color:#C9BCF0}

/* ================= LİSTE ================= */
.liste{background:var(--kart);border:1px solid var(--hat2);border-radius:9px;
  overflow:hidden;box-shadow:var(--golge)}
.sat{display:flex;align-items:center;gap:10px;width:100%;text-align:left;
  background:none;border:0;border-bottom:1px solid var(--hat);padding:9px 13px;
  cursor:pointer;text-decoration:none;color:inherit}
.sat:last-child{border-bottom:0}
.sat:hover{background:var(--vurgu-z)}
.sat .ad{font-weight:600;font-size:13.5px}
.sat .sag{margin-left:auto;display:flex;align-items:center;gap:10px}
.sat .men{font-family:var(--m);font-size:9.5px;color:var(--celik);
  text-transform:uppercase;letter-spacing:.07em}
.sat .alan{font-family:var(--m);font-size:10.5px;color:var(--celik)}
.sat .ok{color:var(--vurgu);font-size:14px;font-weight:600}
.sat .esl{font-size:10.5px;color:var(--uyari);font-family:var(--m)}
.sat .sayi{font-family:var(--m);font-size:13px;min-width:42px;text-align:right;font-weight:500}
.sat .sayi.yok{color:var(--hat2);font-weight:400}
.sat.eski{background:var(--uyari-z)}

/* kayıt kartı */
.kayit{padding:10px 13px 10px 26px;border-bottom:1px solid var(--hat);
  border-left:3px solid transparent;background:#FCFDFF}
.kayit:last-child{border-bottom:0}
.kayit.satis {border-left-color:var(--satis)}
.kayit.servis{border-left-color:var(--servis)}
.kayit.ikisi {border-left-color:var(--ikisi)}
.kayit .k1{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kayit .kad{font-weight:600;font-size:13.5px}
.kayit .k2{color:var(--celik);font-size:12.5px;margin-top:2px}
.kayit .ilcerz{font-family:var(--m);font-size:10px;text-transform:uppercase;
  letter-spacing:.05em;color:var(--celik)}
.kayit .k3{display:flex;gap:14px;align-items:center;margin-top:4px;flex-wrap:wrap}
.kayit .tel{font-family:var(--m);font-size:12.5px;font-weight:500}
.kayit .tel a{text-decoration:none}
.kayit .giris{font-size:11.5px;text-decoration:none;color:var(--vurgu);
  border:1px solid var(--hat2);border-radius:5px;padding:2px 8px;background:#fff}
.kayit .giris:hover{border-color:var(--vurgu);background:var(--vurgu-z)}
.kayit.eski{background:var(--uyari-z)}

.ustcubuk{display:flex;gap:9px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.geri,.kop{border:1px solid var(--hat2);background:#fff;border-radius:6px;
  padding:6px 11px;cursor:pointer;font-size:12.5px;font-weight:500}
.geri:hover,.kop:hover{border-color:var(--murekkep)}
.ilbaslik{font-size:17px;font-weight:700}

.cipler{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.cip{border:1px solid var(--hat2);background:#fff;border-radius:16px;padding:4px 12px;
  cursor:pointer;font-size:12.5px}
.cip:hover{border-color:var(--murekkep)}
.cip.secili{background:var(--murekkep);border-color:var(--murekkep);color:#fff}

/* rol süzgeci */
.rolsuz{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.rolsuz button{border:1.5px solid var(--hat2);background:#fff;border-radius:7px;
  padding:6px 13px;cursor:pointer;font-size:12.5px;font-weight:500;
  display:inline-flex;align-items:center;gap:6px}
.rolsuz button .n{font-family:var(--m);font-size:11px;opacity:.75}
.rolsuz button:hover{border-color:var(--murekkep)}
.rolsuz button.secili{color:#fff}
.rolsuz button[data-r="tum"].secili   {background:var(--murekkep);border-color:var(--murekkep)}
.rolsuz button[data-r="satis"].secili {background:var(--satis); border-color:var(--satis)}
.rolsuz button[data-r="servis"].secili{background:var(--servis);border-color:var(--servis)}
.rolsuz button[data-r="ikisi"].secili {background:var(--ikisi); border-color:var(--ikisi)}

.bilgi{background:var(--uyari-z);border:1px solid #F0D9B5;color:var(--uyari);
  border-radius:8px;padding:10px 13px;font-size:12.5px;margin-bottom:14px}
.bos{padding:30px;text-align:center;color:var(--celik);font-size:13px}
.baslikcubuk{display:flex;gap:10px;padding:7px 13px;font-family:var(--m);font-size:9.5px;
  letter-spacing:.09em;text-transform:uppercase;color:var(--celik);
  background:#F0F4FA;border-bottom:1px solid var(--hat2)}
.baslikcubuk .sagb{margin-left:auto}

.kutular{display:grid;gap:11px;grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
  margin-bottom:16px}
/* çubuk grafik */
.cubuk{position:relative;display:block;height:5px;border-radius:3px;background:var(--hat);
  margin-top:5px;overflow:hidden}
.cubuk i{position:absolute;left:0;top:0;bottom:0;border-radius:3px;display:block}
.cubuk i.s{background:var(--satis)} .cubuk i.v{background:var(--servis)}
.sat .govde{flex:1;min-width:0}
.sat .ustsatir{display:flex;align-items:center;gap:9px}
/* hızlı arama */
.hizli{display:flex;gap:8px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.hizli input{flex:1;min-width:220px;border:1px solid var(--hat2);background:#fff;
  border-radius:7px;padding:9px 12px;outline:none;font-size:13.5px}
.hizli input:focus{border-color:var(--vurgu);box-shadow:0 0 0 3px rgba(24,100,171,.15)}
.oneri{background:#fff;border:1px solid var(--hat2);border-radius:8px;margin-top:-8px;
  margin-bottom:14px;max-height:280px;overflow:auto;box-shadow:var(--golge)}
.oneri:empty{display:none}
.kapsam{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;color:var(--celik);
  font-family:var(--m);margin-bottom:14px}
.kapsam b{color:var(--murekkep);font-weight:500}
.kutu{background:var(--kart);border:1px solid var(--hat2);border-radius:9px;
  padding:13px 15px;box-shadow:var(--golge)}
.kutu .n{font-family:var(--m);font-size:26px;font-weight:500;line-height:1;display:block}
.kutu .e{font-size:11px;font-family:var(--m);letter-spacing:.08em;text-transform:uppercase;
  color:var(--celik);margin-top:5px;display:block}
.kutu.satis  .n{color:var(--satis)}
.kutu.servis .n{color:var(--servis)}
.kutu.ikisi  .n{color:var(--ikisi)}
.ikili{display:grid;gap:16px;grid-template-columns:1fr 1fr}
@media (max-width:820px){.ikili{grid-template-columns:1fr}}
.bslk{font-size:13.5px;font-weight:600;margin:0 0 7px;display:flex;gap:8px;
  align-items:baseline}
.bslk span{font-family:var(--m);font-size:11px;color:var(--celik);font-weight:400}
.altbar{display:flex;gap:8px;margin:0 0 14px;flex-wrap:wrap}
.btn{border:1px solid var(--hat2);background:#fff;border-radius:7px;padding:8px 14px;
  cursor:pointer;font-size:13px;font-weight:500;box-shadow:var(--golge)}
.btn:hover{border-color:var(--murekkep)}
.btn.ana{background:var(--vurgu);border-color:var(--vurgu);color:#fff}
.btn.ana:hover{background:#14568F}
.btn:disabled{opacity:.6;cursor:default}

/* ================= YAZDIRMA: A4 DİKEY ================= */
@media print{
  @page{size:A4 portrait;margin:12mm 10mm}
  .serit,.ara,.cipler,.altbar,.rolsuz,.geri,.kop,.sek,.bilgi,.bos{display:none!important}
  body{background:#fff;font-size:9pt;color:#000}
  .sar{max-width:none;padding:0}
  .tepe{border-bottom:2px solid #000;padding:0 0 6pt;margin-bottom:8pt;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .tepe h1{font-size:15pt}
  .tepe img{height:30px} .tepe .sag-logo{height:38px}
  .liste{border:0;box-shadow:none;border-radius:0}
  .baslikcubuk{background:#122036!important;color:#fff!important;font-size:7.5pt;
    -webkit-print-color-adjust:exact;print-color-adjust:exact}
  .kayit{page-break-inside:avoid;padding:5pt 6pt 5pt 10pt;font-size:8.5pt}
  .kayit .kad{font-size:9pt}
  .kayit .giris{display:none}
  .sat{page-break-inside:avoid}
  .rol{-webkit-print-color-adjust:exact;print-color-adjust:exact;font-size:7pt}
  .yazdir-bilgi{display:block!important}
}
.yazdir-bilgi{display:none;font-family:var(--m);font-size:8pt;color:#444;
  margin:0 0 8pt;text-align:center}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>

<header class="tepe">
  <img src="__LOGO_SOL__" alt="Kuralkan">
  <div class="orta">
    <h1>Motosiklet Bayi ve Servis Ağı</h1>
    <p class="alt">Türkiye · <span id="mSayi">0</span> Marka · <span id="kSayi">0</span> Nokta</p>
  </div>
  <img class="sag-logo" src="__LOGO_SAG__" alt="Dayanışma">
</header>

<div class="yazdir-bilgi" id="yazdirBilgi"></div>

<div class="serit">
  <span>Veri: <b id="veriTarih">—</b></span>
  <span id="veriOzet"></span>
  <nav class="sek">
    <button id="sekOzet">Özet</button>
    <button id="sekIl" class="aktif">İller</button>
    <button id="sekMarka">Markalar</button>
  </nav>
</div>

<div class="sar" id="sar">

  <section id="vOzet" style="display:none">
    <h2>Genel Durum</h2>
    <p class="notm">Satırlara tıklayarak ayrıntıya inebilirsiniz.</p>
    <div class="hizli">
      <input id="hizliAra" type="search"
             placeholder="İl, ilçe, marka veya bayi adı ara — doğrudan git">
    </div>
    <div class="oneri" id="oneriKutu"></div>
    <div class="kutular" id="kutular"></div>
    <div class="kapsam" id="kapsam"></div>
    <div class="altbar">
      <button class="btn ana" id="btnOzetTumXls">Tümünü Excel indir</button>
      <button class="btn" id="btnOzetYaz2">Yazdır / PDF</button>
    </div>
    <div class="ikili">
      <div>
        <h3 class="bslk">İllere göre <span id="ilAdet"></span></h3>
        <div class="liste">
          <div class="baslikcubuk"><span>İl</span>
            <span class="sagb" style="min-width:52px;text-align:right">Satış</span>
            <span style="min-width:52px;text-align:right">Servis</span>
            <span style="min-width:52px;text-align:right">Toplam</span></div>
          <div id="ozetIl"></div>
        </div>
      </div>
      <div>
        <h3 class="bslk">Markalara göre <span id="mrkAdet"></span></h3>
        <div class="liste">
          <div class="baslikcubuk"><span>Marka</span>
            <span class="sagb" style="min-width:52px;text-align:right">Satış</span>
            <span style="min-width:52px;text-align:right">Servis</span>
            <span style="min-width:52px;text-align:right">Toplam</span></div>
          <div id="ozetMarka"></div>
        </div>
      </div>
    </div>
    <h3 class="bslk" style="margin-top:20px">İlçe dağılımı <span id="ilceAdet"></span></h3>
    <div class="liste">
      <div class="baslikcubuk"><span>İl / İlçe</span>
        <span class="sagb" style="min-width:52px;text-align:right">Satış</span>
        <span style="min-width:52px;text-align:right">Servis</span>
        <span style="min-width:60px;text-align:right">Marka</span>
        <span style="min-width:52px;text-align:right">Toplam</span></div>
      <div id="ozetIlce"></div>
    </div>
  </section>

  <section id="vIl">
    <h2>İl seçin</h2>
    <p class="notm">İl seçtikten sonra ilçe, marka ve satış/servis süzgeçlerini kullanabilirsiniz.</p>
    <div class="altbar" id="ilUstbar" style="display:none">
      <button class="btn ana" id="btnTumIlXls">Tüm illeri Excel indir</button>
    </div>
    <input class="ara" id="araIl" type="search" placeholder="İl adı veya plaka kodu" autocomplete="off">
    <div class="liste" id="ilListe"></div>
    <div class="bos" id="ilBos" style="display:none">Bu isimde il yok.</div>
  </section>

  <section id="vMarkalar" style="display:none">
    <div class="ustcubuk">
      <button class="geri" id="geri">← İller</button>
      <span class="plaka"><span class="tr">TR</span><span class="kod" id="kod">34</span></span>
      <span class="ilbaslik" id="ilAdi"></span>
      <button class="kop" id="kopyala">İl adını kopyala</button>
    </div>
    <div class="cipler" id="ilceCipler"></div>
    <div class="rolsuz" id="rolSuzgec"></div>
    <div class="altbar" id="ustbar" style="display:none">
      <button class="btn ana" id="btnXls">Excel indir</button>
      <button class="btn" id="btnHtml">HTML kaydet</button>
      <button class="btn" id="btnCsv">CSV</button>
      <button class="btn" id="btnYaz">Yazdır / PDF</button>
    </div>
    <input class="ara" id="araMarka" type="search" placeholder="Marka, bayi adı veya adres ara" autocomplete="off">
    <div class="liste" id="markaListe"></div>
    <div class="bos" id="markaBos" style="display:none">Sonuç yok.</div>
  </section>

  <section id="vMarkaDetay" style="display:none">
    <div class="ustcubuk">
      <button class="geri" id="geriMarka">← Markalar</button>
      <span class="ilbaslik" id="mdAd"></span>
    </div>
    <p class="notm" id="mdOzet"></p>
    <div class="rolsuz" id="mdRolSuzgec"></div>
    <div class="altbar">
      <button class="btn ana" id="btnMarkaXls">Excel indir</button>
      <button class="btn" id="btnMarkaHtml">HTML kaydet</button>
      <button class="btn" id="btnMarkaYaz">Yazdır / PDF</button>
    </div>
    <div class="liste" id="mdListe"></div>
  </section>

  <section id="vTumMarka" style="display:none">
    <h2>Marka listesi</h2>
    <p class="notm"><span id="mSay2">0</span> marka · <span id="mBayi">0</span> nokta</p>
    <div class="altbar">
      <button class="geri" id="sirala">Nokta sayısına göre sırala</button>
      <button class="btn ana" id="btnOzetXls">Özet tablosunu Excel indir</button>
      <button class="btn" id="btnOzetYaz">Yazdır / PDF</button>
    </div>
    <div class="bilgi" id="sayiUyari">
      <b>Sayılar henüz toplanmadı.</b> Tarama ilk kez çalıştığında bu sütunlar dolar.
    </div>
    <input class="ara" id="araTum" type="search" placeholder="Marka veya menşe ara" autocomplete="off">
    <div class="liste">
      <div class="baslikcubuk"><span>Marka</span>
        <span class="sagb" style="min-width:46px;text-align:right">Satış</span>
        <span style="min-width:46px;text-align:right">Servis</span>
        <span style="min-width:46px;text-align:right">İkisi</span>
        <span style="min-width:46px;text-align:right">Toplam</span></div>
      <div id="tumListe"></div>
    </div>
    <div class="bos" id="tumBos" style="display:none">Sonuç yok.</div>
  </section>

</div>
<script>
const D = __VERI__;
const $ = s => document.querySelector(s);
const [B_MARKA,B_AD,B_IL,B_ILCE,B_ADRES,B_TEL,B_DURUM,B_ROL,B_GIRIS] = [0,1,2,3,4,5,6,7,8];
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const kat = s => (s||"").toLocaleLowerCase("tr")
  .replace(/[çğıöşü]/g,c=>({"ç":"c","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u"}[c]))
  .replace(/[^a-z0-9]+/g," ").trim();

const ROL_SINIF = {satis:"satis", servis:"servis", satis_servis:"ikisi"};
const ROL_AD    = {satis:"Satış", servis:"Servis", satis_servis:"Satış + Servis"};

let IL=null, ILCE="", ROL="tum", MD=null, SIRA="ad";
const VAR_VERI = D.bayiler.length > 0;

/* ---------- üst bilgiler ---------- */
$("#mSayi").textContent = D.markalar.length;
$("#kSayi").textContent = D.bayiler.length.toLocaleString("tr-TR");
$("#mSay2").textContent = D.markalar.length;
$("#mBayi").textContent = D.bayiler.length.toLocaleString("tr-TR");
$("#veriTarih").textContent = new Date(D.olusturma)
  .toLocaleString("tr-TR",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"});
(function(){
  const s={satis:0,servis:0,satis_servis:0};
  D.bayiler.forEach(b=>s[b[B_ROL]]=(s[b[B_ROL]]||0)+1);
  $("#veriOzet").innerHTML = VAR_VERI
    ? `<b>${s.satis}</b> satış · <b>${s.servis}</b> servis · <b>${s.satis_servis}</b> ikisi`
    : "";
})();
if(VAR_VERI) $("#sayiUyari").style.display="none";

/* ---------- rol süzgeci ---------- */
function rolSuzgecCiz(hedef, veri){
  const s={tum:veri.length,satis:0,servis:0,ikisi:0};
  veri.forEach(b=>s[ROL_SINIF[b[B_ROL]]]++);
  const et={tum:"Tümü",satis:"Sadece satış",servis:"Sadece servis",ikisi:"Satış + Servis"};
  $(hedef).innerHTML = ["tum","satis","servis","ikisi"].map(r=>
    `<button data-r="${r}" class="${ROL===r?"secili":""}">${et[r]}
       <span class="n">${s[r]}</span></button>`).join("");
}
function rolBagla(hedef, ciz){
  $(hedef).onclick = e => {
    const b=e.target.closest("button"); if(!b) return;
    ROL = b.dataset.r; ciz();
  };
}
const rolGecer = b => ROL==="tum" || ROL_SINIF[b[B_ROL]]===ROL;

/* ---------- ekranlar ---------- */
/* Ekranı gösterir. gecmis=true ise adres etiketine yazar; böylece tarayıcının
   geri tuşu sayfadan çıkmak yerine bir önceki ekrana döner. */
function ekran(v, gecmis=true){
  ["vOzet","vIl","vMarkalar","vTumMarka","vMarkaDetay"].forEach(x=>$("#"+x).style.display="none");
  $("#"+v).style.display="block";
  $("#sar").classList.toggle("genis", v==="vTumMarka"||v==="vMarkaDetay"||v==="vOzet");
  $("#sekOzet").classList.toggle("aktif", v==="vOzet");
  $("#sekIl").classList.toggle("aktif", v==="vIl"||v==="vMarkalar");
  $("#sekMarka").classList.toggle("aktif", v==="vTumMarka"||v==="vMarkaDetay");
  window.scrollTo(0,0);
  if(gecmis) durumYaz(v);
}

/* ---------- tarayıcı geçmişi ----------
   Adres etiketi (#) kullanıyoruz: pushState dosya olarak açılan sayfalarda
   geçmiş kaydı oluşturmuyor, hash her ortamda çalışıyor. Ayrıca kullanıcı
   bulunduğu ekranın bağlantısını paylaşabiliyor. */
let _kendiYazdi = false;

function durumYaz(v){
  const p = new URLSearchParams();
  p.set("e", v);
  if(IL) p.set("il", IL.ad);
  if(ILCE) p.set("ilce", ILCE);
  if(MD && v === "vMarkaDetay") p.set("marka", MD.ad);
  if(ROL && ROL !== "tum") p.set("rol", ROL);
  const h = "#" + p.toString();
  if(location.hash === h) return;
  _kendiYazdi = true;
  location.hash = h;
  setTimeout(() => { _kendiYazdi = false; }, 0);
}

function hashUygula(){
  const p = new URLSearchParams(location.hash.slice(1));
  const v = p.get("e") || "vOzet";
  ROL = p.get("rol") || "tum";
  const marka = p.get("marka"), il = p.get("il"), ilce = p.get("ilce") || "";

  if(v === "vMarkaDetay" && marka){
    MD = OZET.find(m => m.ad === marka);
    if(MD){ cizMD(); ekran("vMarkaDetay", false); return; }
  }
  if(v === "vMarkalar" && il){
    const bulunan = D.iller.find(x => x.ad === il);
    if(bulunan){
      IL = bulunan; ILCE = ilce;
      $("#kod").textContent = IL.plaka; $("#ilAdi").textContent = IL.ad;
      cizIlce();
      if(ILCE) [...$("#ilceCipler").children].forEach(
        c => c.classList.toggle("secili", c.dataset.i === ILCE));
      cizMarka(); ekran("vMarkalar", false); return;
    }
  }
  if(v === "vTumMarka"){ cizTum(); ekran("vTumMarka", false); return; }
  if(v === "vIl"){ cizIl(); ekran("vIl", false); return; }
  cizOzet(); ekran("vOzet", false);
}

window.addEventListener("hashchange", () => { if(!_kendiYazdi) hashUygula(); });
$("#sekOzet").onclick  = () => { cizOzet(); ekran("vOzet"); };
$("#sekIl").onclick    = () => ekran(IL?"vMarkalar":"vIl");
$("#sekMarka").onclick = () => { cizTum(); ekran("vTumMarka"); };
$("#geri").onclick     = () => { IL=null; ILCE=""; ROL="tum"; $("#araMarka").value=""; ekran("vIl"); };
$("#geriMarka").onclick= () => { ROL="tum"; cizTum(); ekran("vTumMarka"); };

/* ---------- ÖZET ---------- */
function sayRol(veri){
  const c={satis:0,servis:0,ikisi:0};
  veri.forEach(b=>c[ROL_SINIF[b[B_ROL]]]++);
  // "Satış + Servis" olanlar hem satışa hem servise dahil
  return {satis:c.satis+c.ikisi, servis:c.servis+c.ikisi,
          ikisi:c.ikisi, toplam:veri.length};
}
function cizOzet(){
  const t=sayRol(D.bayiler);
  const iller=new Set(D.bayiler.map(b=>b[B_IL]).filter(Boolean));
  const ilceler=new Set(D.bayiler.filter(b=>b[B_ILCE]).map(b=>b[B_IL]+"/"+b[B_ILCE]));
  const markalar=new Set(D.bayiler.map(b=>b[B_MARKA]));
  const bicim=n=>n.toLocaleString("tr-TR");

  $("#kutular").innerHTML=`
    <div class="kutu"><span class="n">${bicim(t.toplam)}</span><span class="e">Toplam Nokta</span></div>
    <div class="kutu satis"><span class="n">${bicim(t.satis)}</span><span class="e">Satış Noktası</span></div>
    <div class="kutu servis"><span class="n">${bicim(t.servis)}</span><span class="e">Servis Noktası</span></div>
    <div class="kutu ikisi"><span class="n">${bicim(t.ikisi)}</span><span class="e">Satış + Servis</span></div>
    <div class="kutu"><span class="n">${markalar.size}</span><span class="e">Marka</span></div>
    <div class="kutu"><span class="n">${iller.size}</span><span class="e">İl</span></div>
    <div class="kutu"><span class="n">${ilceler.size}</span><span class="e">İlçe</span></div>`;

  // Kapsama bilgisi
  const telli=D.bayiler.filter(b=>b[B_TEL]).length;
  const ilceli=D.bayiler.filter(b=>b[B_ILCE]).length;
  const eski=D.bayiler.filter(b=>b[B_DURUM]!=="Güncel").length;
  $("#kapsam").innerHTML=
    `<span>Telefonu olan: <b>%${Math.round(telli/t.toplam*100)}</b></span>
     <span>İlçesi belirli: <b>%${Math.round(ilceli/t.toplam*100)}</b></span>
     <span>Kapsanan il: <b>${iller.size}/81</b></span>
     ${eski?`<span style="color:var(--uyari)">Doğrulanamayan: <b>${eski}</b></span>`:""}`;

  // Satır çizici — yanında oransal çubuk
  const enCok = v => Math.max(1, ...v.map(x=>x[1].length));
  function satirlar(veri, tip){
    const m=enCok(veri);
    return veri.map(([ad,v])=>{
      const c=sayRol(v);
      const p=(D.iller.find(x=>x.ad===ad)||{}).plaka;
      return `<button class="sat" data-${tip}="${esc(ad)}">
        ${p?`<span class="plaka"><span class="tr">TR</span><span class="kod">${p}</span></span>`:""}
        <span class="govde">
          <span class="ustsatir"><span class="ad">${esc(ad)}</span></span>
          <span class="cubuk">
            <i class="s" style="width:${c.satis/m*100}%"></i>
            <i class="v" style="left:${c.satis/m*100}%;width:${c.servis/m*100}%"></i>
          </span>
        </span>
        <span class="sag">
          <span class="sayi" style="min-width:46px;color:var(--satis)">${c.satis}</span>
          <span class="sayi" style="min-width:46px;color:var(--servis)">${c.servis}</span>
          <span class="sayi" style="min-width:46px;font-weight:700">${c.toplam}</span>
          <span class="ok">›</span></span></button>`;}).join("");
  }

  const ilG={};
  D.bayiler.forEach(b=>{ if(b[B_IL]) (ilG[b[B_IL]]||=[]).push(b); });
  const ilS=Object.entries(ilG).sort((a,b)=>b[1].length-a[1].length);
  $("#ilAdet").textContent=`${ilS.length} il`;
  $("#ozetIl").innerHTML=satirlar(ilS,"il");

  const mG={};
  D.bayiler.forEach(b=>(mG[b[B_MARKA]]||=[]).push(b));
  const mS=Object.entries(mG).sort((a,b)=>b[1].length-a[1].length);
  $("#mrkAdet").textContent=`${mS.length} marka`;
  $("#ozetMarka").innerHTML=satirlar(mS,"mrk");

  // İlçe dağılımı — ilk 60, en yoğundan
  const iG={};
  D.bayiler.forEach(b=>{ if(b[B_ILCE]) (iG[b[B_IL]+"|"+b[B_ILCE]]||=[]).push(b); });
  const iS=Object.entries(iG).sort((a,b)=>b[1].length-a[1].length).slice(0,60);
  $("#ilceAdet").textContent=`en yoğun ${iS.length} ilçe · toplam ${ilceler.size}`;
  $("#ozetIlce").innerHTML=iS.map(([k,v])=>{
    const [il,ilce]=k.split("|"), c=sayRol(v);
    return `<button class="sat" data-il="${esc(il)}" data-ilce="${esc(ilce)}">
      <span class="ad">${esc(ilce)}</span>
      <span class="men">${esc(il)}</span>
      <span class="sag">
        <span class="sayi" style="min-width:52px;color:var(--satis)">${c.satis}</span>
        <span class="sayi" style="min-width:52px;color:var(--servis)">${c.servis}</span>
        <span class="sayi" style="min-width:60px">${new Set(v.map(x=>x[B_MARKA])).size}</span>
        <span class="sayi" style="min-width:52px;font-weight:700">${c.toplam}</span>
        <span class="ok">›</span></span></button>`;}).join("");
  yazdirBilgiGuncelle("Genel Özet", D.bayiler.length);
}
function ozetTiklama(e){
  const b=e.target.closest("button.sat"); if(!b) return;
  if(b.dataset.mrk){ markaAc(b.dataset.mrk); return; }
  if(b.dataset.il){
    IL=D.iller.find(x=>x.ad===b.dataset.il); if(!IL) return;
    ILCE=b.dataset.ilce||""; ROL="tum";
    $("#kod").textContent=IL.plaka; $("#ilAdi").textContent=IL.ad;
    cizIlce();
    if(ILCE){ [...$("#ilceCipler").children].forEach(c=>
      c.classList.toggle("secili", c.dataset.i===ILCE)); }
    cizMarka(); ekran("vMarkalar");
  }
}
["#ozetIl","#ozetMarka","#ozetIlce"].forEach(x=>$(x).onclick=ozetTiklama);

/* ---------- hızlı arama: her şeyde ara, doğrudan git ---------- */
let zh;
$("#hizliAra").oninput = () => { clearTimeout(zh); zh=setTimeout(hizliCiz,140); };
function hizliCiz(){
  const q=kat($("#hizliAra").value);
  if(q.length<2){ $("#oneriKutu").innerHTML=""; return; }
  const out=[];
  D.iller.filter(i=>kat(i.ad).includes(q)).slice(0,4).forEach(i=>{
    const n=D.bayiler.filter(b=>b[B_IL]===i.ad).length;
    out.push(`<button class="sat" data-il="${esc(i.ad)}">
      <span class="plaka"><span class="tr">TR</span><span class="kod">${i.plaka}</span></span>
      <span class="ad">${esc(i.ad)}</span>
      <span class="sag"><span class="men">İL</span>
      <span class="sayi">${n}</span><span class="ok">›</span></span></button>`);});
  OZET.filter(m=>kat(m.ad).includes(q)&&m.toplam).slice(0,4).forEach(m=>
    out.push(`<button class="sat" data-mrk="${esc(m.ad)}">
      <span class="ad">${esc(m.ad)}</span>
      <span class="sag"><span class="men">MARKA</span>
      <span class="sayi">${m.toplam}</span><span class="ok">›</span></span></button>`));
  const ilceler=[...new Set(D.bayiler.filter(b=>b[B_ILCE]&&kat(b[B_ILCE]).includes(q))
    .map(b=>b[B_IL]+"|"+b[B_ILCE]))].slice(0,4);
  ilceler.forEach(k=>{
    const [il,ilce]=k.split("|");
    const n=D.bayiler.filter(b=>b[B_IL]===il&&b[B_ILCE]===ilce).length;
    out.push(`<button class="sat" data-il="${esc(il)}" data-ilce="${esc(ilce)}">
      <span class="ad">${esc(ilce)}</span><span class="men">${esc(il)}</span>
      <span class="sag"><span class="men">İLÇE</span>
      <span class="sayi">${n}</span><span class="ok">›</span></span></button>`);});
  const bayiler=D.bayiler.filter(b=>kat(b[B_AD]).includes(q)).slice(0,5);
  bayiler.forEach(b=>out.push(`<button class="sat" data-il="${esc(b[B_IL])}"
      data-ilce="${esc(b[B_ILCE])}">
      <span class="ad">${esc(b[B_AD])}</span>
      <span class="men">${esc(b[B_MARKA])} · ${esc(b[B_ILCE]||b[B_IL])}</span>
      <span class="sag"><span class="ok">›</span></span></button>`));
  $("#oneriKutu").innerHTML = out.join("") ||
    `<div class="bos">Sonuç yok.</div>`;
}
$("#oneriKutu").onclick = e => { ozetTiklama(e); $("#hizliAra").value=""; $("#oneriKutu").innerHTML=""; };
$("#btnOzetTumXls").onclick = e => excelIndir({tip:"tum"},e.target);
$("#btnOzetYaz2").onclick = () => window.print();

/* ---------- iller ---------- */
function cizIl(){
  $("#ilUstbar").style.display = VAR_VERI ? "flex":"none";
  const q=kat($("#araIl").value);
  const l=D.iller.filter(i=>!q||kat(i.ad).includes(q)||i.plaka.startsWith(q));
  $("#ilBos").style.display=l.length?"none":"block";
  $("#ilListe").innerHTML=l.map(i=>{
    const b=D.bayiler.filter(x=>x[B_IL]===i.ad);
    const n=VAR_VERI?b.length:null;
    const s=b.filter(x=>x[B_ROL]==="satis"||x[B_ROL]==="satis_servis").length;
    const v=b.filter(x=>x[B_ROL]==="servis"||x[B_ROL]==="satis_servis").length;
    return `<button class="sat" data-slug="${i.slug}">
      <span class="plaka"><span class="tr">TR</span><span class="kod">${i.plaka}</span></span>
      <span class="ad">${esc(i.ad)}</span>
      <span class="sag">
        ${n?`<span class="rol satis">${s} satış</span>
             <span class="rol servis">${v} servis</span>`:""}
        <span class="sayi ${n?"":"yok"}">${n||"—"}</span>
        <span class="ok">›</span></span></button>`;}).join("");
}
$("#ilListe").onclick = e => {
  const b=e.target.closest(".sat"); if(!b) return;
  IL=D.iller.find(x=>x.slug===b.dataset.slug); ILCE=""; ROL="tum";
  $("#kod").textContent=IL.plaka; $("#ilAdi").textContent=IL.ad;
  cizIlce(); cizMarka(); ekran("vMarkalar");
};
let z1; $("#araIl").oninput=()=>{clearTimeout(z1);z1=setTimeout(cizIl,110);};

/* ---------- ilçe ---------- */
function cizIlce(){
  const l=[...new Set(D.bayiler.filter(b=>b[B_IL]===IL.ad).map(b=>b[B_ILCE]).filter(Boolean))]
    .sort((a,b)=>a.localeCompare(b,"tr"));
  $("#ilceCipler").innerHTML = l.length
    ? `<button class="cip secili" data-i="">Tüm ${esc(IL.ad)}</button>`+
      l.map(x=>`<button class="cip" data-i="${esc(x)}">${esc(x)}</button>`).join("") : "";
}
$("#ilceCipler").onclick=e=>{
  const b=e.target.closest(".cip"); if(!b) return;
  ILCE=b.dataset.i;
  [...$("#ilceCipler").children].forEach(c=>c.classList.toggle("secili",c===b));
  cizMarka();
};

/* ---------- kayıt kartı ---------- */
function kayitHtml(x){
  const sn=ROL_SINIF[x[B_ROL]];
  return `<div class="kayit ${sn} ${x[B_DURUM]!=="Güncel"?"eski":""}">
    <div class="k1"><span class="kad">${esc(x[B_AD])}</span>
      <span class="rol ${sn}">${esc(ROL_AD[x[B_ROL]]||"")}</span>
      ${x[B_DURUM]!=="Güncel"?`<span class="rol" style="background:var(--uyari-z);color:var(--uyari);border-color:#F0D9B5">${esc(x[B_DURUM])}</span>`:""}
    </div>
    <div class="k2"><span class="ilcerz">${esc(x[B_ILCE]||x[B_IL])}</span> ${esc(x[B_ADRES])}</div>
    <div class="k3">
      <span class="tel">${x[B_TEL]?`<a href="tel:${esc(x[B_TEL].replace(/\s/g,""))}">${esc(x[B_TEL])}</a>`:"—"}</span>
      ${x[B_GIRIS]?`<a class="giris" href="${esc(x[B_GIRIS])}" target="_blank" rel="noopener">Marka sayfasına git ↗</a>`:""}
    </div></div>`;
}

/* ---------- ilin markaları ---------- */
function bolgeVeri(){
  return D.bayiler.filter(b=>b[B_IL]===IL.ad && (!ILCE||b[B_ILCE]===ILCE));
}
function cizMarka(){
  const tum=bolgeVeri();
  rolSuzgecCiz("#rolSuzgec", tum);
  const q=kat($("#araMarka").value);
  const l=D.markalar.filter(m=>!q||kat(m.ad+" "+m.mensei+" "+m.alan).includes(q));

  $("#markaListe").innerHTML=l.map(m=>{
    const bs=tum.filter(x=>x[B_MARKA]===m.ad && rolGecer(x));
    if(!bs.length){
      if(q && !kat(m.ad).includes(q)) return "";
      if(ROL!=="tum") return "";
      return `<a class="sat" href="${esc(m.bayi||m.site)}" target="_blank" rel="noopener">
        <span class="ad">${esc(m.ad)}</span>
        <span class="sag"><span class="alan">${esc(m.alan)}</span>
        <span class="ok">↗</span></span></a>`;
    }
    const acik=ACIK.has(m.ad);
    const s=bs.filter(x=>x[B_ROL]!=="servis").length, v=bs.filter(x=>x[B_ROL]!=="satis").length;
    return `<button class="sat" data-m="${esc(m.ad)}">
        <span class="ad">${esc(m.ad)}</span>
        <span class="sag">
          ${s?`<span class="rol satis">${s} satış</span>`:""}
          ${v?`<span class="rol servis">${v} servis</span>`:""}
          <span class="sayi">${bs.length}</span>
          <span class="ok">${acik?"⌄":"›"}</span></span></button>`
      + (acik?bs.map(kayitHtml).join(""):"");
  }).join("");

  const gorunen=tum.filter(rolGecer);
  $("#markaBos").style.display=gorunen.length?"none":"block";
  $("#ustbar").style.display=VAR_VERI&&tum.length?"flex":"none";
  yazdirBilgiGuncelle(`${IL.ad}${ILCE?" / "+ILCE:""}`, gorunen.length);
}
const ACIK=new Set();
$("#markaListe").onclick=e=>{
  const b=e.target.closest("button.sat"); if(!b) return;
  const m=b.dataset.m; ACIK.has(m)?ACIK.delete(m):ACIK.add(m); cizMarka();
};
let z2; $("#araMarka").oninput=()=>{clearTimeout(z2);z2=setTimeout(cizMarka,110);};
rolBagla("#rolSuzgec", cizMarka);

$("#kopyala").onclick=async()=>{
  try{await navigator.clipboard.writeText(IL.ad);$("#kopyala").textContent="Kopyalandı ✓";}
  catch{$("#kopyala").textContent="Kopyalanamadı";}
  setTimeout(()=>$("#kopyala").textContent="İl adını kopyala",1700);
};

/* ---------- marka özeti ---------- */
const OZET=(()=>{
  const o={};
  D.markalar.forEach(m=>o[m.ad]={ad:m.ad,mensei:m.mensei,alan:m.alan,bayi_link:m.bayi,
    site:m.site,tazelik:m.tazelik||"",satis:0,servis:0,ikisi:0,toplam:0,
    iller:new Set(),ilceler:new Set()});
  D.bayiler.forEach(b=>{const x=o[b[B_MARKA]]; if(!x)return;
    x.toplam++; x[ROL_SINIF[b[B_ROL]]]++;
    if(b[B_IL])x.iller.add(b[B_IL]);
    if(b[B_ILCE])x.ilceler.add(b[B_IL]+"/"+b[B_ILCE]);});
  return Object.values(o);
})();
$("#sirala").onclick=()=>{
  SIRA=SIRA==="ad"?"sayi":"ad";
  $("#sirala").textContent=SIRA==="sayi"?"Alfabetik sırala":"Nokta sayısına göre sırala";
  cizTum();
};
function cizTum(){
  const q=kat($("#araTum").value);
  let l=OZET.filter(m=>!q||kat(m.ad+" "+m.mensei+" "+m.alan).includes(q));
  l=SIRA==="sayi"?[...l].sort((a,b)=>b.toplam-a.toplam||a.ad.localeCompare(b.ad,"tr"))
                 :[...l].sort((a,b)=>a.ad.localeCompare(b.ad,"tr"));
  $("#tumBos").style.display=l.length?"none":"block";
  $("#tumListe").innerHTML=l.map(m=>{
    const t=m.toplam>0;
    const ic=`<span class="ad">${esc(m.ad)}</span><span class="men">${esc(m.mensei)}</span>
      <span class="sag">
        <span class="sayi ${m.satis?"":"yok"}" style="min-width:46px">${m.satis||"—"}</span>
        <span class="sayi ${m.servis?"":"yok"}" style="min-width:46px">${m.servis||"—"}</span>
        <span class="sayi ${m.ikisi?"":"yok"}" style="min-width:46px">${m.ikisi||"—"}</span>
        <span class="sayi ${t?"":"yok"}" style="min-width:46px;font-weight:700">${m.toplam||"—"}</span>
        <span class="ok">${t?"›":"↗"}</span></span>`;
    return t?`<button class="sat" data-m="${esc(m.ad)}">${ic}</button>`
            :`<a class="sat" href="${esc(m.bayi_link||m.site)}" target="_blank" rel="noopener">${ic}</a>`;
  }).join("");
  yazdirBilgiGuncelle("Marka listesi", l.length);
}
let z3; $("#araTum").oninput=()=>{clearTimeout(z3);z3=setTimeout(cizTum,110);};
$("#tumListe").onclick=e=>{const b=e.target.closest("button.sat"); if(b) markaAc(b.dataset.m);};

/* ---------- marka detayı ---------- */
function markaAc(ad){
  MD=OZET.find(m=>m.ad===ad); if(!MD)return;
  ROL="tum"; $("#mdAd").textContent=ad; cizMD(); ekran("vMarkaDetay");
}
function cizMD(){
  const tum=D.bayiler.filter(x=>x[B_MARKA]===MD.ad);
  rolSuzgecCiz("#mdRolSuzgec", tum);
  const b=tum.filter(rolGecer);
  $("#mdOzet").textContent=`${b.length} nokta · ${MD.iller.size} il · ${MD.ilceler.size} ilçe`
    +(MD.tazelik&&MD.tazelik!=="Güncel"?` · ${MD.tazelik}`:"");
  const g={};
  b.forEach(x=>(g[x[B_IL]||"— il bilinmiyor —"]||=[]).push(x));
  $("#mdListe").innerHTML=Object.keys(g).sort((a,c)=>a.localeCompare(c,"tr")).map(il=>
    `<div class="baslikcubuk"><span>${esc(il)}</span>
       <span class="sagb">${g[il].length} nokta</span></div>`+
    g[il].map(kayitHtml).join("")).join("");
  yazdirBilgiGuncelle(MD.ad, b.length);
}
rolBagla("#mdRolSuzgec", cizMD);

function yazdirBilgiGuncelle(baslik, adet){
  const et={tum:"tümü",satis:"sadece satış",servis:"sadece servis",ikisi:"satış + servis"};
  $("#yazdirBilgi").textContent =
    `${baslik} · ${adet} kayıt · ${et[ROL]} · ${$("#veriTarih").textContent}`;
}

/* ================= DIŞA AKTARMA ================= */
const BASLIK=["Marka","Ünvan / Bayi Adı","Rol","İl","İlçe","Adres","Telefon",
              "Veri Durumu","Marka Sayfası"];
const EN=[{wch:16},{wch:38},{wch:14},{wch:14},{wch:16},{wch:50},{wch:16},{wch:24},{wch:44}];
const satirDisa = x => [x[B_MARKA],x[B_AD],ROL_AD[x[B_ROL]]||"",x[B_IL],x[B_ILCE],
                        x[B_ADRES],x[B_TEL],x[B_DURUM],x[B_GIRIS]];

async function xlsxYukle(){
  if(window.XLSX) return true;
  return new Promise(ok=>{const s=document.createElement("script");
    s.src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js";
    s.onload=()=>ok(true); s.onerror=()=>ok(false); document.head.appendChild(s);});
}
function sayfaEkle(wb,ad,satirlar,gen){
  const ws=XLSX.utils.aoa_to_sheet(satirlar);
  ws["!cols"]=gen; ws["!freeze"]={xSplit:0,ySplit:1};
  XLSX.utils.book_append_sheet(wb,ws,ad.replace(/[\\\/\?\*\[\]:]/g,"-").slice(0,31));
}
function dosyaAdi(k,uz){
  const d=new Date(),p=n=>String(n).padStart(2,"0");
  return `${k}-${d.getFullYear()}${p(d.getMonth()+1)}${p(d.getDate())}.${uz}`;
}
function indir(blob,ad){
  const u=URL.createObjectURL(blob),a=document.createElement("a");
  a.href=u;a.download=ad;a.click();setTimeout(()=>URL.revokeObjectURL(u),1500);
}
function rolOzeti(veri){
  const s=[["Rol","Nokta Sayısı"]];
  const c={satis:0,servis:0,satis_servis:0};
  veri.forEach(b=>c[b[B_ROL]]++);
  s.push(["Sadece satış",c.satis],["Sadece servis",c.servis],
         ["Satış + Servis",c.satis_servis],[],["TOPLAM",veri.length]);
  return s;
}

async function excelIndir(kap,btn){
  const eski=btn?btn.textContent:"";
  if(btn){btn.disabled=true;btn.textContent="Hazırlanıyor…";}
  if(!(await xlsxYukle())){
    if(btn){btn.textContent="İnternet gerekiyor";
      setTimeout(()=>{btn.textContent=eski;btn.disabled=false;},2500);}
    return;
  }
  const wb=XLSX.utils.book_new();
  let veri,ad;
  if(kap.tip==="marka"){
    veri=D.bayiler.filter(b=>b[B_MARKA]===kap.ad);
    ad=`${kat(kap.ad).replace(/ /g,"-")}-bayi-servis`;
    sayfaEkle(wb,"Rol Özeti",rolOzeti(veri),[{wch:22},{wch:14}]);
    const s={};veri.forEach(b=>s[b[B_IL]||"—"]=(s[b[B_IL]||"—"]||0)+1);
    const k=[["İl","Nokta Sayısı"]];
    Object.entries(s).sort((a,b)=>b[1]-a[1]).forEach(([a,b])=>k.push([a,b]));
    k.push([],["TOPLAM",veri.length]);
    sayfaEkle(wb,"İl Kırılımı",k,[{wch:20},{wch:14}]);
  } else if(kap.tip==="bolge"){
    veri=D.bayiler.filter(b=>b[B_IL]===kap.il&&(!kap.ilce||b[B_ILCE]===kap.ilce));
    ad=`${kat(kap.il).replace(/ /g,"")}${kap.ilce?"-"+kat(kap.ilce).replace(/ /g,""):""}-bayi-servis`;
    sayfaEkle(wb,"Rol Özeti",rolOzeti(veri),[{wch:22},{wch:14}]);
    const s={};veri.forEach(b=>{const m=b[B_MARKA];(s[m]||=[0,0,0]);
      s[m][b[B_ROL]==="satis"?0:b[B_ROL]==="servis"?1:2]++;});
    const k=[["Marka","Satış","Servis","Satış+Servis","Toplam"]];
    Object.entries(s).sort((a,b)=>(b[1][0]+b[1][1]+b[1][2])-(a[1][0]+a[1][1]+a[1][2]))
      .forEach(([m,v])=>k.push([m,v[0],v[1],v[2],v[0]+v[1]+v[2]]));
    sayfaEkle(wb,"Marka Dağılımı",k,[{wch:22},{wch:10},{wch:10},{wch:13},{wch:10}]);
    if(!kap.ilce){
      const i={};veri.forEach(b=>{const x=b[B_ILCE]||"—";i[x]=(i[x]||0)+1;});
      const ik=[["İlçe","Nokta Sayısı","Marka Çeşidi"]];
      Object.entries(i).sort((a,b)=>b[1]-a[1]).forEach(([a,b])=>
        ik.push([a,b,new Set(veri.filter(x=>(x[B_ILCE]||"—")===a).map(x=>x[B_MARKA])).size]));
      sayfaEkle(wb,"İlçe Kırılımı",ik,[{wch:22},{wch:14},{wch:14}]);
    }
  } else if(kap.tip==="tum_iller"){
    veri=D.bayiler; ad="il-il-bayi-servis";
    const iller=[...new Set(veri.map(b=>b[B_IL]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"tr"));
    const o=[["İl","Satış","Servis","Satış+Servis","Toplam","Marka Çeşidi","İlçe"]];
    iller.forEach(il=>{const a=veri.filter(b=>b[B_IL]===il);
      o.push([il,a.filter(b=>b[B_ROL]==="satis").length,a.filter(b=>b[B_ROL]==="servis").length,
        a.filter(b=>b[B_ROL]==="satis_servis").length,a.length,
        new Set(a.map(b=>b[B_MARKA])).size,new Set(a.map(b=>b[B_ILCE]).filter(Boolean)).size]);});
    o.push([],["TOPLAM",veri.filter(b=>b[B_ROL]==="satis").length,
      veri.filter(b=>b[B_ROL]==="servis").length,
      veri.filter(b=>b[B_ROL]==="satis_servis").length,veri.length,
      new Set(veri.map(b=>b[B_MARKA])).size,""]);
    sayfaEkle(wb,"İl Özeti",o,[{wch:20},{wch:9},{wch:9},{wch:13},{wch:10},{wch:13},{wch:9}]);
    sayfaEkle(wb,"Tüm Kayıtlar",[BASLIK,...veri.map(satirDisa)],EN);
    iller.forEach(il=>{const a=veri.filter(b=>b[B_IL]===il);
      if(a.length) sayfaEkle(wb,il,[BASLIK,...a.map(satirDisa)],EN);});
    XLSX.writeFile(wb,dosyaAdi(ad,"xlsx"));
    if(btn){btn.textContent=eski;btn.disabled=false;} return;
  } else {
    veri=D.bayiler; ad="tum-turkiye-bayi-servis";
    const o=[["Marka","Menşei","Satış","Servis","Satış+Servis","Toplam","İl","İlçe","Veri Durumu","Kaynak"]];
    [...OZET].sort((a,b)=>b.toplam-a.toplam||a.ad.localeCompare(b.ad,"tr")).forEach(m=>
      o.push([m.ad,m.mensei,m.satis,m.servis,m.ikisi,m.toplam,m.iller.size,m.ilceler.size,
              m.tazelik||(m.toplam?"Güncel":"Henüz taranmadı"),m.bayi_link||m.site]));
    o.push([],["TOPLAM","",veri.filter(b=>b[B_ROL]==="satis").length,
      veri.filter(b=>b[B_ROL]==="servis").length,
      veri.filter(b=>b[B_ROL]==="satis_servis").length,veri.length,
      new Set(veri.map(b=>b[B_IL]).filter(Boolean)).size,"","",""]);
    sayfaEkle(wb,"Marka Özeti",o,[{wch:20},{wch:14},{wch:9},{wch:9},{wch:13},{wch:9},
                                  {wch:7},{wch:8},{wch:24},{wch:44}]);
    sayfaEkle(wb,"Tüm Kayıtlar",[BASLIK,...veri.map(satirDisa)],EN);
    [...new Set(veri.map(b=>b[B_MARKA]))].sort((a,b)=>a.localeCompare(b,"tr")).forEach(m=>{
      const a=veri.filter(b=>b[B_MARKA]===m);
      if(a.length) sayfaEkle(wb,m,[BASLIK,...a.map(satirDisa)],EN);});
  }
  if(kap.tip!=="tum_iller"&&kap.tip!=="tum")
    sayfaEkle(wb,"Kayıtlar",[BASLIK,...veri.map(satirDisa)],EN);
  XLSX.writeFile(wb,dosyaAdi(ad,"xlsx"));
  if(btn){btn.textContent=eski;btn.disabled=false;}
}

/* HTML kaydet: sayfanın o anki halini tek dosya olarak indirir */
function htmlKaydet(etiket){
  const kopya=document.documentElement.cloneNode(true);
  kopya.querySelectorAll(".sek,.altbar,.ara").forEach(e=>e.remove());
  const blob=new Blob(["<!doctype html>\n"+kopya.outerHTML],
                      {type:"text/html;charset=utf-8"});
  indir(blob,dosyaAdi(kat(etiket).replace(/ /g,"-")||"liste","html"));
}

$("#btnXls").onclick      = e => excelIndir({tip:"bolge",il:IL.ad,ilce:ILCE},e.target);
$("#btnTumIlXls").onclick = e => excelIndir({tip:"tum_iller"},e.target);
$("#btnOzetXls").onclick  = e => excelIndir({tip:"tum"},e.target);
$("#btnMarkaXls").onclick = e => excelIndir({tip:"marka",ad:MD.ad},e.target);
$("#btnHtml").onclick      = () => htmlKaydet(IL.ad+(ILCE?"-"+ILCE:""));
$("#btnMarkaHtml").onclick = () => htmlKaydet(MD.ad);
$("#btnYaz").onclick=$("#btnMarkaYaz").onclick=$("#btnOzetYaz").onclick=()=>window.print();
$("#btnCsv").onclick=()=>{
  const b=bolgeVeri().filter(rolGecer);
  const csv=[BASLIK,...b.map(satirDisa)]
    .map(r=>r.map(c=>`"${String(c??"").replace(/"/g,'""')}"`).join(";")).join("\r\n");
  indir(new Blob(["\uFEFF"+csv],{type:"text/csv;charset=utf-8"}),
        dosyaAdi(kat(IL.ad).replace(/ /g,""),"csv"));
};

cizOzet();
ekran('vOzet', false);
try{ history.replaceState({ekran:'vOzet'},''); }catch(e){}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    cikti = sys.argv[1] if len(sys.argv) > 1 else "site/index.html"
    yol, adet, markali = uret(cikti)
    print(f"✓ {yol}  ·  {adet} kayıt  ·  {markali} markada veri var")
