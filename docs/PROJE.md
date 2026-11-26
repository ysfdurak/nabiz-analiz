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

Arıza Defteri'nin üreticisinde her türün **gizli** bir β değeri var (`katalog.js` → `asinma`). Bu değer API'den verilmez. Nabız Analiz yalnız kayıtlara bakarak tahmin eder.

### 4.0 Gerçek sıklık (surum 6, 26.11.2026): önce veriyi düzelttik

surum 5'e kadar sentetik veri sahadakinin **10-20 katıydı**: forklift başına yılda ~160 kayıt (gerçekte ~10), tek bir reach truckta yılda 68 cuma hidrolik arızası. Nedeni senaryodaki `yogunluk: 3` çarpanı ve yüksek tür oranlarıydı. Analiz o veride çok iyi görünüyordu (24/24 doğru, "forklift bakımı 30 → 13 gün"), ama bu sonuçlar **şişirilmiş verinin ürünüydü**.

- **Bu yapı uygun değil, şöyle uygulanır:** Bir modeli, ancak gerçeğe benzeyen veride gösterdiği başarıyla anlat. Kolay veride %100 başarı, modelin değil verinin özelliğidir. Önce verinin sahaya uyduğunu (alan uzmanı gözüyle) doğrula, sonra modeli dene.
- Arıza Defteri surum 6'da her türün sıklığı sahadaki düzeyle gerekçelendirildi (katalogda tür başına "yılda ~N / ekipman" notu). Forklift başına yılda ~9 kayıt, bunun ~4'ü teknisyen gerektiren arıza.
- Gerçek sıklıkta **bir yıllık veri yetmiyor**: 23 türün yalnız 9'u doğru, 7'si "veri yetersiz", 2'si yanlış pozitif. Bakım yazılımları gerçekte de yılları saklar. Bu yüzden Arıza Defteri artık 3 yıl üretiyor (`GECMIS_GUN=1095`) ve analiz 3 yılı kullanıyor (`ANALIZ_GUN=1095`).

### 4.1 Kör deneme (surum 6, 3 yıl, 1.445 kayıt)

| Tür | Arıza | Gerçek β | Takvim β (90%) | Çalışma saati β (90%) | Sınıf (takvim / saat) |
| --- | --- | --- | --- | --- | --- |
| FL-AKU akü soketi / kablosu hasarlı | 16 | 1,00 | 1,18 (0,77–1,70) | 1,13 (0,74–1,64) | rastgele / rastgele |
| FL-CAT çatal hasarı / yükte hasar | 17 | 1,00 | 1,21 (0,80–1,74) | 1,21 (0,80–1,73) | rastgele / rastgele |
| FL-FRN fren ayarı bozuk | 25 | 1,40 | 0,97 (0,69–1,31) | 0,94 (0,67–1,27) | rastgele ✗ / rastgele ✗ |
| FL-HID hidrolik kaçak | 50 | 1,60 | 1,63 (1,30–2,01) | 1,62 (1,29–2,00) | aşınma / aşınma |
| FL-LAS lastik hasarı | 33 | 1,80 | 1,57 (1,18–2,03) | 1,60 (1,20–2,06) | aşınma / aşınma |
| FL-SNS uyarı ışığı / sensör hatası | 44 | 1,00 | 0,82 (0,63–1,03) | 0,81 (0,63–1,02) | rastgele / rastgele |
| KV-BNT bant kayması | 37 | 1,00 | 0,77 (0,58–0,99) | 0,76 (0,57–0,98) | erken ✗ / erken ✗ |
| KV-FTS fotosel arızası | 26 | 1,00 | 0,98 (0,70–1,32) | 0,98 (0,70–1,32) | rastgele / rastgele |
| KV-HIZ hat yavaş çalışıyor | 15 | 1,00 | 0,71 (0,45–1,05) | 0,71 (0,45–1,04) | rastgele / rastgele |
| KV-MTR motor / redüktör arızası | 3 | 2,20 | — | — | yetersiz / yetersiz |
| KV-SIK koli sıkışması | 186 | 1,00 | 0,95 (0,84–1,06) | 0,95 (0,84–1,07) | rastgele / rastgele |
| RT-AKU akü soketi / kablosu hasarlı | 6 | 1,00 | — | — | yetersiz / yetersiz |
| RT-AYR kaldırma yüksekliği ayarı | 12 | 0,70 | 0,68 (0,41–1,05) | 0,67 (0,40–1,04) | rastgele ✗ / rastgele ✗ |
| RT-HID hidrolik kaçak / basınç düşük | 84 | 1,50 | 1,14 (0,95–1,35) | 1,16 (0,97–1,37) | rastgele ✗ / rastgele ✗ |
| RT-MAS direk zinciri / kaldırma sorunu | 13 | 2,50 | 5,21 (3,55–7,12) | 5,35 (3,76–7,15) | aşınma / aşınma |
| RT-SNS yükseklik sensörü hatası | 18 | 1,00 | 1,07 (0,71–1,53) | 1,07 (0,72–1,53) | rastgele / rastgele |
| SR-ACL açılışta ısınma / test turu uzun sürdü | 19 | 1,00 | 0,69 (0,46–0,98) | 0,68 (0,46–0,96) | erken ✗ / erken ✗ |
| SR-OKU barkod okuyucu hatası (yanlış oluk) | 35 | 1,00 | 0,92 (0,69–1,19) | 0,93 (0,70–1,20) | rastgele / rastgele |
| SR-SIK sıkışma | 62 | 1,00 | 0,88 (0,71–1,07) | 0,90 (0,73–1,09) | rastgele / rastgele |
| SR-TRY tray / klape arızası | 51 | 2,00 | 2,19 (1,77–2,66) | 2,30 (1,87–2,79) | aşınma / aşınma |
| ST-AYR gerginlik ayarı bozuk | 26 | 0,60 | 0,63 (0,45–0,85) | 0,61 (0,43–0,82) | erken / erken |
| ST-FLM film kopması | 67 | 1,00 | 0,95 (0,77–1,15) | 0,96 (0,78–1,16) | rastgele / rastgele |

**Sonuç: 22 türün 15'i doğru, 2'si "veri yetersiz", 5'i yanlış.** (ST-MTR 3 yılda hiç arızalanmadı, tabloda yok.)

- **Ana aşınan türler bulunuyor:** forklift hidrolik kaçak (50 arıza, 1,63 / gerçek 1,60), lastik (33, 1,57 / 1,80), sorter tray (51, 2,19 / 2,00). 30-50 arıza, aşınmayı görmek için gereken en az veri gibi duruyor.
- **RT-MAS sınıfı doğru, sayı değil:** 13 arızayla β 5,21 (gerçek 2,50). Az veriyle nokta tahmine güvenilmez; aralık (3,55-7,12) bunu söylüyor.
- **"Veri yetersiz" doğru cevap:** Konveyör motoru gerçekte birkaç yılda bir arızalanır; 3 yılda 3 arızayla hiçbir model aşınma söyleyemez. Böyle parçaların bakımı veriyle değil, üretici talimatıyla belirlenir.
- **Yanlışlar ve nedenleri:**
  - FL-FRN (25 arıza, gerçek 1,40 → 0,97 rastgele) ve RT-AYR (12 arıza, erken → rastgele): etki küçük, veri az.
  - RT-HID (84 arıza, gerçek 1,50 → 1,14 rastgele): kayıtların çoğu RT-03'ün cuma arızası, zamandan bağımsız. Analiz yanılmıyor, verinin çoğu gerçekten rastgele. A3 bu türde bakım aralığını değil, kök nedeni önerir.
  - KV-BNT ve SR-ACL (rastgele → erken): 22 tür aynı anda %90 güvenle sınanınca beklenen yanlış pozitif.
- **Burada bir test daha yapalım:** Aynı katalogla 20 farklı tohumda kör deneme; her türün kaç kez doğru çıktığını say. Tek bir veri setindeki 15/22, şanslı ya da şanssız olabilir.

### 4.2 Bakım aralığı önerileri: yön değişti

Plansız duruş çarpanına duyarlılık (gün; parantezde günlük duruş maliyetindeki düşüş; `*` arama sınırına, 180 güne, dayandı):

| Tip | Mevcut | ×1 | ×1,5 | ×2 (varsayılan) | ×3 | ×4 |
| --- | --- | --- | --- | --- | --- | --- |
| Forklift | 30 | 116 (%38) | 90 (%27) | 75 (%20) | 59 (%11) | 49 (%6) |
| Reach truck | 30 | 38 (%6) | 35 (%2) | 33 (%1) | 31 (%0) | 29 (%0) |
| Sorter | 30 | 29 (%0) | 25 (%2) | 22 (%4) | 18 (%10) | 16 (%14) |
| Konveyör | 45 | 180* | 180* | 180* | 180* | 180* |
| Streç | 60 | 180* | 180* | 180* | 180* | 180* |

- **Şişirilmiş veride "forklift 30 → 13 gün" çıkıyordu; gerçek sıklıkta "30 gün yeterli, uzatılabilir".** Arıza seyrekleşince planlı bakımın kendi maliyeti ağır basıyor. Yalnız sorterde (tray aşınması, ayda ~2) kısaltma çıkıyor.
- **Bu yapı uygun değil, şöyle uygulanır:** Model yalnız arıza duruşunu görür. Planlı bakımın başka işleri de var: yasal periyodik kontrol (iş ekipmanı), üretici talimatı ve garanti, yağlama ve temizlik, emniyet. Bu yüzden "uzatılabilir" önerisi bir karar değil, "mevcut aralık bu arızalar için aşırı değil" demektir. Nabız ekranı ve A3 bu notu yazıyor.
- **Sayaç:** Takvimden sayaca geçmenin kazancı yine %1'den az (forklift −%0,4, reach truck %1,0, sorter %0,2). Aşınan türü olmayan tiplerde (konveyör, streç) karşılaştırma yapılmıyor.
- **Rastgele türler β = 1 (karar 26.11.2026):** Sınıfı rastgele olan türün anlamlı olmayan β̂'sı maliyete girince öneri oynuyordu. Bu türler β = 1 alınır; η, mevcut aralıktaki beklenen arıza korunacak biçimde yeniden hesaplanır (`guvenilirlik._anlamli`).

<details><summary>Önceki sürümler (şişirilmiş veri, surum 4-5): neden artık geçerli değil</summary>

surum 4-5'te kör deneme 23-24/24 doğruydu ve öneriler "forklift 30 → 12-13, reach truck 30 → 9-10 gün" idi. SR-ACL'nin yanlış "aşınma" çıkması ve tohum değişince kaybolması, çoklu karşılaştırma açıklamasını desteklemişti; bu ders hâlâ geçerli. Sayıların kendisi geçerli değil: veri sahadakinin 10-20 katıydı.
</details>

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
| `test_veri_ve_kor_tahmin.py` | Döngü kurma kuralları; kör tahmin (5 aşınan sınıf doğru ve ±%35, 2 erken, 5 rastgele) ve bilinen SR-ACL yanılgısı; öneriler maliyeti düşürür; sayaç karşılaştırması (takvim döngüsü sezona göre oynar, kazanç küçük); çalışma saati fonksiyonu |
| `test_app.py` | Güvenlik başlıkları, kapalı `/docs`, 400/404/503, önbellek (5 istek → 1 hesap), hız sınırı ve sahte `X-Forwarded-For`, MCP anahtarı ve salt okuma |
| `test_gercek_ip.py` | Vekil ve Cloudflare başlık kuralları |

Örneklem (24 Kasım 2026, yerel): Arıza Defteri (360 gün) → Nabız Analiz → Nabız "Analiz" ve A3 ekranları açıldı, tablo yukarıdaki gibi. Güvenlik taraması (`tara.py --audit`, `pip-audit` dahil) temiz. Docker derlemesi **[doğrulanacak]**.

## 8. Bilinen sınırlar

- Sınıflandırma takvim günüyle. Çalışma saati ekseni de var (V3) ama bu veride sınıflandırmayı iyileştirmedi; politika karşılaştırmasında kullanılıyor.
- 22 tür aynı anda sınanıyor; yanlış pozitif denetimi yok (KV-BNT, SR-ACL "erken" çıkıyor).
- Gerçek sıklıkta 3 yıl bile seyrek arızalar (motor, akü soketi) için yetmiyor: "veri yetersiz".
- Maliyet modeli planlı bakımın arıza dışı amaçlarını (yasal kontrol, üretici talimatı, yağlama) görmüyor; uzatma önerileri bu yüzden karar değil, işaret.
- Tip içi farklılık β'yı 1'e çekiyor (hiyerarşik model yok).
- Bakım aralığı tüm tip için tek değer. Ekipman başına (yaşlı forklifte daha sık) öneri yok.
- Maliyet duruş dakikası. Parça ve işçilik maliyeti yok.
- Duyarlılık analizi ekranda yok (`PLANSIZ_CARPAN` sabit).

## 9. Mülakat soruları

1. **Neden Weibull değil?** Ekipman onarılıyor, yenilenmiyor. Onarılan sistemde arızalar arası süreler bağımsız değildir. Doğru model, zamanı bakımdan ölçen güç yasası sürecidir.
2. **β ne anlatıyor, yöneticiye nasıl söylersin?** "Bu arıza bakımdan uzaklaştıkça artıyor mu?" β > 1 ise evet, bakım işe yarar. β ≈ 1 ise bakım bu arızayı etkilemez, başka önlem gerekir.
3. **Az veride ne yapıyorsun?** Sınıfı nokta tahmin değil güven aralığı belirler. 9 arızalık bir türde aralık 1'i kestiği için "aşınma" demiyoruz.
4. **Modelin doğru çalıştığını nasıl bildin?** İki yolla: bilinen β ile benzetim (kapsama ~%90), ve Arıza Defteri'nin gizli β'larına karşı kör deneme Gerçek sıklıktaki 3 yıllık veride 22 türün 15'i doğru, 2'si "veri yetersiz". Ama önce verinin kendisini sorguladım: ilk sürümde veri sahadakinin 10-20 katıydı ve model %100 başarılı görünüyordu. Kolay veride başarı, modelin değil verinin özelliğidir.
5. **SR-ACL neden yanlış çıktı?** İlk açıklamam "takvim günüyle ölçüyoruz" idi; çalışma saatine geçip test ettim, sonuç değişmedi. İkinci açıklama: 24 türün aynı anda %90 güvenle sınanması; 13 rastgele türde ~1 yanlış pozitif beklenir. Veri tohumu değişince (surum 5) SR-ACL doğru çıktı: yanılgı şansa bağlıydı. Çözüm yanlış pozitif denetimi (Benjamini-Hochberg), bedeli zayıf aşınmayı kaçırmak.
5b. **Bakımı sayaca mı bağlamalı?** Bu depoda hayır: kullanım ±%20 oynuyor, sayacın kazancı %1'den az.
5c. **Neden öneri "kısalt"tan "uzatılabilir"e döndü?** Şişirilmiş veride arıza çoktu, sık bakım kârlıydı. Gerçek sıklıkta forkliftte yılda ~4 teknisyen arızası var; planlı bakımın maliyeti ağır basıyor. Ama model bakımın yasal kontrol ve üretici talimatı gibi amaçlarını görmüyor; bu yüzden "uzat" değil "mevcut aralık aşırı değil" diye okunur. Sayaç, kullanımı çok oynayan ekipmanda (yedek, sezonluk) değer.
6. **Bakım aralığı nasıl hesaplanıyor?** Periyodik bakım ve minimal onarım politikasında gün başına maliyet en aza indiriliyor. Tek türde analitik çözüm var, test sayısal sonucu onunla karşılaştırıyor.
7. **Neden ayrı servis, neden Python?** scipy'nin kök bulma, optimizasyon ve dağılım fonksiyonları hazır. Diğer servisler Node'da. HTTP ve MCP dil bağımsız olduğu için ikisi sorunsuz konuşuyor.
8. **Güvenlik?** Dışarı açık değil. Yine de şablondaki her önlem var: başlıklar, hız sınırı, sabit sürede anahtar karşılaştırması, özetle sabitlenmiş bağımlılıklar ve `pip-audit`.
9. **Gerçek depoda ilk ne değişirdi?** Ekipmanın kendi saat sayacı (burada vardiya üretiminden tahmin ediliyor), parça maliyeti, ekipman başına öneri.
10. **Bu sonuçla ne yapılır?** Aşınan türler bakım talimatına girer ve aralık ayarlanır. Rastgele türler kontrol listesine ve otonom bakıma gider. Erken dönem türleri için bakım sonrası kontrol yazılır. Nabız'daki A3 taslağı bunu otomatik önerir.

## 10. Kendini test et

- β = 1,15, aralık 0,92–1,40: hangi sınıf?
- Bir türün bütün arızaları bakımdan sonraki ilk 3 günde: β 1'den büyük mü küçük mü?
- `PLANSIZ_CARPAN` 2'den 4'e çıkarsa önerilen aralık kısalır mı, uzar mı?
- Arızasız döngüleri atarsak ne olur?
- Streç için neden sayı değil "uzatılabilir" yazıyor?

Cevaplar (önce kendin dene): rastgele (aralık 1'i kesiyor) · küçük (erken dönem) · kısalır (arıza daha pahalı, daha sık bakım değer) · arıza olduğundan sık görünür (η küçülür), bakım aralığı önerisi gereksiz kısalır · aşınma kanıtı yok, en iyi değer arama sınırının (180 gün) dışında; sayı sınırdır, bu yüzden "uzatılabilir" denir.

## 11. Elle yapılacak alıştırma

**Değişiklik (20 dakika):** `PLANSIZ_CARPAN` için duyarlılık. `tools/duyarlilik.py` diye küçük bir betik yaz:

1. `tests/veri/ariza-defteri-3yil.json.gz`'yi oku (bak: `tests/conftest.py`).
2. `Analizci(SahteKaynak(ornek), plansiz_carpan=c)` ile c = 1,5, 2, 3, 4 için raporu al.
3. Her tip için önerilen aralığı tablo olarak yazdır.

Beklenen: aşınan tiplerde çarpan büyüdükçe aralık kısalır. Sonucunu yukarıdaki duyarlılık tablosuyla karşılaştır; streçte neden değiştiğini açıklayabiliyor musun?

**5 dakikalık demo:**
1. Nabız → Analiz: RT-MAS kırmızı (aşınma), FL-AKU gri (rastgele), ST-AYR sarı (erken dönem). Güven çizgilerini göster.
2. "Neden Weibull değil" sorusunu bir cümleyle cevapla.
3. Bakım aralığı: reach truck 30 → 10 gün, streç "uzatılabilir". Neden zıt yönler?
4. Kör deneme: önce verinin gerçekçi olmadığını fark edip düzelttiğin (sahadakinin 10-20 katı); gerçek sıklıkta 3 yılla 15/22 doğru ve "veri yetersiz"in neden doğru cevap olduğu. Öneri yönünün değişmesi (kısalt → yeterli) ve modelin görmediği bakım amaçları. Takvim-sayaç tablosu: "sayaç bu depoda gerekmiyor" sonucu.
5. RT-MAS'ın A3 taslağı: karşı önlemde bakım aralığı önerisi otomatik geliyor.

## 12. Değişiklik günlüğü

| Tarih | Değişiklik |
| --- | --- |
| 26.11.2026 | Gerçek sıklık (Arıza Defteri surum 6): veri sahadakinin 10-20 katıydı, düzeltildi. Analiz dönemi 3 yıl (`ANALIZ_GUN=1095`); test verisi `ariza-defteri-3yil.json.gz`. Kör deneme 15/22 + 2 yetersiz; öneriler "kısalt"tan "mevcut yeterli"ye döndü (yalnız sorter kısalt). Testler gerçek sıklığa göre yeniden yazıldı. 23 test. |
| 26.11.2026 | Arıza Defteri surum 5 (akü şarjı arıza sayılmıyor): test verisi ve tablolar yenilendi. Kör deneme takvimde 24/24; SR-ACL yanılgısı kayboldu (çoklu karşılaştırma açıklamasını destekliyor). Streç testi sabit sayı yerine aralık (30-90 gün). 23 test. |
| 26.11.2026 | V3: kullanım ekseni (`KullanimSaati`, Arıza Defteri vardiya üretiminden) ve takvim-sayaç karşılaştırması (`sayac_karsilastir`, tip başına `sayac` alanı). Kör deneme surum 4 verisiyle yenilendi (takvim 23/24, çalışma saati 22/24). SR-ACL açıklaması düzeltildi (çalışma saati düzeltmedi; küçük örneklem + çoklu karşılaştırma). Kör deneme testi "sınıf doğru, tahmin ±%35"; test verisi `tools/ornek_al.py` ile yeniden üretilir. 23 test. |
| 26.11.2026 | Rastgele sınıfındaki türler bakım aralığı hesabında β = 1 alınır (streç önerisi artık çarpana göre oynamıyor); sınıra dayanan öneri `sinirda` alanıyla işaretlenir. Duyarlılık tablosu yenilendi; 21 test. |
| 25.11.2026 | İlk CI: çalışma bağımlılıkları da kurulur (requirements-dev yalnız pytest içeriyordu); Dependabot yalnız Python yama sürümü önerir. Plansız duruş çarpanı duyarlılık tablosu (×1-×4); üst sınıra dayanan öneri gerekçede belirtilir (+1 test kontrolü). |
| 24.11.2026 | V1: güç yasası tahmini (profil olabilirlik, %90 aralık), sınıflandırma, Barlow-Hunter bakım aralığı, Arıza Defteri istemcisi, saatlik önbellek, FastAPI + MCP (3 salt okuma aracı), güvenlik katmanı (Python şablonuyla aynı), özetle sabit bağımlılıklar, 20 test (kör deneme dahil), Docker ve kurulum betiği. Güvenlik taraması ve `pip-audit` temiz. |
