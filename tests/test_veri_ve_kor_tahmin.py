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
    for tur, beta in GERCEK.items():
        assert r[tur]["sinif"] == "asinma", tur
        assert r[tur]["beta_alt"] <= beta <= r[tur]["beta_ust"] * 1.05, f"{tur}: {r[tur]['beta']} [{r[tur]['beta_alt']}, {r[tur]['beta_ust']}] gerçek {beta}"
    for tur in ("RT-AYR", "ST-AYR"):
        assert r[tur]["sinif"] == "erken", tur
    for tur in ("FL-AKU", "KV-SIK", "RT-AKU", "FL-SNS", "ST-FLM"):
        assert r[tur]["sinif"] == "rastgele", tur
    # Bilinen yanılgı: sabah açılış kaybı (SR-ACL) yalnız 08-16'da olur, bakım da sabah 9'da;
    # takvim günüyle ölçünce bakım gününün sabahı eksik görünür ve yalancı aşınma çıkar. Doküman: "çalışma saati".
    assert r["SR-ACL"]["beta"] > 1


def test_bakim_araligi_onerileri(ornek, sahte_kaynak):
    r = {t["tip"]: t for t in Analizci(sahte_kaynak(ornek), saat=lambda: ornek["analizAni"]).rapor()["tipler"]}
    assert r["reach_truck"]["onerilen_gun"] < 30 and "RT-MAS" in r["reach_truck"]["asinanTurler"]
    assert r["strec"]["onerilen_gun"] > 60, "streçte aşınma kanıtı zayıf (ST-MTR az veri): aralık uzar"
    for t in r.values():
        assert t["maliyet_onerilen"] <= t["maliyet_mevcut"] + 1e-6
