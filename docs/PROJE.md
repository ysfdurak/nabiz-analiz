# Nabız Analiz: proje dokümanı

Bu doküman, kodu ben yazmamış olsam bile projeyi baştan sona anlatabilmem ve savunabilmem için tutulur. Ortak altyapı ve güvenlik: [ysfdurak.com → docs/](https://github.com/ysfdurak/ysfdurak.com/tree/main/docs) (Python için 3b bölümü). Kardeşleri: [Arıza Defteri](https://github.com/ysfdurak/ariza-defteri) (veri), [Nabız](https://github.com/ysfdurak/nabiz) (ekranlar).

Son güncelleme: 24 Kasım 2026 (V1, Nabız V2'nin parçası).

---

## 1. Bir bakışta

| | |
| --- | --- |
| **Ne** | Arıza kayıtlarından arıza türü başına güvenilirlik sınıfı (aşınma / rastgele / erken dönem) ve ekipman tipi başına bakım aralığı önerisi |
| **Kimin için** | Bakım şefi, depo yöneticisi. Ekranı Nabız'da ("Analiz" sekmesi, A3 taslakları). |
| **Dil** | Python 3.13: FastAPI, scipy, numpy, MCP Python SDK |
| **Adres** | Yalnız iç ağ: `http://nabiz-analiz:8000` |
| **Depo** | github.com/ysfdurak/nabiz-analiz **[doğrulanacak: henüz gönderilmedi]** |

## 2. Sorun ve verdiğim kararlar

**Sorun.** Depoda planlı bakım "her ekipman 30 günde bir" diye yapılır. Ama her arıza bakımla önlenmez. Hangi arızanın bakımdan etkilendiğini bilmeden bakımı sıklaştırmak duruş ekler, seyreltmek de arızayı artırır.

| Karar | Neden | Bedeli |
| --- | --- | --- |
| Ayrı bir **Python** servisi | İstatistik ve optimizasyon (scipy) Python'da doğal. Node'da elle yazmak hem uzun hem hataya açık. | İkinci bir dil, ikinci bir kurulum. Şablonla hafifletildi. |
| **Weibull değil, güç yasası süreci** | Ekipman onarılır, yenilenmez. Klasik Weibull "yenileme" varsayar ve yanlış model olur (aşağıda). | Daha az bilinen model; anlatmak gerekir. |
| Saati **planlı bakım** sıfırlar | TPM'in sorusu "planlı bakım işe yarıyor mu?" | Bakım kaydı olmayan dönem kullanılamaz |
| Tip içindeki ekipmanlar **birlikte** tahmin edilir | Tek forkliftte veri az. 8 forklift birlikte güçlü. | Ekipmanlar arası fark (yaş, kullanım) β'yı 1'e doğru çeker (kör denemede görüldü) |
| Sınıfı **güven aralığı** belirler, nokta tahmin değil | β = 1,1 bulmak "aşınma var" demek değildir; az veride tesadüf olabilir | Az veride sınıf "rastgele" kalır (ST-MTR örneği) |
| Maliyet birimi **duruş dakikası** | Para verisi yok; dakika herkesin anladığı birim | Gerçek maliyet farkı `PLANSIZ_CARPAN` ile yaklaşık |
| Dışarı açık değil, MCP Nabız'dan | Saldırı yüzeyi küçük; tek giriş noktası | Doğrudan Claude bağlantısı yok (istenirse açılır) |

## 3. Matematik: içeride gerçekte ne oluyor?

### 3.1 Neden "Weibull" değil?

Klasik Weibull analizi bir parçanın **ömrünü** modeller. Parça bozulur, yenisi takılır ve saat sıfırlanır (yenileme). Forkliftte hortum patlayınca hortum değişir ama forklift **aynı yaşta kalır**. Buna "minimal onarım" denir. Bir sonraki arızanın olasılığı, forkliftin bakımdan bu yana geçen süresine bağlıdır, son arızaya değil.

Bu durumda doğru model, arıza **yoğunluğu** zamanla değişen bir Poisson sürecidir (NHPP). En yaygın biçimi güç yasasıdır (Crow-AMSAA):

```
λ(t) = (β/η)·(t/η)^(β−1)      t: planlı bakımdan sonra geçen gün
Λ(t) = (t/η)^β                 0..t arasında beklenen arıza sayısı
```

- **β > 1:** yoğunluk zamanla artar (aşınma). Bakım saati sıfırladığı için işe yarar.
- **β = 1:** yoğunluk sabittir (rastgele). Bakım bu arızayı etkilemez.
- **β < 1:** yoğunluk başta yüksektir (erken dönem). Bakım yapılınca arıza artar: bakım işinde sorun vardır.

> **Bu yapı uygun değil, şöyle uygulanır:** "Arızalar arası süreye Weibull uydurmak" sık yapılan bir hatadır. Onarılan sistemde arızalar arası süreler bağımsız değildir. Doğrusu: zamanı bakımdan ölçmek ve süreci (NHPP) modellemek.

### 3.2 Tahmin (en çok olabilirlik)

Veri, döngülerden oluşur: her ekipmanın iki planlı bakımı arası bir döngüdür. Son döngü bugünde kesilir.

```
döngü j:  uzunluk T_j,  içindeki arızaların bakımdan sonraki günleri t_ij
log-olabilirlik:  ℓ(β, η) = N·ln β − N·β·ln η + (β−1)·Σ ln t_ij − Σ_j (T_j/η)^β
η'ya göre türev = 0  →  η^β = Σ T_j^β / N
yerine koyunca tek değişkenli "profil" ℓ(β); türevinin kökü scipy.optimize.brentq ile bulunur
```

- **Arızasız döngüler de girer.** Yalnız arızalı döngüleri almak arıza sıklığını olduğundan yüksek gösterir (η küçülür). Sonuçta bakım aralığı önerisi gereksiz yere kısalır. Test, arızasız döngü eklenince η'nın büyüdüğünü denetler.
- **Döngüler eşit uzunluktaysa** sonuç kapalı formla aynıdır: β = N / Σ ln(T/t). Test bunu da denetler. Bakım gecikince döngüler eşit olmaz, bu yüzden genel çözüm gerekir.

### 3.3 Güven aralığı

Profil olabilirlik oranı: 2·[ℓ(β̂) − ℓ(β)] ≤ χ²₁(0,90). Aralığın iki ucu yine `brentq` ile bulunur. Test, 200 benzetimde aralığın gerçeği yaklaşık %90 kapsadığını doğrular. Gözlenen kapsama %84–96 bandında, yani aralık ne dar ne geniş.

### 3.4 Bakım aralığı (Barlow-Hunter)

T günde bir planlı bakım, arada minimal onarım. Gün başına maliyet:

```
C(T) = ( Cp + Σ_k Cr_k · (T/η_k)^β_k ) / T
Cp: bir planlı bakımın ortalama süresi (dk)
Cr_k: k türü arızanın ortalama duruşu × PLANSIZ_CARPAN (varsayılan 2)
```

`scipy.optimize.minimize_scalar` ile 7–180 gün arasında en küçük değer bulunur. Tek aşınan türde analitik çözüm vardır, test sayısal sonucu onunla karşılaştırır:

```
T* = η · ( Cp / ((β−1)·Cr) )^(1/β)
```

β ≤ 1 olan türler önerilen aralığı değiştirmez: rastgele türün maliyeti T'den bağımsızdır. Hiç aşınan tür yoksa öneri üst sınıra gider ve gerekçe "bakımı sıklaştırmak arızayı azaltmaz" der.

## 4. Kör deneme: gerçeği bulabiliyor mu?

Arıza Defteri'nin üreticisinde her türün **gizli** bir β değeri var (`katalog.js` → `asinma`). Bu değer API'den verilmez. Nabız Analiz yalnız kayıtlara bakarak tahmin eder. 360 gün, 4.288 kayıt:

| Tür | Arıza | Gerçek β | Tahmin β (%90 aralık) | Sınıf | Doğru mu |
| --- | --- | --- | --- | --- | --- |
| RT-MAS direk zinciri | 95 | 2,50 | 2,51 (2,13–2,92) | aşınma | ✓ |
| KV-MTR motor | 29 | 2,20 | 1,95 (1,44–2,58) | aşınma | ✓ |
| SR-TRY klape | 46 | 2,00 | 2,17 (1,74–2,65) | aşınma | ✓ |
| FL-LAS lastik | 196 | 1,80 | 1,59 (1,42–1,76) | aşınma | ✓ |
| FL-HID hidrolik | 273 | 1,60 | 1,56 (1,42–1,71) | aşınma | ✓ |
| RT-HID hidrolik | 236 | 1,50 | 1,25 (1,13–1,39) | aşınma | ✓ |
| FL-FRN fren | 156 | 1,40 | 1,24 (1,09–1,40) | aşınma | ✓ |
| ST-MTR tabla motoru | 9 | 2,00 | 1,67 (0,95–2,65) | rastgele | ✗ (az veri) |
| RT-AYR yükseklik ayarı | 56 | 0,70 | 0,67 (0,53–0,82) | erken dönem | ✓ |
| ST-AYR gerginlik ayarı | 46 | 0,60 | 0,49 (0,38–0,61) | erken dönem | ✓ |
| SR-ACL açılış ısınması | 38 | 1,00 | 1,51 (1,17–1,91) | aşınma | ✗ (yanılgı) |
| Diğer 13 rastgele tür | 22–626 | 1,00 | 0,83–1,11 | rastgele | ✓ (13/13) |

24 türün 22'si doğru sınıflandı. İki yanılgı da öğretici:

- **ST-MTR (az veri):** Yalnız 9 arıza var, aralık 1'i kesiyor. Sistem "aşınma" demiyor. Bu doğru davranış: kanıt yetersizken iddiada bulunmamak.
- **SR-ACL (yalancı aşınma):** Açılış kaybı yalnız sabah vardiyasında (08–16) olur. Planlı bakım da sabah 9'da yapılır. Bakım gününün sabahında açılış zaten yapılmış olur, yani bakımdan hemen sonraki saatlerde bu arıza "görünmez". Zaman takvim günüyle ölçüldüğü için bu boşluk aşınma gibi okunur. **Şöyle daha iyi olur:** zamanı takvim günü yerine çalışma saatiyle (saat sayacı) ölçmek. Gerçek depoda da arıza yalnız çalışırken olur. Test bu yanılgıyı bilerek belgeliyor.
- **Tahminin 1'e doğru kayması (RT-HID 1,25 / gerçek 1,50; FL-LAS, FL-FRN):** Tip içindeki ekipmanların yaşı, kullanımı ve otonom bakım etkisi farklı. RT-03'ün cuma sorunu zamandan bağımsız ek arıza üretir. Hepsi birlikte tahmin edilince desen "sulanır". Sınıf yine doğru çıkar ama β küçük görünür. **Şöyle daha iyi olur:** ekipman başına ayrı ölçek (η) ile ortak β (hiyerarşik model).

**Bakım aralığı önerileri (aynı veri):**

| Tip | Mevcut | Önerilen | Ekipman başına yıllık arıza | Not |
| --- | --- | --- | --- | --- |
| Forklift | 30 gün | 12 gün | 229 → 200 | Hidrolik, lastik, fren aşınıyor |
| Reach truck | 30 gün | 10 gün | 208 → 181 | RT-MAS çok güçlü aşınıyor (β 2,5) |
| Sorter | 30 gün | 14 gün | 300 → 256 | SR-TRY + SR-ACL (yanılgı aralığı kısaltıyor olabilir) |
| Konveyör | 45 gün | 28 gün | 308 → 303 | Yalnız motor aşınıyor, kazanç küçük |
| Streç | 60 gün | 121 gün | 109 → 103 | Aşınma kanıtı yok: aralık uzatılabilir |

**Duyarlılık (25.11.2026, aynı veri):** Plansız duruş çarpanı değişince öneri ne kadar oynuyor? Parantezde günlük duruş maliyetindeki düşüş.

| Tip | Mevcut | ×1 | ×1,5 | ×2 (varsayılan) | ×3 | ×4 |
| --- | --- | --- | --- | --- | --- | --- |
| Forklift | 30 | 19 (%3) | 14 (%7) | 12 (%11) | 9 (%15) | 8 (%19) |
| Reach truck | 30 | 15 (%11) | 12 (%15) | 10 (%18) | 9 (%22) | 7 (%25) |
| Sorter | 30 | 19 (%5) | 16 (%8) | 14 (%11) | 12 (%14) | 11 (%16) |
| Konveyör | 45 | 38 (%0) | 32 (%1) | 28 (%2) | 24 (%4) | 21 (%5) |
| Streç | 60 | 154 (%16) | 133 (%11) | 121 (%8) | 109 (%6) | 102 (%4) |

Okuma:
- **Yön sağlam, sayı değil.** Forklift, reach truck ve sorterda her çarpanda "daha sık bakım" çıkıyor; konveyörde kazanç her durumda küçük. Yöneticiye "30 yerine 10-15 gün" diye aralık olarak sunulmalı, tek sayı olarak değil.
- **Çarpan 1 bile kısaltıyor:** Plansız duruş planlı bakımdan pahalı olmasa da aşınan türler yüzünden sık bakım kazandırıyor. Sonuç yalnız çarpan varsayımına dayanmıyor.
- **Streç dikkat:** Aşınma kanıtı yok ama öneri 102-154 gün arasında oynuyor. Sebep: sınıfı "rastgele" olan türlerin nokta tahmini β̂ 1'in biraz üstünde ve maliyete bu tahminle giriyor. **Şöyle daha iyi olur:** sınıfı rastgele olan türü β = 1 alıp hesaplamak (o zaman öneri üst sınıra gider) ya da streçte yalnız "uzatılabilir" demek. Karar senin; şimdilik nokta tahmini kullanılıyor ve gerekçe metni "aşınma görülmüyor" diyor.
- **Sınır uyarısı eklendi:** Öneri 180 günlük üst sınıra dayanırsa gerekçe artık bunun bir en iyi değer değil, sınır olduğunu söylüyor (test: `test_asinma_yoksa_aralik_uzar`).

> **Burada bir test daha yapalım:** Sorterda SR-ACL'yi (yalancı aşınma) dışarıda bırakıp öneriyi yeniden hesapla; 14 günün ne kadarı bu yanılgıdan geliyor görülür.

## 5. Kod turu

| Dosya | Ne yapar | Dikkat |
| --- | --- | --- |
| `analiz/guvenilirlik.py` | Matematik: `guc_yasasi_tahmin`, `en_iyi_aralik`, `maliyet_orani`, test için `guc_yasasi_benzet` | Saf: ağ, saat, veritabanı yok |
| `analiz/veri.py` | Kayıtlardan döngüler: bakım = sınır, arızasız döngü de girer, ilk bakımdan öncesi atılır | Zaman Türkiye saatli ISO metninden |
| `analiz/istemci.py` | Arıza Defteri'nden ana veri + ekipman başına 360 gün (toplu istek 2.000 sınırını aşabilir) | httpx, 10 sn zaman aşımı |
| `analiz/servis.py` | Raporu birleştirir, saatlik önbellek, kilit (aynı anda iki hesap yok), dış hata olursa son rapor + uyarı | Web ve MCP aynı `Analizci`'yi çağırır |
| `analiz/app.py` | FastAPI uçları + MCP + dış katman (başlıklar, hız sınırı, MCP anahtarı) | Kural içermez; şablonla aynı katman |
| `analiz/gercek_ip.py` | Node'daki `gercek-ip.js`'in Python karşılığı | |

**Python'u bilmiyorsan, okuma sırası:** önce `tests/test_guvenilirlik.py` (ne beklendiği), sonra `guvenilirlik.py` (nasıl hesaplandığı), en son `servis.py` (verinin nereden geldiği).

## 6. Sunucu ve yayın

[docs/SUNUCU_KURULUMU.md](SUNUCU_KURULUMU.md). Özetle: `kurulum-nabiz-analiz.sh`, dışarı açık değil, Nabız'a `ANALIZ_URL` yazılır. Bağımlılıklar özetle sabit (`pip install --require-hashes`), CI'da `pip-audit`.

## 7. Testler

`pytest`: 20 test, 1,5 saniye.

| Dosya | Neyi kanıtlıyor |
| --- | --- |
| `test_guvenilirlik.py` | β = 2,5 / 1 / 0,6 benzetimde geri bulunur; güven aralığı kapsaması yaklaşık %90; eşit döngüde kapalı formla aynı; az veride sınıf yok; arızasız döngü η'yı büyütür; bakım aralığı analitik çözümle aynı; aşınma yoksa aralık uzar |
| `test_veri_ve_kor_tahmin.py` | Döngü kurma kuralları; kör tahmin (5 aşınan, 2 erken, 5 rastgele tür) ve bilinen SR-ACL yanılgısı; öneriler maliyeti düşürür |
| `test_app.py` | Güvenlik başlıkları, kapalı `/docs`, 400/404/503, önbellek (5 istek → 1 hesap), hız sınırı ve sahte `X-Forwarded-For`, MCP anahtarı ve salt okuma |
| `test_gercek_ip.py` | Vekil ve Cloudflare başlık kuralları |

Örneklem (24 Kasım 2026, yerel): Arıza Defteri (360 gün) → Nabız Analiz → Nabız "Analiz" ve A3 ekranları açıldı, tablo yukarıdaki gibi. Güvenlik taraması (`tara.py --audit`, `pip-audit` dahil) temiz. Docker derlemesi **[doğrulanacak]**.

## 8. Bilinen sınırlar

- Zaman takvim günüyle ölçülüyor, çalışma saatiyle değil (SR-ACL yanılgısı).
- Tip içi farklılık β'yı 1'e çekiyor (hiyerarşik model yok).
- Bakım aralığı tüm tip için tek değer. Ekipman başına (yaşlı forklifte daha sık) öneri yok.
- Maliyet duruş dakikası. Parça ve işçilik maliyeti yok.
- Duyarlılık analizi ekranda yok (`PLANSIZ_CARPAN` sabit).

## 9. Mülakat soruları

1. **Neden Weibull değil?** Ekipman onarılıyor, yenilenmiyor. Onarılan sistemde arızalar arası süreler bağımsız değildir. Doğru model, zamanı bakımdan ölçen güç yasası sürecidir.
2. **β ne anlatıyor, yöneticiye nasıl söylersin?** "Bu arıza bakımdan uzaklaştıkça artıyor mu?" β > 1 ise evet, bakım işe yarar. β ≈ 1 ise bakım bu arızayı etkilemez, başka önlem gerekir.
3. **Az veride ne yapıyorsun?** Sınıfı nokta tahmin değil güven aralığı belirler. 9 arızalık bir türde aralık 1'i kestiği için "aşınma" demiyoruz.
4. **Modelin doğru çalıştığını nasıl bildin?** İki yolla: bilinen β ile benzetim (kapsama ~%90), ve Arıza Defteri'nin gizli β'larına karşı kör deneme (24 türün 22'si doğru; iki yanılgının nedeni biliniyor).
5. **SR-ACL neden yanlış çıktı?** Açılış kaybı yalnız sabah olur, bakım da sabah yapılır. Takvim günüyle ölçünce bakımdan hemen sonra arıza görünmez ve aşınma gibi okunur. Çözüm, zamanı çalışma saatiyle ölçmek.
6. **Bakım aralığı nasıl hesaplanıyor?** Periyodik bakım ve minimal onarım politikasında gün başına maliyet en aza indiriliyor. Tek türde analitik çözüm var, test sayısal sonucu onunla karşılaştırıyor.
7. **Neden ayrı servis, neden Python?** scipy'nin kök bulma, optimizasyon ve dağılım fonksiyonları hazır. Diğer servisler Node'da. HTTP ve MCP dil bağımsız olduğu için ikisi sorunsuz konuşuyor.
8. **Güvenlik?** Dışarı açık değil. Yine de şablondaki her önlem var: başlıklar, hız sınırı, sabit sürede anahtar karşılaştırması, özetle sabitlenmiş bağımlılıklar ve `pip-audit`.
9. **Gerçek depoda ilk ne değişirdi?** Saat sayacı verisi (çalışma saati), parça maliyeti, ekipman başına öneri.
10. **Bu sonuçla ne yapılır?** Aşınan türler bakım talimatına girer ve aralık ayarlanır. Rastgele türler kontrol listesine ve otonom bakıma gider. Erken dönem türleri için bakım sonrası kontrol yazılır. Nabız'daki A3 taslağı bunu otomatik önerir.

## 10. Kendini test et

- β = 1,15, aralık 0,92–1,40: hangi sınıf?
- Bir türün bütün arızaları bakımdan sonraki ilk 3 günde: β 1'den büyük mü küçük mü?
- `PLANSIZ_CARPAN` 2'den 4'e çıkarsa önerilen aralık kısalır mı, uzar mı?
- Arızasız döngüleri atarsak ne olur?
- Streç için öneri neden 121 gün?

Cevaplar (önce kendin dene): rastgele (aralık 1'i kesiyor) · küçük (erken dönem) · kısalır (arıza daha pahalı, daha sık bakım değer) · arıza olduğundan sık görünür (η küçülür), bakım aralığı önerisi gereksiz kısalır · aşınma kanıtı yok, bakım arızayı azaltmıyor, maliyet yalnız bakımın kendisi.

## 11. Elle yapılacak alıştırma

**Değişiklik (20 dakika):** `PLANSIZ_CARPAN` için duyarlılık. `tools/duyarlilik.py` diye küçük bir betik yaz:

1. `tests/veri/ariza-defteri-360.json.gz`'yi oku (bak: `tests/conftest.py`).
2. `Analizci(SahteKaynak(ornek), plansiz_carpan=c)` ile c = 1,5, 2, 3, 4 için raporu al.
3. Her tip için önerilen aralığı tablo olarak yazdır.

Beklenen: aşınan tiplerde çarpan büyüdükçe aralık kısalır. Sonucunu yukarıdaki duyarlılık tablosuyla karşılaştır; streçte neden değiştiğini açıklayabiliyor musun?

**5 dakikalık demo:**
1. Nabız → Analiz: RT-MAS kırmızı (aşınma), FL-AKU gri (rastgele), ST-AYR sarı (erken dönem). Güven çizgilerini göster.
2. "Neden Weibull değil" sorusunu bir cümleyle cevapla.
3. Bakım aralığı: reach truck 30 → 10 gün, streç 60 → 121 gün. Neden zıt yönler?
4. Kör deneme tablosu: 24 türün 22'si doğru, SR-ACL yanılgısının nedeni.
5. RT-MAS'ın A3 taslağı: karşı önlemde bakım aralığı önerisi otomatik geliyor.

## 12. Değişiklik günlüğü

| Tarih | Değişiklik |
| --- | --- |
| 25.11.2026 | İlk CI: çalışma bağımlılıkları da kurulur (requirements-dev yalnız pytest içeriyordu); Dependabot yalnız Python yama sürümü önerir. Plansız duruş çarpanı duyarlılık tablosu (×1-×4); üst sınıra dayanan öneri gerekçede belirtilir (+1 test kontrolü). |
| 24.11.2026 | V1: güç yasası tahmini (profil olabilirlik, %90 aralık), sınıflandırma, Barlow-Hunter bakım aralığı, Arıza Defteri istemcisi, saatlik önbellek, FastAPI + MCP (3 salt okuma aracı), güvenlik katmanı (Python şablonuyla aynı), özetle sabit bağımlılıklar, 20 test (kör deneme dahil), Docker ve kurulum betiği. Güvenlik taraması ve `pip-audit` temiz. |
