# Motosiklet Bayileri

63 motosiklet markasının resmi sitelerindeki yetkili bayi listelerini toplar,
il/ilçe bazında birleştirir ve tek sayfada yayınlar.

**Kurulum:** [KURULUM-GITHUB.md](KURULUM-GITHUB.md) — 6 adım, 10 dakika,
bilgisayarına hiçbir şey kurulmaz.

---

## Nasıl çalışır

```
Her gece 03:00
   ↓
GitHub sunucusu brands.yaml'daki markaları sırayla gezer
   ↓
Veriyi temizler (Türkçe karakter, il/ilçe ayrıştırma, tekilleştirme)
   ↓
bayiler.db'ye yazar — hiçbir kayıt silinmez
   ↓
index.html üretilir ve yayınlanır
   ↓
https://KULLANICI-ADIN.github.io/motosiklet-bayileri/
```

## Sayfa iki modda çalışır

Bir marka **taranmışsa**, satırı açılır ve o ildeki bayilerini gösterir.
**Taranmamışsa**, satır markanın kendi bayi sayfasına götürür.

Yani sistem yarım doluyken de işe yarar. Tarif ekledikçe link satırları
gerçek listeye dönüşür.

## Veri asla silinmez

Bir markanın sitesi gece açılmazsa o markanın bayileri listeden düşmez.
Sarı işaretle "son doğrulanmış veri" olarak kalır. Detay:
[bayiradar/store.py](bayiradar/store.py) başındaki açıklama.

Dört katmanlı koruma: toptan çökme, kısmi çökme (sayfaların bir kısmı
gelmemesi), anomali eşiği (kayıt sayısının çakılması), kayıp sayacı
(bir bayi 3 sağlıklı taramada görünmezse düşmüş sayılır).

## Marka tarifi eklemek

`brands.yaml` dosyasını düzenle. Her marka 5-10 satırlık bir tarif.
Kod değişmez. Ayrıntı dosyanın başındaki açıklamada.

## Yerelde çalıştırmak (isteğe bağlı)

```bash
pip install -r requirements.txt
python cli.py tara --marka "Mondial"
python cli.py durum
python uret_index.py site/index.html
```
