"""Servis katmanı: web kapısı (/v1) ve MCP kapısı (/mcp) aynı fonksiyonları çağırır.
Rapor saatte bir hesaplanır (veri günde bir değişir); hesap sırasında gelen istekler önceki raporu alır."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone, timedelta

from .guvenilirlik import GucYasasi, en_iyi_aralik, guc_yasasi_tahmin
from .istemci import AnaKaynak, DisServisHatasi
from .veri import donguler, ortalama_sureler

TR = timezone(timedelta(hours=3))
YORUM = {
    "asinma": "Bakımdan uzaklaştıkça sıklaşıyor (aşınma). Planlı bakım bu arızayı önler; aralık bu türe göre ayarlanmalı.",
    "rastgele": "Zamandan bağımsız (rastgele). Planlı bakımı sıklaştırmak azaltmaz; kontrol listesi, otonom bakım ve kök neden analizi gerekir.",
    "erken": "Bakımdan hemen sonra sık (erken dönem). Bakım işinin kalitesine bakılmalı: montaj, ayar, son kontrol.",
    "yetersiz": "Güvenilir sonuç için yeterli arıza yok.",
}


class KuralHatasi(Exception):
    def __init__(self, mesaj: str, durum: int = 400):
        super().__init__(mesaj)
        self.durum = durum


class Analizci:
    def __init__(self, kaynak: AnaKaynak, gun: int = 360, plansiz_carpan: float = 2.0, sure_sn: int = 3600, saat=time.time):
        self.kaynak, self.gun, self.plansiz_carpan, self.sure_sn, self.saat = kaynak, gun, plansiz_carpan, sure_sn, saat
        self._rapor: dict | None = None
        self._zaman = 0.0
        self._kilit = threading.Lock()

    def rapor(self) -> dict:
        if self._rapor is not None and self.saat() - self._zaman < self.sure_sn:
            return self._rapor
        if not self._kilit.acquire(blocking=self._rapor is None):
            return self._rapor  # başka istek hesaplıyor: eskisini ver
        try:
            self._rapor = self._hesapla()
            self._zaman = self.saat()
            return self._rapor
        except DisServisHatasi as h:
            if self._rapor is not None:
                return {**self._rapor, "uyari": f"Güncellenemedi, son rapor gösteriliyor: {h}"}
            raise
        finally:
            self._kilit.release()

    def _hesapla(self) -> dict:
        ana = self.kaynak.ana_veriler()
        tipler = {e["kod"]: e["tip"] for e in ana["ekipmanlar"]}
        kayitlar = self.kaynak.kayitlar(self.gun, list(tipler))
        an = self.saat()
        d = donguler(kayitlar, tipler, an)
        tur_sure, bakim_sure = ortalama_sureler(kayitlar)
        tur_bilgi = {t["kod"]: t for t in ana["arizaTurleri"]}

        modeller: dict[str, GucYasasi] = {}
        turler = []
        for (tip, tur), dl in sorted(d.items()):
            m = guc_yasasi_tahmin(dl)
            modeller[tur] = m
            b = tur_bilgi.get(tur, {})
            turler.append({
                "tur": tur, "ad": b.get("ad", tur), "tip": tip, "kayip": b.get("kayip"), **m.sozluk(),
                "ortSureDk": round(tur_sure.get(tur, 0.0), 1), "yorum": YORUM[m.sinif],
            })

        tip_sonuc = []
        for tip, t in ana["tipler"].items():
            bilesen = [(modeller[x["tur"]], tur_sure.get(x["tur"], 0.0) * self.plansiz_carpan) for x in turler if x["tip"] == tip and x["tur"] in modeller]
            cp = bakim_sure.get(tip)
            if not bilesen or cp is None:
                continue
            o = en_iyi_aralik(bilesen, cp, float(t["bakimGun"]))
            tip_sonuc.append({
                "tip": tip, "ad": t["ad"], "bakimDk": round(cp, 1), **o.sozluk(),
                "asinanTurler": [x["tur"] for x in turler if x["tip"] == tip and x["sinif"] == "asinma"],
            })
        return {
            "olusturma": datetime.fromtimestamp(an, TR).isoformat(timespec="seconds"),
            "donemGun": self.gun,
            "kayit": len(kayitlar),
            "plansizCarpan": self.plansiz_carpan,
            "yontem": "Güç yasası süreci (Crow-AMSAA), bakım döngüsü başına minimal onarım; β için %90 profil olabilirlik aralığı. Bakım aralığı: periyodik bakım + minimal onarım maliyet oranı (Barlow-Hunter), maliyet birimi duruş dakikası; plansız duruş planlıdan " + f"{self.plansiz_carpan:g} kat pahalı sayılır.",
            "turler": turler,
            "tipler": tip_sonuc,
        }

    def tur(self, kod: str) -> dict:
        for t in self.rapor()["turler"]:
            if t["tur"] == kod:
                return t
        raise KuralHatasi("Arıza türü raporda yok (kod yanlış ya da veri yok).", 404)

    def ozet(self) -> dict:
        r = self.rapor()
        sayi = {s: sum(1 for t in r["turler"] if t["sinif"] == s) for s in ("asinma", "rastgele", "erken", "yetersiz")}
        return {"olusturma": r["olusturma"], "siniflar": sayi, "tipler": r["tipler"]}
