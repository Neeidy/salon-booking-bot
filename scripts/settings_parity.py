"""settings_parity — the rules for comparing n8n workflow `settings` (MIGRATION-PLAN §3r settings-parity, O1; reshaped
at D6c, 2026-10-27, when the copy↔original pairing ended).

Workflow settings are not versioned (they live beside `activeVersion`, not in it) and the public API drops some keys on
create and update (`binaryMode` is "derived, ignored" per the instance's own spec), so a settings difference was
invisible until a deploy failed on it. Callers: check-content-parity.py and the deploy helper (a live workflow against
its committed export), workflow-step.py (before a snapshot, and across a PUT).

  committed_vs_live(committed, live, allow=None)
        the committed export carries exactly the live settings — except a key the workflow's spec allowlists
        (db/copies/<key>.json → settings_allow): such a key may be live while ABSENT from the export, and then only
        with EXACTLY its allowlisted value (type-strict). The key in the export too, any other value, or a key nobody
        allowlisted: red. (D6c: Main's binaryMode "separate" — the API cannot set it, every reader treats absent as
        "separate".)
  check_allowlist(allow)
        every entry covers "value" with one JSON scalar and names its ruling.

An allowlist entry is {"<key>": {"covers": "value", "value": <one JSON scalar>, "ruling": "<where the ruling is
recorded>"}}. There is no blanket allowance, no "any value" entry and no range. *The "absent" kind and
copy_vs_original went with the pairing:* they compared a copy with its original, and after D6c there is no original.
"""



def _s(settings, side, errs):
    if settings is None:
        return {}
    if not isinstance(settings, dict):           # fail loud: an unexpected shape must not compare as "empty"
        errs.append(f'settings: the {side} settings are not an object ({type(settings).__name__})')
        return {}
    return settings


def check_allowlist(allow):
    errs = []
    if not isinstance(allow, dict):
        return [f'settings allowlist must be an object, got {type(allow).__name__}']
    for key, entry in allow.items():
        covers = entry.get('covers') if isinstance(entry, dict) else None
        if covers != 'value':
            errs.append(f"settings allowlist entry '{key}' must cover \"value\" "
                        f"(got covers={covers if isinstance(entry, dict) else entry!r})")
        elif (not isinstance(entry.get('value'), (str, bool, int, float))
              or isinstance(entry.get('value'), float) and entry['value'] != entry['value']):
            errs.append(f"settings allowlist entry '{key}' covers \"value\" but names no single scalar value")
        elif not str(entry.get('ruling', '')).strip():
            errs.append(f"settings allowlist entry '{key}' names no ruling")
    return errs


def committed_vs_live(committed, live, allow=None):
    errs = check_allowlist(allow) if allow else []
    if allow and not isinstance(allow, dict):     # named above; nothing below can read it
        return errs
    c, l = _s(committed, 'committed', errs), _s(live, 'live', errs)
    ok_live = {k: e['value'] for k, e in (allow or {}).items()
               if isinstance(e, dict) and e.get('covers') == 'value' and isinstance(e.get('value'), (str, bool, int, float))}
    for key in sorted(set(c) | set(l)):
        if key not in l:
            errs.append(f"settings: '{key}' is in the committed export but not live (committed={c[key]!r})")
        elif key not in c:
            if key in ok_live:
                v = l[key]                    # type-strict: in Python True == 1, and n8n's settings are typed JSON
                if type(v) is not type(ok_live[key]) or v != ok_live[key]:
                    errs.append(f"settings: '{key}' is allowlisted live only as exactly {ok_live[key]!r} (live={v!r})")
            else:
                errs.append(f"settings: '{key}' is live but not in the committed export (live={l[key]!r})")
        elif key in ok_live:
            errs.append(f"settings: '{key}' is allowlisted as live-only but the committed export carries it "
                        f"(committed={c[key]!r}): the allowance and the export cannot both hold the key")
        elif c[key] != l[key]:
            errs.append(f"settings: '{key}' differs (committed={c[key]!r} live={l[key]!r})")
    return errs
