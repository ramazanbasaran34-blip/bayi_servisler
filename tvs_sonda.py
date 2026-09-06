#!/usr/bin/env python3
"""TVS bayi bulucusunun veri ucunu bulur.

turkiye.tvsmotor.com/tr/dealer-locator sayfası listeyi kendi içinde
tutmuyor; ayrı bir uygulamaya yönlendiriyor:
    https://location.tvsmotor.com/#/dealer-locator?country=TR

Bu uygulama verisini bir API'den çekiyor ama adres paketlenmiş JS içinde,
kaynakta düz metin geçmiyor. Sayfayı gerçek tarayıcıda açıp giden TÜM
JSON yanıtlarını kaydediyoruz; bir kez öğrenince tarama düz istekle
yapılabilir, tarayıcıya gerek kalmaz.

    python tvs_sonda.py
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")
URL = "https://location.tvsmotor.com/#/dealer-locator?country=TR"
KULLANICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def main() -> None:
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {"url": URL, "yanitlar": []}

    with sync_playwright() as pw:
        t = pw.chromium.launch()
        ctx = t.new_context(user_agent=KULLANICI, locale="tr-TR")
        s = ctx.new_page()
        sayac = {"n": 0}

        def yanit_izle(y):
            try:
                ct = (y.headers or {}).get("content-type", "")
            except Exception:                                   # noqa: BLE001
                return
            if "json" not in ct.lower():
                return
            try:
                metin = y.text()
            except Exception:                                   # noqa: BLE001
                return
            if len(metin) < 200:
                return
            sayac["n"] += 1
            ad = f"tvs-json-{sayac['n']:02d}.json"
            (CIKTI / f"{ad}.gz").write_bytes(
                gzip.compress(metin.encode("utf-8", "replace")))
            # Bayi verisi mi? İpucu alanları arıyoruz
            ipucu = [k for k in ("dealer", "latitude", "longitude", "address",
                                 "city", "phone", "outlet")
                     if k.lower() in metin.lower()[:4000]]
            rapor["yanitlar"].append({
                "dosya": ad, "url": y.url[:180], "boyut": len(metin),
                "ipucu": ipucu,
            })

        # İSTEK gövdesi de lazım: kategori (SALES/SERVICE/SPARES) burada
        # belirtiliyor ve tarama bunu taklit edecek.
        def istek_izle(i):
            if "apim.tvsmotor.com" not in i.url:
                return
            k = {"url": i.url[:200], "method": i.method}
            try:
                if i.post_data:
                    k["govde"] = i.post_data[:600]
                k["basliklar"] = {a: b for a, b in (i.headers or {}).items()
                                  if a.lower() in ("content-type", "authorization",
                                                   "x-api-key", "apikey", "origin")}
            except Exception:                                   # noqa: BLE001
                pass
            rapor.setdefault("istekler", []).append(k)

        s.on("request", istek_izle)
        s.on("response", yanit_izle)
        s.goto(URL, wait_until="networkidle", timeout=90000)
        s.wait_for_timeout(6000)

        # Servis ve Yedek Parça sekmelerine de bas: her birinin isteği
        # kaydedilsin, kategorinin nasıl gönderildiğini görelim.
        for etiket in ("Servis", "Service", "Yedek", "Spares"):
            try:
                el = s.get_by_text(etiket, exact=False).first
                if el and el.is_visible():
                    el.click(timeout=4000)
                    s.wait_for_timeout(3500)
                    rapor.setdefault("tiklanan", []).append(etiket)
            except Exception:                                   # noqa: BLE001
                continue

        icerik = s.content()
        (CIKTI / "tvs-sayfa.html.gz").write_bytes(
            gzip.compress(icerik.encode("utf-8", "replace")))
        rapor["sayfa_boyut"] = len(icerik)
        ctx.close()
        t.close()

    Path("ham/tvs-sonda.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()
