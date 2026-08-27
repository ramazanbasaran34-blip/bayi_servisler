"""Sayfa çekme katmanı.

Üç strateji:
  http     – requests ile düz GET/POST (en hızlı, tercih edilen)
  browser  – Playwright ile gerçek tarayıcı (JS ile çizilen harita/liste için)

Nazik davranıyoruz: istekler arası bekleme, retry, gerçek User-Agent.
70 siteyi peş peşe dövmek IP ban demektir.
"""

import hashlib
import random
import time
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

CACHE_DIR = Path(".cache")


class Fetcher:
    def __init__(self, delay=1.2, timeout=25, retries=3, use_cache=True):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.use_cache = use_cache
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        })
        self._browser = None
        CACHE_DIR.mkdir(exist_ok=True)

    # ---------------------------------------------------------------- cache
    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest() + ".txt")

    def _cached(self, key: str, max_age=3600):
        if not self.use_cache:
            return None
        p = self._cache_path(key)
        if p.exists() and time.time() - p.stat().st_mtime < max_age:
            return p.read_text(encoding="utf-8")
        return None

    def _store(self, key: str, body: str):
        if self.use_cache:
            self._cache_path(key).write_text(body, encoding="utf-8")

    # ----------------------------------------------------------------- http
    def get(self, url, method="GET", data=None, headers=None, max_age=3600,
            encoding=None):
        # Yerel dosya: seçicileri internete çıkmadan test etmek için
        if not url.startswith(("http://", "https://")):
            return Path(url).read_text(encoding="utf-8")

        key = f"{method}:{url}:{data}"
        hit = self._cached(key, max_age)
        if hit is not None:
            return hit

        last = None
        for attempt in range(self.retries):
            try:
                time.sleep(self.delay + random.random() * 0.4)
                r = self.session.request(
                    method, url, data=data, headers=headers,
                    timeout=self.timeout,
                )
                r.raise_for_status()
                # Türk siteleri sık sık windows-1254 kullanır ve bunu doğru
                # bildirmez; yanlış kodlama "İstanbul" yerine "�stanbul" verir.
                r.encoding = encoding or r.apparent_encoding or r.encoding
                self._store(key, r.text)
                return r.text
            except Exception as e:          # noqa: BLE001
                last = e
                time.sleep(2 ** attempt)
        raise RuntimeError(f"{url} çekilemedi: {last}")

    # -------------------------------------------------------------- browser
    def render(self, url, wait_selector=None, wait_ms=2500, max_age=3600):
        """JS ile dolan sayfalar için. Playwright kurulu değilse anlaşılır hata verir."""
        key = f"RENDER:{url}"
        hit = self._cached(key, max_age)
        if hit is not None:
            return hit
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:
            raise RuntimeError(
                "Bu marka için tarayıcı gerekiyor. Kurulum:\n"
                "  pip install playwright && playwright install chromium"
            ) from e

        if self._browser is None:
            self._pw = sync_playwright().start()
            try:
                self._browser = self._pw.chromium.launch(headless=True)
            except Exception:
                # Chromium indirilmemişse bir kez kendisi kursun. İş akışındaki
                # kurulum adımı atlanmış olabilir; buna bağlı kalmıyoruz.
                import subprocess
                import sys as _sys
                subprocess.run([_sys.executable, "-m", "playwright",
                                "install", "--with-deps", "chromium"],
                               check=False, timeout=600)
                self._browser = self._pw.chromium.launch(headless=True)
        page = self._browser.new_page(user_agent=UA, locale="tr-TR")
        try:
            page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=self.timeout * 1000)
            else:
                page.wait_for_timeout(wait_ms)
            html = page.content()
            self._store(key, html)
            return html
        finally:
            page.close()

    def close(self):
        if self._browser:
            self._browser.close()
            self._pw.stop()
            self._browser = None
