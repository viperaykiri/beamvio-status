# beamvio-status

BeamVio hizmetlerinin sağlık ölçümü ve durum sayfası.

- **Ölçüm noktası (Türkiye):** `probe.py` + `agent/run.sh` sunucuda 5 dakikada bir çalışır;
  web sitesi, panel, güncelleme servisi, indirme ve bağlantı sunucusunu yoklar, sonucu
  tek commit'lik `heartbeat` dalına yazar.
- **Bekçi (GitHub Actions):** `watchdog.py` 10 dakikada bir nabzı değerlendirir. Bir kontrol
  başarısızsa ya da nabız 20 dakikadan eskiyse iş kırmızıya düşer ve GitHub hesap sahibine
  e-posta gönderir.
- **Durum sayfası:** `docs/` (GitHub Pages).

`KNOWN_ISSUES` (Actions değişkeni): alarm üretmeyecek ve sayfada gösterilmeyecek kontroller.
