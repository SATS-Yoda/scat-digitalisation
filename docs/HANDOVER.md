# Meal request console: handover

State as of 12 Nov 2026. Read this before writing code. It replaces the design handover of
11 Nov 2026 (kept in git history). Items under "Open" are not decided; do not guess them.

Companion files:

- [README.md](../README.md): how to run, endpoints, deviations from the SATS baseline.
- [scatdd_console_additions.sql](scatdd_console_additions.sql): draft SQL for the console
  tables, including one table proposed on 12 Nov. Not run on the shared database.
- [result_export.json](result_export.json): column export of the existing tables.
- The requirement document (RFQ v3.12, "Documentation Digitalization") is not in the repo.
  Annex 12 is the scope of work; Appendix B has I033/I034 samples; Appendix C has the AMF
  sample. It sits in the owner's OneDrive under `GenAI\SCAT`.

## What the system does

Airlines email meal requests (telexes) for flights catered by SATS. The system extracts
them into two SAP interface record sets, I033 (pax counts per class) and I034 (special
meals), lets a user review and edit them, and sends them to SAP as fixed-width files over
SFTP. Each flight has two stages, `P24H` and `P06H`. The AMF (additional meal form)
compares P24H with P06H and is for the user's view only; it never goes to SAP.

Flow:

1. An Azure Logic App saves each email to Blob storage and triggers the Dify extraction
   workflow.
2. The Dify extraction workflow writes versions of I033 and I034 rows to PostgreSQL.
3. The console (this repo) lets users review, edit and press Send.
4. The backend calls the Dify SAP-send workflow, which builds the files and uploads them.
5. Upload succeeded means "Sent". There is no acknowledgement from SAP.

Out of scope for this repo: the Logic App and both Dify workflows (owned by the intern).

## Build order and status

| Step | What | Status |
| --- | --- | --- |
| 1 | Console tables as a migration on the shared database | Not started. No Alembic yet |
| 2 | Backend read side | Done, commit `0b95297` |
| 3 | Backend edits, review, Send | Done, commit `8983cb0` |
| 4 | Frontend, plus admin endpoints | Done, commit `1969136` |
| 5 | Entra sign-in and roles | Backend built, commit `d12a86e`, tested with fakes only. Frontend changes not started. Never run against Entra or Redis: blocked on IT for real values |
| 6 | Auto-release | Not started |

All work is on the local branch `feat/backend-read-side`. Nothing has been pushed and there
is no pull request. `main` holds only the initial commit.

Checks at the last commit: backend 39 tests pass on SQLite; the 37 tests that existed at
step 3 also passed on PostgreSQL. The two admin endpoint tests added in step 4 have not
been run on PostgreSQL. Frontend type check, 4 unit tests and production build pass.

## Decisions

Carried over from the design:

- **Send unit:** outbound flight + date + status. Exactly one I033 file and one I034 file
  per send unit, ever.
- **Sent is final:** a sent stage is locked. No edits, no resend. Corrections go in SAP.
- **Return sector:** the return flight is sent inside its outbound flight's files and has
  no Send of its own. On the dashboard it is its own row under the outbound flight.
- **Return link:** held in `scatdd_return_sector_map_test`, not on each record.
- **Edits:** each save creates a new version; old versions are kept.
- **Plant:** SQ is ICC1, every other airline is ICC2. Derived from the airline code.
- **Send button:** browser calls the backend; the backend calls Dify. The Dify key never
  reaches the browser.
- **Release blocking:** open review items whose error type has `blocks_release` block Send.

Made by the owner on 12 Nov 2026:

- **Missing return flight at Send:** warn and allow (default taken; users have not
  confirmed).
- **Review items are resolved in the console** by the user.
- **SQ special meal increase at P06H on a user edit:** warn and allow.
- **"Reviewed OK" is an explicit button** for now.
- **Edited codes are free text** until a list of valid special meal codes is provided. The
  owner asked to be reminded about that list.

Made during the build (change if the owner disagrees):

- A save writes a new I033 version for one sector plus a full copy of its I034 lines. It
  must name the version it was based on, and is refused if another save came first.
- Edits are refused while a send is `SENDING`, as well as once sent.
- `NOT_RELEASED` is reversible: the stage can still be sent later.
- A return flight is editable on its own page and is locked by its outbound flight's send.
- Blocking review items on the return flight also block the outbound flight's Send.
- A review item with no status counts against both stages of its flight.
- A stage is locked if any version has `sent_to_sap_at`, not only the current one.
- Review resolution offers `AMENDED` (remarks optional) and `ACCEPTED` (remarks required).
  `REPROCESSED` and the `DISMISSED` state are left to the workflow.
- "Reviewed amended" is derived: any current sector created by a user.
- One active return flight per outbound flight, enforced when a mapping is saved.
- A failed send can be retried; it reuses its send row, so `file_seq` and the file names
  stay the same, and a file that already uploaded is skipped.

## AMF rules as implemented

From the requirement document (Annex 12 section 2.1.4-5, Appendix C), in
`backend/app/commands.py` (`amf_lines`):

- Pax lines carry the P06H pax count per class slot, not a delta.
- Special meal lines carry P06H minus P24H per (class, meal type, code). Zero changes are
  left out. For SQ only reductions are shown; for other airlines both directions.
- Cabin comes from the first letter of the class: P is `P`, J is `J`, S is `YD`, Y is `Y`.
- Crew (staff) slots are left off the form.
- The AMF is regenerated on every save of either stage, when both stages have data.

## What the shared test database showed

Read on 12 Nov 2026 (structure and code values only):

- All ids are `GENERATED ALWAYS AS IDENTITY`.
- "One current version" partial unique indexes exist on I033 and on the AMF.
- I034 has a foreign key to its I033 version, with cascade delete.
- `created_source` is `SYSTEM` or `USER`. Review states are `OPEN`, `RESOLVED`,
  `DISMISSED`; resolution types are `AMENDED`, `ACCEPTED`, `REPROCESSED`.
- AMF line types are `PAX` and `SPML`; cabins are `P`, `J`, `YD`, `Y`.
- The extraction workflow already writes AMF rows.
- An error type `SQ_INCREASE_IGNORED` exists (informational, non-blocking).
- The three console tables do not exist there yet.

`backend/app/tables.py` mirrors all of this, so the local and dev databases behave like
the real one.

## Environment

Machine and network:

- The repo lives in a OneDrive folder. That breaks hard links (`uv`) and makes OneDrive
  sync `frontend/node_modules`. Moving the repo out of OneDrive would remove both problems.
- Corporate TLS inspection: `uv` needs `UV_SYSTEM_CERTS=true`; npm and Node need
  `NODE_EXTRA_CA_CERTS` pointing at an export of the Windows trusted roots. One was made at
  `%LOCALAPPDATA%\scat-console\windows-roots.pem`. Never disable certificate checks.
- The Python virtual environment is outside OneDrive at
  `%LOCALAPPDATA%\scat-console\venv` (`UV_PROJECT_ENVIRONMENT`), with `UV_LINK_MODE=copy`.
- Run backend commands from `backend/`, as `uv run python -m ...`. Running `pytest.exe`
  directly is blocked on this laptop; `python -m pytest` works.
- Node is v18 (the baseline expects 20). No Docker and no local PostgreSQL.
- PowerShell 5.1: pass multi-line commit messages with `git commit -F <file>`.
- `.claude/launch.json` starts both dev servers for the preview pane.

Databases:

- **Local:** SQLite file `backend/dev.db`, rebuilt by `uv run python -m app.seed`.
- **Azure test server:** reachable only from the owner's phone hotspot. It is not
  production. Database `postgres` holds the intern's seven `scatdd_*_test` tables; the
  console only ever read it. Database `scat_console_dev` was created for this work; the
  seed and the PostgreSQL test run (`TEST_ON_POSTGRES=1`) wipe and rebuild it and touch no
  other database.
- `backend/.env` is gitignored. It currently points at SQLite. When it points at the Azure
  server it has held the admin login, so treat it as sensitive and do not print it.

Dify:

- Base URL: `https://difyoss.ai-dev.sats.com.sg/v1` (a dev instance).
- The SAP-send workflow's API was showing "Unavailable", which means it is not published
  yet, so no API key exists. The key goes in `backend/.env` as `DIFY_SAP_SEND_API_KEY`,
  never in chat or the repo.
- The real workflow has never been called. Tests use a fake. A real call uploads real
  files, so confirm the target SFTP folder with the intern first.

## SAP-send workflow contract

Input (agreed with the intern):

```json
{
  "airline": "QR",
  "flt_nbr": "943",
  "actdate": "2026-11-12",
  "status": "P24H",
  "file_seq": 1,
  "send_i033": true,
  "send_i034": true
}
```

One call covers the whole outbound flight: all its sectors plus the return flight's rows.
`file_seq` is the `send_id` of the send row.

Output (proposed, not confirmed by the intern; `backend/app/dify.py` reads this shape):

```json
{
  "i033_uploaded": true,
  "i033_file_name": "...",
  "i034_uploaded": true,
  "i034_file_name": "...",
  "error": ""
}
```

The workflow writes `sent_to_sap_at` only after both files uploaded, on the outbound and
the return rows.

## Added 12 Nov 2026 (commits `d12a86e`, `6e9b7d1`)

- **Audit trail page** (`/audit`, `GET /api/audit`): built from records that already exist
  (I033 versions, reviewed-OK marks, resolved review items, send decisions). No new table.
  Return flight and airline setting changes keep only their latest editor, so they are not
  in the trail; a history table would be needed. The server returns the latest 200 events
  (max 500); the action filter works on those. Not run on PostgreSQL.
- **Stage page layout:** review items sit above the sectors. At P06H the AMF is a third
  column from the 2xl breakpoint (1536 px); below that it sits under the source email.
  The source email stays pinned only when the AMF is not below it.
- **AMF as two tables:** passengers per cabin, then special meal changes (cabin, meal type,
  code, change).
- **Evidence highlight:** hovering or focusing a review item marks its evidence in the source
  email. Stored offsets are used only if they select the stored snippet in the preview text;
  otherwise the snippet is searched for, and nothing is marked if it is not in the preview.
  Checked in the browser on the seed data; frontend now has 8 unit tests.
- `frontend/vite.config.ts` reads `API_URL` for the dev proxy (default 127.0.0.1:8000), so a
  second backend on another port can be tried without stopping the first.

## Known gaps in what is built

- With `AUTH_DEV_MODE=true` and no `ENTRA_*` values every endpoint is open and acts as a
  fixed admin (`backend/app/auth.py`). Without either, the process refuses to start. Do not
  deploy before step 5 is verified against Entra.
- A send interrupted by a process crash stays `SENDING` and needs a manual reset.
- The source email shows `body_preview` only; reading the full text from Blob is not built.
- Airline settings are stored but nothing reads them until step 6.
- No Alembic, Dockerfile, Helm chart, pipeline, structured logging or metrics yet.
- The frontend has no ESLint or component tests, and FastAPI does not serve the built
  files yet.
- In the browser, the Send confirm, Resolve, Do not release and the admin save actions
  were not clicked through; the backend behind them is tested.
- The dashboard has no "Missing" status: that needs departure times, which are not stored.

## Next steps

Step 5, Entra sign-in and roles:

Built (54 backend tests pass on SQLite): `IdentityProvider` and `SessionStore`
interfaces, `/auth/login`, `/auth/callback`, `/auth/logout`, `/api/me`, an opaque httpOnly
session cookie, a per-session CSRF token checked on every write, group-to-plant and admin
mapping, plant-scoped reads (the flight list is filtered; stage, version, AMF and email
reads answer 403 for the other plant), and admin-only settings reads. Audit fields record
the signed-in identity id. Only the session id is stored, not Entra tokens, because nothing
calls a downstream API as the user. Group changes apply at the next sign-in or expiry.

Left to do:

- Verify `EntraProvider` and `RedisSessionStore` (`backend/app/adapters.py`, added with
  `msal` and `redis`) against a real tenant and Redis; needs the items under "With IT".
  Check that the app registration emits the `groups` claim; with more than 200 groups sign-in
  is refused with a clear message. `EntraProvider` fetches the tenant's OIDC metadata when
  the process starts, so a wrong tenant id fails at boot.
- Frontend: send `X-CSRF-Token` (from `/api/me`) on writes, send the browser to
  `/auth/login` on 401, show the signed-in user and a sign-out action. The CSRF header makes
  every browser write fail until then when real sign-in is on.
- Sessions in memory work for one process only; do not run several pods on it.

Also pending:

- Re-run the full test suite on PostgreSQL (hotspot needed) to cover the admin endpoints.
- Step 1: turn the console SQL into an Alembic migration and agree with the intern who
  runs it on the shared database.
- First real Dify send, once the workflow is published and its target folder is confirmed.

## Open

With the owner:

- Accept or change the proposed table `scatdd_i033_review_test` in the draft SQL.
- Provide the list of valid special meal codes (reminder owed).
- Whether `.claude/launch.json` stays in the repo.
- Whether to push the branch and open a pull request.

With the intern:

- Publish the SAP-send workflow with the agreed input, and confirm the output shape.
- Maximum digits for `file_seq`.
- Reading the return-flight mapping table in the SAP-send workflow.
- A few existing AMF pax lines carry `J` as `source_class`, which matches no I033 class
  column. The console writes the column name (`JM`, `JF`, and so on).
- Whether crew pax should appear on the AMF.
- The format of `eml_uri` / `text_uri`, to read the full email from Blob.

With SAP (blocks the SAP-send workflow, not the console):

- Status codes for P24H and P06H (the file's status field is three characters).
- File naming rule, an I033 sample file, and the target SFTP folder.

With IT:

- Deployment owner for AKS, and a network route from the cluster to the database.
- Entra app registration (tenant id, client id, secret, redirect URL) and the ICC1, ICC2
  and admin groups with test users.
- A Redis for sessions.
- Which Dify instance production uses; the current one is a dev instance.

With the users:

- Missing return flight at Send: block, or warn and allow (built as warn and allow).

## Engineering rules

Follow the SATS engineering baseline (the `sats-engineering` skill) and, for UI, the SATS
design package vendored in `frontend/src/styles/sats/`. Deviations are listed in the
README. Test data is synthetic only. Real operational samples (the `.dat` file, telex
samples) stay out of the repo; `.gitignore` excludes `*.dat` and `*.eml`.
