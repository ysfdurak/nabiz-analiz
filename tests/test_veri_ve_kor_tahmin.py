"""Döngü kurma ve "kör tahmin": analiz, Arıza Defteri üreticisinin gizli β değerlerini veriden bulabiliyor mu?"""
import pytest

from analiz.servis import Analizci
from analiz.veri import donguler, ortalama_sureler

GUN = 86400


def kayit(e, tip, kayip, tur, gun, saat=10, sure=30):
    from datetime import datetime, timedelta, timezone
    an = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=3))) + timedelta(days=gun, hours=saat)
    return {"ekipman": {"kod": e, "tip": tip}, "kayip": {"kod": kayip}, "tur": {"kod": tur}, "baslangic": an.isoformat(), "sure_dk": sure}


def test_donguler_bakimla_baslar_arizasiz_dongu_sayilir_ilk_bakimdan_oncesi_atilir():
    k = [
        kayit("FL-01", "forklift", "ariza", "FL-HID", 2),        # ilk bakımdan önce: atılır
        kayit("FL-01", "forklift", "planli", "FL-PLN", 5, 9),
        kayit("FL-01", "forklift", "ariza", "FL-HID", 15, 9),    # 10. gün
        kayit("FL-01", "forklift", "planli", "FL-PLN", 35, 9),   # 30 günlük döngü
        kayit("FL-01", "forklift", "planli", "FL-PLN", 65, 9),   # arızasız döngü
    ]
    from analiz.veri import zaman
    son = zaman(k[-1]["baslangic"]) + 10 * GUN
    d = donguler(k, {"FL-01": "forklift"}, son)
    assert d[("forklift", "FL-HID")] == [(30.0, [10.0]), (30.0, []), (10.0, [])]
    tur, bakim = ortalama_sureler(k)
    assert tur == {"FL-HID": 30.0} and bakim == {"forklift": 30.0}


# Gerçek sıklıkta (surum 6) 3 yılda yeterli arızası olan aşınan türler (her biri 30-50 arıza).
GERCEK = {"FL-HID": 1.6, "FL-LAS": 1.8, "SR-TRY": 2.0}


def test_kor_tahmin(ornek, sahte_kaynak):
    a = Analizci(sahte_kaynak(ornek), saat=lambda: ornek["analizAni"])
    r = {t["tur"]: t for t in a.rapor()["turler"]}
    # 30-50 arızası olan aşınan türde sınıf doğru ve nokta tahmini ±%35. Doküman: "Kör deneme".
    for tur, beta in GERCEK.items():
        assert r[tur]["sinif"] == "asinma", tur
        assert abs(r[tur]["beta"] - beta) / beta <= 0.35, f"{tur}: {r[tur]['beta']} [{r[tur]['beta_alt']}, {r[tur]['beta_ust']}] gerçek {beta}"
    # RT-MAS: 3 yılda 13 arıza. Sınıf doğru ama β abartılı (5,2 / gerçek 2,5): az veriyle nokta tahmine güvenilmez.
    assert r["RT-MAS"]["sinif"] == "asinma"
    # KV-MTR (motor/redüktör) gerçekte birkaç yılda bir arızalanır: 3 yılda 3 arıza, yargı yok. Doğru cevap "veri yetersiz".
    assert r["KV-MTR"]["sinif"] == "yetersiz"
    assert r["ST-AYR"]["sinif"] == "erken"
    for tur in ("FL-AKU", "KV-SIK", "FL-SNS", "ST-FLM", "SR-SIK", "SR-OKU"):
        assert r[tur]["sinif"] == "rastgele", tur
    # Bilinen yanılgılar (doküman): FL-FRN ve RT-HID aşınıyor ama "rastgele" çıkıyor (RT-HID'de RT-03'ün cuma arızaları
    # zamandan bağımsız ve kayıtların çoğu). KV-BNT ve SR-ACL rastgele ama "erken" çıkıyor: 22 tür sınanınca beklenen yanlış
    # pozitif. Testler bunları sabitlemez; veri değişince değişebilirler.


def test_bakim_araligi_onerileri(ornek, sahte_kaynak):
    r = {t["tip"]: t for t in Analizci(sahte_kaynak(ornek), saat=lambda: ornek["analizAni"]).rapor()["tipler"]}
    # Gerçek sıklıkta arıza seyrek, planlı bakımın maliyeti ağır basar: öneriler mevcut aralığın çevresinde ya da üstünde.
    assert {"FL-HID", "FL-LAS"} <= set(r["forklift"]["asinanTurler"])
    assert "RT-MAS" in r["reach_truck"]["asinanTurler"] and 20 < r["reach_truck"]["onerilen_gun"] < 60
    assert "SR-TRY" in r["sorter"]["asinanTurler"] and r["sorter"]["onerilen_gun"] < 30
    # Konveyör ve streçte aşınma görünmüyor (motor arızası birkaç yılda bir): öneri sınıra dayanır, "uzatılabilir" gösterilir.
    for tip in ("konveyor", "strec"):
        assert r[tip]["asinanTurler"] == [] and r[tip]["sinirda"], tip
    for t in r.values():
        assert t["maliyet_onerilen"] <= t["maliyet_mevcut"] + 1e-6


def test_sayac_karsilastirmasi(ornek, sahte_kaynak):
    """V3: takvim ve sayaç politikası. Bu depoda günlük kullanım ±%20 oynar; sayaca geçmenin kazancı küçük olmalı,
    asıl karar aralığın kendisi. Döngü başına çalışma saati yıl içinde oynar (yoğun sezon)."""
    r = Analizci(sahte_kaynak(ornek), saat=lambda: ornek["analizAni"]).rapor()
    fl = next(t for t in r["tipler"] if t["tip"] == "forklift")
    s = fl["sayac"]
    assert s is not None
    assert 12 < s["gunluk_saat"] < 17
    assert s["donem_saat_ust"] > s["donem_saat_alt"] * 1.15, "takvim döngüsünde çalışma saati sezona göre oynamalı"
    assert abs(s["kazanc"]) < 0.05, f"sayaç kazancı {s['kazanc']}"
    assert s["onerilen_saat"] == pytest.approx(fl["onerilen_gun"] * s["gunluk_saat"], rel=0.35)


def test_kullanim_saati():
    from analiz.veri import KullanimSaati
    from datetime import datetime, timedelta, timezone
    ks = KullanimSaati([{"gun": "2026-01-01", "vardiya": 1, "ekipman": "E", "planli_dk": 240},
                        {"gun": "2026-01-01", "vardiya": 2, "ekipman": "E", "planli_dk": 480}])
    t = lambda saat: datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=3))).timestamp() + saat * 3600  # noqa: E731
    assert ks("E", t(8)) == 0
    assert ks("E", t(10)) == pytest.approx(2.0)     # 1. vardiyada 2 saat
    assert ks("E", t(15)) == pytest.approx(4.0)     # 240 dk kullanıldı, vardiya bitmeden de 4 saatte kalır
    assert ks("E", t(20)) == pytest.approx(8.0)     # 4 + 2. vardiyanın 4 saati
