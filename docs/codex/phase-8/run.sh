#!/bin/bash
# Phase 8 R2: ONE Codex run on CRT #14 in the 7-2 R2 harness — the runner of attempt 2, committed as a record
# (docs/codex/phase-8/containment.md). The only change from the file that ran: the session scratch directory and the
# repository path were literals there and are parameters here. Prints counts and statuses only (never the auth file,
# never a command's output). Run after the prompt commit is pushed; the pin is origin/main.
# Usage: bash docs/codex/phase-8/run.sh <an empty scratch directory OUTSIDE the repository>
set -uo pipefail
S=${1:?usage: run.sh <scratch directory outside the repository>}
R=$(git rev-parse --show-toplevel)
case "$(realpath "$S")/" in "$(realpath "$R")"/*) echo "STOP: the scratch directory is inside the repository"; exit 1;; esac
EXP=$S/export
CH=$S/codexhome
PIN=$(git -C "$R" rev-parse refs/remotes/origin/main)
[ "$PIN" = "$(git -C "$R" rev-parse HEAD)" ] || { echo "STOP: HEAD is not the pushed origin/main"; exit 1; }
[ ! -e "$EXP" ] && [ ! -e "$CH" ] || { echo "STOP: export or codex home already exists (remove by literal path)"; exit 1; }

# the export: a single-branch fetch of the pushed main into an empty repository — no remote, no reflog, no hooks
git init -q "$EXP" && git -C "$EXP" -c core.logAllRefUpdates=false fetch -q --no-tags "$R" refs/remotes/origin/main:refs/heads/main \
  && git -C "$EXP" -c core.logAllRefUpdates=false checkout -q main || { echo "STOP: export failed"; exit 1; }
rm -r "$EXP/.git/hooks"; [ -d "$EXP/.git/logs" ] && rm -r "$EXP/.git/logs"
[ "$(git -C "$EXP" rev-parse HEAD)" = "$PIN" ] && [ -z "$(git -C "$EXP" remote)" ] || { echo "STOP: export is not the pin"; exit 1; }
NFILES=$(find "$EXP" -type f | wc -l)
echo "pin ${PIN:0:7} · export files $NFILES"

# the temporary codex home: a copy of the login file only, 0700 / 0600; the prompt with {PIN} filled
mkdir -m 700 "$CH" && install -m 600 "$HOME/.codex/auth.json" "$CH/auth.json"
git -C "$R" show "$PIN:docs/codex/phase-8/prompt.md" | awk 'f{print} /<!-- prompt -->/{f=1}' | sed "s/{PIN}/$PIN/g" > "$CH/prompt.txt"
echo "prompt lines $(wc -l < "$CH/prompt.txt")"

INNER='
set -u
bad=0
got=$(awk '"'"'$2!~/^\/(proc|dev|sys)(\/|$)/{print $2}'"'"' /proc/self/mounts | sort | tr "\n" " ")
want="/ /audit /codexhome /etc/hostname /etc/hosts /etc/resolv.conf "
[ "$got" = "$want" ] || { echo "MOUNT CHECK FAILED: [$got]"; bad=1; }
awk '"'"'$2=="/audit"{print $4}'"'"' /proc/self/mounts | grep -q "^ro" || { echo "MOUNT CHECK FAILED: /audit not read-only"; bad=1; }
[ "$(find /audit -type f | wc -l)" = "$NFILES" ] || { echo "MOUNT CHECK FAILED: /audit file count"; bad=1; }
touch /audit/.w 2>/dev/null && { echo "MOUNT CHECK FAILED: /audit writable"; bad=1; }
[ $bad = 0 ] || exit 97
echo "mount check OK"
[ "${PROBE_ONLY:-}" = 1 ] && exit 0
cp -a /audit /home/auditor/work && cp -a /deps/web/node_modules /home/auditor/work/web/ && cp -a /deps/scripts/node_modules /home/auditor/work/scripts/
cd /home/auditor/work
codex exec --dangerously-bypass-approvals-and-sandbox \
  --disable apps --disable browser_use --disable browser_use_external --disable browser_use_full_cdp_access \
  --disable computer_use --disable hooks --disable image_generation --disable in_app_browser --disable multi_agent \
  --disable plugins --disable remote_plugin --disable plugin_sharing --disable shell_snapshot \
  -C /home/auditor/work --json -o /codexhome/final.md "$(cat /codexhome/prompt.txt)" > /codexhome/events.jsonl 2> /codexhome/stderr.txt
echo "codex exit $?"
'
# negative + positive control of the mount check, Codex never starts in either
EXTRA=$S/extra-mount-control; mkdir -p "$EXTRA"
docker run --rm --network none --label c72=probe --cap-drop ALL --security-opt no-new-privileges --hostname audit \
  -e NFILES="$NFILES" -e PROBE_ONLY=1 -v "$EXP":/audit:ro -v "$CH":/codexhome -v "$EXTRA":/extra:ro c72-codex-audit:r2 bash -c "$INNER" >/dev/null
NEG=$?
docker run --rm --network none --label c72=probe --cap-drop ALL --security-opt no-new-privileges --hostname audit \
  -e NFILES="$NFILES" -e PROBE_ONLY=1 -v "$EXP":/audit:ro -v "$CH":/codexhome c72-codex-audit:r2 bash -c "$INNER" >/dev/null
POS=$?
echo "mount-check controls: one extra mount → exit $NEG (want 97) · as intended → exit $POS (want 0)"
[ "$NEG" = 97 ] && [ "$POS" = 0 ] || { echo "STOP: the mount check is not proven able to fail and to pass"; exit 1; }
START=$(date +%s)
timeout 2400 docker run --rm --label c72=run --cap-drop ALL --security-opt no-new-privileges --hostname audit --dns 1.1.1.1 \
  -e CODEX_HOME=/codexhome -e HOME=/home/auditor -e TERM=dumb -e NFILES="$NFILES" \
  -v "$EXP":/audit:ro -v "$CH":/codexhome c72-codex-audit:r2 bash -c "$INNER"
RC=$?
echo "container exit $RC · seconds $(( $(date +%s) - START ))"
ls "$CH" | grep -v auth.json | tr '\n' ' '; echo
