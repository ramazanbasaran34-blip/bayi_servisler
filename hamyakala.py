#!/usr/bin/env python3
"""Sayfaların HAM HTTP gövdesini olduğu gibi kaydeder.

Neden ayrı bir betik: yakala.py tarayıcı DOM'unu kaydediyor ve <script>
etiketlerini siliyor (COP_ETIKET). Kuba, RKS, Kymco, BMW gibi sitelerde
bayi verisi sayfaya gömülü bir JS dizisinde duruyor — yani tam olarak
silinen yerde. Bu yüzden o markalarda yıllardır boş dosya kaydediliyordu.

Burada tarayıcı yok, JS yok, kırpma yok. Tek bir GET, gövde ne geldiyse o.
Saniyeler sürer.

    python hamyakala.py            # hepsi
    python hamyakala.py Kuba RKS   # seçili

Çıktı: ham/<ad>.<uzanti>.gz  +  ham/ozet.json
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

import requests

CIKTI = Path("ham")

# Tarayıcı gibi görün: bazı sunucular çıplak istemciye kısa sayfa veriyor.
BASLIK = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}

# ad -> (url, uzanti)
HEDEFLER: dict[str, tuple[str, str]] = {
    # --- verinin sayfaya gömülü olduğu düşünülenler ---
    "kuba":       ("https://www.kubamotor.com.tr/bayi-servis/kubamotor", "html"),
    "rks":        ("https://www.rksmotor.com.tr/bayi-servis/rksmotor.html", "html"),
    "rks-standart": ("https://www.rksmotor.com.tr/page/bayi-servis/standart-bayi-agi.html", "html"),
    "kymco":      ("https://www.kymco.com.tr/tr/satis-servis-agi.html", "html"),
    "bmw":        ("https://www.bmw-motorrad.com.tr/tr/ssl/yetkili-satici-ve-servisler.html", "html"),
    "leksas":     ("https://www.leksas.com.tr/bayi-servis/", "html"),
    "kimmi":      ("https://kimmimotor.com/servisler/", "html"),
    "csn":        ("https://csnmotor.com.tr/servis-noktalarimiz/", "html"),
    "taktas":     ("https://taktas.com.tr/servislerimiz", "html"),

    # --- doğrudan veri uçları (keşif raporundan) ---
    "nanok-api":  ("https://nanok.com.tr/api/dealers", "json"),
    "meka-maps":  ("https://www.mekamotor.com.tr/resman/uploads/maps.xml", "xml"),

    # --- Piaggio grubu: satış ve servis AYRI sayfalarda, ikisi de aynı
    #     gömülü GeoJSON yapısını kullanıyor (Kymco ile birebir aynı).
    "vespa-servis":   ("https://www.vespa.com.tr/tr/yetkili-servisler.html", "html"),
    "aprilia-servis": ("https://www.aprilia.com.tr/tr/yetkili-servisler.html", "html"),
    "piaggio-servis": ("https://www.piaggio.com.tr/tr/yetkili-servisler.html", "html"),
    "suzuki-servis":  ("https://www.suzuki.com.tr/tr/motosiklet/servis.html", "html"),

    # --- MJ Group: Kuba ve RKS'in sahibi, kendi sitelerinden link veriliyor.
    #     Kullanıcı onayıyla resmi kaynak kabul edildi (2026-08).
    "mj-kuba-bayi":   ("https://www.mj.com.tr/bayi-servis-agi/kuba-motor-bayi-agi/", "html"),
    "mj-kuba-servis": ("https://www.mj.com.tr/bayi-servis-agi/kuba-motor-servis-agi/", "html"),
    "mj-rks-bayi":    ("https://www.mj.com.tr/bayi-servis-agi/rks-motor-bayi-agi/", "html"),
    "mj-rks-servis":  ("https://www.mj.com.tr/bayi-servis-agi/rks-motor-servis-agi/", "html"),
    "mj-agi":         ("https://www.mj.com.tr/bayi-servis-agi/", "html"),
    # RKS menüsünden çıkan olası veri ucu
    "rks-services":   ("https://user.rksmotor.com.tr/services.php", "html"),

    # --- spormoto ---
    "ktm-servis":       ("https://spormoto.com/ktm/ktm-servisler/", "html"),
    "ktm-satis":        ("https://spormoto.com/ktm/bayiler/", "html"),
    "husqvarna-servis": ("https://spormoto.com/husqvarna/husqvarna-servisler/", "html"),
    "husqvarna-satis":  ("https://spormoto.com/husqvarna/bayiler/", "html"),
}

TEL = re.compile(r"0?\s*\(?5?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.S | re.I)


def yakala(ad: str, url: str, uzanti: str) -> dict:
    bilgi: dict = {"url": url}
    try:
        y = requests.get(url, headers=BASLIK, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        bilgi["hata"] = f"{type(e).__name__}: {e}"[:200]
        return bilgi

    govde = y.text
    bilgi["kod"] = y.status_code
    bilgi["son_url"] = y.url
    bilgi["boyut"] = len(govde)
    bilgi["tel_toplam"] = len(TEL.findall(govde))
    # Asıl soru: telefonlar script içinde mi? Öyleyse veri gömülü demektir.
    bilgi["tel_script_ici"] = sum(
        len(TEL.findall(s)) for s in SCRIPT.findall(govde)
    )
    if y.url != url:
        bilgi["yonlendi"] = True

    CIKTI.mkdir(exist_ok=True)
    (CIKTI / f"{ad}.{uzanti}.gz").write_bytes(
        gzip.compress(govde.encode("utf-8", "replace"))
    )
    return bilgi


def marka_hedefleri(adlar: list[str]) -> dict[str, tuple[str, str]]:
    """markalar.json'daki 'bayi' adreslerinden hedef sözlüğü üretir.

    Böylece her yeni marka için bu dosyayı elle düzenlemek gerekmiyor:
        python hamyakala.py --markalar "Hero,Musatti,Vespa"
    """
    kayit = json.loads(Path("markalar.json").read_text(encoding="utf-8"))
    tablo = {m["ad"]: m for m in kayit}
    out: dict[str, tuple[str, str]] = {}
    for ad in adlar:
        m = tablo.get(ad)
        if not m:
            print(f"  ! markalar.json'da yok: {ad}")
            continue
        anahtar = "m-" + re.sub(r"[^a-z0-9]+", "-", ad.lower()).strip("-")
        out[anahtar] = (m["bayi"], "html")
        # Ana sayfa da işe yarayabilir (bayi bağlantısı değişmiş olabilir)
        if m.get("site") and m["site"].rstrip("/") != m["bayi"].rstrip("/"):
            out[anahtar + "-ana"] = (m["site"], "html")
    return out


def main() -> None:
    argv = sys.argv[1:]
    if "--markalar" in argv:
        i = argv.index("--markalar")
        adlar = [a.strip() for a in argv[i + 1].split(",") if a.strip()]
        secili = marka_hedefleri(adlar)
    else:
        istenen = argv
        if istenen:
            secili = {k: v for k, v in HEDEFLER.items()
                      if any(a.lower() in k for a in istenen)}
        else:
            secili = HEDEFLER

    ozet: dict[str, dict] = {}
    onceki = CIKTI / "ozet.json"
    if onceki.exists():
        try:
            ozet = json.loads(onceki.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            ozet = {}
    for ad, (url, uzanti) in secili.items():
        print(f"→ {ad}", flush=True)
        b = yakala(ad, url, uzanti)
        ozet[ad] = b
        if "hata" in b:
            print(f"   ✗ {b['hata'][:80]}")
        else:
            print(f"   {b['kod']}  {b['boyut']//1024}KB  "
                  f"tel={b['tel_toplam']} (script içi {b['tel_script_ici']})"
                  + ("  [YÖNLENDİ]" if b.get("yonlendi") else ""))

    CIKTI.mkdir(exist_ok=True)
    (CIKTI / "ozet.json").write_text(
        json.dumps(ozet, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✓ {len(ozet)} hedef → {CIKTI}/")


if __name__ == "__main__":
    main()
