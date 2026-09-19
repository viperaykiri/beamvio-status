"""BeamVio sağlık ölçümü (ölçüm noktası: Türkiye).

Kontrolleri çalıştırır ve ham sonucu `heartbeat.json`'a yazar. Değerlendirme
(durum, olay kaydı, alarm) GitHub'daki bekçi iş akışında (`watchdog.py`) yapılır;
bu betik yalnız ölçer.

Ortam değişkenleri:
  RELAY_ADDR   host:port — bağlantı sunucusunun doğrudan adresi
"""

import json
import os
import socket
import ssl
import struct
import time
import urllib.request
from datetime import datetime, timezone

WEB = "https://beamvio.com"
UA = "beamvio-status/1.0"
TIMEOUT = 15


def http(url, method="GET"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            return r.status, r.read(200_000) if method == "GET" else b""
    except urllib.error.HTTPError as e:
        return e.code, b""


def check_site():
    code, _ = http(f"{WEB}/tr")
    return code == 200, f"HTTP {code}"


def check_panel():
    code, _ = http(f"{WEB}/tr/login")
    return code == 200, f"HTTP {code}"


def check_manifest():
    code, body = http(f"{WEB}/api/v1/update/manifest?channel=stable")
    if code != 200:
        return False, f"HTTP {code}"
    data = json.loads(body)
    ok = bool(data.get("available")) and bool(data.get("version")) and len(data.get("sha256", "")) == 64
    return ok, f"sürüm {data.get('version')}" if ok else "manifest eksik"


def check_download():
    code, _ = http(f"{WEB}/download/BeamVio-Setup.exe", method="HEAD")
    return code == 200, f"HTTP {code}"


def relay_handshake(host, port):
    """Relay'e bağlanıp challenge ister; geçerli yanıtta süre (ms) döner."""
    t0 = time.monotonic()
    with socket.create_connection((host, port), timeout=TIMEOUT) as s:
        s.settimeout(TIMEOUT)
        s.sendall(struct.pack(">I", 1) + bytes([0x0B]))
        head = b""
        while len(head) < 4:
            chunk = s.recv(4 - len(head))
            if not chunk:
                raise ConnectionError("bağlantı kapandı")
            head += chunk
        n = struct.unpack(">I", head)[0]
        if n < 1 or n > 4096:
            raise ValueError("geçersiz çerçeve")
        tag = s.recv(1)
        if tag != b"\x0c":
            raise ValueError("beklenmeyen yanıt")
    return int((time.monotonic() - t0) * 1000)


def check_relay():
    addr = os.environ.get("RELAY_ADDR", "").strip()
    if not addr:
        return False, "yapılandırılmamış"
    host, _, port = addr.rpartition(":")
    try:
        ms = relay_handshake(host, int(port))
        return True, f"{ms} ms"
    except Exception as e:  # adres içermeyen kısa hata sınıfı
        return False, type(e).__name__


def check_relay_public():
    try:
        ms = relay_handshake("relay.beamvio.com", 21118)
        return True, f"{ms} ms"
    except Exception as e:
        return False, type(e).__name__


CHECKS = [
    ("site", "Web sitesi", check_site),
    ("panel", "Yönetim paneli", check_panel),
    ("manifest", "Güncelleme servisi", check_manifest),
    ("download", "İndirme", check_download),
    ("relay", "Bağlantı sunucusu", check_relay),
    ("relay_public", "Bağlantı sunucusu (genel DNS)", check_relay_public),
]


def main():
    out = os.environ.get("HEARTBEAT_FILE", "heartbeat.json")
    results = {}
    for key, label, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, type(e).__name__
        results[key] = {"label": label, "ok": ok, "detail": detail}
    beat = {
        "checkedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "results": results,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(beat, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
