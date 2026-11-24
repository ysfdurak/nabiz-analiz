# Sunucu kurulumu

Nabız Analiz dışarı açılmaz. Caddy bloğu ve alan adı yoktur. Nabız aynı `web` ağından `http://nabiz-analiz:8000` adresiyle okur. Claude'a Nabız'ın MCP kapısındaki `guvenilirlik` aracı üzerinden ulaşılır.

Sıra: Arıza Defteri (`kurulum-ariza.sh`) → Nabız (`kurulum-nabiz.sh`) → Nabız Analiz:

```bash
bash ~/ysfdurak.com/sunucu/kurulum-nabiz-analiz.sh
```

Betik kodu çeker, `.env`'i oluşturur (MCP kapalı), konteyneri kurar. Nabız'ın `.env`'inde `ANALIZ_URL` yoksa ekleyip Nabız'ı yeniden başlatır. Kontrol: `https://nabiz.ysfdurak.com/#/analiz`.

| Ayar | Varsayılan | Not |
| --- | --- | --- |
| `ARIZA_DEFTERI_URL` | `http://ariza-defteri:8080` | |
| `ANALIZ_GUN` | 360 | Arıza Defteri en az bu kadar geçmiş tutmalı (`GECMIS_GUN=360`) |
| `PLANSIZ_CARPAN` | 2 | Plansız duruşun planlıya göre maliyeti; bakım aralığı önerisi buna duyarlıdır |
| `MCP_ENABLED` | false | Açılacaksa anahtar gerekir ve dışarı açmak için Caddy bloğu eklenir |

Konteyner: `python:3.13.18-slim-trixie`, root olmayan kullanıcı, salt okunur kök, `cap_drop: ALL`, 384 MB. Veri tutmaz, yedek gerekmez.

**[doğrulanacak]** Docker imajı bu oturumda derlenemedi (Docker servisi yoktu). İlk kurulumda `sudo docker logs nabiz-analiz` ile açılışı kontrol et.

## Güncelleme

`bash ~/ysfdurak.com/sunucu/kurulum-nabiz-analiz.sh`. Bağımlılıklar `requirements.txt`'te özetle sabit olduğu için Dependabot PR'ı gelmeden sürüm değişmez.
