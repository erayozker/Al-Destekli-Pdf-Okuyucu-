# Al-Destekli-Pdf-Okuyucu-
PDF dosyalarını yükleyip görüntüleme, özetleme, arama, not alma, karşılaştırma ve OpenAI destekli soru-cevap özellikleri sunan Flask tabanlı PDF okuyucu uygulaması.


# PDF Okuyucu ve Ozetleyici

Python ile gelistirilmis basit PDF okuyucu ve ozetleyici uygulamasi.

## Kullanilan teknolojiler

- Python: Ana programlama dili.
- Flask: Web uygulamasi ve backend rotalari.
- Flask flash: Yukleme ve hata bildirimleri.
- PyMuPDF: PDF sayfalarini okuma, metin cikarma ve sayfa goruntuleme.
- Heuristic summarizer: Harici AI servisi olmadan hizli ozet ve anahtar kelime cikarma.

## Mimari

- `app.py`: Uygulama giris noktasi.
- `pdfokuyucu/__init__.py`: Flask application factory.
- `pdfokuyucu/routes.py`: HTTP route ve form akislari.
- `pdfokuyucu/repository.py`: SQLite belge gecmisi ve not kayitlari.
- `pdfokuyucu/pdf_service.py`: PDF okuma, sayfa render, tablo ve gorsel cikarma.
- `pdfokuyucu/analysis.py`: Ozetleme, anahtar kelime ve PDF karsilastirma.
- `pdfokuyucu/search.py`: Gelismis arama ve metin vurgulama.
- `pdfokuyucu/options.py`: Query/form parametrelerini parse etme.
- `pdfokuyucu/models.py`: Veri modelleri.
- `pdfokuyucu/config.py`: Sabitler ve uygulama ayarlari.
- `pdfokuyucu/ai_service.py`: OpenAI ozetleme, PDF soru-cevap ve semantik arama.

## OpenAI ayarlari

AI ozellikleri icin ortam degiskeni gerekir:

```bash
set OPENAI_API_KEY=sk-...
```

Istege bagli model ayarlari:

```bash
set OPENAI_MODEL=gpt-5.2
set OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

`OPENAI_API_KEY` yoksa uygulama calismaya devam eder; AI ozet ve soru-cevap bolumleri durum mesaji gosterir, semantik arama ise leksik yedek arama moduna duser.

## Ozellikler

- PDF yukleme ve sayfa sayfa goruntuleme.
- PDF metninden otomatik ozet ve anahtar kelime cikarma.
- PDF icinde kelime veya ifade arama.
- Arama sonuclarindan ilgili sayfaya gecme ve sayfa metninde eslesmeleri vurgulama.
- Koyu/acik tema secimi.
- Sayfa numarasina dogrudan gitme.
- PDF dosya adi, boyutu ve yuklenme tarihi bilgisi.
- Kisa, orta ve detayli ozet secimi.
- Anahtar kelime sayisini belirleme.
- PDF sayfasini yakinlastirma ve kucultme.
- Son yuklenen belgeleri gecici listede gorme.
- Gelismis arama: buyuk/kucuk harf duyarliligi, tam kelime, coklu kelime ve sayfa araligi.
- Sol tarafta sayfa kucuk resimleri ile hizli gezinme.
- Belge genel ozeti, secili sayfa ozeti, bolum/sayfa bazli ozetler ve secili metin ozeti.
- PDF icindeki tablolari cikarma ve CSV olarak indirme.
- PDF icindeki gorselleri listeleme ve indirme.
- Sayfa notlari ekleme, kaydetme ve disari aktarma.
- Iki PDF karsilastirma, metin farklarini ve ortak anahtar kelimeleri gorme.
- SQLite tabanli gecmis: yuklenen belgeleri kaydetme ve daha sonra tekrar acma.
- OpenAI API ile akademik, yonetici, madde madde, teknik ve cocuklara anlatir gibi AI ozetleme.
- PDF soru-cevap ve belge sohbet ekrani.
- Kaynak sayfa numarasi ve kisa alinti odakli cevaplar.
- OpenAI embeddings ile semantik arama; API yoksa leksik yedek arama.
- Tam metni veya ozeti `.txt` olarak indirme.
- Kelime ve karakter sayisi gibi belge istatistikleri.

## Daha gelismis surum icin oneriler

- OpenAI API veya yerel LLM: Daha kaliteli ozetleme, soru-cevap ve analiz.
- ChromaDB veya FAISS: PDF icinde anlamsal arama.
- FastAPI: Uygulamayi API olarak sunmak.
- PostgreSQL veya SQLite: Dosya gecmisi, kullanici kayitlari ve analizleri saklamak.
- React veya Vue: Daha ozel ve gelismis bir frontend gerekiyorsa.

## Calistirma

```bash
pip install -r requirements.txt
python app.py
