# Nabız Analiz

Depo ekipmanı için **güvenilirlik analizi** ve **bakım aralığı önerisi** (Python). [Arıza Defteri](https://github.com/ysfdurak/ariza-defteri)'nin kayıtlarından her arıza türü için şunu söyler: bu arıza bakımdan uzaklaştıkça mı artıyor (**aşınma**), zamandan bağımsız mı (**rastgele**), yoksa bakımdan hemen sonra mı çıkıyor (**erken dönem**)? Sonra ekipman tipi başına toplam duruşu en aza indiren planlı bakım aralığını hesaplar. Sonuçlar [Nabız](https://github.com/ysfdurak/nabiz)'ın "Analiz" ekranında ve A3 taslaklarında görünür.

Ticari olmayan bir portföy projesidir. Veri sentetiktir (kurgusal Yıldız Ev & Yaşam deposu). Portföyün [Python servis şablonu](https://github.com/ysfdurak/ysfdurak.com/tree/main/sablonlar/python-servis)nun ilk kullanıcısıdır.

## Neden önemli?

Planlı bakım yalnız **aşınan** arızaları önler. Rastgele bir arızada (sensör, sıkışma) bakımı sıklaştırmak arızayı azaltmaz, sadece duruş ekler. Erken dönem arızası (bakımdan sonra ayar bozulması) ise bakım işinin kendisinde sorun olduğunu gösterir. Hangi arızanın hangi sınıfta olduğunu bilmek, bakım bütçesini doğru yere koymak demektir.

## Yöntem (kısaca)

- **Güç yasası süreci (Crow-AMSAA):** Ekipman arızada yenilenmez, onarılır. Saati sıfırlayan şey planlı bakımdır. Her bakım döngüsünde arıza yoğunluğu λ(t) = (β/η)(t/η)^(β−1) varsayılır. β ve η, bütün döngülerden en çok olabilirlikle tahmin edilir. β için %90 güven aralığı profil olabilirlikle bulunur.
- **Sınıf:** Güven aralığı tamamen 1'in üstündeyse aşınma, altındaysa erken dönem, 1'i kesiyorsa rastgele sayılır. 8'den az arızada sınıf verilmez.
- **Bakım aralığı:** Periyodik bakım + minimal onarım (Barlow-Hunter). C(T) = (Cp + Σ Cr·(T/η)^β) / T en küçük yapılır. Maliyet birimi duruş dakikasıdır, plansız duruş planlıdan 2 kat pahalı sayılır.

Ayrıntı ve kör deneme sonuçları: [docs/PROJE.md](docs/PROJE.md).

## Kendi bilgisayarında dene

Python 3.13 gerekir. Arıza Defteri çalışıyor olmalı (`npm run start:dev`, 8080).

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt
ARIZA_DEFTERI_URL=http://localhost:8080 .venv/bin/python -m analiz      # http://localhost:8000/v1/ozet
.venv/bin/python -m pytest -q                                           # matematik, kör tahmin, HTTP, MCP
```

## API

| Yol | Ne döner |
| --- | --- |
| `GET /v1/guvenilirlik?tip=reach_truck` | Bütün rapor: tür başına β (güven aralığıyla), η, sınıf, ortalama duruş; tip başına bakım aralığı önerisi |
| `GET /v1/ozet` | Sınıf sayıları ve bakım aralığı önerileri |
| `GET /v1/tur/{kod}` | Tek arıza türü |
| `GET /v1/durum`, `GET /healthz` | Sürüm, son rapor zamanı |
| `POST /mcp` (anahtarla, varsayılan kapalı) | `guvenilirlik_ozeti`, `ariza_turleri`, `ariza_turu` (salt okuma) |

Rapor saatte bir yeniden hesaplanır. Arıza Defteri'ne ulaşılamazsa son rapor bir uyarıyla döner.

## Belgeler

- [Proje dokümanı](docs/PROJE.md): matematik, kararlar, kör deneme, kod turu, mülakat soruları
- [Sunucu kurulumu](docs/SUNUCU_KURULUMU.md)

## Lisans

Bu proje [PolyForm Shield 1.0.0](LICENSE.md) lisansıyla yayınlanır. Kaynak kodu açıktır, ancak resmi anlamda bir "açık kaynak" lisansı değildir. Test veri seti (`tests/veri/`) de aynı lisansa tabidir.

- **Serbest:** Kişiler, okullar ve şirketler kendi işlerinde ücretsiz kullanabilir, değiştirebilir ve kendi bilgisayarlarına ya da sunucularına kurabilir. İzin almak gerekmez.
- **Yazılı izin gerekir:** Yazılımı satmak, adını değiştirip ürün gibi sunmak ya da bununla (ücretsiz olsa bile) rakip bir ürün veya hizmet sunmak.
- **Garanti yok:** Yazılım olduğu gibi sunulur. Bağlayıcı olan İngilizce lisans metnidir.
- Üçüncü taraf bileşenler kendi lisanslarına tabidir.

Kurumunuzda kullanıyorsanız haber verirseniz sevinirim: kurulumda yardımcı olabilir, kurumunuza özel ihtiyaçları birlikte değerlendirebiliriz. Kurum içi kurulum için [docs/SUNUCU_KURULUMU.md](docs/SUNUCU_KURULUMU.md) yeterlidir: kendi arıza kayıtlarınız Arıza Defteri biçiminde olmalı (planlı bakımlar dahil). İletişim: iletisim@ysfdurak.com

### License (English)

Released under [PolyForm Shield 1.0.0](LICENSE.md). The source is available, but this is not an OSI "open source" licence. The test dataset is covered by the same licence.

- **Free:** individuals, schools and companies may use it in their own work, change it and run it on their own computers or servers. No permission needed.
- **Needs written permission:** selling it, rebranding it as a product, or providing a product or service that competes with it (even free of charge).
- **No warranty:** provided as is. The English licence text is binding.
- Third-party components keep their own licences.

Using it in your organisation? I'd be glad to hear from you: I can help with setup and look at your organisation's needs together. Contact: contact@ysfdurak.com
