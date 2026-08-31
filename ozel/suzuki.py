"""Suzuki — servis sayfası gömülü `stores` GeoJSON.

Satış sayfası (satis.html) bayi listesi İÇERMİYOR; sadece test sürüşü ve
destek metni var (ham yakalamada telefon sayısı 2). Bu yüzden Suzuki için
yalnızca servis ağı toplanıyor; satış noktası verisi sitede yayınlanmıyor.
"""

from __future__ import annotations

from .geojson_stores import coz_stores

MARKA = "Suzuki"

KAYNAKLAR = {
    "servis": "https://www.suzuki.com.tr/tr/motosiklet/yetkili-servisler.html",
}
TEST = {
    ("Suzuki", "servis"): "suzuki-servis.html",
}


def coz(rol: str, govde: str, url: str) -> list[dict]:
    return coz_stores(rol, govde)
