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

# Kayıt türü etiketleri. Bazı siteler (Rutec gibi) her noktanın türünü
# açıkça yazıyor: "Satış Noktası", "Yetkili Servis", "Bölge Bayisi".
# Bunlar firma adı ya da ilçe DEĞİL — rol bilgisi. Ayrıştırıcı bunları
# tanımazsa "Yetkili Servis" adında bir bayi uyduruyor.
# Etiketler ASCII'ye katlanarak karşılaştırılıyor: "Satış Noktası" -> "satis noktasi".
# Doğrudan Türkçe karakterle regex yazmak kelime sınırı (\b) davranışı yüzünden
# şaşırtıyordu; katlama hem daha basit hem daha güvenilir.
TUR_ESLEME = [
    ("servis", ("yetkili servis", "servis noktasi", "teknik servis",
                "servis agi", "sadece servis", "servis merkezi",
                "authorized service", "service point")),
    ("satis_servis", ("satis ve servis", "bayi ve servis", "satis servis",
                      "satis / servis", "bayi servis", "satis+servis")),
    ("satis", ("satis noktasi", "bolge bayisi", "yetkili bayi", "yetkili satici",
               "teslimat noktasi", "showroom", "bayi", "satici", "magaza",
               "dealer", "sales point", "satis magazasi")),
]


def tur_coz(metin: str) -> str:
    """Metin bir kayıt türü etiketi mi? Öyleyse rolü döner, değilse boş.

    Rutec gibi siteler her noktanın türünü açıkça yazıyor ("Satış Noktası",
    "Yetkili Servis", "Bölge Bayisi"). Bunlar firma adı ya da ilçe DEĞİL.
    Tanınmazsa "Yetkili Servis" adında bir bayi uydurulmuş oluyor.
    """
    if not metin or len(metin) > 32:
        return ""
    from .normalize import fold
    f = fold(metin)
    if not f:
        return ""
    for rol, etiketler in TUR_ESLEME:
        for e in etiketler:
            # Tam eşleşme ya da etiketin metnin tamamını kaplaması
            if f == e or (e in f and len(f) <= len(e) + 10):
                return rol
    return ""


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


def COP_JETON(m: str) -> bool:
    """Metin gerçek bir isim mi? CSS artığı / rakam yığını değil mi?

    Honda'nın sayfasında ayrıştırıcı '243', '24d', '24h' gibi jetonları
    firma adı sanmıştı; bunlar sınıf adlarıydı.
    """
    t = m.strip()
    if len(t) < 4:
        return False
    harf = sum(1 for c in t if c.isalpha())
    if harf < 3:
        return False
    # Harf/rakam karışık kısa jetonlar ("24d", "a1b2")
    if len(t) <= 8 and re.fullmatch(r"[a-z0-9]+", t, re.I) and any(c.isdigit() for c in t):
        return False
    return True


def _ilk_telefon(m: str) -> str:
    """Birleşik yazılmış telefonlardan ilkini alır.

    Voge'de '0232 716 89 70 – 0532 396 63 73' tek alan olarak geliyordu.
    """
    e = TEL.search(m)
    return e.group(0) if e else ""


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
                rec["telefon"] = _ilk_telefon(m)
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
    from .normalize import IL_BY_FOLD, fold
    kalan, il_adaylari = [], []
    for c, m in yap:
        if id(c) in kullanildi or TEL.search(m) or ADRES.search(m):
            continue
        if len(m) < 3 or m.strip().lower().rstrip(":") in COP:
            continue
        temiz = re.sub(r"\s+", " ", m).strip()
        # Tür etiketi mi? Öyleyse rol olarak al, ad/ilçe adayı sayma.
        rol = tur_coz(temiz)
        if rol and not rec.get("rol"):
            rec["rol"] = rol
            continue
        # İl adı mı? Firma adı olamaz — il alanına yazılır.
        # (Kove'de "BALIKESİR" firma adı sanılıyordu, gerçek ad ilçeye düşüyordu.)
        if fold(temiz) in IL_BY_FOLD:
            il_adaylari.append(temiz)
            continue
        # Anlamsız jeton mu? ("243", "24d" gibi CSS artıkları)
        if not COP_JETON(temiz):
            continue
        kalan.append((c, temiz))

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

    if il_adaylari and not rec.get("il"):
        rec["il"] = il_adaylari[0]

    if not rec["telefon"] and not rec["adres"]:
        return None
    return rec


def cikar(html: str) -> list[dict]:
    """Sayfadan bayi kayıtlarını otomatik çıkarır."""
    soup = BeautifulSoup(html, "html.parser")
    for g in soup(list(GURULTU)):
        g.decompose()

    en_iyi, en_iyi_puan = [], 0.0
    for _, _, elemanlar in kaplari_bul(soup)[:5]:
        kayitlar = [r for r in (_kaydi_cikar(e) for e in elemanlar) if r]
        if len(kayitlar) < max(2, len(elemanlar) * 0.5):
            continue
        puan = _kalite(kayitlar)
        # Yeterince temizse doğrudan kabul et
        if puan >= 0.75:
            return kayitlar
        # Değilse en iyisini akılda tut, sonraki adaya bak
        if puan > en_iyi_puan:
            en_iyi, en_iyi_puan = kayitlar, puan
    # Hiçbiri temiz değilse en iyisini ver — ama çok kötüyse hiç verme.
    # Honda'da ayrıştırıcı CSS sınıf adlarını firma sanmıştı; böyle bir kap
    # artık reddediliyor ve marka 'hatali' işaretlenip eski verisi korunuyor.
    return en_iyi if en_iyi_puan >= 0.45 else []


def _kalite(kayitlar) -> float:
    """Çıkan kayıtlar ne kadar inandırıcı? 0-1 arası.

    Kaplardan hangisinin doğru olduğunu ayırt etmek için. Sadece "kaç kayıt
    çıktı" bakmak yetmiyor; çöp de kayıt gibi görünebiliyor.
    """
    if not kayitlar:
        return 0.0
    n = len(kayitlar)
    p = 0.0
    # Adı inandırıcı olanların oranı
    p += 0.45 * sum(1 for k in kayitlar if len(k["bayi_adi"]) >= 6
                    and " " in k["bayi_adi"].strip()) / n
    # Telefonu olanlar
    p += 0.25 * sum(1 for k in kayitlar if k["telefon"]) / n
    # Adresi olanlar
    p += 0.20 * sum(1 for k in kayitlar if len(k["adres"]) > 12) / n
    # Adlar birbirinden farklı mı (aynı etiket çoğaltılmamış)
    p += 0.10 * (len({k["bayi_adi"] for k in kayitlar}) / n)
    return p


# ============================================================================
#  İL DİZİNİ TESPİTİ
# ============================================================================
def il_baglantilari(html: str, temel_url: str) -> dict:
    """Sayfa bir il dizini mi? Öyleyse {il: url} döner.

    Arora (/bayiler/Ankara), Kral (/kategori/bayiler/adana) gibi siteler ana
    bayi sayfasında bayi göstermiyor; 81 ile giden bağlantı listesi sunuyor.
    Bu sayfada bayi aramak boş sonuç verir — bağlantıları izlemek gerekir.
    """
    from urllib.parse import urljoin, urlparse

    from .normalize import ILLER, fold

    soup = BeautifulSoup(html, "html.parser")
    il_fold = {fold(i): i for i in ILLER}
    il_fold["afyon"] = "Afyonkarahisar"
    il_fold["icel"] = "Mersin"
    il_fold["urfa"] = "Şanlıurfa"

    bulunan = {}
    ana_alan = urlparse(temel_url).netloc
    for a in soup.find_all("a", href=True):
        metin = fold(a.get_text(" ", strip=True))
        href = a["href"]
        # Bağlantı metni ya da adresin son parçası bir il adı mı?
        aday = il_fold.get(metin)
        if not aday:
            son = fold(href.rstrip("/").split("/")[-1].split("?")[0])
            aday = il_fold.get(son)
        if not aday:
            continue
        tam = urljoin(temel_url, href)
        if urlparse(tam).netloc != ana_alan:
            continue
        bulunan.setdefault(aday, tam)

    # En az 20 il varsa bu gerçekten bir dizin sayfasıdır
    return bulunan if len(bulunan) >= 20 else {}


# ============================================================================
#  GÖMÜLÜ JSON
# ============================================================================
def json_gomulu(html: str) -> list[dict]:
    """HTML içine gömülü JSON'dan bayi listesi çıkarır.

    Modern siteler (Next.js, Nuxt, Vue) veriyi __NEXT_DATA__ gibi bir script
    etiketinde gönderiyor. Sayfa görsel olarak JS ile çiziliyor ama veri
    aslında HTML'in içinde — tarayıcı açmaya gerek yok.
    """
    import json as _json

    from .koordinat import en_yakin_il, turkiyede_mi

    ADAY_ANAHTAR = ("phone", "telefon", "tel", "gsm", "phonenumber", "telephone")
    ADRES_ANAHTAR = ("address", "adres", "adres1", "street", "addressline1")
    LAT_ANAHTAR = ("lat", "latitude", "enlem", "y")
    LNG_ANAHTAR = ("lng", "lon", "long", "longitude", "boylam", "x")

    def _bul(d, adaylar):
        for a in adaylar:
            for k, v in d.items():
                if k.lower() == a and v not in (None, ""):
                    return v
        return None

    def kayit_mi(d):
        """Bayi kaydına benziyor mu?

        İki kalıp var:
          klasik → telefon + adres
          harita → ad + koordinat  (Yamaha, BMW gibi harita tabanlı bulucular
                   telefon vermeyebiliyor ama koordinat hep var)
        """
        if not isinstance(d, dict):
            return False
        k = {x.lower() for x in d}
        if any(a in k for a in ADAY_ANAHTAR) and any(a in k for a in ADRES_ANAHTAR):
            return True
        adli = any(a in k for a in ("name", "title", "unvan", "dealername", "firma"))
        return adli and any(a in k for a in LAT_ANAHTAR) and any(a in k for a in LNG_ANAHTAR)

    def gez(o, bulunan):
        if isinstance(o, list):
            uygun = [x for x in o if kayit_mi(x)]
            if len(uygun) >= 3:
                bulunan.append(uygun)
            for x in o:
                gez(x, bulunan)
        elif isinstance(o, dict):
            for v in o.values():
                gez(v, bulunan)

    soup = BeautifulSoup(html, "html.parser")
    kumeler = []
    for sc in soup.find_all("script"):
        ham = sc.string or sc.get_text() or ""
        if not ham or len(ham) < 60:
            continue
        for parca in re.findall(r"(\{.*\}|\[.*\])", ham, re.S)[:3]:
            try:
                gez(_json.loads(parca), kumeler)
            except Exception:
                continue

    if not kumeler:
        return []
    en_buyuk = max(kumeler, key=len)

    def al(d, adaylar):
        for a in adaylar:
            for k, v in d.items():
                if k.lower() == a and v:
                    return str(v)
        return ""

    out = []
    yurtdisi = 0
    for d in en_buyuk:
        ad = al(d, ("name", "title", "unvan", "bayi", "dealername", "firma"))
        if not ad:
            continue

        lat, lng = _bul(d, LAT_ANAHTAR), _bul(d, LNG_ANAHTAR)
        il = al(d, ("city", "il", "sehir", "province", "town"))

        # Global bulucular komşu ülke bayilerini de döndürüyor. Koordinat
        # varsa Türkiye dışındakileri burada eliyoruz.
        if lat is not None and lng is not None:
            if not turkiyede_mi(lat, lng):
                yurtdisi += 1
                continue
            if not il:
                il = en_yakin_il(lat, lng)

        # Kayıt türü alanı: rolü doğrudan kaynağından al
        rol = ""
        tur = al(d, ("type", "tur", "tür", "tip", "kategori", "category",
                     "nokta_turu", "dealertype", "pointtype"))
        if tur:
            rol = tur_coz(tur)

        # Ülke alanı varsa ona da bak
        ulke = al(d, ("country", "countrycode", "ulke", "iso"))
        if ulke and ulke.strip().lower() not in (
                "tr", "tur", "turkey", "türkiye", "turkiye", "türkei"):
            yurtdisi += 1
            continue

        kayit = {
            "bayi_adi": ad,
            "il": il or "",
            "ilce": al(d, ("district", "ilce", "county", "region")),
            "adres": al(d, ADRES_ANAHTAR),
            "telefon": al(d, ADAY_ANAHTAR),
            "email": al(d, ("email", "eposta", "mail")),
            "website": al(d, ("website", "web", "url", "site")),
        }
        if rol:
            kayit["rol"] = rol
        out.append(kayit)
    return out


# ============================================================================
#  İL SEÇİCİ KEŞFİ
# ============================================================================
def il_secicileri_bul(html: str, temel_url: str) -> list[tuple[str, str]]:
    """Sayfada il seçen bir açılır liste var mı? Varsa (url, il) çiftleri üretir.

    Neden gerekli: çoğu bayi sayfası parametresiz açıldığında listenin sadece
    bir dilimini gösteriyor. Mondial'de 390 kayıt gelirken 600 servisin hiçbiri
    gelmemişti; sebep servis sayfasına il parametresi verilmemesiydi.

    Elle her markaya parametre yazmak yerine sayfadaki <select> içinde il
    adlarını arıyoruz. Bulursak seçeneğin değerini ve alanın adını kullanarak
    81 il için adres üretiyoruz.
    """
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    from .normalize import ILLER, fold

    soup = BeautifulSoup(html, "html.parser")
    il_fold = {fold(i): i for i in ILLER}
    il_fold.update({"afyon": "Afyonkarahisar", "icel": "Mersin",
                    "mersin icel": "Mersin", "urfa": "Şanlıurfa",
                    "k maras": "Kahramanmaraş"})

    en_iyi = None
    for sec in soup.find_all("select"):
        secenekler = []
        for o in sec.find_all("option"):
            metin = fold(o.get_text(" ", strip=True))
            deger = (o.get("value") or "").strip()
            if not deger or deger.lower() in ("", "0", "-1", "sec", "seciniz"):
                continue
            il = il_fold.get(metin)
            if il:
                secenekler.append((deger, il))
        # En az 20 il tanınıyorsa bu gerçekten il seçicisidir
        if len(secenekler) >= 20:
            ad = (sec.get("name") or sec.get("id") or "").strip()
            if ad and (en_iyi is None or len(secenekler) > len(en_iyi[1])):
                en_iyi = (ad, secenekler)

    if not en_iyi:
        return []

    alan, secenekler = en_iyi
    parca = urlparse(temel_url)
    out = []
    for deger, il in secenekler:
        q = dict(parse_qsl(parca.query))
        q[alan] = deger
        out.append((urlunparse(parca._replace(query=urlencode(q))), il))
    return out
