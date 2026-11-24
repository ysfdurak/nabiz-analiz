"""Ayarlar: ortam değişkenlerinden. Hatalar toplu döner; sunucu eksik ayarla başlamaz."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse


def _sayi(v, varsayilan, alt, ust):
    try:
        return min(ust, max(alt, int(v)))
    except (TypeError, ValueError):
        return varsayilan


@dataclass
class Ayarlar:
    ariza_url: str
    gun: int
    plansiz_carpan: float
    dakikalik_istek: int
    mcp_acik: bool
    mcp_anahtarlari: list[str] = field(default_factory=list)
    hatalar: list[str] = field(default_factory=list)


def yukle(env=os.environ) -> Ayarlar:
    hatalar = []
    url = (env.get("ARIZA_DEFTERI_URL") or "").strip()
    if not url or urlparse(url).scheme not in ("http", "https"):
        hatalar.append("ARIZA_DEFTERI_URL gerekli (ör. http://ariza-defteri:8080).")
    anahtarlar = [a.strip() for a in (env.get("MCP_ANAHTARLARI") or "").split(",") if a.strip()]
    if any(len(a) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]+", a) for a in anahtarlar):
        hatalar.append("MCP_ANAHTARLARI: her anahtar en az 32 karakter, yalnız harf, rakam, tire, alt çizgi (openssl rand -hex 32).")
    mcp_acik = env.get("MCP_ENABLED") == "true"
    if mcp_acik and not anahtarlar:
        hatalar.append("MCP_ENABLED=true için MCP_ANAHTARLARI gerekli.")
    try:
        carpan = min(10.0, max(1.0, float(env.get("PLANSIZ_CARPAN", "2"))))
    except ValueError:
        carpan = 2.0
    return Ayarlar(url, _sayi(env.get("ANALIZ_GUN"), 360, 90, 365), carpan, _sayi(env.get("DAKIKALIK_ISTEK"), 60, 5, 1000), mcp_acik, anahtarlar, hatalar)
