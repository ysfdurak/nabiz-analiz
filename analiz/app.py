"""HTTP katmanı: /healthz, /v1 (okuma), /mcp (Claude, anahtarla). Kural içermez.

Python şablonunun (ysfdurak.com → sablonlar/python-servis) ilk kullanıcısıdır; Node servislerindeki kalıbın aynısı:
  - Her yanıtta güvenlik başlıkları ve sıkı CSP (bu servis HTML sunmaz: default-src 'none')
  - IP başına dakikalık istek sınırı (gerçek IP yalnız güvenilen vekilden)
  - MCP: sabit sürede karşılaştırılan anahtar; anahtarlar bellekte yalnız özet olarak durur
  - Beklenmeyen hatada iç ayrıntı sızmaz; OpenAPI/Swagger sayfaları kapalı (dış CDN yükler, gerek yok)
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager

import mcp_types
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from . import __version__
from .config import Ayarlar
from .gercek_ip import gercek_ip
from .istemci import DisServisHatasi
from .servis import Analizci, KuralHatasi

log = logging.getLogger("nabiz-analiz")
BASLIKLAR = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-frame-options", b"DENY"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=(), usb=()"),
    (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
    (b"cache-control", b"no-store"),
]
OKUMA = mcp_types.ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
TALIMAT = """Nabız Analiz, Yıldız Ev & Yaşam deposundaki ekipman arızalarının güvenilirlik analizidir (veri Arıza Defteri'nden, SENTETİK).
Her arıza türü için güç yasası (Crow-AMSAA) β: >1 aşınma (planlı bakım işe yarar), ≈1 rastgele (bakım sıklaştırmak işe yaramaz), <1 erken dönem (bakım kalitesi).
Ekipman tipi başına bakım aralığı önerisi: periyodik bakım + minimal onarım maliyet oranı, birim duruş dakikası. Sonuçları önerirken güven aralığını da söyle."""


def _ozet(v: str) -> bytes:
    return hashlib.sha256(v.encode()).digest()


def olustur(ayarlar: Ayarlar, analizci: Analizci, saat=time.monotonic):
    mcp_ozetleri = [_ozet(a) for a in ayarlar.mcp_anahtarlari]

    # --- MCP kapısı: servisin okuma fonksiyonları araç olarak -------------------------------------------
    mcp = MCPServer(name="nabiz-analiz", version=__version__, instructions=TALIMAT)

    @mcp.tool(annotations=OKUMA, description="Güvenilirlik özeti: sınıf sayıları ve ekipman tipi başına bakım aralığı önerisi.")
    def guvenilirlik_ozeti() -> dict:
        return analizci.ozet()

    @mcp.tool(annotations=OKUMA, description="Bütün arıza türleri: β (güven aralığıyla), η (gün), sınıf, ortalama duruş, yorum. tip verilirse yalnız o ekipman tipi (forklift, reach_truck, konveyor, sorter, strec).")
    def ariza_turleri(tip: str | None = None) -> dict:
        r = analizci.rapor()
        return {"yontem": r["yontem"], "turler": [t for t in r["turler"] if not tip or t["tip"] == tip]}

    @mcp.tool(annotations=OKUMA, description="Tek arıza türünün güvenilirlik sonucu (kod ör. RT-MAS).")
    def ariza_turu(kod: str) -> dict:
        return analizci.tur(kod)

    mcp_app = mcp.streamable_http_app(
        streamable_http_path="/mcp", json_response=True, stateless_http=True, max_request_body_size=64 * 1024,
        # Ana bilgisayar denetimi kapalı: istek ters vekilden ya da iç ağdan gelir ve anahtar ister (aşağıda).
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    # --- Web kapısı ----------------------------------------------------------------------------------------
    @asynccontextmanager
    async def omur(_app):
        async with mcp_app.router.lifespan_context(mcp_app):
            yield

    api = FastAPI(title="Nabız Analiz", version=__version__, docs_url=None, redoc_url=None, openapi_url=None, lifespan=omur)

    @api.exception_handler(KuralHatasi)
    async def kural(_r: Request, h: KuralHatasi):
        return JSONResponse({"hata": str(h)}, status_code=h.durum)

    @api.exception_handler(DisServisHatasi)
    async def dis(_r: Request, h: DisServisHatasi):
        return JSONResponse({"hata": str(h)}, status_code=503)

    @api.exception_handler(Exception)
    async def beklenmeyen(_r: Request, h: Exception):
        log.exception("Beklenmeyen hata")
        return JSONResponse({"hata": "İstek işlenemedi."}, status_code=500)

    @api.get("/healthz")
    def saglik():
        return {"ok": True}

    @api.get("/v1/durum")
    def durum():
        r = analizci._rapor
        return {"surum": __version__, "sonRapor": r["olusturma"] if r else None, "donemGun": ayarlar.gun, "plansizCarpan": ayarlar.plansiz_carpan}

    @api.get("/v1/guvenilirlik")
    def guvenilirlik(tip: str | None = None):
        r = analizci.rapor()
        if tip and tip not in {t["tip"] for t in r["turler"]}:
            raise KuralHatasi("Ekipman tipi tanınmıyor.")
        return {**r, "turler": [t for t in r["turler"] if not tip or t["tip"] == tip]}

    @api.get("/v1/ozet")
    def ozet():
        return analizci.ozet()

    @api.get("/v1/tur/{kod}")
    def tur(kod: str):
        if len(kod) > 10:
            raise KuralHatasi("Kod geçersiz.")
        return analizci.tur(kod)

    # --- Dış kat: güvenlik başlıkları, hız sınırı, MCP yönlendirme ----------------------------------------
    pencere: dict[str, list[float]] = {}

    async def yanit(send, durum: int, govde: bytes, ek=()):
        await send({"type": "http.response.start", "status": durum, "headers": [(b"content-type", b"application/json; charset=utf-8"), *BASLIKLAR, *ek]})
        await send({"type": "http.response.body", "body": govde})

    def mcp_yetkili(scope) -> bool:
        if not mcp_ozetleri:
            return False
        basliklar = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        yetki = basliklar.get("authorization", "")
        sunulan = yetki[7:].strip() if yetki.lower().startswith("bearer ") else scope["path"][len("/mcp/"):]
        if not sunulan:
            return False
        h = _ozet(sunulan)
        return any(hmac.compare_digest(a, h) for a in mcp_ozetleri)

    async def uygulama(scope, receive, send):
        if scope["type"] != "http":
            return await api(scope, receive, send)

        async def basliklarla(mesaj):
            if mesaj["type"] == "http.response.start":
                var = {k.lower() for k, _ in mesaj.get("headers", [])}
                mesaj["headers"] = [*mesaj.get("headers", []), *[(k, v) for k, v in BASLIKLAR if k not in var]]
            await send(mesaj)

        yol = scope["path"]
        if yol == "/healthz":
            return await api(scope, receive, basliklarla)
        basliklar = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        ip = gercek_ip((scope.get("client") or ("", 0))[0], basliklar)
        an = saat()
        k = pencere.setdefault(ip, [an, 0])
        if an - k[0] > 60:
            k[0], k[1] = an, 0
        k[1] += 1
        if len(pencere) > 10_000:
            pencere.clear()
        if k[1] > ayarlar.dakikalik_istek:
            return await yanit(send, 429, '{"hata": "Çok hızlı istek. Bir dakika sonra yeniden dene."}'.encode(), [(b"retry-after", b"60")])
        if yol == "/mcp" or yol.startswith("/mcp/"):
            if not ayarlar.mcp_acik:
                return await yanit(send, 404, '{"hata": "MCP kapısı bu kurulumda kapalı."}'.encode())
            if not mcp_yetkili(scope):
                return await yanit(send, 401, '{"hata": "Geçerli bir MCP erişim anahtarı gerekli."}'.encode())
            if scope["method"] != "POST":
                return await yanit(send, 405, '{"hata": "Yöntem desteklenmiyor."}'.encode(), [(b"allow", b"POST")])
            return await mcp_app({**scope, "path": "/mcp", "raw_path": b"/mcp"}, receive, basliklarla)
        return await api(scope, receive, basliklarla)

    return uygulama
