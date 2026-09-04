"""Falcon — tek JSON isteğiyle tüm ağ.

NEDEN ÖZEL MODÜL
Falcon tarayıcı ile ve il seçerek taranıyordu: 81 il × 2 rol = 162
sayfa yükleme. Bu 80 dakikalık sınıra takılıp her turda zaman aşımına
uğruyordu ("Falcon taranıyor has timed out after 80 minutes").

Oysa sitenin kendi JSON ucu var ve TÜM ağı tek istekte veriyor:
    https://falconmotosiklet.com/api/bayiler.php
    {"tumBayiler":[{"Unvani":..,"Il":..,"Ilce":..,"Adres":..,"Gsm":..,
                    "typeModel":{"mb":bool,"yp":bool,"ms":bool}}, ...]}

typeModel alanı rolü söylüyor:
    ms = motosiklet servisi   → servis
    mb / yp = bayi            → satış
İkisi de doğruysa satış + servis.
"""

from __future__ import annotations

import json
import re

MARKA = "Falcon"

KAYNAKLAR = {"hepsi": "https://falconmotosiklet.com/api/bayiler.php"}
TEST = {("Falcon", "hepsi"): "falcon-api.json"}


def _rol(t: dict) -> str:
    if not isinstance(t, dict):
        return "satis"
    servis = bool(t.get("ms"))
    satis = bool(t.get("mb")) or bool(t.get("yp"))
    if satis and servis:
        return "satis_servis"
    if servis:
        return "servis"
    return "satis"


def coz(rol: str, govde: str, url: str) -> list[dict]:
    # Yanıtın başında/sonunda fazladan metin olabiliyor
    m = re.search(r'\{.*"tumBayiler".*\}', govde, re.S)
    ham = m.group(0) if m else govde
    try:
        d = json.loads(ham)
    except json.JSONDecodeError:
        return []

    out: list[dict] = []
    gorulen: set[tuple] = set()
    for b in d.get("tumBayiler") or []:
        ad = (b.get("Unvani") or "").strip()
        if not ad:
            continue
        tel = (b.get("Gsm") or b.get("Tel") or "").strip()
        anahtar = (ad.casefold(), tel)
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        out.append({
            "bayi_adi": ad,
            "il": (b.get("Il") or "").strip(),
            "ilce": (b.get("Ilce") or "").strip(),
            "adres": (b.get("Adres") or "").strip(),
            "telefon": tel,
            "email": (b.get("Email") or "").strip(),
            "website": "",
            "rol": _rol(b.get("typeModel")),
        })
    return out
