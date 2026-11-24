"""Arıza Defteri kayıtlarından analiz girdisi: bakım döngüleri ve maliyetler. Saf fonksiyonlar.

Bir ekipmanın planlı bakım kayıtları (kayıp = 'planli') döngü sınırlarıdır. Her döngü için:
  T  = bir sonraki bakıma (ya da analiz anına) kadar geçen gün
  ti = o döngüdeki her arızanın bakımdan sonraki günü
Arızasız döngüler de veriye girer (önemli: yalnız arızalı döngüleri almak β'yı yukarı çeker).
İlk bakımdan önceki arızalar kullanılmaz: o döngünün başlangıcı bilinmiyor.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

GUN_SN = 86400.0


def zaman(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


def donguler(kayitlar: list[dict], ekipman_tipleri: dict[str, str], analiz_ani: float) -> dict[tuple[str, str], list[tuple[float, list[float]]]]:
    """(tip, arıza türü) → döngüler. Tip içindeki bütün ekipmanların döngüleri birleştirilir (ortak β, η)."""
    bakimlar: dict[str, list[float]] = defaultdict(list)
    arizalar: dict[str, list[tuple[str, float]]] = defaultdict(list)
    turler: dict[str, set[str]] = defaultdict(set)
    for k in kayitlar:
        e = k["ekipman"]["kod"]
        an = zaman(k["baslangic"])
        if k["kayip"]["kod"] == "planli":
            bakimlar[e].append(an)
        else:
            arizalar[e].append((k["tur"]["kod"], an))
            turler[ekipman_tipleri.get(e, "?")].add(k["tur"]["kod"])
    sonuc: dict[tuple[str, str], list[tuple[float, list[float]]]] = defaultdict(list)
    for e, tip in ekipman_tipleri.items():
        b = sorted(bakimlar.get(e, []))
        for i, bas in enumerate(b):
            bit = b[i + 1] if i + 1 < len(b) else analiz_ani
            if bit <= bas:
                continue
            T = (bit - bas) / GUN_SN
            for tur in turler.get(tip, ()):
                ts = [(an - bas) / GUN_SN for t, an in arizalar.get(e, []) if t == tur and bas < an <= bit]
                sonuc[(tip, tur)].append((T, ts))
    return dict(sonuc)


def ortalama_sureler(kayitlar: list[dict]) -> tuple[dict[str, float], dict[str, float]]:
    """Arıza türü başına ve (planlı bakım için) ekipman tipi başına ortalama duruş dakikası (yalnız kapanmış kayıtlar)."""
    tur_t: dict[str, list[int]] = defaultdict(list)
    bakim_t: dict[str, list[int]] = defaultdict(list)
    for k in kayitlar:
        if k.get("sure_dk") is None:
            continue
        if k["kayip"]["kod"] == "planli":
            bakim_t[k["ekipman"]["tip"]].append(k["sure_dk"])
        else:
            tur_t[k["tur"]["kod"]].append(k["sure_dk"])
    ort = lambda d: {a: sum(v) / len(v) for a, v in d.items() if v}  # noqa: E731
    return ort(tur_t), ort(bakim_t)
