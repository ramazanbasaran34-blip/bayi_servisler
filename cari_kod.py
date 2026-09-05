#!/usr/bin/env python3
"""Her fiziksel firmaya 4 haneli cari kod verir.

FİRMA NEDİR
Bir firma birden çok markanın bayisi olabiliyor (rekor: 14 marka).
Veritabanında her marka×nokta ayrı satır, ama fiziksel firma tek.
Aynı TELEFON + aynı İLÇE = aynı firma kabul ediliyor. Şube başka
ilçedeyse ayrı firma sayılıyor.

Ada göre eşleştirmiyoruz: 1817 firmada aynı numara farklı adla
yazılmış ("YUSUF BAĞCI" / "BAĞCI MOTOR (SEYHAN ŞB.)", ticari unvan
karşısında tabela adı). Ad güvenilmez, telefon güvenilir.

KOD BİÇİMİ
4 karakter, büyük harf + rakam (örn. "K7M2"). Karıştırılabilen
karakterler (0/O, 1/I, 5/S) alfabeden çıkarıldı.

KODLAR SABİT KALIR
Üretilen eşleme cari_kodlar.json'da saklanıyor. Betik tekrar
çalıştığında var olan firmalar kodunu korur, yalnızca yeni firmalara
kod verilir. Böylece bir bayinin kodu zamanla değişmez.

    python cari_kod.py            # eksik kodları tamamla
    python cari_kod.py --rapor    # sadece durum
"""

from __future__ import annotations

import json
import random
import sqlite3
import sys
from pathlib import Path

from ozel.tr import anahtar

DOSYA = Path("cari_kodlar.json")
DB = "bayiler.db"

# 0/O, 1/I, 5/S karışmasın diye çıkarıldı
ALFABE = "ABCDEFGHJKLMNPQRTUVWXYZ2346789"


# Şirket eklerini eleyip firmanın ayırt edici kelimelerini bırakır.
# "HAFIZLAR OTOMOTİV ... SAN VE TİC LTD ŞTİ" -> {hafizlar, otomotiv, ...}
_GENEL = {
    "san", "sanayi", "tic", "ticaret", "ltd", "limited", "sti", "sirketi",
    "as", "a", "s", "ve", "insaat", "taahhut", "turizm", "pazarlama",
    "otomotiv", "motor", "motorlu", "araclar", "motosiklet", "bisiklet",
    "nak", "nakliyat", "gida", "ith", "ihr", "dis", "ic", "grup",
}


def _ad_kelimeleri(ad: str) -> set:
    return {k for k in anahtar(ad).split()
            if len(k) > 2 and k not in _GENEL}


def _adres_kelimeleri(adres: str) -> set:
    _DOLGU = {"mah", "mahalle", "mahallesi", "cad", "cadde", "caddesi",
              "sok", "sokak", "no", "blv", "bulvar", "bulvari", "apt",
              "kat", "ic", "kapi", "sitesi", "blok", "carsi", "merkez"}
    return {k for k in anahtar(adres or "").split()
            if len(k) > 1 and k not in _DOLGU}


def ayni_adres_mi(a: str, b: str, esik: float = 0.5) -> bool:
    """Aynı yeri gösteriyor mu? Yazım farkı bölmesin diye benzerlik."""
    A, B = _adres_kelimeleri(a), _adres_kelimeleri(b)
    if not A or not B:
        return True
    if A <= B or B <= A:
        return True
    return len(A & B) / len(A | B) >= esik


def firma_anahtari(tel: str, il: str, ilce: str, ad: str,
                   adres: str = "") -> str:
    """Aynı fiziksel işyerini tanımlayan anahtar.

    Telefon güçlü kanıt AMA tek başına yetmiyor: farklı firmalar aynı
    numarayı paylaşabiliyor. Niğde'de "HAFIZLAR OTOMOTİV" ile "MERTAS
    PAZARLAMA" aynı numarayı kullanıyor ve tek firmaya iniyorlardı;
    Hafızlar'ın kartında olmadığı hâlde Hero rozeti çıkıyordu.

    Bu yüzden telefona ADIN AYIRT EDİCİ İLK KELİMESİ de ekleniyor.
    Şirket ekleri (san, tic, ltd, ştı...) sayılmıyor, böylece aynı
    firmanın farklı yazımları ("MANAVGAT MOTOR / YASİN AĞGEDİK" ile
    "YASİN AĞGEDİK") yine birleşiyor — ortak kelimeleri var.
    """
    t = "".join(c for c in (tel or "") if c.isdigit())
    t = t[-10:] if len(t) >= 10 else ""
    if t:
        # ADIN TAMAMI anahtarda: aynı işyerinin farklı yazımları ayrı
        # anahtar üretir ama main() onları AYNI koda bağlar. "Alfabetik
        # ilk kelime" denendi ve kararsız çıktı (705 grup yanlış ayrıldı):
        # bir kayıttaki fazladan kelime sırayı değiştiriyordu.
        # ADRES DE ANAHTARDA: aynı numarayı paylaşan AYRI şubeler ayrı
        # firma. CFMoto/Edremit'te Özdemir Mağazaları'nın Altınkum ve
        # Camivasat şubeleri, Bayhas Motors'un şubeleri böyle. Aynı koda
        # düşerlerse birbirine karışıyorlar.
        return (f"T:{t}|{anahtar(il)}|{anahtar(ilce)}|{anahtar(ad)}"
                f"|{anahtar(adres)[:60]}")
    # Telefonsuz kayıtlar ad + adrese göre ayrılıyor
    return f"A:{anahtar(ad)}|{anahtar(il)}|{anahtar(ilce)}|{anahtar(adres)[:60]}"


def _kod_uret(rnd: random.Random) -> str:
    return "".join(rnd.choice(ALFABE) for _ in range(4))


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    # KAPALI/KALDIRILMIŞ KAYITLAR DA KOD ALIYOR. Süzgeç varken bir bayi
    # kapandığında kodsuz kalıyordu; sonra geri açılınca yeni kod alıp
    # geçmişiyle bağı kopuyordu. Açılışta da kapanışta da kodu olsun.
    rows = [dict(r) for r in con.execute(
        "SELECT bayi_adi, il, ilce, telefon, adres FROM bayiler")]
    con.close()

    anahtarlar = {firma_anahtari(r["telefon"], r["il"], r["ilce"],
                                 r["bayi_adi"], r.get("adres", ""))
                  for r in rows}

    # ---- Aynı işyerinin farklı yazımlarını tek koda bağla ----
    #
    # Aynı telefon+il+ilçe bir "kova". Kova içinde adlar ORTAK AYIRT
    # EDİCİ KELİME taşıyorsa aynı işyeri sayılıyor:
    #   "MANAVGAT MOTOR / YASİN AĞGEDİK" ~ "YASİN AĞGEDİK"   → birleşir
    #   "HAFIZLAR OTOMOTİV"  ~  "MERTAS PAZARLAMA"           → ayrı kalır
    # İkincisi gerçek bir hataydı: Hafızlar'ın kartında Hero rozeti
    # çıkıyordu, oysa Hero bayisi olan Mertaş'tı.
    kovalar: dict[tuple, list] = {}
    for a in anahtarlar:
        if not a.startswith("T:"):
            continue
        p = a.split("|")
        kovalar.setdefault((p[0], p[1], p[2]), []).append(a)

    birlesik: dict[str, str] = {}          # anahtar -> grup temsilcisi
    for kova, uyeler in kovalar.items():
        gruplar: list[list[str]] = []      # her grup: [anahtar, ...]
        kelime: list[set] = []             # grubun kelime havuzu
        adresler: list[str] = []           # grubun temsilci adresi
        for a in sorted(uyeler):
            parca = a.split("|")
            ad = parca[3] if len(parca) > 3 else ""
            adr = parca[4] if len(parca) > 4 else ""
            k = {w for w in ad.split() if len(w) > 2 and w not in _GENEL}
            for i, hav in enumerate(kelime):
                # Ad ortak kelime taşıyor AMA adres başkaysa ayrı şube:
                # aynı koda bağlamıyoruz.
                if (not k or not hav or (k & hav)) and \
                        ayni_adres_mi(adr, adresler[i]):
                    gruplar[i].append(a)
                    kelime[i] |= k
                    break
            else:
                gruplar.append([a]); kelime.append(set(k)); adresler.append(adr)
        for g in gruplar:
            temsil = g[0]
            for a in g:
                birlesik[a] = temsil

    eslesme: dict[str, str] = {}
    if DOSYA.exists():
        eslesme = json.loads(DOSYA.read_text(encoding="utf-8"))

    # ESKİ KODLARI KORU: format değişti (ada da bakılıyor). Eski
    # "T:tel|il|ilce" anahtarının kodunu, o kovanın ilk grubuna taşı.
    for eski_a, k in list(eslesme.items()):
        if not eski_a.startswith("T:") or eski_a.count("|") != 2:
            continue
        for a, temsil in birlesik.items():
            if a.startswith(eski_a + "|") and temsil not in eslesme:
                eslesme[temsil] = k
                break

    kullanilan = set(eslesme.values())
    # Grup üyelerinin hepsi temsilcinin kodunu alacak; kod yalnızca
    # temsilciler için üretiliyor.
    temsilciler = {birlesik.get(a, a) for a in anahtarlar}
    eksik = sorted(temsilciler - set(eslesme))

    if "--rapor" in sys.argv:
        print(f"firma: {len(anahtarlar)} | kodlu: {len(anahtarlar) - len(eksik)} "
              f"| kodsuz: {len(eksik)}")
        return

    # Sabit tohum: aynı veriyle aynı kodlar
    rnd = random.Random(20260901)
    kapasite = len(ALFABE) ** 4
    if len(anahtarlar) > kapasite * 0.6:
        print(f"UYARI: {len(anahtarlar)} firma, 4 haneli kod kapasitesi "
              f"{kapasite}. Çakışma denemeleri artabilir.")

    for a in eksik:
        for _ in range(10000):
            k = _kod_uret(rnd)
            if k not in kullanilan:
                kullanilan.add(k)
                eslesme[a] = k
                break
        else:
            raise SystemExit("kod havuzu tükendi")

    # Grup üyelerini temsilcinin koduna bağla
    for a, temsil in birlesik.items():
        if temsil in eslesme:
            eslesme[a] = eslesme[temsil]

    # Artık kullanılmayan firmaların kodunu SİLMİYORUZ: bayi geri
    # gelirse eski kodunu alsın.
    DOSYA.write_text(json.dumps(eslesme, ensure_ascii=False, indent=0,
                                sort_keys=True), encoding="utf-8")
    print(f"firma: {len(anahtarlar)} | yeni kod: {len(eksik)} "
          f"| dosyadaki toplam: {len(eslesme)}")


if __name__ == "__main__":
    main()
