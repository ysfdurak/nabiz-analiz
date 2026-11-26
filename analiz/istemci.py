"""Arıza Defteri istemcisi: ana veriler ve ekipman başına kayıtlar (zaman aşımıyla, sunucudan sunucuya)."""
from __future__ import annotations

import httpx


class DisServisHatasi(Exception):
    pass


class AnaKaynak:
    def __init__(self, url: str, istemci: httpx.Client | None = None, zaman_asimi: float = 10.0):
        self.kok = url.rstrip("/")
        self.istemci = istemci or httpx.Client(timeout=zaman_asimi, headers={"accept": "application/json"})

    def _al(self, yol: str, **params) -> dict:
        try:
            y = self.istemci.get(self.kok + yol, params=params)
        except httpx.HTTPError as h:
            raise DisServisHatasi(f"Arıza Defteri'ne ulaşılamadı ({type(h).__name__}).") from h
        if y.status_code != 200:
            raise DisServisHatasi(f"Arıza Defteri {y.status_code} döndü.")
        return y.json()

    def ana_veriler(self) -> dict:
        return self._al("/v1/ana-veriler")

    def kayitlar(self, gun: int, ekipmanlar: list[str]) -> list[dict]:
        """Ekipman başına çekilir (bir ekipmanın 3 yılı 2000 kaydı aşmaz; toplu istek aşabilir)."""
        hepsi: list[dict] = []
        for e in ekipmanlar:
            hepsi += self._al("/v1/arizalar", gun=gun, ekipman=e, limit=2000)["kayitlar"]
        return hepsi

    def uretim(self, gun: int, ekipmanlar: list[str]) -> list[dict]:
        """Vardiya üretimi (planli_dk: ekipmanın o vardiyada kullanıldığı süre). Kullanım ekseni için."""
        hepsi: list[dict] = []
        for e in ekipmanlar:
            hepsi += self._al("/v1/uretim", gun=gun, ekipman=e)["satirlar"]
        return hepsi
