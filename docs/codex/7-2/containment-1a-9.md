# 7-2 Tur 1 — the three containment flags (runs 1a and 9)

Ruling R1 (Yigitcan, 2026-10-25): all three flags are FALSE POSITIVES, accepted on the evidence below. The log-based
checker (`scripts/codex-containment.py`) tokenises a whole command as shell, so the BODY of an interpreter heredoc
(Python or Node source) was read as shell words. From Tur 1b on, containment is ISOLATION (a container that sees only
the read-only `git archive` export and a temporary Codex home); the checker still runs per run, as information only.

Runs 1a and 9 ran on the host, read-only sandbox, from a worktree at `f1a47eb`. Each flagged command ran with its
working directory inside that worktree (the session log's `cwd`). The bodies are reproduced verbatim, as Codex wrote
them; every value in them is synthetic.

## Flag 1 — run 1a

Checker rule(s): absolute path outside the worktree '//[^\\s\\x27\\x22]+'

```
python3 - <<'PY'
import json,re
w=json.load(open('n8n/workflow.main.copy.sanitized.json'))
names=['Save State','Save State (Post-Write)','Build Reply Payload','Send Reply To Origin','Finalize Outbound','Channel Switch','Should Send?','LLM Unavailable Reply','Send Error Response','Build Owner Alert','Build Reschedule Event Request','Book Reschedule Appointment','Check Race (Reschedule)','Update Appointment (Reschedule)','Build Reschedule-Done State']
for name in names:
 n=next(n for n in w['nodes'] if n['name']==name)
 print('\nNODE',name)
 for k in ['parameters','onError','retryOnFail','alwaysOutputData']:
  if k in n:
   v=n[k]; s=v.get('jsCode') if isinstance(v,dict) and 'jsCode' in v else json.dumps(v,indent=2)
   print(k,re.sub(r'https?://[^\s\x27\x22]+','[URL redacted]',s))
PY
```

## Flag 2 — run 9

Checker rule(s): unparseable shell script

```
node --experimental-vm-modules --input-type=module <<'NODE'
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {EventEmitter} from 'node:events';
const base = new URL('./web/dashboard/', import.meta.url);
const env = Object.fromEntries(['PGHOST','PGDATABASE','PGUSER','PGPASSWORD'].map(k=>[k,'synthetic']));
env.CLIENT_CONFIG_JSON=JSON.stringify({business:{timezone:'Europe/Vienna'}});
const calls=[];
const surname='AUDIT_SURNAME';
const unicodeNumber=Array.from('12345678901',c=>String.fromCodePoint(0x660+Number(c))).join('');
const inputs=[unicodeNumber,`AUDIT_FIRST ${surname} 1234567`];
class FakePool extends EventEmitter {
  query(sql){
    calls.push(sql);
    if(sql.includes('current_user AS role')) return Promise.resolve({rows:[{role:'synthetic',writable:0}]});
    const appt=sql.includes('FROM salon.appointments');
    return Promise.resolve({rows:Array.from({length:101},(_,i)=>({id:'synthetic'+i,fields:appt ? {start_utc:'2027-01-01T10:00:00Z',status:'booked',customer_name:inputs[i%2],service:'=1+1',channel:'widget',sender_key:'FORBIDDEN_MARKER'} : {name:inputs[i%2],phone:'+431111111111',source:'widget',sender_key:'FORBIDDEN_MARKER'}}))});
  }
}
const context=vm.createContext({Response,console,process:{env}});
const pg=new vm.SyntheticModule(['default'],function(){this.setExport('default',{Pool:FakePool});},{context});
const cache=new Map();
async function load(url){
  if(cache.has(url.href)) return cache.get(url.href);
  const m=new vm.SourceTextModule(stripTypeScriptTypes(readFileSync(url,'utf8')),{context,identifier:url.href});
  cache.set(url.href,m);
  await m.link((s,parent)=>s==='pg'?pg:load(new URL(s,parent.identifier)));
  return m;
}
for(const kind of ['appointments','leads']){
 const route=await load(new URL(`app/api/export/${kind}/route.ts`,base));
 await route.evaluate();
 for(const flag of [undefined,'0','true',' 1','1']){
  if(flag===undefined) delete env.DASHBOARD_EXPORT_ENABLED; else env.DASHBOARD_EXPORT_ENABLED=flag;
  const before=calls.length;
  const response=await route.namespace.GET();
  const body=await response.text();
  console.log(JSON.stringify({kind,flag:flag??'unset',status:response.status,queries:calls.length-before,unicodeNumberLeaks:body.includes(unicodeNumber),surnameLeaks:body.includes(surname),forbiddenMarkerLeaks:body.includes('FORBIDDEN_MARKER'),truncated:body.includes('(truncated:'),noStore:response.headers.get('cache-control')==='no-store',formulaNeutralised:body.includes('"\'=1+1"')}));
 }
}
NODE
```

## Flag 3 — run 9

Checker rule(s): absolute path outside the worktree '/'

```
node --experimental-vm-modules --input-type=module <<'NODE'
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
import {stripTypeScriptTypes} from 'node:module';
import {EventEmitter} from 'node:events';
import assert from 'node:assert/strict';
import {nextTick} from 'node:process';
const root=new URL('./',import.meta.url);
for(const file of ['web/dashboard/lib/exportCsv.test.ts','web/dashboard/lib/store.behaviour.test.ts']){
 const cases=[]; const pg={}; const cache=new Map();
 const safeFs={readFileSync(url,encoding){const u=url instanceof URL?url:new URL(url,root);if(!u.href.startsWith(root.href))throw new Error('outside repo');return readFileSync(u,encoding);}};
 const context=vm.createContext({Response,Request,Buffer,URL,setImmediate,console:{...console},process:{env:{},nextTick},fetch:()=>{throw new Error('network forbidden');}});
 const builtin={'node:assert/strict':{default:assert},'node:fs':safeFs,'node:test':{test:(name,fn)=>cases.push({name,fn})},'node:events':{EventEmitter},'node:module':{createRequire:()=>s=>{if(s!=='pg')throw new Error('unexpected package');return pg;}},'pg':{default:pg}};
 const bcache=new Map();
 async function load(url){
  if(cache.has(url.href))return cache.get(url.href);
  const m=new vm.SourceTextModule(stripTypeScriptTypes(readFileSync(url,'utf8')),{context,identifier:url.href,initializeImportMeta(meta){meta.url=url.href;},importModuleDynamically:async(s,parent)=>{const m=await load(new URL(s,parent.identifier));if(m.status==='linked')await m.evaluate();return m;}});
  cache.set(url.href,m);
  await m.link(async(s,parent)=>{
   if(s in builtin){if(bcache.has(s))return bcache.get(s);const obj=builtin[s];const m=new vm.SyntheticModule(Object.keys(obj),function(){for(const[k,v]of Object.entries(obj))this.setExport(k,v);},{context});bcache.set(s,m);return m;}
   return load(new URL(s,parent.identifier));
  });
  return m;
 }
 const m=await load(new URL(file,root));await m.evaluate();
 let passed=0;
 for(const {name,fn}of cases){try{await fn();passed++;}catch(e){console.log('FAIL:',name,e.message);}}
 console.log(JSON.stringify({suite:file.split('/').at(-1),passed,total:cases.length,realEnvironmentRead:false,networkCalls:0}));
}
NODE
```

## Tur 1b — containment by isolation (runs 1b, 2, 5, 6, 12, 4, 11)

Each run had its own container, built from a throwaway local image (Alpine + bash, Node, Python and the Codex binary
copied into the image). From the host it saw exactly two directories: the `git archive` export of `f1a47eb` (no `.git`,
265 files = the files tracked at the pin), mounted read-only at `/audit`, and a temporary Codex home holding only a
copy of the CLI's login file, plus the three files Docker writes for every container (`/etc/hostname`, `/etc/hosts`,
`/etc/resolv.conf`, set by flags to a fixed hostname and a public resolver, so nothing in them is read from the host).
No capabilities, no privilege escalation, no host environment (`CODEX_HOME HOME HOSTNAME PATH PWD SHLVL TERM` only).
Codex's own read-only sandbox does not work inside a container (it cannot create a namespace), so it ran with its
sandbox off and the container as the boundary (Yigitcan's brief, Tur 1b). Consequence, stated: commands could reach
the network and the login-file copy; every command line was therefore scanned afterwards for that copy, the
environment, `/proc` and network tools or URLs.

**Mount check inside every container, before Codex started:** the mount table had to equal exactly `/`, `/audit`,
`/codexhome` and the three Docker files; `/audit` had to show 265 files and refuse a write. If not, Codex did not start
and every running run was killed. Negative control: the same check with one extra host directory mounted exited 97
before Codex; the control without it passed.

| Target | Mount check | Duration | Commands | Log-checker flags (information only, R1) | Commands touching the login copy, env, /proc or network |
|---|---|---|---|---|---|
| 1b | OK | 408 s | 19 | 9 | 1 |
| 2 | OK | 311 s | 12 | 7 | 0 |
| 5 | OK | 283 s | 10 | 3 | 0 |
| 6 | OK | 408 s | 21 | 3 | 0 |
| 12 | OK | 519 s | 32 | 5 | 1 |
| 4 | OK | 609 s | 22 | 13 | 5 |
| 11 | OK | 397 s | 21 | 4 | 4 |

The 11 command lines in the last column were read one by one: synthetic `$env` / `process.env` stubs in offline
harnesses, a comment saying a harness uses no curl or env, reads of `.env.example` and of the guard scripts (target 4
is about them), the guard scripts run under bash with an EMPTY environment inside `/audit`, a synthetic host
`audit-origin.invalid.test` piped through `grep` to probe the host-leak guard, and Codex masking `https://` URLs itself
before printing. None read the login copy or made a network call.
