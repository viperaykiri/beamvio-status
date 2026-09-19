"""BeamVio durum bekçisi (GitHub Actions).

Ölçüm noktasının `heartbeat` dalına yazdığı son sonucu değerlendirir:
- Nabız `STALE_MINUTES`'tan eskiyse ölçüm noktası (ve büyük olasılıkla sunucu)
  erişilemez sayılır → alarm.
- Kontrol başarısızsa → alarm (KNOWN_ISSUES'taki kontroller hariç).
Durum değiştiyse `docs/status.json` + `docs/incidents.json` güncellenir ve
`.changed` işareti bırakılır. Alarm varsa süreç 1 ile çıkar (iş kırmızıya
düşer → GitHub hesap sahibine e-posta).

Ortam değişkenleri:
  HEARTBEAT_FILE  ölçüm sonucu (varsayılan: heartbeat.json)
  KNOWN_ISSUES    virgülle ayrılmış kontrol adları: alarm üretmez, sayfada
                  gösterilmez (yalnız iş günlüğünde).
"""

import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
STALE_MINUTES = 20
MAX_INCIDENTS = 200


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def main():
    known = {x.strip() for x in os.environ.get("KNOWN_ISSUES", "").split(",") if x.strip()}
    now_dt = datetime.now(timezone.utc).replace(microsecond=0)
    now = now_dt.isoformat()
    beat = load(os.environ.get("HEARTBEAT_FILE", "heartbeat.json"), {})
    prev = load(os.path.join(DOCS, "status.json"), {}).get("checks", {})
    incidents = load(os.path.join(DOCS, "incidents.json"), [])

    measured = {}
    age_min = None
    if beat.get("checkedAt"):
        age_min = (now_dt - datetime.fromisoformat(beat["checkedAt"])).total_seconds() / 60
    fresh = age_min is not None and age_min <= STALE_MINUTES
    measured["probe"] = {
        "label": "Ölçüm noktası",
        "ok": fresh,
        "detail": f"{age_min:.0f} dk önce" if age_min is not None else "veri yok",
    }
    if fresh:
        measured.update(beat.get("results", {}))

    results = {}
    alarm = []
    changed = not prev
    for key, r in measured.items():
        state = "up" if r.get("ok") else ("known" if key in known else "down")
        print(f"{key:13} {state:6} {r.get('detail')}")
        if state == "known":
            continue
        old = prev.get(key, {})
        since = old.get("since") if old.get("state") == state else now
        results[key] = {"label": r.get("label", key), "state": state, "detail": r.get("detail"), "since": since}
        if old and old.get("state") != state:
            changed = True
            incidents.insert(0, {"at": now, "check": key, "label": results[key]["label"],
                                 "from": old.get("state"), "to": state, "detail": r.get("detail")})
        if state == "down":
            alarm.append(f"{results[key]['label']}: {r.get('detail')}")

    # Nabız bayatken ölçülemeyen kontroller önceki durumlarıyla sayfada kalır.
    if not fresh:
        for key, old in prev.items():
            results.setdefault(key, old)

    os.makedirs(DOCS, exist_ok=True)
    status = {"checkedAt": now, "overall": "down" if alarm else "up", "checks": results}
    with open(os.path.join(DOCS, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DOCS, "incidents.json"), "w", encoding="utf-8") as f:
        json.dump(incidents[:MAX_INCIDENTS], f, ensure_ascii=False, indent=2)
    if changed:
        open(os.path.join(ROOT, ".changed"), "w").close()

    if alarm:
        print("ALARM: " + "; ".join(alarm))
        sys.exit(1)


if __name__ == "__main__":
    main()
