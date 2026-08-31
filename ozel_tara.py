#!/usr/bin/env python3
"""ozel/ altındaki marka toplayıcılarını CANLI çalıştırır.

Her marka kendi modülünde; bu betik sadece istekleri atıp sonucu
veritabanına yazar. Üç gezinme biçimi var:

  tek     — tek adres, ülkenin tamamı (Falcon, Nanok, Meka, Kral, Vespa...)
  il_adi  — il adıyla adres (Zelsun, Motolux, CSN)
  il_kodu — plaka koduyla adres (Musatti)

    python ozel_tara.py                 # hepsi
    python ozel_tara.py falcon kral     # seçili
    python ozel_tara.py --kuru          # veritabanına yazma
"""

from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

import requests

from bayiradar.normalize import ILLER, fold, tr_upper
from bayiradar.parse import finalize
from bayiradar.store import commit_tarama, db, now

BASLIK = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
}

PLAKA = {ad: f"{i + 1:02d}" for i, ad in enumerate(ILLER)}

# modül -> gezinme biçimi
GEZINME = {
    "falcon": "tek", "nanok": "tek", "meka": "tek",
    "kral": "tek", "vespa": "tek", "suzuki": "tek", "isotlar": "tek",
    "zelsun": "il_adi", "motolux": "il_adi", "csn": "il_adi",
    "musatti": "il_kodu",
}

MODULLER = list(GEZINME)


def _slug(il: str) -> str:
    return fold(il).replace(" ", "-")


def _hedefler(mod_ad: str, mod) -> list[tuple[str, str, str, str]]:
    """(marka, rol, url, il) listesi döner."""
    bicim = GEZINME[mod_ad]
    out = []

    if bicim == "tek":
        # İsotlar'da anahtar marka adı, ötekilerde rol
        for anahtar, url in mod.KAYNAKLAR.items():
            if anahtar in ("Peugeot", "Horwin", "Lambretta"):
                out.append((anahtar, "hepsi", url, ""))
            else:
                out.append((mod.MARKA, anahtar, url, ""))
        return out

    for il in ILLER:
        if bicim == "il_adi":
            if mod_ad == "zelsun":
                for rol in ("satis", "servis"):
                    out.append((mod.MARKA, rol, mod.il_url(rol, tr_upper(il)), il))
            elif mod_ad == "motolux":
                out.append((mod.MARKA, "hepsi", mod.il_url(_slug(il)), il))
            elif mod_ad == "csn":
                for rol in ("satis", "servis"):
                    out.append((mod.MARKA, rol, mod.il_url(rol, _slug(il)), il))
        else:  # il_kodu
            for rol in ("satis", "servis"):
                out.append((mod.MARKA, rol, mod.il_url(rol, PLAKA[il]), il))
    return out


def marka_tara(mod_ad: str, log=print) -> dict[str, list[dict]]:
    mod = importlib.import_module(f"ozel.{mod_ad}")
    kodlama = getattr(mod, "KODLAMA", None)
    oturum = requests.Session()
    oturum.headers.update(BASLIK)

    toplam: dict[str, list[dict]] = {}
    denendi = basarili = 0
    ilk_il_kotu = 0

    for marka, rol, url, il in _hedefler(mod_ad, mod):
        denendi += 1
        try:
            y = oturum.get(url, timeout=60)
            if y.status_code >= 400:
                raise RuntimeError(f"HTTP {y.status_code}")
            govde = y.content.decode(kodlama, "replace") if kodlama else y.text
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ {marka}/{rol}/{il or '-'}: {str(e)[:50]}")
            ilk_il_kotu += 1
            if ilk_il_kotu > 12:
                log("    ✗ çok fazla hata, bu marka bırakılıyor")
                break
            continue
        basarili += 1

        try:
            ek = {}
            degiskenler = mod.coz.__code__.co_varnames[:mod.coz.__code__.co_argcount]
            if "il" in degiskenler:
                ek["il"] = il
            ham = mod.coz(rol, govde, url, **ek)
        except Exception as e:  # noqa: BLE001
            log(f"    ✗ ayrıştırma {marka}/{il}: {str(e)[:60]}")
            continue

        cfg = {"il_ilce_birlesik": "konum"} if ham and "konum" in ham[0] else {}
        for r in ham:
            k = finalize(dict(r), marka, url, cfg)
            if k:
                toplam.setdefault(marka, []).append(k)

        if il:
            time.sleep(0.25)

    kapsam = basarili / denendi if denendi else 0.0
    for marka in toplam:
        log(f"  {marka}: {len(toplam[marka])} kayıt "
            f"(kapsam %{kapsam * 100:.0f})")
    return toplam


def main() -> None:
    kuru = "--kuru" in sys.argv
    istenen = [a for a in sys.argv[1:] if not a.startswith("-")]
    moduller = istenen or MODULLER

    rapor: dict = {}
    basladi = now()

    for mod_ad in moduller:
        print(f"\n=== {mod_ad.upper()} ===")
        try:
            sonuc = marka_tara(mod_ad)
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ {type(e).__name__}: {e}")
            rapor[mod_ad] = {"hata": str(e)[:150]}
            continue

        for marka, kayitlar in sonuc.items():
            iller = {k.get("il") for k in kayitlar if k.get("il")}
            r = {"kayit": len(kayitlar), "il": len(iller),
                 "ilsiz": sum(1 for k in kayitlar if not k.get("il"))}
            if not kuru and kayitlar:
                with db() as con:
                    r["db"] = str(commit_tarama(con, marka, kayitlar, 1.0, basladi))[:180]
            rapor[marka] = r
            print(f"  → {marka}: {json.dumps(r, ensure_ascii=False)[:150]}")

    Path("ham").mkdir(exist_ok=True)
    Path("ham/ozel-tarama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n" + json.dumps(rapor, ensure_ascii=False, indent=1)[:1500])


if __name__ == "__main__":
    main()
