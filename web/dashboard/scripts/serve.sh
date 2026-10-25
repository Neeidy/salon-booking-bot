#!/bin/sh
# serve.sh — how ops/systemd/salon-dashboard.service starts the dashboard (7-F1, item 13).
#
# WHY a wrapper: the dashboard reads its client config from CLIENT_CONFIG_JSON (lib/shopConfig.ts, fail-closed), and
# a systemd Environment= line cannot carry a file's contents. The unit names the FILE; this reads it into the env
# and then becomes `npm start` (exec), so no idle shell sits between systemd and npm. npm runs the server as its
# child; both live in the unit's cgroup, so a stop or a crash takes the whole tree down together.
#
# Exit 78 (EX_CONFIG) when the config is unset, not a regular file, unreadable or empty: the unit's
# RestartPreventExitStatus=78 stops there instead of restarting into the same error five times.
set -eu

cfg="${CLIENT_CONFIG_FILE:-}"
if [ -z "$cfg" ] || [ ! -f "$cfg" ] || [ ! -r "$cfg" ] || [ ! -s "$cfg" ]; then
  echo "serve.sh: CLIENT_CONFIG_FILE is unset, not a file, unreadable or empty ('$cfg') — not starting" >&2
  exit 78
fi
CLIENT_CONFIG_JSON="$(cat "$cfg")"
export CLIENT_CONFIG_JSON
exec npm start
