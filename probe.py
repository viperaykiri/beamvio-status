"""BeamVio dış sağlık yoklaması.

Her kontrol bağımsızdır; sonuç `docs/status.json`'a yazılır. Durum bir önceki
çalışmaya göre değiştiyse `docs/incidents.json`'a kayıt düşülür. Kritik bir
kontrol başarısızsa süreç 1 ile çıkar (iş kırmızıya düşer → GitHub e-posta ile
bildirir).

Ortam değişkenleri:
  RELAY_ADDR      host:port — relay'in doğrudan adresi (gizli; loglara basılmaz)
  KNOWN_ISSUES    virgülle ayrılmış kontrol adları: başarısız olsalar da alarm
                  üretmezler ve sayfada gösterilmezler (yalnız iş günlüğünde).
"""

import json
import os
import socket
import ssl
import struct
import sys
import time
import urllib.request
from datetime import datetime, timezone

WEB = "https://beamvio.com"
UA = "beamvio-status/1.0"
TIMEOUT = 15
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
MAX_INCIDENTS = 200


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


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def main():
    known = {x.strip() for x in os.environ.get("KNOWN_ISSUES", "").split(",") if x.strip()}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    prev = load(os.path.join(DOCS, "status.json"), {}).get("checks", {})
    incidents = load(os.path.join(DOCS, "incidents.json"), [])

    results = {}
    alarm = []
    changed = not prev
    for key, label, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, type(e).__name__
        state = "up" if ok else ("known" if key in known else "down")
        print(f"{key:13} {state:6} {detail}")
        # Bilinen sorun sayfada gösterilmez; yalnız iş günlüğünde kalır.
        if state == "known":
            continue
        old = prev.get(key, {})
        since = old.get("since") if old.get("state") == state else now
        results[key] = {"label": label, "state": state, "detail": detail, "since": since}
        if old and old.get("state") != state:
            changed = True
            incidents.insert(0, {"at": now, "check": key, "label": label, "from": old.get("state"), "to": state, "detail": detail})
        if state == "down":
            alarm.append(f"{label}: {detail}")

    os.makedirs(DOCS, exist_ok=True)
    overall = "down" if alarm else "up"
    status = {"checkedAt": now, "overall": overall, "checks": results}
    with open(os.path.join(DOCS, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DOCS, "incidents.json"), "w", encoding="utf-8") as f:
        json.dump(incidents[:MAX_INCIDENTS], f, ensure_ascii=False, indent=2)

    # Yalnız durum değişince commit edilir (iş akışı bu işarete bakar).
    if changed:
        open(os.path.join(os.path.dirname(DOCS), ".changed"), "w").close()

    if alarm:
        print("ALARM: " + "; ".join(alarm))
        sys.exit(1)


if __name__ == "__main__":
    main()
