"""Otomatik ayrıştırma — tarif yazmadan bayi kaydı çıkarır.

63 marka için 63 el yazması tarif sürdürülebilir değil. Bu modül sayfadaki
tekrar eden yapıyı kendisi bulur: kardeşleri aynı sınıfa sahip, içinde telefon
ve adres geçen kapları arar, en yüksek puanlıyı seçer ve alanları ayıklar.

Mükemmel değil — bazı sitelerde tutmaz, o zaman el yazması tarife düşülür.
Ama çoğu Türk bayi sayfası aynı kalıbı kullanıyor: bir kap, içinde ünvan,
ilçe, adres, telefon.

Yanlış veri üretmemek için muhafazakâr davranır: telefonu ya da adresi
olmayan kaydı atar.
"""

import re
from collections import defaultdict

from bs4 import BeautifulSoup

TEL = re.compile(r"(?:\+90|0)?[\s\(]*\d{3}[\)\s\.\-]*\d{3}[\s\.\-]*\d{2}[\s\.\-]*\d{2}"
                 r"|\b0?\d{10}\b")
ADRES = re.compile(r"\b(mah|mh|mahalle|mahallesi|cad|cd|cadde|caddesi|sok|sk|"
                   r"sokak|blv|bulv|bulvar|no\s*:|osb|sanayi|apt|plaza|iş\s*mrk)\b"
                   r"[\.\s:]", re.I)
GURULTU = {"script", "style", "noscript", "svg", "head", "meta", "link",
           "iframe", "footer", "nav"}

# Ticari ünvan işaretleri — bayi adını ilçe adından ayırmak için
TICARI = re.compile(
    r"\b(motor|motorlu|motosiklet|moto|bisiklet|oto|otomotiv|ticaret|tic|"
    r"ltd|şti|sti|san|sanayi|a\.?ş|as|koll|kollektif|grup|group|market|"
    r"merkez[iı]|servis|plaza|center|garage|garaj|makina|makine|traktör|"
    r"yedek|aksesuar|show\s*room|showroom|kardeşler|ve\s+o[gğ]ullar[iı]|"
    r"limited|anonim)\b", re.I)

# Bayi adı olamayacak metinler
COP = {"ara", "detay", "harita", "yol tarifi al", "yol tarifi", "devamı",
       "daha fazla", "iletişim", "bilgi al", "göster", "adres", "telefon",
       "tıklayınız", "detaylı bilgi", "konum", "haritada göster"}


def _sinif_anahtari(el):
    return (el.name, tuple(sorted(c for c in (el.get("class") or [])
                                  if not re.match(r"^(w|col|row)-?\d", c))))


def _puan(metin):
    p = 0
    if TEL.search(metin):
        p += 5
    if ADRES.search(metin):
        p += 4
    if 40 < len(metin) < 900:
        p += 2
    return p


def kaplari_bul(soup, en_az=3):
    """Bayi kaydına benzeyen, tekrar eden eleman gruplarını puanlayarak döner."""
    gruplar = defaultdict(list)
    for el in soup.find_all(True):
        if el.name in GURULTU or el.parent is None:
            continue
        gruplar[(id(el.parent),) + _sinif_anahtari(el)].append(el)

    adaylar = []
    for elemanlar in gruplar.values():
        if len(elemanlar) < en_az:
            continue
        metinler = [e.get_text(" ", strip=True) for e in elemanlar]
        telli = sum(1 for m in metinler if TEL.search(m))
        if telli < max(2, len(elemanlar) * 0.4):
            continue
        adaylar.append((sum(_puan(m) for m in metinler) / len(elemanlar),
                        len(elemanlar), elemanlar))
    adaylar.sort(key=lambda a: (-a[0], -a[1]))
    return adaylar


def _yapraklar(kap):
    """İçinde metinli başka eleman olmayan elemanlar."""
    out = []
    for c in kap.find_all(True):
        if c.name in GURULTU:
            continue
        if any(x.get_text(strip=True) for x in c.find_all(True)):
            continue
        m = c.get_text(" ", strip=True)
        if m and len(m) < 400:
            out.append((c, m))
    return out


def _kaydi_cikar(kap):
    """Tek bir kaptan bayi kaydı çıkarır. Çıkaramazsa None."""
    rec = {"bayi_adi": "", "il": "", "ilce": "", "adres": "",
           "telefon": "", "email": "", "website": ""}
    kullanildi = set()
    yap = _yapraklar(kap)

    # Telefon — tel: bağlantısı varsa en güvenilir
    tel = kap.select_one("a[href^='tel:']")
    if tel:
        rec["telefon"] = tel.get("href", "")[4:]
    else:
        for c, m in yap:
            if TEL.search(m):
                rec["telefon"] = TEL.search(m).group(0)
                kullanildi.add(id(c))
                break

    # E-posta
    mail = kap.select_one("a[href^='mailto:']")
    if mail:
        rec["email"] = mail.get("href", "")[7:]

    # Adres
    for c, m in yap:
        if id(c) in kullanildi:
            continue
        if ADRES.search(m) and len(m) > 15:
            rec["adres"] = re.sub(r"^\s*adres\s*[:\-]\s*", "", m, flags=re.I)
            kullanildi.add(id(c))
            break

    # Kalan adaylar: telefon/adres olmayan anlamlı metinler
    kalan = []
    for c, m in yap:
        if id(c) in kullanildi or TEL.search(m) or ADRES.search(m):
            continue
        if len(m) < 3 or m.strip().lower().rstrip(":") in COP:
            continue
        kalan.append((c, re.sub(r"\s+", " ", m).strip()))

    # Bayi adı ile ilçeyi ayır.
    #
    # Uzunluk tek başına yetmiyor: "EYÜP SULTAN" (ilçe) ile "Ctn Motor" (bayi)
    # örneğinde uzun olan ilçeydi. Daha güvenilir ayraç: bayi adları neredeyse
    # her zaman bir ticari kelime içerir, ilçe adları hiç içermez.
    if not kalan:
        return None

    ticari = [(c, m) for c, m in kalan if TICARI.search(m)]
    if len(ticari) == 1:
        rec["bayi_adi"] = ticari[0][1]
        digerleri = [m for c, m in kalan if c is not ticari[0][0]]
    else:
        # Ticari kelime yok ya da birden çok var → uzunluğa düş
        sirali = sorted(kalan, key=lambda x: -len(x[1]))
        rec["bayi_adi"] = sirali[0][1]
        digerleri = [m for _, m in sirali[1:]]

    # İlçe: kalanlar içinde kısa ve ticari kelime içermeyen
    for m in digerleri:
        if len(m) <= 30 and not TICARI.search(m):
            rec["ilce"] = m
            break

    if not rec["telefon"] and not rec["adres"]:
        return None
    return rec


def cikar(html: str) -> list[dict]:
    """Sayfadan bayi kayıtlarını otomatik çıkarır."""
    soup = BeautifulSoup(html, "html.parser")
    for g in soup(list(GURULTU)):
        g.decompose()

    for _, _, elemanlar in kaplari_bul(soup)[:3]:
        kayitlar = [r for r in (_kaydi_cikar(e) for e in elemanlar) if r]
        # En az yarısından kayıt çıkabiliyorsa bu kap doğrudur
        if len(kayitlar) >= max(2, len(elemanlar) * 0.5):
            return kayitlar
    return []
