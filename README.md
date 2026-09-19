# beamvio-status

BeamVio hizmetlerinin dış sağlık yoklaması ve durum sayfası.

- `probe.py` — web sitesi, panel, güncelleme servisi, indirme ve bağlantı sunucusunu yoklar.
- `.github/workflows/probe.yml` — 10 dakikada bir çalışır; kritik bir kontrol başarısızsa iş
  kırmızıya düşer ve GitHub hesap sahibine e-posta ile bildirir.
- `docs/` — GitHub Pages durum sayfası (`status.json`, `incidents.json`).

Ayarlar (depo → Settings → Secrets and variables → Actions):

| Ad | Tür | Açıklama |
|---|---|---|
| `RELAY_ADDR` | secret | Bağlantı sunucusunun doğrudan adresi (`host:port`) |
| `KNOWN_ISSUES` | variable | Alarm üretmeyecek kontroller (virgülle), ör. `relay_public` |
