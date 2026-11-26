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


GERCEK = {"RT-MAS": 2.5, "KV-MTR": 2.2, "SR-TRY": 2.0, "FL-HID": 1.6, "FL-LAS": 1.8}


def test_kor_tahmin(ornek, sahte_kaynak):
    a = Analizci(sahte_kaynak(ornek), saat=lambda: ornek["analizAni"])
    r = {t["tur"]: t for t in a.rapor()["turler"]}
    # Sınıf her aşınan türde doğru olmalı. Nokta tahmini ±%35: üreticinin aşınma çarpanı [0,15; 4] ile sınırlı (yüksek β
    # düzleşir), tip içindeki ekipmanlar birleştirilir ve RT-03'ün cuma arızaları zamandan bağımsızdır; bu yüzden %90
    # aralığı gerçeği her zaman kapsamaz (surum 4 verisinde 10 türün 6'sı). Doküman: "Kör deneme".
    for tur, beta in GERCEK.items():
        assert r[tur]["sinif"] == "asinma", tur
        assert abs(r[tur]["beta"] - beta) / beta <= 0.35, f"{tur}: {r[tur]['beta']} [{r[tur]['beta_alt']}, {r[tur]['beta_ust']}] gerçek {beta}"
    for tur in ("RT-AYR", "ST-AYR"):
        assert r[tur]["sinif"] == "erken", tur
    for tur in ("FL-AKU", "KV-SIK", "RT-AKU", "FL-SNS", "ST-FLM"):
        assert r[tur]["sinif"] == "rastgele", tur
    # Bilinen yanılgı: SR-ACL rastgele olduğu halde aşınma çıkıyor (32 arıza, aralık 1'e çok yakın). Çalışma saati ekseni
    # bunu düzeltmedi (V3'te denendi). En olası açıklama küçük örneklem ve 24 türün aynı anda sınanması: %90 güvenle
    # ~1-2 yanlış pozitif beklenir. Doküman: "Kör deneme".
    assert r["SR-ACL"]["beta"] > 1


def test_bakim_araligi_onerileri(ornek, sahte_kaynak):
    r = {t["tip"]: t for t in Analizci(sahte_kaynak(ornek), saat=lambda: ornek["analizAni"]).rapor()["tipler"]}
    assert r["reach_truck"]["onerilen_gun"] < 30 and "RT-MAS" in r["reach_truck"]["asinanTurler"]
    assert r["strec"]["onerilen_gun"] > 60, "streçte aşınma kanıtı zayıf (ST-MTR az veri): aralık uzar"
    for t in r.values():
        assert t["maliyet_onerilen"] <= t["maliyet_mevcut"] + 1e-6


def test_sayac_karsilastirmasi(ornek, sahte_kaynak):
    """V3: takvim ve sayaç politikası. Bu depoda günlük kullanım ±%20 oynar; sayaca geçmenin kazancı küçük olmalı,
    asıl kazanç aralığı kısaltmak. Döngü başına çalışma saati yıl içinde oynar (yoğun sezon)."""
    r = Analizci(sahte_kaynak(ornek), saat=lambda: ornek["analizAni"]).rapor()
    fl = next(t for t in r["tipler"] if t["tip"] == "forklift")
    s = fl["sayac"]
    assert s is not None
    assert 12 < s["gunluk_saat"] < 17
    assert s["donem_saat_ust"] > s["donem_saat_alt"] * 1.3, "takvim döngüsünde çalışma saati sezona göre oynamalı"
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
