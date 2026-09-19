#!/usr/bin/env bash
# Ölçüm noktası: kontrolleri çalıştırır ve sonucu depo'nun tek commit'lik
# `heartbeat` dalına zorla yazar (geçmiş büyümez). Cron ile 5 dakikada bir.
#
# Kurulum: /opt/beamvio-status/{probe.py,run.sh,deploy_key}
# Ortam:   /etc/beamvio-status.env  (RELAY_ADDR=host:port)
set -euo pipefail

DIR=/opt/beamvio-status
REPO=git@github.com:viperaykiri/beamvio-status.git
export GIT_SSH_COMMAND="ssh -i $DIR/deploy_key -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

set -a
# shellcheck disable=SC1091
. /etc/beamvio-status.env
set +a

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

HEARTBEAT_FILE="$work/heartbeat.json" timeout 120 python3 "$DIR/probe.py" >/dev/null

cd "$work"
git init -q
git add heartbeat.json
git -c user.name=beamvio-probe -c user.email=probe@beamvio.invalid commit -q -m "nabız"
git push -q -f "$REPO" HEAD:heartbeat
