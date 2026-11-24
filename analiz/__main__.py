"""Başlatma: python -m analiz   (ayarlar: .env.example)"""
import logging
import sys

import uvicorn

from .app import olustur
from .config import yukle
from .istemci import AnaKaynak
from .servis import Analizci

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)  # her Arıza Defteri isteğini kayda yazmasın


def main() -> None:
    ayarlar = yukle()
    if ayarlar.hatalar:
        print("Nabız Analiz başlatılamadı, ayarları kontrol et:\n - " + "\n - ".join(ayarlar.hatalar), file=sys.stderr)
        sys.exit(1)
    analizci = Analizci(AnaKaynak(ayarlar.ariza_url), gun=ayarlar.gun, plansiz_carpan=ayarlar.plansiz_carpan)
    import os
    port = int(os.environ.get("PORT", "8000"))
    logging.getLogger("nabiz-analiz").info("Nabız Analiz: %s · Arıza Defteri %s · MCP %s", port, ayarlar.ariza_url, "açık" if ayarlar.mcp_acik else "kapalı")
    # Ters vekilin arkasında: X-Forwarded-For'u uvicorn değil gercek_ip yorumlar (proxy_headers kapalı).
    uvicorn.run(olustur(ayarlar, analizci), host=os.environ.get("HOST", "0.0.0.0"), port=port, proxy_headers=False,
                server_header=False, date_header=False, log_level="info", timeout_keep_alive=5, limit_concurrency=64)


if __name__ == "__main__":
    main()
