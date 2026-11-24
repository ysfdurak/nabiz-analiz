"""Matematik: bilinen β ile üretilen veride tahmin doğru mu, güven aralığı gerçeği kapsıyor mu, bakım aralığı formülle uyuşuyor mu."""
import numpy as np
import pytest

from analiz.guvenilirlik import (EN_AZ_ARIZA, GucYasasi, beklenen_ariza, en_iyi_aralik, guc_yasasi_benzet,
                                 guc_yasasi_tahmin, maliyet_orani)


@pytest.mark.parametrize("beta, sinif", [(2.5, "asinma"), (1.0, "rastgele"), (0.6, "erken")])
def test_bilinen_beta_geri_bulunur(beta, sinif):
    # Tek bir tohum: %90 aralık 10 denemenin ~1'inde gerçeği kaçırır (bu beklenen). Kapsama oranını ayrı test ölçer.
    rng = np.random.default_rng(42)
    # Farklı uzunlukta döngüler (bazı bakımlar gecikmiş): kapalı form değil, profil olabilirlik gerekir
    donguler = guc_yasasi_benzet(beta, 20.0, list(rng.uniform(25, 45, size=150)), rng)
    m = guc_yasasi_tahmin(donguler)
    assert m.beta_alt <= beta <= m.beta_ust
    assert abs(m.beta - beta) / beta < 0.15
    assert m.sinif == sinif


def test_guven_araligi_kapsama_orani():
    """%90 aralık, tekrarlanan denemelerin yaklaşık %90'ında gerçeği kapsamalı (aralık ne dar ne geniş)."""
    rng = np.random.default_rng(11)
    kapsadi = 0
    for _ in range(200):
        m = guc_yasasi_tahmin(guc_yasasi_benzet(1.8, 30.0, [30.0] * 25, rng))
        kapsadi += m.beta_alt <= 1.8 <= m.beta_ust
    assert 0.84 <= kapsadi / 200 <= 0.96


def test_esit_dongude_kapali_form_ile_ayni():
    """Bütün döngüler aynı uzunluktaysa en çok olabilirlik kapalı formdur: β = N / Σ ln(T/t)."""
    rng = np.random.default_rng(3)
    d = guc_yasasi_benzet(2.0, 25.0, [30.0] * 60, rng)
    n = sum(len(ts) for _, ts in d)
    kapali = n / sum(np.log(T / t) for T, ts in d for t in ts)
    assert guc_yasasi_tahmin(d).beta == pytest.approx(kapali, rel=1e-6)


def test_az_veri_sinif_vermez_ve_arizasiz_donguler_sayilir():
    assert guc_yasasi_tahmin([(30.0, [10.0, 20.0])]).sinif == "yetersiz"
    assert EN_AZ_ARIZA == 8
    # Arızasız döngü eklemek η'yı büyütmeli (aynı arızalar daha uzun gözleme yayılır)
    rng = np.random.default_rng(5)
    d = guc_yasasi_benzet(2.0, 20.0, [30.0] * 40, rng)
    a = guc_yasasi_tahmin(d)
    b = guc_yasasi_tahmin(d + [(30.0, [])] * 40)
    assert b.eta > a.eta


def test_en_iyi_aralik_analitik_cozumle_ayni():
    """Tek aşınan tür için T* = η · (Cp / ((β-1)·Cr))^(1/β)."""
    m = GucYasasi(100, 50, 2.5, 2.2, 2.8, 40.0, "asinma")
    cp, cr = 120.0, 300.0
    beklenen = 40.0 * (cp / ((2.5 - 1) * cr)) ** (1 / 2.5)
    o = en_iyi_aralik([(m, cr)], cp, mevcut_gun=30.0)
    assert o.onerilen_gun == pytest.approx(beklenen, rel=0.01)
    assert o.maliyet_onerilen <= maliyet_orani(30.0, [(m, cr)], cp)
    assert beklenen_ariza(m, 40.0) == pytest.approx(1.0)


def test_asinma_yoksa_aralik_uzar():
    rastgele = GucYasasi(100, 50, 1.0, 0.9, 1.1, 10.0, "rastgele")
    erken = GucYasasi(50, 50, 0.6, 0.5, 0.7, 60.0, "erken")
    o = en_iyi_aralik([(rastgele, 50.0), (erken, 80.0)], 120.0, mevcut_gun=60.0)
    assert o.asinan_tur == 0
    assert o.onerilen_gun > 170
    assert "aşınma görülmüyor" in o.gerekce
