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

Arıza Defteri'nin üreticisinde her türün **gizli** bir β değeri var (`katalog.js` → `asinma`). Bu değer API'den verilmez. Nabız Analiz yalnız kayıtlara bakarak tahmin eder. Veri: surum 4 (26.11.2026, kullanımlı üretici), 360 gün, 4.241 kayıt. Tablo hem takvim günüyle hem çalışma saatiyle yapılan tahmini gösterir.

| Tür | Arıza | Gerçek β | Takvim: tahmin (%90 aralık) | Çalışma saati: tahmin | Sınıf (takvim / saat) |
| --- | --- | --- | --- | --- | --- |
| RT-MAS direk zinciri | 82 | 2,50 | 2,13 (1,78–2,52) | 2,06 (1,73–2,43) | aşınma ✓ / aşınma ✓ |
| KV-MTR motor | 26 | 2,20 | 2,12 (1,53–2,83) | 2,16 (1,56–2,89) | aşınma ✓ / aşınma ✓ |
| SR-TRY tray | 40 | 2,00 | 2,60 (2,07–3,20) | 2,60 (2,06–3,20) | aşınma ✓ / aşınma ✓ |
| ST-MTR döner tabla motoru arızası | 12 | 2,00 | 1,87 (1,16–2,80) | 1,94 (1,20–2,92) | aşınma ✓ / aşınma ✓ |
| FL-LAS lastik hasarı | 195 | 1,80 | 1,54 (1,38–1,72) | 1,54 (1,38–1,72) | aşınma ✓ / aşınma ✓ |
| FL-HID hidrolik kaçak | 250 | 1,60 | 1,58 (1,44–1,74) | 1,62 (1,47–1,78) | aşınma ✓ / aşınma ✓ |
| RT-HID hidrolik kaçak | 233 | 1,50 | 1,26 (1,14–1,40) | 1,26 (1,14–1,40) | aşınma ✓ / aşınma ✓ |
| FL-FRN fren ayarı bozuk | 145 | 1,40 | 1,33 (1,17–1,51) | 1,32 (1,16–1,50) | aşınma ✓ / aşınma ✓ |
| SR-ACL açılışta ısınma | 32 | 1,00 | 1,43 (1,08–1,85) | 1,41 (1,06–1,83) | aşınma ✗ / aşınma ✗ |
| RT-AYR kaldırma yüksekliği ayarı | 55 | 0,70 | 0,66 (0,53–0,81) | 0,66 (0,52–0,81) | erken dönem ✓ / erken dönem ✓ |
| ST-AYR gerginlik ayarı bozuk | 44 | 0,60 | 0,58 (0,45–0,73) | 0,63 (0,49–0,80) | erken dönem ✓ / erken dönem ✓ |
| Diğer 13 rastgele tür | 18–614 | 1,00 | 0,88–1,10 | | rastgele 13/13 / 12/13 |

**Sonuç:** Takvim ekseninde 24 türün 23'ü doğru sınıflandı, çalışma saati ekseninde 22'si (KV-SIK sınırda: 1,09 [1,01–1,19]). Aşınan ve erken dönem türlerinin hepsi doğru. Analiz bu yüzden sınıflandırmada takvim eksenini kullanıyor; çalışma saati, bakım politikası karşılaştırmasında kullanılıyor (aşağıda).

- **SR-ACL (yalancı aşınma), açıklama düzeltildi (26.11.2026):** Önceki sürümde "takvim günüyle ölçüldüğü için, çalışma saatine geçince düzelir" demiştik. V3'te denedik, düzelmedi: çalışma saatiyle de 1,41 (1,06–1,83). Daha olası açıklama küçük örneklem ve çoklu karşılaştırma: 32 arıza var, 24 tür aynı anda %90 güvenle sınanıyor. Rastgele bir türün yanlışlıkla "aşınma" çıkma olasılığı tür başına ~%5, 13 rastgele türde yaklaşık 1 yanlış pozitif beklenir.
  - **Bu yapı uygun değil, şöyle uygulanır:** Bir hipotezi dokümana "neden" diye yazmadan önce test et. "Çalışma saatine geçince düzelir" bir hipotezdi; test edilince yanlış çıktı.
  - **Şöyle daha iyi olur:** Çok sayıda tür birlikte sınanırken yanlış pozitif oranını denetlemek (Benjamini-Hochberg) ya da küçük örneklemde "aşınma" demek için daha güçlü kanıt istemek. Bedeli: gerçek ama zayıf aşınmayı (ST-MTR, 12 arıza) kaçırmak. Karar bekliyor.
- **%90 aralığı gerçeği her zaman kapsamıyor (10 türün 6'sı):** Üç bilinen neden var:
  1. Üreticide aşınma çarpanı [0,15; 4] aralığıyla sınırlı, bu yüksek β'yı düzleştirir (RT-MAS 2,13 / gerçek 2,50).
  2. Tip içindeki ekipmanlar birleştiriliyor; yaş ve kullanım farkı tahmini 1'e doğru çeker (RT-HID 1,26 / gerçek 1,50).
  3. RT-03'ün cuma arızaları zamandan bağımsız ek arıza üretir.
  Sınıf doğru çıkıyor, sayı kayıyor. Test bu yüzden "aralık gerçeği kapsıyor" yerine "sınıf doğru ve tahmin ±%35" diye denetliyor. **Şöyle daha iyi olur:** ekipman başına ayrı ölçek (η) ile ortak β (hiyerarşik model).

### 4.1 Takvim mi, sayaç mı? (V3)

Arıza Defteri surum 4'te aşınma bakımdan beri **çalışılan süreyle** ilerliyor ve ekipmanın kullanımı sezona göre değişiyor. Soru: bakımı takvime göre (her 30 günde bir) mi, sayaca göre (her N çalışma saatinde bir) mi yapmalı?

`sayac_karsilastir` iki politikayı aynı modelle karşılaştırır. Takvim politikasında her döngünün çalışma saati gerçek kullanım profilinden hesaplanır (yıl boyunca T günlük pencereler); sayaç politikasında her döngü aynı saattir.

| Tip | Takvim önerisi | Günlük çalışma (sa) | Takvim döngüsü (sa, yıl içinde) | Sayaç önerisi (sa) | Sayaca geçmenin kazancı |
| --- | --- | --- | --- | --- | --- |
| Forklift | 30 → 12 gün | 14,8 | 148–232 | 177 | %0,2 |
| Reach truck | 30 → 10 gün | 14,8 | 121–185 | 145 | %0,2 |
| Konveyör | 45 → 26 gün | 14,8 | 342–469 | 356 | −%1,5 |
| Sorter | 30 → 14 gün | 11,3 | 137–198 | 157 | −%0,4 |
| Streç | 60 → 67 gün | 11,4 | 724–788 | 680 | −%1,6 |

- **Sonuç: bu depoda sayaca geçmek kazandırmıyor** (fark %2'den az; eksi değerler model gürültüsü). Asıl kazanç aralığı kısaltmak (30 → 12 gün: duruş maliyetinde %11).
- **İçeride ne oluyor:** Sayacın kazancı, döngüden döngüye çalışma saatinin ne kadar oynadığına bağlı. Güç yasası dışbükey (β > 1) olduğu için uzun döngünün fazladan arızası, kısa döngünün kazancından büyüktür (Jensen eşitsizliği). Ama burada kullanım yalnız ±%20 oynuyor ve önerilen döngü kısa (12 gün). Kazanç ikinci dereceden küçük kalıyor.
- **Sayaç ne zaman değer?** Kullanımın çok oynadığı yerde: yedek ekipman (bazı haftalar hiç çalışmayan), sezonluk hat, vardiya sayısı değişen operasyon. Ekran bu sonucu tip başına "takvim yeterli" diye söylüyor; sayaç (bakımdan beri çalışma saati) yine gösteriliyor, çünkü bir ekipmanın aynı takvim gününde ne kadar yıprandığını görmek bakım planlamacısı için değerli.
- **Burada bir test daha yapalım:** Yoğun sezonda (kasım-aralık) yalnız 2 vardiya çalışan bir senaryo (kullanım oynaması büyür) ile tabloyu yeniden üret; sayacın kazancı büyümeli.

**Bakım aralığı önerileri ve duyarlılık (surum 4 verisi):** Plansız duruş çarpanı değişince öneri ne kadar oynuyor? Gün; parantezde günlük duruş maliyetindeki düşüş; `*` arama sınırına (7 ya da 180 gün) dayandı.

| Tip | Mevcut | ×1 | ×1,5 | ×2 (varsayılan) | ×3 | ×4 |
| --- | --- | --- | --- | --- | --- | --- |
| Forklift | 30 | 19 (%3) | 15 (%7) | 12 (%11) | 9 (%15) | 8 (%19) |
| Reach truck | 30 | 15 (%9) | 12 (%13) | 10 (%16) | 8 (%20) | 7* (%23) |
| Sorter | 30 | 19 (%7) | 16 (%11) | 14 (%13) | 12 (%17) | 11 (%20) |
| Konveyör | 45 | 36 (%1) | 30 (%2) | 26 (%4) | 21 (%6) | 19 (%7) |
| Streç | 60 | 87 (%4) | 74 (%1) | 67 (%0) | 58 (%0) | 54 (%0) |

- **Yön sağlam, sayı değil.** Forklift, reach truck ve sorterda her çarpanda "daha sık bakım" çıkıyor. Yöneticiye "30 yerine 10-15 gün" diye aralık olarak sunulmalı, tek sayı olarak değil. Çarpan 1 bile kısaltıyor: sonuç yalnız "plansız duruş pahalıdır" varsayımına dayanmıyor.
- **Rastgele türler β = 1 (karar 26.11.2026).** Sınıfı rastgele olan türün anlamlı olmayan β̂'sı (ör. 1,2) maliyete girince öneri oynuyordu; surum 3 verisinde streç 102-154 gün arasında gidip geliyordu. Artık bu türler β = 1 alınır; η, mevcut aralıktaki beklenen arıza korunacak biçimde yeniden hesaplanır. Kod: `guvenilirlik._anlamli`; test: `test_rastgele_turun_nokta_tahmini_araligi_oynatmaz`. Sınıra dayanan öneri sayı olarak değil "uzatılabilir" diye gösterilir (`sinirda`).
- **Streç değişti:** surum 3'te "uzatılabilir" diyordu (aşınan tür yoktu). surum 4 verisinde ST-MTR'nin aşınması 12 arızayla görünür oldu (1,87 [1,16–2,80]) ve öneri mevcut 60 güne yakın (67 gün, kazanç ~%0). Veri değişince öneri değişir; bu yüzden öneri her saat yeniden hesaplanıyor.

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
- 24 tür aynı anda sınanıyor; yanlış pozitif denetimi yok (SR-ACL).
- Tip içi farklılık β'yı 1'e çekiyor (hiyerarşik model yok).
- Bakım aralığı tüm tip için tek değer. Ekipman başına (yaşlı forklifte daha sık) öneri yok.
- Maliyet duruş dakikası. Parça ve işçilik maliyeti yok.
- Duyarlılık analizi ekranda yok (`PLANSIZ_CARPAN` sabit).

## 9. Mülakat soruları

1. **Neden Weibull değil?** Ekipman onarılıyor, yenilenmiyor. Onarılan sistemde arızalar arası süreler bağımsız değildir. Doğru model, zamanı bakımdan ölçen güç yasası sürecidir.
2. **β ne anlatıyor, yöneticiye nasıl söylersin?** "Bu arıza bakımdan uzaklaştıkça artıyor mu?" β > 1 ise evet, bakım işe yarar. β ≈ 1 ise bakım bu arızayı etkilemez, başka önlem gerekir.
3. **Az veride ne yapıyorsun?** Sınıfı nokta tahmin değil güven aralığı belirler. 9 arızalık bir türde aralık 1'i kestiği için "aşınma" demiyoruz.
4. **Modelin doğru çalıştığını nasıl bildin?** İki yolla: bilinen β ile benzetim (kapsama ~%90), ve Arıza Defteri'nin gizli β'larına karşı kör deneme (24 türün 22'si doğru; iki yanılgının nedeni biliniyor).
5. **SR-ACL neden yanlış çıktı?** İlk açıklamam "takvim günüyle ölçüyoruz" idi; çalışma saatine geçip test ettim, sonuç değişmedi. Daha olası açıklama: 32 arıza ve 24 türün aynı anda %90 güvenle sınanması; 13 rastgele türde ~1 yanlış pozitif beklenir. Çözüm yanlış pozitif denetimi (Benjamini-Hochberg), bedeli zayıf aşınmayı kaçırmak.
5b. **Bakımı sayaca mı bağlamalı?** Bu depoda hayır: kullanım ±%20 oynuyor, sayacın kazancı %2'den az. Asıl kazanç aralığı kısaltmak. Sayaç, kullanımı çok oynayan ekipmanda (yedek, sezonluk) değer.
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

1. `tests/veri/ariza-defteri-360.json.gz`'yi oku (bak: `tests/conftest.py`).
2. `Analizci(SahteKaynak(ornek), plansiz_carpan=c)` ile c = 1,5, 2, 3, 4 için raporu al.
3. Her tip için önerilen aralığı tablo olarak yazdır.

Beklenen: aşınan tiplerde çarpan büyüdükçe aralık kısalır. Sonucunu yukarıdaki duyarlılık tablosuyla karşılaştır; streçte neden değiştiğini açıklayabiliyor musun?

**5 dakikalık demo:**
1. Nabız → Analiz: RT-MAS kırmızı (aşınma), FL-AKU gri (rastgele), ST-AYR sarı (erken dönem). Güven çizgilerini göster.
2. "Neden Weibull değil" sorusunu bir cümleyle cevapla.
3. Bakım aralığı: reach truck 30 → 10 gün, streç "uzatılabilir". Neden zıt yönler?
4. Kör deneme tablosu: 24 türün 23'ü doğru; SR-ACL için hipotezi nasıl test edip düzelttiğin. Takvim-sayaç tablosu: "sayaç bu depoda gerekmiyor" sonucu.
5. RT-MAS'ın A3 taslağı: karşı önlemde bakım aralığı önerisi otomatik geliyor.

## 12. Değişiklik günlüğü

| Tarih | Değişiklik |
| --- | --- |
| 26.11.2026 | V3: kullanım ekseni (`KullanimSaati`, Arıza Defteri vardiya üretiminden) ve takvim-sayaç karşılaştırması (`sayac_karsilastir`, tip başına `sayac` alanı). Kör deneme surum 4 verisiyle yenilendi (takvim 23/24, çalışma saati 22/24). SR-ACL açıklaması düzeltildi (çalışma saati düzeltmedi; küçük örneklem + çoklu karşılaştırma). Kör deneme testi "sınıf doğru, tahmin ±%35"; test verisi `tools/ornek_al.py` ile yeniden üretilir. 23 test. |
| 26.11.2026 | Rastgele sınıfındaki türler bakım aralığı hesabında β = 1 alınır (streç önerisi artık çarpana göre oynamıyor); sınıra dayanan öneri `sinirda` alanıyla işaretlenir. Duyarlılık tablosu yenilendi; 21 test. |
| 25.11.2026 | İlk CI: çalışma bağımlılıkları da kurulur (requirements-dev yalnız pytest içeriyordu); Dependabot yalnız Python yama sürümü önerir. Plansız duruş çarpanı duyarlılık tablosu (×1-×4); üst sınıra dayanan öneri gerekçede belirtilir (+1 test kontrolü). |
| 24.11.2026 | V1: güç yasası tahmini (profil olabilirlik, %90 aralık), sınıflandırma, Barlow-Hunter bakım aralığı, Arıza Defteri istemcisi, saatlik önbellek, FastAPI + MCP (3 salt okuma aracı), güvenlik katmanı (Python şablonuyla aynı), özetle sabit bağımlılıklar, 20 test (kör deneme dahil), Docker ve kurulum betiği. Güvenlik taraması ve `pip-audit` temiz. |
