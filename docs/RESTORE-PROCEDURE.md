# Restore procedure (generic, placeholder-only)

> **Role of this file:** the GENERIC shape of a full restore of this stack: n8n engine, its database and
> encryption key, the host config, and the repo. **It is not the copy you use on the day.** The canonical
> copy of a given restore point lives INSIDE that backup directory, next to the files it names, so that it
> travels with the off-server copy and can still be read when both the server and the repo are gone.
> This file holds no values, hosts, ids or backup file names. Every `<…>` is a placeholder you fill in on
> the day.
> Related, narrower: [n8n-rollback.md](n8n-rollback.md), which covers per-step node snapshots during a
> refactor. First recorded for the migration's D0, [ARCHITECTURE-DECISIONS.md](ARCHITECTURE-DECISIONS.md)
> 2026-10-19.

**Rule zero: measure before you restore.** Decide which layer is broken, and restore only that layer.
A full restore over a partly working system destroys the evidence of what broke.

## What a restore point contains (and who can take it)

| Item | Why it is needed | Taken by |
|---|---|---|
| Raw API export of every live workflow (draft + published) | Level A restore without touching the DB | Claude (API) |
| The n8n SQLite DB, taken with SQLite's online `.backup` | Workflows, credentials (encrypted), activation state | the nightly job / operator (docker) |
| The n8n `config` file | **Holds the encryption key.** Without it, credentials in the DB cannot be decrypted | the nightly job / operator |
| Compose file + host env | Service definitions, image version, engine env | operator (root) |
| Local env files | Operator tooling and the frontends | operator (the deny rule blocks Claude, deliberately) |
| Repo: a pushed tag + `git bundle --all` | Code and docs, with or without GitHub | Claude |
| A checksum file covering every item | The only check that covers **every byte of every item** | whoever adds the item |

A DB and a `config` from different moments **do not mix**: if the key does not match, every credential
is unreadable after the restore.

## 0 · Is the backup itself intact?
```
cd <BACKUP_DIR> && sha256sum -c <CHECKSUM_FILE>       # macOS: shasum -a 256 -c <CHECKSUM_FILE>
```
Any FAILED line → stop and use the other copy (server ↔ off-server).

## 1 · Repo
```
git fetch origin --tags && git switch --detach <RESTORE_TAG>
# without GitHub:
git clone <BACKUP_DIR>/<REPO_BUNDLE> <DIR> && git -C <DIR> fsck --full
```
⚠ **`git bundle verify` does not check pack contents.** It was measured staying green on a corrupted
bundle. The content check is `clone` (index-pack) plus `fsck --full`.

## 2 · n8n

### Level A: n8n is healthy, only workflow content broke
PUT each workflow back from its export through the public API. The body holds only `name`, `nodes`,
`connections` and `settings`. **A raw PUT auto-publishes, so this writes to production and needs written
approval first** ([irreversible-actions.md](../.claude/rules/irreversible-actions.md)). Do the smallest
workflow first, as the trial. If a credential the workflow references by id was deleted, Level A is not
enough: go to Level B.

### Level B: the DB, credentials or n8n itself broke (root + docker: the operator)
1. Stop the n8n service (confirm the service name first: `docker compose ps --services`).
2. **Copy the BROKEN DB out first**, for forensics. Do not delete it.
3. Copy the backup DB into the data volume, and **remove any stale `-wal` / `-shm` files**. Otherwise
   SQLite replays them over the restored file.
4. Restore `config` only if it changed, and only from the SAME moment as the DB.
5. Restore the compose file + env only if they changed. Diff first.
6. **Never start an n8n image OLDER than the one the DB was taken with.** The DB carries its last schema
   migration, and an older image cannot open it.
7. Start the service.

## 3 · Anything the change added (e.g. a Postgres service)
Revert it through the compose restore. **Do not delete its data volume**: keep it for forensics. Deleting
it is a separate, explicit decision.

## 4 · External data the backup does NOT hold
List it in the backup's own manifest. For as long as such data is not backed up, the way back depends on
it staying **untouched**. Write that down as a precondition of every step that could change it.

## 5 · Is it fixed? Measure, do not assume
- The API lists the expected workflows; published node counts equal the manifest's.
- Turnstile: published config `enabled: true`, and a dummy token → 403.
- `python3 scripts/check-live-parity.py` · `python3 scripts/check-content-parity.py` · `npm --prefix scripts run check-all`
- Log the incident in [OPERATIONAL-INCIDENTS.md](OPERATIONAL-INCIDENTS.md).

## Verifying a restore point: what each instrument can and cannot see (measured 2026-10-19)
- **sha256**: catches any changed byte. It is the only check here that covers every byte of every item.
- **SQLite `PRAGMA integrity_check`**: does not guarantee content integrity. It stayed `ok` on a copy with
  one flipped byte in row data (a column with no index, checked with `PRAGMA index_list`), went red on a flipped page-type byte, and went red on a
  flipped byte in an INDEXED column (row/index mismatch). So it catches structure and some content.
- **`git bundle verify`**: header and prerequisites only. Use clone plus `fsck --full`.
- **gzip/tar**: reading the archive end to end (`tar tzf`) fails on a flipped byte inside the compressed
  stream (CRC). The gzip HEADER is not covered: a flipped header timestamp byte passed.
Every check used to declare a restore point must be shown going red on a corrupted copy. A check that
cannot fail has measured nothing.
