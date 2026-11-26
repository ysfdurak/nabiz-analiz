"""HTTP: başlıklar, hız sınırı, MCP anahtarı, dış servis hatası, kapalı belgeler."""
import pytest
from fastapi.testclient import TestClient

from analiz.app import olustur
from analiz.config import yukle
from analiz.servis import Analizci

MCP = "m" * 40


def istemci(ornek, sahte_kaynak, ag=True, **env):
    a = yukle({"ARIZA_DEFTERI_URL": "http://ariza-defteri:8080", "MCP_ENABLED": "true", "MCP_ANAHTARLARI": MCP, **env})
    assert a.hatalar == []
    kaynak = sahte_kaynak(ornek, ag)
    return TestClient(olustur(a, Analizci(kaynak, saat=lambda: ornek["analizAni"]))), kaynak


def test_okuma_ve_basliklar(ornek, sahte_kaynak):
    c, _ = istemci(ornek, sahte_kaynak)
    with c:
        r = c.get("/v1/guvenilirlik?tip=reach_truck")
        assert r.status_code == 200
        assert {t["tip"] for t in r.json()["turler"]} == {"reach_truck"}
        for b in ("content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy"):
            assert b in r.headers
        assert r.headers["content-security-policy"].startswith("default-src 'none'")
        assert c.get("/v1/tur/RT-MAS").json()["sinif"] == "asinma"
        assert c.get("/v1/tur/YOK-1").status_code == 404
        assert c.get("/v1/guvenilirlik?tip=uzay").status_code == 400
        assert c.get("/v1/ozet").json()["siniflar"]["asinma"] >= 3  # gerçek sıklıkta (surum 6) 3 yılda 4 aşınan tür görünür
        for yol in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(yol).status_code == 404


def test_dis_servis_yoksa_503_ve_ayrinti_sizmaz(ornek, sahte_kaynak):
    c, _ = istemci(ornek, sahte_kaynak, ag=False)
    with c:
        r = c.get("/v1/ozet")
        assert r.status_code == 503
        assert "Traceback" not in r.text


def test_rapor_onbellekte(ornek, sahte_kaynak):
    c, k = istemci(ornek, sahte_kaynak)
    with c:
        for _ in range(5):
            c.get("/v1/ozet")
        assert k.cagri == 1


def test_hiz_siniri(ornek, sahte_kaynak):
    c, _ = istemci(ornek, sahte_kaynak, DAKIKALIK_ISTEK="5")
    with c:
        kodlar = [c.get("/v1/durum").status_code for _ in range(7)]
        assert kodlar[-2:] == [429, 429]
        assert c.get("/healthz").status_code == 200
        # Sahte X-Forwarded-For dışarıdan gelirse sınır atlatılamaz (TestClient 'testclient' adresinden gelir: özel ağ değil)
        assert c.get("/v1/durum", headers={"x-forwarded-for": "1.2.3.4"}).status_code == 429


def test_mcp(ornek, sahte_kaynak):
    c, _ = istemci(ornek, sahte_kaynak)
    h = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
    with c:
        assert c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=h).status_code == 401
        assert c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers={**h, "authorization": "Bearer " + "y" * 40}).status_code == 401
        hh = {**h, "authorization": f"Bearer {MCP}"}
        c.post("/mcp", json={"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}, headers=hh)
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, headers=hh)
        assert r.status_code == 200, r.text
        araclar = r.json()["result"]["tools"]
        assert sorted(a["name"] for a in araclar) == ["ariza_turleri", "ariza_turu", "guvenilirlik_ozeti"]
        assert all(a["annotations"]["readOnlyHint"] for a in araclar)
        r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "ariza_turu", "arguments": {"kod": "RT-MAS"}}}, headers=hh)
        assert "asinma" in r.text
        assert c.get("/mcp", headers=hh).status_code == 405


def test_mcp_kapali_ve_ayar_hatalari(ornek, sahte_kaynak):
    assert yukle({}).hatalar
    assert yukle({"ARIZA_DEFTERI_URL": "http://x", "MCP_ENABLED": "true"}).hatalar
    assert yukle({"ARIZA_DEFTERI_URL": "http://x", "MCP_ANAHTARLARI": "kisa"}).hatalar
    c, _ = istemci(ornek, sahte_kaynak, MCP_ENABLED="false")
    with c:
        assert c.post("/mcp", json={}).status_code == 404
