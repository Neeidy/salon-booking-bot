#!/usr/bin/env bash
# Offline test for db/ops/pg-backup.sh (D6a, MIGRATION-PLAN §3t). A FAKE docker stands in for the Postgres
# container, the throwaway and pg_dump/pg_restore; it records every argv, so the test can assert what the script
# SENT as well as what it decided. What this proves: the snapshot is exported and handed to pg_dump; the stats are
# read in that session; no secret appears in any argv; an empty dump, a flipped byte, a short table of contents and
# a restore whose rows differ are each refused, by name; the container lookup refuses 0 or 2 candidates; retention
# removes only the backup's own old files. What it does NOT prove: that real pg_dump/pg_restore behave as the fake
# does. The real run (round 2, the operator's block) is where a flipped byte meets the real pg_restore.
# Run: bash tests/ops/pg-backup.test.sh </dev/null
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${PG_BACKUP_SRC:-$ROOT/db/ops/pg-backup.sh}"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/fake.py" <<'PY'
import sys, os
a = sys.argv[1:]
open(os.environ['PGB_ARGV'], 'a').write(' '.join(a) + '\n')
CT, IMG = 'fake-postgres-1', 'sha256:fakeimage'
TABLES = ['appointments', 'bot_metrics', 'conversations', 'leads', 'processed_messages']
def stats(var):
    return os.environ.get(var) or '\n'.join(f'{t} 2 {t[:4]}md5' for t in TABLES)
if a[:1] == ['ps']:
    print(os.environ.get('PGB_PS', CT)); sys.exit(0)
if a[:1] == ['inspect']:
    print(IMG); sys.exit(0)
if a[:1] == ['run']:
    assert '--network' in a and a[a.index('--network') + 1] == 'none', a
    open(os.environ['PGB_STATE'] + '.throwaway', 'w').write('up'); sys.exit(0)
if a[:2] == ['rm', '-f']:
    try: os.remove(os.environ['PGB_STATE'] + '.throwaway')
    except FileNotFoundError: pass
    sys.exit(0)
if a[0] != 'exec':
    sys.stderr.write(f'fake docker: unexpected {a}\n'); sys.exit(9)
inter = a[1] == '-i'
rest = a[2:] if inter else a[1:]
who, cmd = rest[0], rest[1:]
if cmd[0] == 'psql':
    # interactive in the source container (the snapshot session), one-shot in the throwaway (restored stats)
    for line in sys.stdin:
        if 'pg_export_snapshot' in line:
            print(os.environ.get('PGB_SNAP', '00000003-0000001B-1'), flush=True)
        elif line.startswith('SELECT s FROM ('):
            print(stats('PGB_STATS' if who == CT else 'PGB_RESTORED_STATS'), flush=True)
    sys.exit(0)
if cmd[0] == 'pg_dump':
    sys.stdout.write(os.environ.get('PGB_DUMP', 'PGDMP-fake-archive\n')); sys.exit(0)
if cmd[0] == 'pg_restore' and '--list' in cmd:
    data = sys.stdin.read()
    if 'CORRUPT' in data: sys.stderr.write('pg_restore: error: corrupt archive\n'); sys.exit(1)
    n = int(os.environ.get('PGB_TOC', '5'))
    for t in TABLES[:n]: print(f'3456; 0 16390 TABLE DATA salon {t} salon_owner')
    sys.exit(0)
if cmd[0] == 'pg_restore':
    data = sys.stdin.read()
    sys.exit(1 if 'CORRUPT' in data else 0)
if cmd[0] in ('pg_isready', 'createdb'):
    sys.exit(0)
sys.stderr.write(f'fake docker: unexpected exec {cmd}\n'); sys.exit(9)
PY
printf '#!/bin/sh\nexec python3 %s "$@"\n' "$T/fake.py" > "$T/bin/docker"; chmod +x "$T/bin/docker"
export PATH="$T/bin:$PATH"

PASS=0; FAIL=0
ok()  { PASS=$((PASS + 1)); echo "✓ $1"; }
bad() { FAIL=$((FAIL + 1)); echo "✗ $1"; }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

run() {   # run <label> [env assignments…] -- [args…]   → $OUT, $RC; a fresh backup dir and argv log each time
  local label="$1"; shift
  BK="$T/bk-$label"; mkdir -p "$BK"; : > "$T/argv-$label"
  local envs=()
  while [ "$#" -gt 0 ] && [ "$1" != "--" ]; do envs+=("$1"); shift; done
  [ "${1:-}" = "--" ] && shift
  OUT="$(env PGB_ARGV="$T/argv-$label" PGB_STATE="$T/state-$label" PG_BACKUP_DIR="$BK" "${envs[@]}" bash "$SRC" "$@" 2>&1 </dev/null)"; RC=$?
  ARGV="$T/argv-$label"
}

# 1 — the happy path
run happy --
D="$(ls "$BK"/salon-pg-*.dump 2>/dev/null | head -1)"
check "happy: exit 0, dump written and verified" '[ "$RC" = 0 ] && [ -n "$D" ] && echo "$OUT" | grep -q "verify OK"'
check "happy: the dump, its .sha256 and its .stats are mode 600" '[ "$(stat -c %a "$D" "$D.sha256" "$D.stats" | sort -u)" = 600 ]'
check "happy: pg_dump received the exported snapshot" 'grep -q -- "pg_dump -U postgres -Fc --snapshot=00000003-0000001B-1 salon" "$ARGV"'
check "happy: the stats were read in the snapshot session (5 lines recorded)" '[ "$(wc -l < "$D.stats")" = 5 ]'
check "happy: the throwaway ran with no network, from the running image" 'grep -q -- "run -d --rm --network none --name pg-backup-restore-[0-9]* -e POSTGRES_HOST_AUTH_METHOD=trust sha256:fakeimage" "$ARGV"'
check "happy: the throwaway was removed" '[ ! -e "$T/state-happy.throwaway" ] && grep -q "^rm -f pg-backup-restore-" "$ARGV"'
check "happy: restore without owners or privileges, stopping at the first error" 'grep -q -- "pg_restore -U postgres -d salon --no-owner --no-privileges --exit-on-error" "$ARGV"'
check "happy: readiness is asked over TCP, not the socket" 'grep -q -- "pg_isready -h 127.0.0.1 -U postgres -q" "$ARGV"'
# No secret in argv: nothing names a password, and the only -e is the throwaway's trust setting.
check "no secret in argv: no PASSWORD=, no -W/--password, no PGPASSWORD" '! grep -Eqi "(^| )-e [A-Z_]*PASSWORD|PGPASSWORD|--password|(^| )-W( |$)" "$ARGV"'
check "no secret in argv: every -e is POSTGRES_HOST_AUTH_METHOD=trust" '[ "$(grep -o -- " -e [^ ]*" "$ARGV" | sort -u)" = " -e POSTGRES_HOST_AUTH_METHOD=trust" ]'
CODE_ONLY="$(grep -v '^\s*#' "$SRC")"
check "no secret in the script: no code line sources a file, reads an env file or names a password" '! printf "%s" "$CODE_ONLY" | grep -Eq "PASSWORD|\.env|^\s*(source|\.)\s"'

# 2 — an empty dump is refused
run empty PGB_DUMP= --
check "empty dump: refused at the dump step, exit 1, no .dump kept" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "FAILED at dump: the dump is empty" && ! ls "$BK"/salon-pg-*.dump >/dev/null 2>&1'

# 3 — a flipped byte after writing is caught by the checksum
cp "$D" "$T/flip.dump"; cp "$D.stats" "$T/flip.dump.stats"; (cd "$(dirname "$D")" && sha256sum "$(basename "$D")") | sed "s#$(basename "$D")#flip.dump#" > "$T/flip.dump.sha256"
python3 - "$T/flip.dump" <<'PY'
import sys; p = sys.argv[1]; b = bytearray(open(p, 'rb').read()); b[3] ^= 0x01; open(p, 'wb').write(b)
PY
run flip -- --verify "$T/flip.dump"
check "flipped byte: --verify refuses it at the checksum" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "FAILED at verify: checksum"'
check "flipped byte: nothing was restored (no throwaway started)" '! grep -q "^run " "$ARGV"'

# 4 — a corrupt archive whose checksum was (re)written with it: the restore itself must refuse it
printf 'PGDMP-CORRUPT\n' > "$T/bad.dump"; cp "$D.stats" "$T/bad.dump.stats"; (cd "$T" && sha256sum bad.dump > bad.dump.sha256)
run corrupt -- --verify "$T/bad.dump"
check "corrupt archive: refused at the table of contents" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "FAILED at verify: the dump.s table of contents lists 0"'

# 5 — the restored rows differ from the dump-time stats
run differ PGB_RESTORED_STATS="$(printf 'appointments 2 appomd5\nbot_metrics 2 bot_md5\nconversations 1 convmd5\nleads 2 leadmd5\nprocessed_messages 2 procmd5')" --
check "restored rows differ: refused, exit 1" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "FAILED at verify: the restored rows differ"'
check "restored rows differ: the throwaway is still removed (trap)" '[ ! -e "$T/state-differ.throwaway" ]'

# 6 — a table of contents missing a table
run toc PGB_TOC=4 --
check "short TOC (4 of 5 tables): refused" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "lists 4 of 5"'

# 7 — container lookup
run none PGB_PS= --
check "no Postgres container: refused, nothing dumped" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "0 candidates" && ! grep -q pg_dump "$ARGV"'
run two "PGB_PS=$(printf 'a-postgres-1\nb-postgres-1')" --
check "two Postgres containers: refused, nothing dumped" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "2 candidates" && ! grep -q pg_dump "$ARGV"'
run named PG_CONTAINER=fake-postgres-1 "PGB_PS=$(printf 'a\nb')" --
check "PG_CONTAINER overrides the lookup" '[ "$RC" = 0 ] && ! grep -q "^ps " "$ARGV"'

# 8 — a malformed snapshot id stops before pg_dump
run snap PGB_SNAP='x; DROP' --
check "malformed snapshot id: refused before pg_dump" '[ "$RC" = 1 ] && echo "$OUT" | grep -q "snapshot id is not one" && ! grep -q pg_dump "$ARGV"'

# 9 — retention: only the backup's own files older than KEEP_DAYS go
BKR="$T/bk-retention"; mkdir -p "$BKR"
for f in salon-pg-20260901-120000.dump salon-pg-20260901-120000.dump.sha256 salon-pg-20260901-120000.dump.stats other-job-20260901.bak; do
  touch -d '20 days ago' "$BKR/$f"; done
touch -d '3 days ago' "$BKR/salon-pg-20261021-120000.dump"
OUT="$(env PGB_ARGV="$T/argv-ret" PGB_STATE="$T/state-ret" PG_BACKUP_DIR="$BKR" bash "$SRC" 2>&1 </dev/null)"; RC=$?
check "retention: the 20-day-old dump, .sha256 and .stats removed" '[ "$RC" = 0 ] && ! ls "$BKR"/salon-pg-20260901-* >/dev/null 2>&1'
check "retention: a 3-day-old dump and another job's old file kept" '[ -e "$BKR/salon-pg-20261021-120000.dump" ] && [ -e "$BKR/other-job-20260901.bak" ]'

echo "pg-backup test: $PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
