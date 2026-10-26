"""settings_parity — the rules for comparing n8n workflow `settings` (MIGRATION-PLAN §3r, settings-parity, O1).

Workflow settings are not versioned (they live beside `activeVersion`, not in it), the parity guards compared
nodes only, and the public API drops some keys on create and update (`binaryMode` is "derived, ignored" per the
instance's own spec). So a settings difference was invisible until a deploy failed on it. One module, three
callers: check-content-parity.py (committed vs live, and a paired copy vs its original), the diff tool and the
deploy helper's verify (a copy vs its original).

  committed_vs_live(committed, live)       the committed export must carry exactly the live settings.
  copy_vs_original(original, copy, allow)  a copy carries its original's settings, except the keys its spec
                                           allowlists: an "absent" key must be ABSENT on the copy (D4-1, 2026-10-23);
                                           a "value" key must carry EXACTLY its value (T-4, 2026-10-26).
  check_allowlist(allow)                   every entry covers "absent" or "value" (with its exact value), and names
                                           its ruling.
  absent_keys(allow) / carried(allow)      the two kinds apart, for the deploy helper (strip the first, send the
                                           second).

An allowlist entry is {"<key>": {"covers": "absent", "ruling": "<where the ruling is recorded>"}} or
{"<key>": {"covers": "value", "value": <one JSON scalar>, "ruling": "…"}}. There is no blanket allowance and no
"any value" entry. An "absent" key PRESENT on the copy is red whatever its value: an equal value used to pass, so a
copy created with Main's `availableInMCP: true` would have been exactly as exposed as Main with this guard green (D4
plan, 2026-10-23). A "value" key is red unless the copy carries exactly that value — it exists for a copy that must
be NARROWER than its original (T-4, 2026-10-26: Owner Actions saves execution data on error only, because a
successful run's data holds the Access JWT and a cookie), and it names one value, never a range.
"""


_MISSING = object()


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
        if covers not in ('absent', 'value'):
            errs.append(f"settings allowlist entry '{key}' must cover \"absent\" or \"value\" "
                        f"(got covers={covers if isinstance(entry, dict) else entry!r})")
        elif covers == 'value' and (not isinstance(entry.get('value'), (str, bool, int, float))
                                    or isinstance(entry.get('value'), float) and entry['value'] != entry['value']):
            errs.append(f"settings allowlist entry '{key}' covers \"value\" but names no single scalar value")
        elif not str(entry.get('ruling', '')).strip():
            errs.append(f"settings allowlist entry '{key}' names no ruling")
    return errs


def absent_keys(allow):
    return {k for k, e in (allow or {}).items() if isinstance(e, dict) and e.get('covers') == 'absent'}


def carried(allow):
    # An entry without a single scalar value is reported by check_allowlist; it carries nothing here.
    return {k: e['value'] for k, e in (allow or {}).items()
            if isinstance(e, dict) and e.get('covers') == 'value' and isinstance(e.get('value'), (str, bool, int, float))}


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
    allowed = absent_keys(allow) if isinstance(allow, dict) else set()
    must_carry = carried(allow) if isinstance(allow, dict) else {}
    for key in sorted(set(o) | set(c) | set(must_carry)):
        if key in must_carry:
            v = c.get(key, _MISSING)          # type-strict: in Python True == 1, and n8n's settings are typed JSON
            if v is _MISSING or type(v) is not type(must_carry[key]) or v != must_carry[key]:
                errs.append(f"settings: '{key}' must carry exactly {must_carry[key]!r} on the copy "
                            f"(copy={c.get(key, '<absent>')!r})")
        elif key in c and key in allowed:
            errs.append(f"settings: '{key}' is allowlisted as absent but present on the copy (copy={c[key]!r})")
        elif key in o and key in c:
            if o[key] != c[key]:
                errs.append(f"settings: '{key}' differs on the copy (original={o[key]!r} copy={c[key]!r})")
        elif key in o:
            if key not in allowed:
                errs.append(f"settings: '{key}' is missing on the copy and not allowlisted (original={o[key]!r})")
        else:
            errs.append(f"settings: '{key}' is on the copy but not on the original (copy={c[key]!r})")
    return errs
