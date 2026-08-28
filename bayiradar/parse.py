"""Konfigürasyondan sürülen ayrıştırıcı.

70 marka için 70 ayrı Python dosyası yazmıyoruz. Her marka brands.yaml'de
birkaç satırlık bir tarif. Kod hiç değişmiyor, sadece tarif ekleniyor.
"""

import json
import re

from bs4 import BeautifulSoup

from .normalize import (clean_phone, clean_text, fold, il_ara, resolve_il,
                         split_il_ilce, title_tr)
from .otomatik import cikar as otomatik_cikar

ALANLAR = ["bayi_adi", "il", "ilce", "adres", "telefon", "email", "website"]


# --------------------------------------------------------------------- HTML
def _pick(node, spec):
    """Tek bir alanı çıkarır.

    spec string ise CSS seçici. Dict ise:
      sel   : CSS seçici (yoksa satırın kendisi)
      attr  : metin yerine bu attribute (href, data-lat ...)
      regex : yakalanan metne uygulanacak, 1. grup alınır
      index : birden çok eşleşmede kaçıncısı (varsayılan 0)
    """
    if spec is None:
        return ""
    if isinstance(spec, str):
        spec = {"sel": spec}

    if spec.get("sel"):
        found = node.select(spec["sel"])
        if not found:
            return ""
        el = found[spec.get("index", 0)] if len(found) > spec.get("index", 0) else found[0]
    else:
        el = node

    val = el.get(spec["attr"], "") if spec.get("attr") else el.get_text(" ")
    val = clean_text(val)

    if spec.get("regex"):
        m = re.search(spec["regex"], val, re.I | re.S)
        val = (m.group(1) if m and m.groups() else (m.group(0) if m else ""))
    return clean_text(val)


def parse_html(html: str, cfg: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select(cfg["row"])
    out = []
    for r in rows:
        rec = {a: _pick(r, cfg.get("fields", {}).get(a)) for a in ALANLAR}
        # şemada olmayan yardımcı alanlar (ör. il+ilçe birleşik hücre)
        for ad, spec in (cfg.get("ekstra_alanlar") or {}).items():
            rec[ad] = _pick(r, spec)
        out.append(rec)
    return out


# --------------------------------------------------------------------- JSON
def _jget(obj, path: str):
    """'data.items[].city' benzeri basit yol. [] listeyi açar."""
    cur = obj
    for part in path.split("."):
        if not part:
            continue
        if part.endswith("[]"):
            cur = cur.get(part[:-2], []) if isinstance(cur, dict) else cur
            return cur if isinstance(cur, list) else []
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            return [(_jget(x, part) if isinstance(x, (dict, list)) else None) for x in cur]
        else:
            return None
    return cur


def parse_json(body: str, cfg: dict) -> list[dict]:
    data = json.loads(body) if isinstance(body, str) else body
    items = _jget(data, cfg["root"]) if cfg.get("root") else data
    if isinstance(items, dict):
        items = list(items.values())
    out = []
    for it in items or []:
        rec = {}
        for a in ALANLAR:
            key = cfg.get("fields", {}).get(a)
            if not key:
                rec[a] = ""
                continue
            v = _jget(it, key) if isinstance(key, str) else ""
            rec[a] = clean_text(str(v)) if v is not None else ""
        out.append(rec)
    return out


# ------------------------------------------------------------- son rötuşlar
def finalize(rec: dict, marka: str, kaynak_url: str, cfg: dict) -> dict | None:
    """Ham kaydı standart şemaya oturtur. Adı olmayan kaydı çöpe atar."""
    # il ve ilçe tek alanda geldiyse ayır
    birlesik = cfg.get("il_ilce_birlesik")
    if birlesik and rec.get(birlesik):
        il, ilce = split_il_ilce(rec[birlesik])
        rec["il"], rec["ilce"] = il or rec.get("il", ""), ilce or rec.get("ilce", "")
    elif not rec.get("il"):
        # Son çare: adres ya da ilçe alanında GERÇEK bir il adı geçiyor mu?
        # Geçmiyorsa boş bırakılır — uydurma il yazmak listeyi bozar.
        ilce_ili = il_ara(rec.get("ilce", ""))
        rec["il"] = ilce_ili or il_ara(rec.get("adres", ""))
        # "İlçe" alanında aslında il adı varsa (Rutec'te olduğu gibi) orayı
        # boşalt — yoksa "Adana / Adana" gibi anlamsız kayıt çıkıyor.
        if ilce_ili and fold(rec.get("ilce", "")) == fold(ilce_ili):
            rec["ilce"] = ""

    ad = clean_text(rec.get("bayi_adi", ""))
    if not ad:
        return None

    out = {
        "marka": marka,
        "bayi_adi": ad,
        "il": resolve_il(rec.get("il", "")),
        "ilce": title_tr(clean_text(rec.get("ilce", ""))),
        "adres": clean_text(rec.get("adres", "")),
        "telefon": clean_phone(rec.get("telefon", "")),
        "email": clean_text(rec.get("email", "")).lower(),
        "website": clean_text(rec.get("website", "")),
        "kaynak_url": kaynak_url,
    }
    if rec.get("rol"):
        out["rol"] = rec["rol"]
    return out


# --------------------------------------------------------------- OTOMATİK
def parse_oto(html: str, cfg: dict) -> list[dict]:
    """Tarif yok — yapıyı sayfadan çıkar. Ayrıntı: bayiradar/otomatik.py"""
    return otomatik_cikar(html)
