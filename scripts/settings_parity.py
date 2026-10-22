"""settings_parity — the rules for comparing n8n workflow `settings` (MIGRATION-PLAN §3r, settings-parity, O1).

Workflow settings are not versioned (they live beside `activeVersion`, not in it), the parity guards compared
nodes only, and the public API drops some keys on create and update (`binaryMode` is "derived, ignored" per the
instance's own spec). So a settings difference was invisible until a deploy failed on it. One module, three
callers: check-content-parity.py (committed vs live, and a paired copy vs its original), the diff tool and the
deploy helper's verify (a copy vs its original).

  committed_vs_live(committed, live)       the committed export must carry exactly the live settings.
  copy_vs_original(original, copy, allow)  a copy carries its original's settings; the only exception is a key
                                           its spec allowlists, and then ONLY that key's absence on the copy.
  check_allowlist(allow)                   every entry covers "absent" and nothing else, and names its ruling.

An allowlist entry is {"<key>": {"covers": "absent", "ruling": "<where the ruling is recorded>"}}. There is no
blanket allowance and no "any value" entry: a copy carrying a DIFFERENT value for an allowlisted key is red.
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
        if not isinstance(entry, dict) or entry.get('covers') != 'absent':
            errs.append(f"settings allowlist entry '{key}' must cover \"absent\" only "
                        f"(got covers={(entry or {}).get('covers') if isinstance(entry, dict) else entry!r})")
        elif not str(entry.get('ruling', '')).strip():
            errs.append(f"settings allowlist entry '{key}' names no ruling")
    return errs


def committed_vs_live(committed, live):
    errs = []
    c, l = _s(committed, 'committed', errs), _s(live, 'live', errs)
    for key in sorted(set(c) | set(l)):
        if key not in l:
            errs.append(f"settings: '{key}' is in the committed export but not live (committed={c[key]!r})")
        elif key not in c:
            errs.append(f"settings: '{key}' is live but not in the committed export (live={l[key]!r})")
        elif c[key] != l[key]:
            errs.append(f"settings: '{key}' differs (committed={c[key]!r} live={l[key]!r})")
    return errs


def copy_vs_original(original, copy, allow):
    errs = check_allowlist(allow)
    o, c = _s(original, 'original', errs), _s(copy, 'copy', errs)
    for key in sorted(set(o) | set(c)):
        if key in o and key in c:
            if o[key] != c[key]:
                errs.append(f"settings: '{key}' differs on the copy (original={o[key]!r} copy={c[key]!r})")
        elif key in o:
            if key not in (allow if isinstance(allow, dict) else {}):
                errs.append(f"settings: '{key}' is missing on the copy and not allowlisted (original={o[key]!r})")
        else:
            errs.append(f"settings: '{key}' is on the copy but not on the original (copy={c[key]!r})")
    return errs
