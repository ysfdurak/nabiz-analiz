import gzip
import json
from pathlib import Path

import pytest

VERI = Path(__file__).parent / "veri" / "ariza-defteri-360.json.gz"


@pytest.fixture(scope="session")
def ornek():
    """Arıza Defteri'nden alınmış 360 günlük sentetik kayıt (üreticinin gizli β değerleri testlerde 'gerçek' olarak bilinir)."""
    with gzip.open(VERI, "rt", encoding="utf-8") as f:
        return json.load(f)


class SahteKaynak:
    """Arıza Defteri yerine dosyadan okur; ag=False ise bağlantı hatası verir."""
    def __init__(self, ornek, ag=True):
        self.ornek, self.ag, self.cagri = ornek, ag, 0

    def ana_veriler(self):
        from analiz.istemci import DisServisHatasi
        self.cagri += 1
        if not self.ag:
            raise DisServisHatasi("Arıza Defteri'ne ulaşılamadı (ConnectError).")
        return self.ornek["anaVeriler"]

    def kayitlar(self, gun, ekipmanlar):
        return self.ornek["kayitlar"]


@pytest.fixture
def sahte_kaynak():
    return SahteKaynak
