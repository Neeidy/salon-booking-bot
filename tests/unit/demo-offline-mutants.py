#!/usr/bin/env python3
"""Mutants of scripts/demo-offline.sh (public demo, 2026-10-29). Each one breaks ONE property the script must hold, and
each must turn tests/unit/demo-offline.test.py red — a mutant that survives means the test does not measure it.

Each mutant is a single text replacement in a copy of the script (it must apply exactly once, or the run fails); the
test runs against the copy through its DEMO_OFFLINE variable.

Not in check-all: it re-runs the whole test once per mutant. Run before a change to the script or its test is pushed.
Run: python3 tests/unit/demo-offline-mutants.py        (exit 0 = every mutant killed)
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, 'scripts', 'demo-offline.sh')
TEST = os.path.join(ROOT, 'tests', 'unit', 'demo-offline.test.py')
MUTANTS = {
    'the token printed':
        ("unset VERCEL_TOKEN\n", "echo \"token $VERCEL_TOKEN\" >&2\nunset VERCEL_TOKEN\n"),
    'the token on the curl command line':
        ("-X POST -H @\"$HDR\" -H", "-X POST -H \"Authorization: Bearer $(sed -n 's/^Authorization: Bearer //p' \"$HDR\")\" -H"),
    'the header file left behind':
        ("trap 'rm -f \"$HDR\"' EXIT\n", ""),
    'the env-file permission check removed':
        ("[ $(( 8#$(stat -c %a \"$ENV_FILE\") & 077 )) = 0 ] ||", "true ||"),
    'a 503 counted as online':
        ("  if [ \"$code\" = 200 ]; then echo \"demo: online (200)\"; exit 0; fi",
         "  if [ \"$code\" = 200 ] || [ \"$code\" = 503 ]; then echo \"demo: online (200)\"; exit 0; fi"),
    'success reported without measuring':
        ("deadline=$(( $(date +%s) + POLL_S ))\n", "echo \"demo: offline (503) — measured\"; echo \"demo: online (200) — measured\"; exit 0\n"),
    'an API refusal ignored':
        ("[ \"$status\" = 200 ] || {", "true || {"),
    # (L2 review round) 000 is never "offline"; pause succeeds only on 503; no child sees an exported token
    'no answer (000) reported as offline':
        ("  if [ -z \"$code\" ] || [ \"$code\" = 000 ]; then echo \"demo: NOT measured (no answer)\"; exit 4; fi\n", ""),
    'pause counted as done on any status but 200':
        ("[ \"$ACTION\" = pause ] && [ \"$code\" = paused ]", "[ \"$ACTION\" = pause ] && [ \"$code\" != 200 ]"),
    # (R2a, the convergence residue of MEDIUM-5) only Vercel's paused answer is "offline"
    'any 503 counted as the paused answer':
        ("if [ \"$code\" = 503 ] && [[ \"${out%$'\\n'*}\" == *DEPLOYMENT_PAUSED* ]]; then", "if [ \"$code\" = 503 ]; then"),
    'an unexpected answer counted as offline':
        ("echo \"demo: unexpected answer ($code) — neither online nor Vercel's paused answer; NOT counted as offline\"; exit 5",
         "echo \"demo: offline ($code)\"; exit 3"),
    'an exported token left exported':
        ("export -n VERCEL_TOKEN VERCEL_PROJECT_ID VERCEL_TEAM_ID", "true"),
    'a non-https API address accepted':
        ("|| \"$API\" =~ ^http://127\\.0\\.0\\.1:[0-9]+(/|$) ]]", "|| \"$API\" =~ ^http:// ]]"),
    'a user part in the API address accepted':
        ("if [[ \"$API\" == *@* ]] || ! [[", "if ! [["),
    'an unknown argument ignored':
        ("  *) echo \"usage: bash scripts/demo-offline.sh measure|pause|unpause [--env FILE]\"; exit 2 ;;\nesac\nAPI=",
         "  *) ;;\nesac\nAPI="),
}


def main():
    src = open(SCRIPT, encoding='utf-8').read()
    survived = 0
    with tempfile.TemporaryDirectory(prefix='demo-offline-mutants-') as tmp:
        for i, (label, (old, new)) in enumerate(MUTANTS.items()):
            if src.count(old) != 1:
                print(f'✗ {label}: the anchor occurs {src.count(old)} times (want 1) — the mutant does not apply')
                survived += 1
                continue
            path = os.path.join(tmp, f'm{i}.sh')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(src.replace(old, new))
            r = subprocess.run([sys.executable, TEST], env=dict(os.environ, DEMO_OFFLINE=path), capture_output=True,
                               text=True, timeout=300, stdin=subprocess.DEVNULL)
            killed = r.returncode != 0
            survived += not killed
            print(f"{'✓ killed' if killed else '✗ SURVIVED'}: {label}")
    print(f'demo-offline mutants: {len(MUTANTS) - survived}/{len(MUTANTS)} killed')
    return 0 if survived == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
