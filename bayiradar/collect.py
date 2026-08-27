"""Toplayıcı ve zamanlayıcı.

İki önemli davranış:

1. KAPSAM TAKİBİ. `iterate: il_kodlari` modunda 81 sayfa geziliyor. Kaçının
   başarılı olduğu sayılıyor ve depoya bildiriliyor. 81'in 60'ı geldiyse tarama
   "kısmi" sayılır ve görülmeyen bayiler pasife ÇEKİLMEZ. Bu olmadan bir ağ
   dalgalanması "Pendik'te Honda bayisi yok" sonucunu doğurur.

2. KUYRUK ZAMANLAMA. Markalar sırayla, aralarında nefes payıyla taranır.
   Sabit saat ("00:03 Yamaha") yerine kuyruk kullanılır: bir marka beklenenden
   uzun sürerse sonrakiler kaymaz, sadece geriye doğru ötelenir. Site başına
   ayrı bekleme süresi tanımlanabilir.
"""

import random
import time
from datetime import datetime, timedelta, timezone

import yaml

from .fetch import Fetcher
from .normalize import IL_KODU, ILLER, fold
from .parse import finalize, parse_html, parse_json
from .store import commit_tarama, db, marka_bilgi, now, tarama_hatasi


def load_config(path="brands.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def il_slug(ad: str) -> str:
    """'İstanbul' -> 'istanbul', 'Kahramanmaraş' -> 'kahramanmaras'"""
    return fold(ad).replace(" ", "")


def _urls_for(cfg: dict) -> list[tuple[str, str]]:
    """(url, o_url_hangi_ile_ait) çiftleri döner.

    İkinci değer, sayfada il bilgisi yazmıyorsa kayıtlara il atamak için
    kullanılır — 'il_url_den: true' diyen tarifler buna bakar.
    """
    url = cfg["url"]
    it = cfg.get("iterate")
    if not it:
        return [(url, "")]
    if it in ("il_kodlari",) or (isinstance(it, dict) and it.get("type") == "il_kodlari"):
        return [(url.format(il_kodu=k, il_adi=v, il_slug=il_slug(v)), v)
                for k, v in IL_KODU.items()]
    if it in ("il_slug", "il_adi"):
        return [(url.format(il_slug=il_slug(v), il_adi=v,
                            il_kodu=i + 1), v) for i, v in enumerate(ILLER)]
    if isinstance(it, dict) and it.get("type") == "sayfa":
        return [(url.format(sayfa=i), "")
                for i in range(it.get("baslangic", 1), it["bitis"] + 1)]
    if isinstance(it, list):
        return [(url.format(deger=d), "") for d in it]
    return [(url, "")]


def tara_marka(marka: str, cfg: dict, fetcher: Fetcher, max_age=3600):
    """Tek markayı tarar.

    Döner: (kayitlar, kapsam)  —  kapsam = başarılı URL / toplam URL
    """
    mode = cfg.get("mode", "html")
    kayitlar, gorulen = [], set()
    urls = _urls_for(cfg)
    basarili_url = 0
    ilk_hata = None

    for url, url_ili in urls:
        try:
            if mode == "browser":
                body = fetcher.render(url, cfg.get("wait_selector"), max_age=max_age)
                ham = parse_html(body, cfg)
            elif mode == "json":
                body = fetcher.get(url, method=cfg.get("method", "GET"),
                                   data=cfg.get("data"), headers=cfg.get("headers"),
                                   max_age=max_age, encoding=cfg.get("encoding"))
                ham = parse_json(body, cfg)
            else:
                body = fetcher.get(url, method=cfg.get("method", "GET"),
                                   data=cfg.get("data"), max_age=max_age,
                                   encoding=cfg.get("encoding"))
                ham = parse_html(body, cfg)
            basarili_url += 1
        except Exception as e:                                    # noqa: BLE001
            ilk_hata = ilk_hata or e
            if len(urls) == 1:
                raise RuntimeError(f"{marka}: {e}") from e
            continue          # çok sayfalı taramada devam et, ama kapsamı düşür

        for r in ham:
            # Sayfada il yazmıyorsa URL'deki ilden doldur
            if cfg.get("il_url_den") and url_ili and not r.get("il"):
                r["il"] = url_ili
            rec = finalize(r, marka, url, cfg)
            if not rec:
                continue
            imza = (rec["bayi_adi"], rec["telefon"], rec["ilce"])
            if imza in gorulen:
                continue
            gorulen.add(imza)
            kayitlar.append(rec)

    kapsam = basarili_url / len(urls) if urls else 0.0
    return kayitlar, kapsam


# ============================================================================
#  ZAMANLAMA
# ============================================================================
def tarama_gerekiyor_mu(bilgi: dict, cfg: dict) -> tuple[bool, str]:
    """Bu marka şimdi taranmalı mı? (evet_mi, gerekçe)"""
    periyot = cfg.get("periyot_saat", 24)
    son = bilgi.get("son_basarili")
    if not son:
        return True, "hiç başarılı tarama yok"

    yas = datetime.now(timezone.utc) - datetime.fromisoformat(son)

    # Son deneme hata verdiyse 24 saat bekleme, daha erken tekrar dene
    if bilgi.get("son_deneme_durum") in ("hatali", "kismi", "karantina"):
        son_deneme = bilgi.get("son_deneme")
        if son_deneme:
            bekleme_saat = min(2 ** bilgi.get("ardisik_hata", 1), 12)
            gecen = datetime.now(timezone.utc) - datetime.fromisoformat(son_deneme)
            if gecen < timedelta(hours=bekleme_saat):
                return False, f"hata sonrası {bekleme_saat} saat bekleniyor"
        return True, "önceki deneme başarısızdı, tekrar deneniyor"

    if yas >= timedelta(hours=periyot):
        return True, f"{yas.days * 24 + yas.seconds // 3600} saattir taranmadı"
    return False, f"{periyot} saatlik periyot dolmadı"


def plan_olustur(config_path="brands.yaml", db_path="bayiler.db",
                 zamanlanmis=False) -> list[dict]:
    """Tarama sırasını ve tahmini başlangıç saatlerini hesaplar.

    Sabit saat atamıyoruz. Bir marka 81 sayfa geziyorsa 20 dakika sürebilir;
    sabit saatli plan çakışır. Bunun yerine kuyruk: her marka öncekinin
    bitişinden + nefes payı kadar sonra başlar.
    """
    conf = load_config(config_path)
    ayarlar = conf.get("ayarlar", {})
    marka_arasi = ayarlar.get("marka_arasi_saniye", 180)
    varsayilan_bekleme = ayarlar.get("bekleme", 1.2)

    plan, t = [], datetime.now()
    with db(db_path) as con:
        for marka, cfg in conf.get("markalar", {}).items():
            if cfg.get("pasif"):
                continue
            bilgi = marka_bilgi(con, marka)
            gerek, sebep = tarama_gerekiyor_mu(bilgi, cfg)
            if zamanlanmis and not gerek:
                continue

            sayfa = len(_urls_for(cfg))
            bekleme = cfg.get("bekleme", varsayilan_bekleme)
            # kaba tahmin: sayfa başına bekleme + ~2 sn yanıt süresi
            tahmini_sn = sayfa * (bekleme + 2.0)
            plan.append({
                "marka": marka,
                "baslangic": t,
                "sayfa": sayfa,
                "bekleme": bekleme,
                "tahmini_dk": round(tahmini_sn / 60, 1),
                "sebep": sebep,
                "oncelik": cfg.get("oncelik", 5),
            })
            t += timedelta(seconds=tahmini_sn + marka_arasi)

    # Öncelikli markalar önce (büyük markalar gece erken saatte bitsin)
    plan.sort(key=lambda p: p["oncelik"])
    t = datetime.now()
    for p in plan:
        p["baslangic"] = t
        t += timedelta(seconds=p["tahmini_dk"] * 60 + marka_arasi)
    return plan


# ============================================================================
#  ÇALIŞTIRMA
# ============================================================================
def tara_hepsi(config_path="brands.yaml", sadece=None, db_path="bayiler.db",
               max_age=3600, zamanlanmis=False, log=print) -> dict:
    """Markaları kuyrukta, aralarında nefes payıyla tarar."""
    conf = load_config(config_path)
    ayarlar = conf.get("ayarlar", {})
    marka_arasi = ayarlar.get("marka_arasi_saniye", 180)
    varsayilan_bekleme = ayarlar.get("bekleme", 1.2)

    markalar = {k: v for k, v in conf.get("markalar", {}).items()
                if not v.get("pasif")}
    if sadece:
        markalar = {k: v for k, v in markalar.items() if k in sadece}

    ozet = {"basarili": [], "kismi": [], "karantina": [], "hatali": [],
            "atlanan": [], "toplam_kayit": 0}

    with db(db_path) as con:
        sirali = sorted(markalar.items(), key=lambda kv: kv[1].get("oncelik", 5))
        for i, (marka, cfg) in enumerate(sirali):
            if zamanlanmis:
                gerek, sebep = tarama_gerekiyor_mu(marka_bilgi(con, marka), cfg)
                if not gerek:
                    ozet["atlanan"].append((marka, sebep))
                    log(f"⏭  {marka} atlandı — {sebep}")
                    continue

            # Markalar arası nefes payı: karşı tarafa da, bize de iyi gelir
            if i > 0 and marka_arasi:
                bekle = marka_arasi + random.randint(0, 60)
                log(f"   ⏸  {bekle} sn bekleniyor...")
                time.sleep(bekle)

            fetcher = Fetcher(delay=cfg.get("bekleme", varsayilan_bekleme))
            bas = now()
            log(f"→ {marka} taranıyor...")
            try:
                kayitlar, kapsam = tara_marka(marka, cfg, fetcher, max_age)
                sonuc = commit_tarama(con, marka, kayitlar, kapsam, bas)
            except Exception as e:                                # noqa: BLE001
                sonuc = tarama_hatasi(con, marka, bas, str(e))
            finally:
                fetcher.close()
            con.commit()

            d = sonuc["durum"]
            if d == "basarili":
                ozet["basarili"].append((marka, sonuc["adet"]))
                ozet["toplam_kayit"] += sonuc["adet"]
                ek = f", {sonuc['supheli']} doğrulanamadı" if sonuc["supheli"] else ""
                log(f"  ✓ {sonuc['adet']} bayi ({sonuc['yeni']} yeni{ek})")
            elif d in ("kismi", "karantina"):
                ozet[d].append((marka, sonuc["mesaj"]))
                log(f"  ⚠ {sonuc['mesaj']} — eski veri korundu")
            else:
                ozet["hatali"].append((marka, sonuc["mesaj"]))
                log(f"  ✗ {sonuc['mesaj'][:80]} — eski veri korundu")

    return ozet
