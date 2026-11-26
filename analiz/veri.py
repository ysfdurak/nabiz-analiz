"""Arıza Defteri kayıtlarından analiz girdisi: bakım döngüleri ve maliyetler. Saf fonksiyonlar.

Bir ekipmanın planlı bakım kayıtları (kayıp = 'planli') döngü sınırlarıdır. Her döngü için:
  T  = bir sonraki bakıma (ya da analiz anına) kadar geçen gün
  ti = o döngüdeki her arızanın bakımdan sonraki günü
Arızasız döngüler de veriye girer (önemli: yalnız arızalı döngüleri almak β'yı yukarı çeker).
İlk bakımdan önceki arızalar kullanılmaz: o döngünün başlangıcı bilinmiyor.

İki saat ekseni var (V3):
  takvim   : bakımdan beri geçen gün
  kullanım : bakımdan beri ÇALIŞILAN saat (Arıza Defteri'nin vardiya üretimindeki planlı süre). Ekipman yoğun sezonda
             daha çok çalışır; aşınma takvime değil kullanıma bağlıysa doğru eksen budur. Takvimle bakınca yoğun dönemin
             fazla arızası "aşınma" gibi görünebilir (SR-ACL yanılgısı).
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Callable

GUN_SN = 86400.0


def zaman(iso: str) -> float:
    return datetime.fromisoformat(iso).timestamp()


TR = timezone(timedelta(hours=3))
VARDIYA_BAS = {1: 8, 2: 16, 3: 0}  # Türkiye saati; 3. vardiya günün 00-08'i


class KullanimSaati:
    """Ekipman başına "o ana kadar çalışılan saat" fonksiyonu (vardiya üretiminden).
    Vardiyada çalışılan süre (planli_dk) vardiyanın başından itibaren kullanılmış sayılır; arıza o aralıkta olur."""

    def __init__(self, uretim: list[dict]):
        sirali: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for r in uretim:
            g = datetime.fromisoformat(r["gun"]).replace(tzinfo=TR) + timedelta(hours=VARDIYA_BAS[r["vardiya"]])
            sirali[r["ekipman"]].append((g.timestamp(), float(r["planli_dk"])))
        self._e: dict[str, tuple[list[float], list[float], list[float], float]] = {}
        for e, l in sirali.items():
            l.sort()
            baslar, dk, toplam, t = [], [], [], 0.0
            for b, d in l:
                baslar.append(b); dk.append(d); toplam.append(t); t += d
            gun = (l[-1][0] - l[0][0]) / GUN_SN + 1
            self._e[e] = (baslar, dk, toplam, t / gun)  # son öğe: günlük ortalama dakika

    def gunluk_saat(self, ekipman: str) -> float | None:
        v = self._e.get(ekipman)
        return v[3] / 60 if v else None

    def __call__(self, ekipman: str, an: float) -> float:
        """Kayıt başından `an`a kadar çalışılan saat. Veri dışındaki an için ortalama kullanımla uzatılır."""
        baslar, dk, toplam, gunluk = self._e[ekipman]
        i = bisect_right(baslar, an) - 1
        if i < 0:
            return (an - baslar[0]) / GUN_SN * gunluk / 60
        gecen = (an - baslar[i]) / 60
        if gecen >= 480:  # vardiya verisi yok (bitmemiş vardiya ya da sonrası): ortalamayla uzat
            return (toplam[i] + dk[i] + (an - baslar[i] - 480 * 60) / GUN_SN * gunluk) / 60
        return (toplam[i] + min(dk[i], gecen)) / 60


def donguler(kayitlar: list[dict], ekipman_tipleri: dict[str, str], analiz_ani: float,
             saat: Callable[[str, float], float] | None = None) -> dict[tuple[str, str], list[tuple[float, list[float]]]]:
    """(tip, arıza türü) → döngüler. Tip içindeki bütün ekipmanların döngüleri birleştirilir (ortak β, η).
    saat verilmezse takvim (gün), verilirse kullanım ekseni: saat(ekipman, an) o ana kadar çalışılan saat."""
    olc = (lambda e, an: an / GUN_SN) if saat is None else saat
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
            if saat is not None and e not in getattr(saat, "_e", {e: 1}):
                continue
            o_bas = olc(e, bas)
            T = olc(e, bit) - o_bas
            if T <= 0:
                continue
            for tur in turler.get(tip, ()):
                ts = [max(0.0, olc(e, an) - o_bas) for t, an in arizalar.get(e, []) if t == tur and bas < an <= bit]
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
