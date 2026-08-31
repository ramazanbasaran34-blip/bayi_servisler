#!/usr/bin/env python3
"""Hero — Cloudflare doğrulamasını gerçek tarayıcıyla geçip sayfa yakalar.

Düz istek 403 "Just a moment..." dönüyor; Cloudflare JS doğrulaması var.
Tarayıcıyla açıp doğrulamanın geçmesini bekliyoruz, sonra sayfayı insan
gibi kullanıyoruz: il seç → Ara'ya bas → sonucu kaydet.

Doğrulama bir kez geçildikten sonra çerez oturumda kalıyor, kalan iller
aynı sekmede hızlıca geziliyor.

    python hero_yakala.py            # örnek il (Ankara) — geliştirme için
    python hero_yakala.py --hepsi    # 81 il, tam yakalama
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CIKTI = Path("ham")
SAYFA = {
    "satis":  "https://www.heromotor.com.tr/bayiler/",
    "servis": "https://www.heromotor.com.tr/servisler/",
}
ORNEK_IL = "06"          # Ankara

KULLANICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def dogrulama_bekle(sayfa, azami=60) -> bool:
    """Cloudflare ara sayfası geçene kadar bekler.

    Bazen ilk denemede takılıyor; 20 saniyede geçmezse sayfayı yeniliyoruz.
    """
    for i in range(azami):
        if i and i % 20 == 0:
            try:
                sayfa.reload(wait_until="domcontentloaded")
            except Exception:  # noqa: BLE001
                pass
        baslik = (sayfa.title() or "").lower()
        if "just a moment" not in baslik and "attention required" not in baslik:
            try:
                sayfa.wait_for_selector("select[name=city_box]", timeout=3000)
                return True
            except Exception:  # noqa: BLE001
                pass
        sayfa.wait_for_timeout(1000)
    return False


def il_kodlari(sayfa) -> list[tuple[str, str]]:
    """(deger, ad) — <option> metni inner_text ile BOŞ döner, text_content şart."""
    return sayfa.eval_on_selector_all(
        "select[name=city_box] option",
        "els => els.map(e => [e.value, (e.textContent||'').trim()])"
        ".filter(x => x[0] && x[0] !== '0')")


def sonuc_var_mi(html: str) -> int:
    """Sayfada kaç telefon görünüyor — sonucun geldiğinin işareti."""
    return len(re.findall(
        r"0\s*\(?\d{3}\)?[\s\-/]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", html))


def il_cek(sayfa, kod: str) -> str:
    """İl seçip Ara'ya basar.

    ÖNEMLİ: form gönderildikten sonra Cloudflare doğrulaması TEKRAR
    devreye giriyor. Gönderimden sonra da beklemek şart; yoksa elimize
    "Bir dakika lütfen..." ara sayfası geçiyor.
    """
    try:
        sayfa.select_option("select[name=city_box]", value=kod)
    except Exception:  # noqa: BLE001
        sayfa.select_option("select[name=city_box]", index=1)

    basildi = False
    for sec in ("input[type=submit]", "button[type=submit]",
                "input[name=ara]", "form input[value='Ara']"):
        try:
            sayfa.click(sec, timeout=3000)
            basildi = True
            break
        except Exception:  # noqa: BLE001
            continue
    if not basildi:
        # Düğme bulunamazsa formu doğrudan gönder
        sayfa.evaluate("document.querySelector('select[name=city_box]').form.submit()")

    try:
        sayfa.wait_for_load_state("domcontentloaded", timeout=30000)
    except Exception:  # noqa: BLE001
        pass

    # Gönderim sonrası doğrulama — asıl eksik olan adım buydu
    dogrulama_bekle(sayfa, azami=40)
    sayfa.wait_for_timeout(1200)
    return sayfa.content()


def main() -> None:
    hepsi = "--hepsi" in sys.argv
    CIKTI.mkdir(exist_ok=True)
    rapor: dict = {}

    with sync_playwright() as pw:
        t = pw.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        ctx = t.new_context(user_agent=KULLANICI, locale="tr-TR",
                            viewport={"width": 1366, "height": 900})
        s = ctx.new_page()

        for rol, url in SAYFA.items():
            s.goto(url, wait_until="domcontentloaded", timeout=60000)
            if not dogrulama_bekle(s):
                rapor[rol] = {"hata": "Cloudflare doğrulaması geçilemedi"}
                print(f"  ✗ {rol}: doğrulama geçilemedi")
                continue

            iller = il_kodlari(s)
            rapor[rol] = {"il_sayisi": len(iller), "ornek_secenek": iller[:6]}
            print(f"  {rol}: doğrulama geçildi, {len(iller)} il")
            print(f"    örnek seçenekler: {iller[:6]}")

            if hepsi:
                hedefler = iller
            else:
                # Kod biçimi siteye göre değişiyor ("06" / "6" / "ANKARA");
                # bu yüzden ADA göre eşleştiriyoruz.
                hedefler = [x for x in iller if "ankara" in x[1].casefold()] or iller[:1]
            for kod, ad in hedefler:
                try:
                    html = il_cek(s, kod)
                except Exception as e:  # noqa: BLE001
                    print(f"    ✗ {ad}: {str(e)[:60]}")
                    continue
                tel = sonuc_var_mi(html)
                dosya = f"hero-{rol}-{kod}.html.gz"
                (CIKTI / dosya).write_bytes(gzip.compress(html.encode("utf-8", "replace")))
                print(f"    {ad} ({kod}): {len(html)//1024}KB tel={tel}")
                rapor[rol].setdefault("iller", {})[ad] = tel
                s.goto(url, wait_until="domcontentloaded")
                s.wait_for_timeout(400)
                time.sleep(0.3)
        ctx.close(); t.close()

    (CIKTI / "hero-yakalama.json").write_text(
        json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1)[:600])


if __name__ == "__main__":
    main()
