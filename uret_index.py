#!/usr/bin/env python3
"""index.html üretir — MOTOSİKLET BAYİLERİ.

Tek sayfa, iki kaynak:
  1. Veritabanındaki toplanmış bayiler  → il/ilçe seçince liste açılır
  2. Excel'deki resmi bayi sayfası linkleri → henüz taranmamış markalar için

Bir marka taranmışsa satırı açılır ve bayileri gösterir. Taranmamışsa satır
markanın kendi sayfasına götürür. Yani sistem yarım çalışırken de işe yarar,
tam dolduğunda da.

Kullanım:  python uret_index.py [cikti_yolu]
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from bayiradar.normalize import ILLER, fold, phone_display

PLAKA = {ad: f"{i+1:02d}" for i, ad in enumerate(ILLER)}


def markalari_oku(yol="markalar.json"):
    return json.load(open(yol, encoding="utf-8"))


def veritabanindan_oku(db_yolu="bayiler.db"):
    """(bayiler, marka_durumlari) döner. Veritabanı yoksa boş döner."""
    if not Path(db_yolu).exists():
        return [], {}
    from bayiradar.store import db, marka_durumu, sorgula
    with db(db_yolu) as con:
        kayitlar = sorgula(con)
        durum = {m["marka"]: m for m in marka_durumu(con)}
    return kayitlar, durum


def uret(cikti="index.html", markalar_json="markalar.json", db_yolu="bayiler.db"):
    markalar = markalari_oku(markalar_json)
    kayitlar, durum = veritabanindan_oku(db_yolu)

    # Bayileri kompakt diziye çevir: [marka, ad, il, ilce, adres, tel, durum]
    satirlar = [[k["marka"], k["bayi_adi"], k["il"], k["ilce"], k["adres"],
                 phone_display(k.get("telefon", "")), k.get("veri_durumu", "Güncel")]
                for k in kayitlar]

    say = defaultdict(int)
    for k in kayitlar:
        say[k["marka"]] += 1

    for m in markalar:
        m["sayi"] = say.get(m["ad"]) or None
        d = durum.get(m["ad"])
        m["tazelik"] = d["etiket"] if d else ""

    veri = {
        "olusturma": datetime.now().astimezone().isoformat(timespec="minutes"),
        "iller": sorted([{"ad": i, "plaka": PLAKA[i], "slug": fold(i).replace(" ", "")}
                         for i in ILLER], key=lambda x: fold(x["ad"])),
        "markalar": sorted(markalar, key=lambda m: fold(m["ad"])),
        "bayiler": satirlar,
    }
    Path(cikti).parent.mkdir(parents=True, exist_ok=True)
    Path(cikti).write_text(
        SABLON.replace("__VERI__", json.dumps(veri, ensure_ascii=False,
                                              separators=(",", ":"))),
        encoding="utf-8")
    return cikti, len(satirlar), sum(1 for m in markalar if m["sayi"])


SABLON = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motosiklet Bayileri</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --kagit:#F7F6F3; --murekkep:#16202B; --celik:#5F6E7C; --hat:#E4E1DA;
  --hat2:#CFCBC2; --mavi:#1B4B9E; --vurgu:#0F5E52; --altin:#A8590C;
  --altinz:#FDF3E3;
  --d:"Familjen Grotesk",system-ui,sans-serif; --m:"DM Mono",ui-monospace,monospace;
}
*{box-sizing:border-box} html,body{margin:0}
body{background:var(--kagit);color:var(--murekkep);font-family:var(--d);
  font-size:14px;line-height:1.4;-webkit-font-smoothing:antialiased}
button,input{font:inherit;color:inherit}

.rail{background:var(--murekkep);color:#EDEAE3;padding:11px 20px;display:flex;
  align-items:center;gap:14px;flex-wrap:wrap;position:sticky;top:0;z-index:40}
.rail h1{font-size:15px;font-weight:600;margin:0;letter-spacing:.02em}
.rail .veri{font-family:var(--m);font-size:11px;color:#8B9BAA}
.sek{margin-left:auto;display:flex;gap:6px}
.sek button{background:none;border:1px solid #35404C;color:#9FB0BF;border-radius:4px;
  padding:5px 11px;cursor:pointer;font-size:12.5px}
.sek button:hover{border-color:#5A6875;color:#EDEAE3}
.sek button.aktif{background:#EDEAE3;border-color:#EDEAE3;color:var(--murekkep);font-weight:600}

.sar{max-width:660px;margin:0 auto;padding:20px 18px 60px}
.sar.genis{max-width:840px}
h2{font-size:16px;font-weight:600;margin:0 0 3px}
.notm{color:var(--celik);font-size:12.5px;margin:0 0 14px}

.ara{width:100%;border:1px solid var(--hat2);background:#fff;border-radius:5px;
  padding:7px 11px;outline:none;margin-bottom:12px;font-size:13.5px}
.ara:focus{border-color:var(--vurgu);box-shadow:0 0 0 3px rgba(15,94,82,.12)}

.plaka{display:inline-flex;align-items:stretch;height:19px;border-radius:2px;
  overflow:hidden;border:1px solid var(--murekkep);background:#fff;
  font-family:var(--m);line-height:1;flex:none}
.plaka .tr{background:var(--mavi);color:#fff;font-size:6px;display:flex;
  align-items:flex-end;justify-content:center;width:11px;padding-bottom:2px}
.plaka .kod{display:flex;align-items:center;padding:0 6px;font-size:11.5px;
  font-weight:500;letter-spacing:.04em}

.liste{background:#fff;border:1px solid var(--hat2);border-radius:6px;overflow:hidden}
.sat{display:flex;align-items:center;gap:9px;width:100%;text-align:left;background:none;
  border:0;border-bottom:1px solid var(--hat);padding:8px 12px;cursor:pointer;
  text-decoration:none;color:inherit}
.sat:last-child{border-bottom:0}
.sat:hover{background:#FFFDF6}
.sat .ad{font-weight:500;font-size:13.5px}
.sat .sag{margin-left:auto;display:flex;align-items:center;gap:9px}
.sat .men{font-family:var(--m);font-size:10px;color:var(--celik);
  text-transform:uppercase;letter-spacing:.06em}
.sat .alan{font-family:var(--m);font-size:10.5px;color:var(--celik)}
.sat .ok{color:var(--vurgu);font-size:13px;font-weight:600}
.sat .esl{font-size:10.5px;color:var(--altin);font-family:var(--m)}
.sat .sayi{font-family:var(--m);font-size:12.5px;min-width:40px;text-align:right;
  font-weight:500}
.sat .sayi.yok{color:var(--hat2);font-weight:400}
.sat.eski{background:var(--altinz)}
.sat.eski:hover{background:#FBEDD6}

/* açılan bayi listesi */
.bayiler{border-bottom:1px solid var(--hat);background:#FBFAF7;padding:2px 0}
.bayi{padding:8px 12px 8px 24px;border-bottom:1px solid var(--hat)}
.bayi:last-child{border-bottom:0}
.bayi .b1{font-weight:500;font-size:13px}
.bayi .b2{color:var(--celik);font-size:12px;margin-top:1px}
.bayi .b3{font-family:var(--m);font-size:12px;margin-top:2px}
.bayi .b3 a{color:var(--vurgu);text-decoration:none}
.bayi .b3 a:hover{text-decoration:underline}
.bayi .ilcerz{font-family:var(--m);font-size:10px;color:var(--celik);
  text-transform:uppercase;letter-spacing:.05em}
.bayi.eski{background:var(--altinz)}

.ustcubuk{display:flex;gap:9px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.geri,.kop{border:1px solid var(--hat2);background:#fff;border-radius:5px;
  padding:5px 10px;cursor:pointer;font-size:12.5px;font-weight:500}
.geri:hover,.kop:hover{border-color:var(--murekkep)}
.kop{margin-left:auto;font-weight:400;font-size:12px}
.ilbaslik{font-size:16px;font-weight:600}

.cipler{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.cip{border:1px solid var(--hat2);background:#fff;border-radius:16px;padding:4px 11px;
  cursor:pointer;font-size:12.5px}
.cip:hover{border-color:var(--murekkep)}
.cip.secili{background:var(--murekkep);border-color:var(--murekkep);color:#fff}

.bilgi{background:var(--altinz);border:1px solid #EAD9BC;color:var(--altin);
  border-radius:6px;padding:9px 12px;font-size:12.5px;margin-bottom:14px}
.bos{padding:26px;text-align:center;color:var(--celik);font-size:13px}
.baslikcubuk{display:flex;gap:10px;padding:6px 12px;font-family:var(--m);font-size:9.5px;
  letter-spacing:.09em;text-transform:uppercase;color:var(--celik);
  border-bottom:1px solid var(--hat2)}
.baslikcubuk .sagb{margin-left:auto}
.altbar{display:flex;gap:8px;margin-top:14px}
.btn{border:1px solid var(--hat2);background:#fff;border-radius:5px;padding:7px 13px;
  cursor:pointer;font-size:13px;font-weight:500}
.btn:hover{border-color:var(--murekkep)}
.btn.ana{background:var(--vurgu);border-color:var(--vurgu);color:#fff}

@media print{
  .rail,.ara,.cipler,.altbar,.geri,.kop,.sek,.bilgi{display:none!important}
  body{background:#fff;font-size:10pt}
  .liste{border:0}
  .sat{page-break-inside:avoid}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
</head>
<body>

<header class="rail">
  <h1>MOTOSİKLET BAYİLERİ</h1>
  <span class="veri" id="veriBilgi"></span>
  <nav class="sek">
    <button id="sekIl" class="aktif">İller</button>
    <button id="sekMarka">Marka Listesi</button>
  </nav>
</header>

<div class="sar" id="sar">

  <section id="vIl">
    <h2>İl seçin</h2>
    <p class="notm">Seçtiğiniz ilin markaları alt alta listelenir.</p>
    <input class="ara" id="araIl" type="search" placeholder="İl ara" autocomplete="off">
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
    <input class="ara" id="araMarka" type="search" placeholder="Marka ara" autocomplete="off">
    <div class="liste" id="markaListe"></div>
    <div class="bos" id="markaBos" style="display:none">Bu isimde marka yok.</div>
    <div class="altbar" id="altbar" style="display:none">
      <button class="btn ana" id="btnXls">Excel indir</button>
      <button class="btn" id="btnCsv">CSV</button>
      <button class="btn" id="btnYaz">Yazdır / PDF</button>
    </div>
  </section>

  <!-- MARKA DETAYI -->
  <section id="vMarkaDetay" style="display:none">
    <div class="ustcubuk">
      <button class="geri" id="geriMarka">← Marka listesi</button>
      <span class="ilbaslik" id="mdAd"></span>
    </div>
    <p class="notm" id="mdOzet"></p>
    <div class="altbar" style="margin:0 0 12px">
      <button class="btn ana" id="btnMarkaXls">Bu markayı Excel indir</button>
      <button class="btn" id="btnMarkaYaz">Yazdır / PDF</button>
    </div>
    <div class="liste" id="mdListe"></div>
  </section>

  <section id="vTumMarka" style="display:none">
    <h2>Marka listesi</h2>
    <p class="notm"><span id="mSay">0</span> marka ·
       <span id="mBayi">0</span> bayi toplam</p>
    <div class="ustcubuk">
      <button class="geri" id="sirala">Bayi sayısına göre sırala</button>
      <button class="btn ana" id="btnOzetXls">Özet tablosunu Excel indir</button>
    </div>
    <div class="bilgi" id="sayiUyari">
      <b>Bayi sayıları henüz toplanmadı.</b> Toplayıcı ilk kez çalıştığında bu sütun dolar.
    </div>
    <input class="ara" id="araTum" type="search" placeholder="Marka veya menşe ara" autocomplete="off">
    <div class="liste">
      <div class="baslikcubuk"><span>Marka</span>
        <span class="sagb" style="min-width:52px;text-align:right">İl</span>
        <span style="min-width:52px;text-align:right">Bayi</span></div>
      <div id="tumListe"></div>
    </div>
    <div class="bos" id="tumBos" style="display:none">Sonuç yok.</div>
  </section>

</div>

<script>
const D = __VERI__;
const $ = s => document.querySelector(s);
const [B_MARKA,B_AD,B_IL,B_ILCE,B_ADRES,B_TEL,B_DURUM] = [0,1,2,3,4,5,6];
const esc = s => String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const kat = s => (s||"").toLocaleLowerCase("tr")
  .replace(/[çğıöşü]/g,c=>({"ç":"c","ğ":"g","ı":"i","ö":"o","ş":"s","ü":"u"}[c]))
  .replace(/[^a-z0-9]+/g," ").trim();

let IL=null, ILCE="", ACIK=new Set();
const VAR_VERI = D.bayiler.length > 0;

$("#veriBilgi").textContent = VAR_VERI
  ? `${D.bayiler.length.toLocaleString("tr-TR")} bayi · ${new Date(D.olusturma).toLocaleDateString("tr-TR")}`
  : "";
$("#mSay").textContent = D.markalar.length;
if(VAR_VERI) $("#sayiUyari").style.display="none";

/* ---------- ekranlar ---------- */
function ekran(v){
  ["vIl","vMarkalar","vTumMarka","vMarkaDetay"].forEach(x=>$("#"+x).style.display="none");
  $("#"+v).style.display="block";
  $("#sar").classList.toggle("genis", v==="vTumMarka"||v==="vMarkaDetay");
  $("#sekIl").classList.toggle("aktif", v!=="vTumMarka"&&v!=="vMarkaDetay");
  $("#sekMarka").classList.toggle("aktif", v==="vTumMarka"||v==="vMarkaDetay");
  window.scrollTo(0,0);
}
$("#sekIl").onclick    = () => ekran(IL?"vMarkalar":"vIl");
$("#sekMarka").onclick = () => { cizTum(); ekran("vTumMarka"); };
$("#geri").onclick     = () => { IL=null; ILCE=""; ACIK.clear();
                                 $("#araMarka").value=""; ekran("vIl"); };

/* ---------- iller ---------- */
function ilSayisi(ilAdi){
  return D.bayiler.reduce((n,b)=> n + (b[B_IL]===ilAdi?1:0), 0);
}
function cizIl(){
  const q = kat($("#araIl").value);
  const l = D.iller.filter(i=>!q || kat(i.ad).includes(q) || i.plaka.startsWith(q));
  $("#ilBos").style.display = l.length?"none":"block";
  $("#ilListe").innerHTML = l.map(i=>{
    const n = VAR_VERI ? ilSayisi(i.ad) : null;
    return `<button class="sat" data-slug="${i.slug}">
      <span class="plaka"><span class="tr">TR</span><span class="kod">${i.plaka}</span></span>
      <span class="ad">${esc(i.ad)}</span>
      <span class="sag">${n!==null?`<span class="sayi ${n?"":"yok"}">${n||"—"}</span>`:""}
      <span class="ok">›</span></span></button>`;}).join("");
}
$("#ilListe").onclick = e => {
  const b=e.target.closest(".sat"); if(!b) return;
  IL = D.iller.find(x=>x.slug===b.dataset.slug); ILCE=""; ACIK.clear();
  $("#kod").textContent=IL.plaka; $("#ilAdi").textContent=IL.ad;
  cizIlce(); cizMarka(); ekran("vMarkalar");
};
let z1; $("#araIl").oninput = () => { clearTimeout(z1); z1=setTimeout(cizIl,110); };

/* ---------- ilçe şeridi ---------- */
function cizIlce(){
  const l = [...new Set(D.bayiler.filter(b=>b[B_IL]===IL.ad).map(b=>b[B_ILCE]).filter(Boolean))]
    .sort((a,b)=>a.localeCompare(b,"tr"));
  $("#ilceCipler").innerHTML = l.length
    ? `<button class="cip secili" data-i="">Tüm ${esc(IL.ad)}</button>` +
      l.map(x=>`<button class="cip" data-i="${esc(x)}">${esc(x)}</button>`).join("")
    : "";
}
$("#ilceCipler").onclick = e => {
  const b=e.target.closest(".cip"); if(!b) return;
  ILCE = b.dataset.i;
  [...$("#ilceCipler").children].forEach(c=>c.classList.toggle("secili", c===b));
  cizMarka();
};

/* ---------- ilin markaları ---------- */
function bayiler(marka){
  return D.bayiler.filter(b => b[B_MARKA]===marka && b[B_IL]===IL.ad
    && (!ILCE || b[B_ILCE]===ILCE));
}
function cizMarka(){
  const q = kat($("#araMarka").value);
  const l = D.markalar.filter(m=>!q || kat(m.ad+" "+m.mensei+" "+m.alan).includes(q));
  $("#markaBos").style.display = l.length?"none":"block";

  $("#markaListe").innerHTML = l.map(m=>{
    const bs = bayiler(m.ad);
    const eski = bs.some(b=>b[B_DURUM]!=="Güncel");
    const url = m.sablon ? m.sablon.replace("{slug}",IL.slug) : m.bayi;

    if(!bs.length){
      // Bu marka bu ilde taranmamış → kendi sayfasına gönder
      return `<a class="sat" href="${esc(url)}" target="_blank" rel="noopener">
        <span class="ad">${esc(m.ad)}</span>
        ${m.esl||m.paylasim?`<span class="esl">+${(m.paylasim||[]).map(esc).join(", ")}</span>`:""}
        <span class="sag"><span class="alan">${esc(m.alan)}</span>
        <span class="ok">↗</span></span></a>`;
    }
    const acik = ACIK.has(m.ad);
    return `<button class="sat ${eski?"eski":""}" data-m="${esc(m.ad)}">
        <span class="ad">${esc(m.ad)}</span>
        <span class="sag"><span class="sayi">${bs.length}</span>
        <span class="ok">${acik?"⌄":"›"}</span></span></button>` +
      (acik ? `<div class="bayiler">${bs.map(b=>`
        <div class="bayi ${b[B_DURUM]!=="Güncel"?"eski":""}">
          <div class="b1">${esc(b[B_AD])}</div>
          <div class="b2"><span class="ilcerz">${esc(b[B_ILCE])}</span> ${esc(b[B_ADRES])}</div>
          <div class="b3">${b[B_TEL]?`<a href="tel:${esc(b[B_TEL].replace(/\s/g,""))}">${esc(b[B_TEL])}</a>`:"—"}</div>
        </div>`).join("")}</div>` : "");
  }).join("");

  $("#altbar").style.display = VAR_VERI && D.bayiler.some(b=>b[B_IL]===IL.ad)
    ? "flex" : "none";
}
$("#markaListe").onclick = e => {
  const b=e.target.closest("button.sat"); if(!b) return;
  const m=b.dataset.m;
  ACIK.has(m) ? ACIK.delete(m) : ACIK.add(m);
  cizMarka();
};
let z2; $("#araMarka").oninput = () => { clearTimeout(z2); z2=setTimeout(cizMarka,110); };

$("#kopyala").onclick = async () => {
  try{ await navigator.clipboard.writeText(IL.ad); $("#kopyala").textContent="Kopyalandı ✓"; }
  catch{ $("#kopyala").textContent="Kopyalanamadı"; }
  setTimeout(()=>$("#kopyala").textContent="İl adını kopyala",1700);
};

/* ---------- marka özeti ---------- */
const OZET = (() => {
  const o = {};
  D.markalar.forEach(m => o[m.ad] = {ad:m.ad, mensei:m.mensei, alan:m.alan,
                                     bayi:0, iller:new Set(), ilceler:new Set(),
                                     bayi_link:m.bayi, tazelik:m.tazelik||""});
  D.bayiler.forEach(b => {
    const x = o[b[B_MARKA]]; if(!x) return;
    x.bayi++;
    if(b[B_IL]) x.iller.add(b[B_IL]);
    if(b[B_ILCE]) x.ilceler.add(b[B_IL]+"/"+b[B_ILCE]);
  });
  return Object.values(o);
})();
$("#mBayi").textContent = D.bayiler.length.toLocaleString("tr-TR");

let SIRA = "ad";
$("#sirala").onclick = () => {
  SIRA = SIRA==="ad" ? "bayi" : "ad";
  $("#sirala").textContent = SIRA==="bayi"
    ? "Alfabetik sırala" : "Bayi sayısına göre sırala";
  cizTum();
};

/* ---------- tüm markalar ---------- */
function cizTum(){
  const q = kat($("#araTum").value);
  let l = OZET.filter(m=>!q || kat(m.ad+" "+m.mensei+" "+m.alan).includes(q));
  l = SIRA==="bayi" ? [...l].sort((a,b)=>b.bayi-a.bayi || a.ad.localeCompare(b.ad,"tr"))
                    : [...l].sort((a,b)=>a.ad.localeCompare(b.ad,"tr"));
  $("#tumBos").style.display = l.length?"none":"block";
  $("#tumListe").innerHTML = l.map(m=>{
    const tikla = m.bayi > 0;
    const ic = `<span class="ad">${esc(m.ad)}</span>
      <span class="men">${esc(m.mensei)}</span>
      <span class="sag">
        <span class="sayi ${m.iller.size?"":"yok"}" style="min-width:52px">${m.iller.size||"—"}</span>
        <span class="sayi ${m.bayi?"":"yok"}" style="min-width:52px">${m.bayi||"—"}</span>
        <span class="ok">${tikla?"›":"↗"}</span></span>`;
    return tikla
      ? `<button class="sat" data-m="${esc(m.ad)}">${ic}</button>`
      : `<a class="sat" href="${esc(m.bayi_link)}" target="_blank" rel="noopener">${ic}</a>`;
  }).join("");
}
let z3; $("#araTum").oninput = () => { clearTimeout(z3); z3=setTimeout(cizTum,110); };

$("#tumListe").onclick = e => {
  const b = e.target.closest("button.sat"); if(!b) return;
  markaAc(b.dataset.m);
};

/* ---------- marka detayı ---------- */
let MD = null;
function markaAc(ad){
  MD = OZET.find(m=>m.ad===ad); if(!MD) return;
  $("#mdAd").textContent = ad;
  $("#mdOzet").textContent =
    `${MD.bayi} bayi · ${MD.iller.size} il · ${MD.ilceler.size} ilçe` +
    (MD.tazelik && MD.tazelik!=="Güncel" ? ` · ${MD.tazelik}` : "");

  const b = D.bayiler.filter(x=>x[B_MARKA]===ad);
  const gruplar = {};
  b.forEach(x => (gruplar[x[B_IL]||"— il bilinmiyor —"] ||= []).push(x));
  const iller = Object.keys(gruplar).sort((a,b)=>a.localeCompare(b,"tr"));

  $("#mdListe").innerHTML = iller.map(il=>`
    <div class="baslikcubuk" style="background:#F2F0EC">
      <span>${esc(il)}</span><span class="sagb">${gruplar[il].length} bayi</span></div>` +
    gruplar[il].map(x=>`
      <div class="bayi ${x[B_DURUM]!=="Güncel"?"eski":""}">
        <div class="b1">${esc(x[B_AD])}</div>
        <div class="b2"><span class="ilcerz">${esc(x[B_ILCE])}</span> ${esc(x[B_ADRES])}</div>
        <div class="b3">${x[B_TEL]?`<a href="tel:${esc(x[B_TEL].replace(/\s/g,""))}">${esc(x[B_TEL])}</a>`:"—"}</div>
      </div>`).join("")).join("");
  ekran("vMarkaDetay");
}
$("#geriMarka").onclick = () => { cizTum(); ekran("vTumMarka"); };
$("#btnMarkaYaz").onclick = () => window.print();

/* ---------- EXCEL ---------- */
async function xlsxYukle(){
  if(window.XLSX) return true;
  return new Promise(ok=>{
    const s=document.createElement("script");
    s.src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js";
    s.onload=()=>ok(true); s.onerror=()=>ok(false);
    document.head.appendChild(s);
  });
}

const BASLIK = ["Marka","Bayi Adı","İl","İlçe","Adres","Telefon","Veri Durumu"];
const EN     = [{wch:16},{wch:38},{wch:14},{wch:16},{wch:52},{wch:16},{wch:26}];

function sayfaEkle(wb, ad, satirlar, genislik){
  const ws = XLSX.utils.aoa_to_sheet(satirlar);
  ws["!cols"] = genislik;
  ws["!freeze"] = {xSplit:0, ySplit:1};
  // Sayfa adı: Excel 31 karakter sınırı ve bazı karakterleri kabul etmiyor
  const temiz = ad.replace(/[\\\/\?\*\[\]:]/g,"-").slice(0,31);
  XLSX.utils.book_append_sheet(wb, ws, temiz);
}

function ozetSatirlari(){
  const s = [["Marka","Menşei","Bayi Sayısı","İl Sayısı","İlçe Sayısı",
              "Veri Durumu","Kaynak Site"]];
  [...OZET].sort((a,b)=>b.bayi-a.bayi || a.ad.localeCompare(b.ad,"tr"))
    .forEach(m=>s.push([m.ad, m.mensei, m.bayi, m.iller.size, m.ilceler.size,
                        m.tazelik || (m.bayi?"Güncel":"Henüz taranmadı"), m.alan]));
  s.push([]);
  s.push(["TOPLAM","",D.bayiler.length,
          new Set(D.bayiler.map(b=>b[B_IL]).filter(Boolean)).size,
          new Set(D.bayiler.map(b=>b[B_IL]+"/"+b[B_ILCE])).size,"",""]);
  return s;
}

async function excelIndir(kapsam){
  /* kapsam: {tip:"tum"} | {tip:"marka", ad} | {tip:"bolge", il, ilce} */
  const btn = event?.target;
  const eski = btn ? btn.textContent : "";
  if(btn){ btn.disabled = true; btn.textContent = "Hazırlanıyor…"; }

  if(!(await xlsxYukle())){
    if(btn){ btn.textContent = "İnternet gerekiyor"; setTimeout(()=>{btn.textContent=eski;btn.disabled=false;},2500); }
    return;
  }

  const wb = XLSX.utils.book_new();
  let veri, ad;

  if(kapsam.tip === "marka"){
    veri = D.bayiler.filter(b=>b[B_MARKA]===kapsam.ad);
    ad = `bayiler-${kat(kapsam.ad).replace(/ /g,"-")}`;
    // İl kırılımı
    const say = {};
    veri.forEach(b => say[b[B_IL]||"—"] = (say[b[B_IL]||"—"]||0)+1);
    const kirilim = [["İl","Bayi Sayısı"]];
    Object.entries(say).sort((a,b)=>b[1]-a[1]).forEach(([k,v])=>kirilim.push([k,v]));
    kirilim.push([], ["TOPLAM", veri.length]);
    sayfaEkle(wb, "İl Kırılımı", kirilim, [{wch:20},{wch:14}]);
  } else if(kapsam.tip === "bolge"){
    veri = D.bayiler.filter(b=>b[B_IL]===kapsam.il && (!kapsam.ilce||b[B_ILCE]===kapsam.ilce));
    ad = `bayiler-${kat(kapsam.il).replace(/ /g,"")}${kapsam.ilce?"-"+kat(kapsam.ilce).replace(/ /g,""):""}`;
    const say = {};
    veri.forEach(b => say[b[B_MARKA]] = (say[b[B_MARKA]]||0)+1);
    const kirilim = [["Marka","Bayi Sayısı"]];
    Object.entries(say).sort((a,b)=>b[1]-a[1]).forEach(([k,v])=>kirilim.push([k,v]));
    kirilim.push([], ["TOPLAM", veri.length]);
    sayfaEkle(wb, "Marka Kırılımı", kirilim, [{wch:20},{wch:14}]);
  } else {
    veri = D.bayiler;
    ad = "bayiler-tum-turkiye";
    sayfaEkle(wb, "Marka Özeti", ozetSatirlari(),
      [{wch:20},{wch:16},{wch:13},{wch:11},{wch:12},{wch:26},{wch:26}]);
  }

  sayfaEkle(wb, "Bayiler", [BASLIK, ...veri], EN);

  // Her markaya ayrı sayfa — sadece "tümü" çıktısında ve veri varsa
  if(kapsam.tip === "tum"){
    const markalar = [...new Set(veri.map(b=>b[B_MARKA]))].sort((a,b)=>a.localeCompare(b,"tr"));
    markalar.forEach(m=>{
      const alt = veri.filter(b=>b[B_MARKA]===m);
      if(alt.length) sayfaEkle(wb, m, [BASLIK, ...alt], EN);
    });
  }

  const d=new Date(), pd=n=>String(n).padStart(2,"0");
  XLSX.writeFile(wb, `${ad}-${d.getFullYear()}${pd(d.getMonth()+1)}${pd(d.getDate())}.xlsx`);
  if(btn){ btn.textContent = eski; btn.disabled = false; }
}

$("#btnOzetXls").onclick  = () => excelIndir({tip:"tum"});
$("#btnMarkaXls").onclick = () => excelIndir({tip:"marka", ad:MD.ad});
$("#btnXls").onclick      = () => excelIndir({tip:"bolge", il:IL.ad, ilce:ILCE});

/* ---------- dışa aktarma ---------- */
$("#btnYaz").onclick = () => window.print();
$("#btnCsv").onclick = () => {
  const b = D.bayiler.filter(x=>x[B_IL]===IL.ad && (!ILCE || x[B_ILCE]===ILCE));
  const csv = [["Marka","Bayi","İl","İlçe","Adres","Telefon","Veri Durumu"], ...b]
    .map(r=>r.map(c=>`"${String(c??"").replace(/"/g,'""')}"`).join(";")).join("\r\n");
  const u = URL.createObjectURL(new Blob(["\uFEFF"+csv],{type:"text/csv;charset=utf-8"}));
  const a = document.createElement("a");
  a.href=u; a.download=`bayiler-${kat(IL.ad).replace(/ /g,"")}${ILCE?"-"+kat(ILCE).replace(/ /g,""):""}.csv`;
  a.click(); setTimeout(()=>URL.revokeObjectURL(u),1500);
};

cizIl();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    cikti = sys.argv[1] if len(sys.argv) > 1 else "site/index.html"
    yol, adet, markali = uret(cikti)
    print(f"✓ {yol}  ·  {adet} bayi  ·  {markali} markada veri var")
