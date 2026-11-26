"""Güvenilirlik matematiği. Saf fonksiyonlar: veritabanı, ağ ya da saat kullanmaz; testler doğrudan çağırır.

NEDEN "WEIBULL" DEĞİL DE "GÜÇ YASASI SÜRECİ"?
  Klasik Weibull analizi "parça bozulunca yenisiyle değiştirilir" (yenileme) varsayar: her arızadan sonra saat sıfırlanır.
  Depo ekipmanında arıza çoğunlukla onarılır, ekipman yenilenmez ("minimal onarım"): hortum değişir ama forklift
  yaşlanmaya devam eder. Saati sıfırlayan şey planlı bakımdır. Bu durumda doğru model, her bakım döngüsünde
  arızaların yoğunluğu zamanla değişen bir Poisson sürecidir (NHPP, güç yasası, Crow-AMSAA):

      yoğunluk  λ(t) = (β/η) · (t/η)^(β-1)        t: bakımdan sonra geçen süre (gün)
      beklenen  Λ(t) = (t/η)^β                     0..t arasında beklenen arıza sayısı

  β > 1  → aşınma: bakımdan uzaklaştıkça arıza artar. Planlı bakım işe yarar, aralık optimize edilebilir.
  β ≈ 1  → rastgele: arıza zamandan bağımsız. Planlı bakımı sıklaştırmak bu arızayı azaltmaz; otonom bakım,
           kontrol listesi, eğitim gibi önlemler gerekir.
  β < 1  → erken dönem: bakımdan hemen sonra yüksek (yanlış montaj, ayar bozulması). Bakım işinin kalitesine bakılır.

VERİ: Her "döngü" bir ekipmanın iki planlı bakımı arasındaki dönemdir (son döngü bugünde kesilir).
  döngü = (T, [t1, t2, ...])  T: döngünün gözlenen uzunluğu, ti: o döngüdeki arızaların bakımdan sonraki zamanı (0 < ti ≤ T)
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace

import numpy as np
from scipy import optimize, stats

EN_AZ_ARIZA = 8          # bundan az arızayla sınıf verilmez ("yetersiz veri")
GUVEN = 0.90             # β için güven aralığı düzeyi
BETA_ARALIK = (0.05, 20.0)


@dataclass(frozen=True)
class GucYasasi:
    n: int                 # arıza sayısı
    dongu: int             # döngü sayısı
    beta: float | None     # şekil (en çok olabilirlik)
    beta_alt: float | None
    beta_ust: float | None
    eta: float | None      # ölçek (gün): tek ekipmanda η gün içinde ortalama 1 arıza
    sinif: str             # 'asinma' | 'rastgele' | 'erken' | 'yetersiz'

    def sozluk(self) -> dict:
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def _profil(beta: float, n: int, toplam_log_t: float, T: np.ndarray) -> float:
    """β'ya göre profil log-olabilirlik (η en iyi değerine konmuş):
        ℓ(β) = N ln β + (β-1) Σ ln t - N ln(Σ T^β / N) - N
    (η'ya göre türev sıfırlanınca η^β = Σ T^β / N çıkar; yerine koyunca tek değişkenli fonksiyon kalır.)"""
    toplam = np.sum(T ** beta)
    return n * math.log(beta) + (beta - 1) * toplam_log_t - n * math.log(toplam / n) - n


def guc_yasasi_tahmin(donguler: list[tuple[float, list[float]]]) -> GucYasasi:
    """Birden çok döngüden ortak β ve η'nın en çok olabilirlik tahmini + β için profil olabilirlik güven aralığı."""
    donguler = [(float(T), [float(t) for t in ts if 0 < t <= T]) for T, ts in donguler if T > 0]
    n = sum(len(ts) for _, ts in donguler)
    if n < EN_AZ_ARIZA or not donguler:
        return GucYasasi(n, len(donguler), None, None, None, None, "yetersiz")
    T = np.array([d[0] for d in donguler])
    toplam_log_t = sum(math.log(t) for _, ts in donguler for t in ts)

    # dℓ/dβ = N/β + Σ ln t - N · Σ(T^β ln T) / Σ T^β = 0  → tek kök (ℓ içbükey); brentq ile bulunur.
    def turev(b: float) -> float:
        tb = T ** b
        return n / b + toplam_log_t - n * np.sum(tb * np.log(T)) / np.sum(tb)

    alt, ust = BETA_ARALIK
    if turev(alt) * turev(ust) > 0:  # kök sınır dışında (aşırı veri); en yakın sınır
        beta = alt if abs(turev(alt)) < abs(turev(ust)) else ust
    else:
        beta = optimize.brentq(turev, alt, ust, xtol=1e-9)
    eta = (np.sum(T ** beta) / n) ** (1 / beta)

    # Güven aralığı: 2·[ℓ(β̂) - ℓ(β)] ≤ χ²₁(GUVEN) olan β değerleri (profil olabilirlik oranı)
    tepe = _profil(beta, n, toplam_log_t, T)
    esik = stats.chi2.ppf(GUVEN, df=1) / 2
    fark = lambda b: tepe - _profil(b, n, toplam_log_t, T) - esik  # noqa: E731
    b_alt = optimize.brentq(fark, alt, beta) if fark(alt) > 0 else alt
    b_ust = optimize.brentq(fark, beta, ust) if fark(ust) > 0 else ust

    sinif = "asinma" if b_alt > 1 else "erken" if b_ust < 1 else "rastgele"
    return GucYasasi(n, len(donguler), float(beta), float(b_alt), float(b_ust), float(eta), sinif)


def beklenen_ariza(model: GucYasasi, gun: float) -> float:
    """Bakımdan sonraki 'gun' gün içinde tek ekipmanda beklenen arıza: Λ(t) = (t/η)^β."""
    if model.beta is None:
        return 0.0
    return (gun / model.eta) ** model.beta


@dataclass(frozen=True)
class AralikOnerisi:
    mevcut_gun: float
    onerilen_gun: float
    maliyet_mevcut: float      # dakika-eşdeğeri / gün / ekipman
    maliyet_onerilen: float
    ariza_yil_mevcut: float    # ekipman başına yılda beklenen arıza
    ariza_yil_onerilen: float
    asinan_tur: int            # aralığı belirleyen (β > 1) tür sayısı
    gerekce: str
    sinirda: bool = False      # öneri arama sınırına dayandı: sayı en iyi değer değil; "uzatılabilir" ya da "kısaltılabilir"

    def sozluk(self) -> dict:
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def maliyet_orani(T: float, bilesenler: list[tuple[GucYasasi, float]], bakim_maliyeti: float) -> float:
    """Periyodik bakım + minimal onarım politikası (Barlow-Hunter): T günde bir bakım.
        C(T) = (Cp + Σ_k Cr_k · Λ_k(T)) / T
    Cp: bir planlı bakımın maliyeti, Cr_k: k türünden bir arızanın maliyeti. Birim: duruş dakikası eşdeğeri."""
    return (bakim_maliyeti + sum(cr * beklenen_ariza(m, T) for m, cr in bilesenler)) / T


def en_iyi_aralik(bilesenler: list[tuple[GucYasasi, float]], bakim_maliyeti: float, mevcut_gun: float,
                  sinirlar: tuple[float, float] = (7.0, 180.0)) -> AralikOnerisi:
    """Maliyet oranını en küçük yapan bakım aralığı (gün). Yalnız güvenilir tahmini olan türler hesaba girer.
    β ≤ 1 olan türler planlı bakımdan yararlanmaz: rastgele türün maliyeti T'den bağımsızdır, erken dönem türünde
    sık bakım arızayı artırır. Aşınan tür yoksa öneri, üst sınıra (aralığı uzatmaya) gider.

    Sınıfı "rastgele" olan türde (güven aralığı 1'i kesiyor) nokta tahmini β̂ kullanılmaz, β = 1 alınır: β̂ = 1,2 gibi
    anlamlı olmayan bir değer öneriyi oynatır (streçte 102-154 gün). η, mevcut aralıktaki beklenen arıza sayısı
    korunacak biçimde yeniden hesaplanır; böylece maliyet düzeyi değişmez, yalnız aralığa etkisi kalkar."""
    gecerli = [(_anlamli(m, mevcut_gun), cr) for m, cr in bilesenler if m.beta is not None]
    asinan = sum(1 for m, _ in gecerli if m.sinif == "asinma")
    sonuc = optimize.minimize_scalar(lambda T: maliyet_orani(T, gecerli, bakim_maliyeti), bounds=sinirlar, method="bounded",
                                     options={"xatol": 0.05})
    T_star = float(sonuc.x)
    yil = lambda T: 365 / T * sum(beklenen_ariza(m, T) for m, _ in gecerli)  # noqa: E731
    if not asinan:
        gerekce = "Veride aşınma görülmüyor: planlı bakımı sıklaştırmak arızayı azaltmaz. Aralık uzatılabilir; arıza önleme için kontrol listesi ve eğitim."
    elif T_star < mevcut_gun * 0.9:
        gerekce = "Aşınan türlerin maliyeti, bakım maliyetinden hızlı artıyor: bakım daha sık yapılmalı."
    elif T_star > mevcut_gun * 1.1:
        gerekce = "Aşınma var ama yavaş: aralık biraz uzatılınca toplam duruş azalıyor."
    else:
        gerekce = "Mevcut aralık en iyiye yakın."
    sinirda = T_star >= sinirlar[1] - 1 or T_star <= sinirlar[0] + 0.5
    if T_star >= sinirlar[1] - 1:  # en iyi değer aralığın dışında: sayı bir sınır, gerçek bir en iyi değil
        gerekce += f" Öneri üst sınırda ({sinirlar[1]:.0f} gün): bu bir en iyi değer değil, sınırdır. Aralığı kademeli uzatıp arızayı izleyin."
    elif T_star <= sinirlar[0] + 0.5:
        gerekce += f" Öneri alt sınırda ({sinirlar[0]:.0f} gün): daha sık bakım yerine aşınan türün kök nedenine bakın."
    return AralikOnerisi(mevcut_gun, T_star, maliyet_orani(mevcut_gun, gecerli, bakim_maliyeti), float(sonuc.fun),
                         yil(mevcut_gun), yil(T_star), asinan, gerekce, sinirda)


def _anlamli(m: GucYasasi, mevcut_gun: float) -> GucYasasi:
    """Rastgele sınıfındaki türü β = 1'e çevirir (mevcut aralıktaki beklenen arıza aynı kalır); diğerlerine dokunmaz."""
    if m.sinif != "rastgele" or m.beta == 1.0:
        return m
    eta1 = mevcut_gun / (mevcut_gun / m.eta) ** m.beta
    return replace(m, beta=1.0, eta=eta1)


def guc_yasasi_benzet(beta: float, eta: float, donguler: list[float], rng: np.random.Generator) -> list[tuple[float, list[float]]]:
    """Testler için: bilinen β, η ile döngü verisi üretir (zaman dönüşümü: Λ(t) birim hızlı Poisson sürecidir)."""
    sonuc = []
    for T in donguler:
        L = (T / eta) ** beta
        k = rng.poisson(L)
        u = np.sort(rng.uniform(0, L, size=k))
        sonuc.append((T, list(eta * u ** (1 / beta))))
    return sonuc
