"""Test verisini yeniden üretir: çalışan bir Arıza Defteri'nden 3 yıllık (1095 gün) kayıt ve vardiya üretimi alır.

    python -m tools.ornek_al http://localhost:8091

Çıktı: tests/veri/ariza-defteri-3yil.json.gz (anaVeriler, kayitlar, uretim, analizAni). Arıza Defteri'nin senaryo sürümü
değişince (ör. surum 4: kullanım, surum 5: akü şarjı arıza değil) bunu çalıştırıp testleri ve dokümandaki kör deneme tablosunu yenile.
"""
from __future__ import annotations

import gzip
import json
import sys
import time
from pathlib import Path

from analiz.istemci import AnaKaynak

CIKTI = Path(__file__).resolve().parent.parent / "tests" / "veri" / "ariza-defteri-3yil.json.gz"


def main(url: str) -> None:
    k = AnaKaynak(url)
    ana = k.ana_veriler()
    ekipmanlar = [e["kod"] for e in ana["ekipmanlar"]]
    veri = {"analizAni": time.time(), "anaVeriler": ana, "kayitlar": k.kayitlar(1095, ekipmanlar), "uretim": k.uretim(1095, ekipmanlar)}
    with gzip.open(CIKTI, "wt", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{CIKTI.name}: {len(veri['kayitlar'])} kayıt, {len(veri['uretim'])} vardiya satırı")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8091")
