"""Akeso — akesomotors.com/bayilerimiz/

NEDEN ÖZEL MODÜL
Sayfa Elementor akordeonu: her İL bir açılır başlık, bayiler o başlığın
içeriğinde düz `<h2>` satırları hâlinde. Genel ayrıştırıcı kart/tablo
aradığı için hiç kayıt çıkaramıyor, marka 30 Ağustos'tan beri "hatali"
damgası alıyordu.

Yapı:
    div.elementor-accordion-item
      a.elementor-accordion-title      → İL
      div.elementor-tab-content
        <h2><strong>BAYİ ADI</strong></h2>
        <h2>adres</h2>
        <h2>Tel: +90 (5xx) ...</h2>
        <h2><strong>İKİNCİ BAYİ</strong></h2>   ← aynı ilde birden çok
        ...

Bir ilde birden çok bayi olabildiği için `<strong>` yeni kaydın
başlangıcı sayılıyor; sonraki satırlar telefon kalıbına uyuyorsa
telefon, uymuyorsa adres.

ROL
Site satış/servis ayrımı yapmıyor, tek liste veriyor; kayıtlar
kaynaktaki role (satis_servis) göre yazılıyor.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

MARKA = "Akeso"

KAYNAKLAR = {"satis_servis": "https://www.akesomotors.com/bayilerimiz/"}
TEST = {("Akeso", "satis_servis"): "m-akeso.html"}

_TEL_ETIKET = re.compile(r"^\s*(tel|telefon|gsm)\s*[:.]?\s*", re.I)
_TEL = re.compile(r"(\+?90|0)?[\s(]*\d{3}[\s)]*\d{3}[\s]*\d{2}[\s]*\d{2}")


def _sade(t: str) -> str:
    return re.sub(r"\s+", " ", (t or "")).strip()


def coz(rol: str, govde: str, url: str, il: str | None = None) -> list[dict]:
    s = BeautifulSoup(govde, "html.parser")
    out: list[dict] = []

    for kutu in s.select("div.elementor-accordion-item"):
        baslik = kutu.select_one("a.elementor-accordion-title")
        sehir = _sade(baslik.get_text(" ", strip=True)) if baslik else ""
        icerik = kutu.select_one("div.elementor-tab-content")
        if not icerik:
            continue

        kayit: dict | None = None
        for h in icerik.find_all(["h2", "h3", "p"]):
            metin = _sade(h.get_text(" ", strip=True))
            if not metin:
                continue
            kalin = h.find("strong") or h.find("b")
            if kalin and _sade(kalin.get_text(" ", strip=True)) == metin:
                # Yeni bayi başlıyor
                if kayit and kayit["bayi_adi"]:
                    out.append(kayit)
                kayit = {"bayi_adi": metin, "il": sehir, "ilce": "",
                         "adres": "", "telefon": "", "email": "",
                         "website": "", "rol": "satis_servis"}
                continue
            if kayit is None:
                continue
            if _TEL_ETIKET.match(metin) or (_TEL.search(metin)
                                            and len(metin) < 32):
                t = _TEL.search(_TEL_ETIKET.sub("", metin))
                if t and not kayit["telefon"]:
                    kayit["telefon"] = _sade(t.group(0))
            elif len(metin) > len(kayit["adres"]):
                kayit["adres"] = metin
        if kayit and kayit["bayi_adi"]:
            out.append(kayit)

    return out
