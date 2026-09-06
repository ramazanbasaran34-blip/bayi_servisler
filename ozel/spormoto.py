"""KTM ve Husqvarna — spormoto.com (Türkiye distribütörü).

NEDEN ÖZEL MODÜL
Site 2026 Eylül başında yenilendi. Bayi listesi artık HTML'de değil,
sayfaya gömülü bir JavaScript dizisinde duruyor; sayfada yalnızca o
kartların CSS'i var. Genel ayrıştırıcı kart arayıp bulamayınca KTM 68
kayıttan 9'a, Husqvarna 53'ten 19'a düştü ve düşüş koruması iki markayı
da karantinaya aldı.

İKİ AYRI KAYNAK, İKİ AYRI BİÇİM
  bayiler sayfası : <script> ... var dealers = [ {type, city, name,
                    phone, address, map}, ... ]
                    KTM'de değişken adı "dealers", Husqvarna'da
                    "hqvDealers".
  servisler sayfası: düz HTML tablo. 1. sütun şehir, 2. sütun
                    <strong>AD</strong><br>Tel: ...<br>adres

DİSTRİBÜTÖR DE BAYİDİR
type alanı üç değer alıyor: distributor, exclusive, shop. Distribütör
tek kayıt (SPORMOTO, Kadıköy/İstanbul) ve hem satış hem servis noktası;
üçü de satış noktası sayılıyor, hiçbiri elenmiyor.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

MARKALAR = ("KTM", "Husqvarna")

KAYNAKLAR = {
    "KTM": {
        "satis": "https://www.spormoto.com/ktm/bayiler/",
        "servis": "https://www.spormoto.com/ktm/ktm-servisler/",
    },
    "Husqvarna": {
        "satis": "https://www.spormoto.com/husqvarna/bayiler/",
        "servis": "https://www.spormoto.com/husqvarna/husqvarna-servisler/",
    },
}

TEST = {
    ("KTM", "satis"): "ktm-satis.html",
    ("KTM", "servis"): "ktm-servis.html",
    ("Husqvarna", "satis"): "husqvarna-satis.html",
    ("Husqvarna", "servis"): "husqvarna-servis.html",
}

# var dealers = [...]  /  var hqvDealers = [...]
_DIZI = re.compile(
    r"(?:var|const|let)\s+\w*[Dd]ealers\s*=\s*\[(.*?)\]\s*;", re.S)
_KAYIT = re.compile(r"\{(.*?)\}", re.S)
_TEL_ETIKET = re.compile(r"^\s*tel\s*[:.]?\s*", re.I)
# Site bazen telefonu ve adresi TEK satıra yazıyor:
#   "Tel: 0530 063 24 41 Bahçelievler Mah. Atatürk Blv. No:187 B ..."
# Baştaki numarayı ayırıp gerisini adres sayıyoruz.
_BAS_TEL = re.compile(r"^((?:0\s*)?(?:\(\d{3}\)|\d{3,4})[\d\s()]{6,14}\d)\s*(.*)$")


def _alan(blok: str, ad: str) -> str:
    m = re.search(rf'{ad}\s*:\s*"((?:[^"\\]|\\.)*)"', blok)
    return m.group(1).replace('\\"', '"').strip() if m else ""


def _satis(govde: str) -> list[dict]:
    """Gömülü JavaScript dizisinden satış noktaları."""
    m = _DIZI.search(govde)
    if not m:
        return []
    out = []
    for k in _KAYIT.findall(m.group(1)):
        ad = _alan(k, "name")
        if not ad:
            continue
        out.append({
            "bayi_adi": ad,
            "il": _alan(k, "city"),
            "ilce": "",
            "adres": _alan(k, "address"),
            "telefon": _alan(k, "phone"),
            "email": "",
            "website": "",
            # distributor / exclusive / shop — üçü de satış noktası
            "_tip": _alan(k, "type"),
        })
    return out


def _servis(govde: str) -> list[dict]:
    """Servis sayfasındaki tablodan yetkili servisler."""
    s = BeautifulSoup(govde, "html.parser")
    out = []
    for tablo in s.find_all("table"):
        for tr in tablo.find_all("tr"):
            td = tr.find_all(["td", "th"])
            if len(td) < 2:
                continue
            il = td[0].get_text(" ", strip=True)
            if not il or il.casefold() in ("şehir", "sehir", "il"):
                continue
            # <strong>AD</strong><br>Tel: ...<br>adres
            kuvvetli = td[1].find(["strong", "b"])
            ad = kuvvetli.get_text(" ", strip=True) if kuvvetli else ""
            satirlar = [x.strip() for x in
                        td[1].get_text("\n", strip=True).split("\n") if x.strip()]
            if not ad and satirlar:
                ad = satirlar[0]
            tel, adres = "", ""
            for x in satirlar:
                if x == ad:
                    continue
                if _TEL_ETIKET.match(x):
                    kalan = _TEL_ETIKET.sub("", x).strip()
                    m = _BAS_TEL.match(kalan)
                    if m:
                        tel = m.group(1).strip()
                        if len(m.group(2)) > len(adres):
                            adres = m.group(2).strip()
                    else:
                        tel = kalan
                elif len(x) > len(adres):
                    adres = x
            if not ad:
                continue
            out.append({
                "bayi_adi": ad, "il": il, "ilce": "", "adres": adres,
                "telefon": tel, "email": "", "website": "",
            })
    return out


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    kayitlar = _servis(govde) if rol == "servis" else _satis(govde)
    for k in kayitlar:
        k.pop("_tip", None)
        k["rol"] = "servis" if rol == "servis" else "satis"
    return kayitlar
