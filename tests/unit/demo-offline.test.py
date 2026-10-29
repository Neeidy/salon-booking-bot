#!/usr/bin/env python3
"""scripts/demo-offline.sh, offline: a stand-in for Vercel's API and for the demo page on 127.0.0.1 (loopback only,
remote-operator.md). The script's real curl calls run against it, through a curl shim on PATH that records every
argument list.

What it proves: `measure` tells 200 from another status from NO answer (000 is "not measured", never "offline");
`pause` succeeds only on a measured 503 and `unpause` only on a measured 200, each after ONE authorised POST to the right
endpoint, failing when the API refuses or the page does not change; an env file that is readable by others, missing,
or lacks the token, an unknown argument and a non-https API address are refused before any request; and the token —
generated here at run time, never written into this file — is in no argument list, no output, no leftover file, and no
child process's environment, even when the env file and the caller export it.

Run: python3 tests/unit/demo-offline.test.py   (DEMO_OFFLINE=<path> runs it against another copy — a mutant)
"""
import glob
import http.server
import os
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.environ.get('DEMO_OFFLINE', os.path.join(ROOT, 'scripts', 'demo-offline.sh'))
PROJECT = 'prj_test0001'


class World:
    def __init__(self, token):
        self.token, self.paused, self.api_status, self.ignore_pause, self.hits = token, False, 200, False, []
        self.paused_code = 503


def make_handler(world):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code):
            self.send_response(code)
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'{}')

        def do_GET(self):
            self.send(world.paused_code if world.paused else 200)

        def do_POST(self):
            world.hits.append((self.path, self.headers.get('Authorization') == f'Bearer {world.token}'))
            if self.headers.get('Authorization') != f'Bearer {world.token}':
                return self.send(403)
            if world.api_status != 200:
                return self.send(world.api_status)
            if self.path.startswith(f'/v1/projects/{PROJECT}/pause'):
                world.paused = not world.ignore_pause
            elif self.path.startswith(f'/v1/projects/{PROJECT}/unpause'):
                world.paused = False
            else:
                return self.send(404)
            self.send(200)
    return H


def main():
    ok = True

    def case(label, good, detail=''):
        nonlocal ok
        ok = ok and good
        print(f"{'✓' if good else '✗'} {label}" + ('' if good or not detail else f'\n    {detail[-400:]}'))

    token = 'vt_' + secrets.token_hex(16)
    world = World(token)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), make_handler(world))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_address[1]}'
    with tempfile.TemporaryDirectory(prefix='demo-offline-') as tmp:
        shim_dir, log = os.path.join(tmp, 'bin'), os.path.join(tmp, 'argv.log')
        os.makedirs(shim_dir)
        real_curl = shutil.which('curl')
        envlog = os.path.join(tmp, 'childenv.log')
        with open(os.path.join(shim_dir, 'curl'), 'w') as f:
            f.write(f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{log}"\nenv >> "{envlog}"\nexec "{real_curl}" "$@"\n')
        os.chmod(os.path.join(shim_dir, 'curl'), 0o755)
        for tool in ('mktemp', 'chmod'):   # the children that run between reading the env file and dropping the token
            real = shutil.which(tool)
            with open(os.path.join(shim_dir, tool), 'w') as f:
                f.write(f'#!/bin/bash\nenv >> "{envlog}"\nexec "{real}" "$@"\n')
            os.chmod(os.path.join(shim_dir, tool), 0o755)
        env_file = os.path.join(tmp, 'vercel.env')
        with open(env_file, 'w') as f:
            f.write(f'VERCEL_TOKEN={token}\nVERCEL_PROJECT_ID={PROJECT}\nVERCEL_TEAM_ID=team_test\n')
        os.chmod(env_file, 0o600)
        tmpdir = os.path.join(tmp, 'tmp')
        os.makedirs(tmpdir)
        env = dict(os.environ, PATH=shim_dir + os.pathsep + os.environ['PATH'], VERCEL_API_URL=base,
                   DEMO_URL=base + '/', POLL_S='4', TMPDIR=tmpdir)

        def run(*argv, ef=env_file):
            r = subprocess.run(['bash', SCRIPT, *argv, '--env', ef], env=env, capture_output=True, text=True,
                               timeout=60, stdin=subprocess.DEVNULL)
            return r.returncode, r.stdout + r.stderr

        rc, out = run('measure')
        case('measure: the page answers 200 → "online", exit 0', rc == 0 and 'online (200)' in out, out)
        world.paused = True
        rc, out = run('measure')
        case('measure: the page answers 503 → "offline", exit 3', rc == 3 and 'offline (503)' in out, out)
        world.paused = False

        rc, out = run('pause')
        case('pause: one authorised POST to the pause endpoint (team in the query), then offline MEASURED → exit 0',
             rc == 0 and world.hits[-1] == (f'/v1/projects/{PROJECT}/pause?teamId=team_test', True)
             and 'offline (503) — measured' in out, out)
        rc, out = run('unpause')
        case('unpause: one authorised POST, then online MEASURED → exit 0',
             rc == 0 and world.hits[-1][0].startswith(f'/v1/projects/{PROJECT}/unpause') and 'online (200) — measured' in out, out)

        world.ignore_pause = True
        rc, out = run('pause')
        case('pause accepted but the page still answers 200 → NOT measured, exit 1', rc == 1 and 'NOT measured' in out, out)
        world.ignore_pause = False
        world.api_status = 403
        rc, out = run('pause')
        case('the API refuses (403) → exit 1, says so', rc == 1 and 'HTTP 403' in out and 'did not accept' in out, out)
        world.api_status = 200

        before = len(world.hits)
        os.chmod(env_file, 0o644)
        rc, out = run('pause')
        case('an env file readable by others → refused before any request (exit 2)', rc == 2 and len(world.hits) == before, out)
        os.chmod(env_file, 0o600)
        rc, out = run('pause', ef=os.path.join(tmp, 'absent.env'))
        case('a missing env file → refused before any request (exit 2)', rc == 2 and len(world.hits) == before, out)
        no_tok = os.path.join(tmp, 'notoken.env')
        with open(no_tok, 'w') as f:
            f.write(f'VERCEL_PROJECT_ID={PROJECT}\n')
        os.chmod(no_tok, 0o600)
        rc, out = run('pause', ef=no_tok)
        case('an env file without the token → refused before any request (exit 2)', rc == 2 and len(world.hits) == before, out)
        rc, out = run('reboot')
        case('an unknown action → usage, exit 2', rc == 2 and 'usage' in out, out)
        for label, argv in (('--env with no file', ['pause', '--env']), ('an unknown argument', ['pause', '--evn', env_file]),
                            ('an extra argument', ['measure', 'now'])):
            r = subprocess.run(['bash', SCRIPT, *argv], env=env, capture_output=True, text=True, timeout=60,
                               stdin=subprocess.DEVNULL)
            case(f'{label} → refused (exit 2), no request', r.returncode == 2 and len(world.hits) == before, r.stdout)
        r = subprocess.run(['bash', SCRIPT, 'pause', '--env', env_file], env=dict(env, VERCEL_API_URL='http://api.example.invalid'),
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        case('a plain-http API address (not loopback) → refused before the token is used (exit 2)',
             r.returncode == 2 and len(world.hits) == before, r.stdout)
        r = subprocess.run(['bash', SCRIPT, 'pause', '--env', env_file],
                           env=dict(env, VERCEL_API_URL=f'http://127.0.0.1:1@{base[len("http://"):]}'),
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        case('a loopback-looking address with a user part (the token would go to the host after "@") → refused (exit 2)',
             r.returncode == 2 and len(world.hits) == before, r.stdout)
        r = subprocess.run(['bash', SCRIPT, 'pause', '--env', env_file],
                           env=dict(env, VERCEL_API_URL='https://api.vercel.com@elsewhere.invalid'),
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        case('an https address with a user part → refused before any request (exit 2)',
             r.returncode == 2 and 'no user part' in r.stdout and len(world.hits) == before, r.stdout)

        # 000 — no answer — is never "offline": measure says NOT measured, pause does not succeed on it
        closed = dict(env, DEMO_URL='http://127.0.0.1:9/')
        r = subprocess.run(['bash', SCRIPT, 'measure'], env=closed, capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
        case('measure with no answer (000) → "NOT measured", exit 4', r.returncode == 4 and 'NOT measured' in r.stdout, r.stdout)
        r = subprocess.run(['bash', SCRIPT, 'pause', '--env', env_file], env=closed, capture_output=True, text=True,
                           timeout=60, stdin=subprocess.DEVNULL)
        case('pause accepted but the page gives no answer (000) → NOT measured, exit 1',
             r.returncode == 1 and 'NOT measured' in r.stdout, r.stdout)
        world.paused_code = 404
        rc, out = run('pause')
        case('pause accepted but the page answers 404, not 503 → NOT measured, exit 1', rc == 1 and 'NOT measured' in out, out)
        world.paused_code = 503
        run('unpause')

        # the env file EXPORTS the token, and the caller's environment carries one too: no child may see either
        exp_file = os.path.join(tmp, 'exported.env')
        with open(exp_file, 'w') as f:
            f.write(f'export VERCEL_TOKEN={token}\nexport VERCEL_PROJECT_ID={PROJECT}\n')
        os.chmod(exp_file, 0o600)
        open(envlog, 'w').close()
        r = subprocess.run(['bash', SCRIPT, 'pause', '--env', exp_file], env=dict(env, VERCEL_TOKEN='caller-' + token),
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        child_env = open(envlog).read()
        case('an exported token (env file and caller): no child process environment holds it, and the pause still works',
             r.returncode == 0 and child_env.count('PATH=') >= 3 and token not in child_env, r.stdout)
        run('unpause')

        all_out = []
        for argv in (('pause',), ('unpause',), ('measure',)):
            all_out.append(run(*argv)[1])
        argv_log = open(log).read()
        case(f'the token is in no curl argument list ({argv_log.count(chr(10))} calls recorded)',
             argv_log.count('\n') >= 6 and token not in argv_log)
        case('the token is in no output, stdout or stderr', not any(token in o for o in all_out))
        case('no file is left in the temporary directory (the header file is removed)', not glob.glob(os.path.join(tmpdir, '*')))
        mode = stat.S_IMODE(os.stat(env_file).st_mode)
        case('the env file is untouched (0600)', mode == 0o600)
    srv.shutdown()
    srv.server_close()
    print('demo-offline:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
