# Meal request console: handover

State as of 13 Nov 2026. Read this before writing code. It replaces the design handover of
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

All work is on the branch `feat/backend-read-side`, which is on GitHub
(`SATS-Yoda/scat-digitalisation`). There is no pull request. `main` holds only the initial
commit. The branch on GitHub was last pushed at `65bebf7`; commits after that are local
until pushed (check with `git status`).

Checks on 13 Nov 2026: backend 55 tests pass on SQLite and on PostgreSQL (the admin
endpoints are now covered there). Frontend type check and 12 unit tests pass. The
production build was last run at step 4 and not repeated.

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
- The console tables do not exist in database `postgres` yet. Against it the flight list,
  stage pages, audit trail and admin pages fail (missing tables); only the AMF and email
  reads work. They do exist in `scat_console_dev` (see Databases).

`backend/app/tables.py` mirrors all of this, so the local and dev databases behave like
the real one.

## Environment

Machine and network:

- The repo lives in a OneDrive folder. That breaks hard links (`uv`) and makes OneDrive
  sync `frontend/node_modules`, where files can turn into cloud-only placeholders that
  vite cannot read ("The cloud operation was unsuccessful"). Moving the repo out of
  OneDrive would remove both problems.
- Corporate TLS inspection: `uv` needs `UV_SYSTEM_CERTS=true`; npm and Node may need
  `NODE_EXTRA_CA_CERTS` pointing at an export of the Windows trusted roots (on the
  13 Nov profile `npm ci` worked without it). Never disable certificate checks.
- The Python virtual environment is outside OneDrive at
  `%LOCALAPPDATA%\scat-console\venv` (`UV_PROJECT_ENVIRONMENT`), with `UV_LINK_MODE=copy`.
  Set both in every new shell, or `uv` will try to build a `.venv` inside the repo. The
  `backend/.venv` that OneDrive carried over from another Windows profile is stale and
  unused. The venv is built on a `uv`-managed Python 3.12 (`uv python install 3.12`); the
  only system Python on the 13 Nov profile was 3.11, and the backend needs 3.12 or later.
- `frontend/node_modules` is a junction to `%LOCALAPPDATA%\scat-console\frontend-deps\
  node_modules`, installed there with `npm ci` from a copy of `package.json` and
  `package-lock.json`. After a dependency change, copy both files there and run `npm ci`
  there. `vite.config.ts` sets `resolve.preserveSymlinks` for this; without it React loads
  twice and the page crashes. Delete the `.vite` folder in the target if vite misbehaves.
- Run backend commands from `backend/`, as `uv run python -m ...`. Running `pytest.exe`
  directly is blocked on the older laptop; `python -m pytest` works.
- Node is v24 on the 13 Nov profile (v18 earlier; the baseline expects 20). No Docker and
  no local PostgreSQL.
- PowerShell 5.1: pass multi-line commit messages with `git commit -F <file>`.
- `.claude/launch.json` starts both dev servers for the preview pane.

Databases:

- **Local:** SQLite file `backend/dev.db`, rebuilt by `uv run python -m app.seed`.
- **Azure test server:** reachable only from the owner's phone hotspot (not from SATS
  wifi; VPN untested). It is not production. Database `postgres` holds the intern's seven
  `scatdd_*_test` tables; the console only ever read it. Database `scat_console_dev` was
  created for this work; the seed and the PostgreSQL test run (`TEST_ON_POSTGRES=1`) wipe
  and rebuild it with synthetic data and touch no other database.
- On 13 Nov the seven intern tables were copied from `postgres` into `scat_console_dev`
  (emails 34, I033 65, I034 1147, AMF 13, AMF lines 88, review items 27, error types 14),
  with ids kept and sequences moved past them, so the console shows real processed data
  without writing to the intern's tables. Every PostgreSQL test run wipes that copy; copy
  it again afterwards. The one-off copy script was not kept in the repo. The console tables
  are empty there, so no return-flight links, sends or airline settings exist yet.
- `backend/.env` is gitignored. On 13 Nov it points at the Azure server, database
  `scat_console_dev` (the URL must name the database and carry `?sslmode=require`, or the
  server falls back to a database named after the login and fails), with `AUTH_DEV_MODE=true`.
  It holds the admin login, so treat it as sensitive and do not print it. To use SQLite
  again, point `DATABASE_URL` back at the SQLite file.

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
  (max 500); the action filter works on those. Covered by the PostgreSQL test run.
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

## Added 13 Nov 2026 (commits `c0fedb4`, `9a4dd3c`, `65bebf7`)

- **Audit trail: one review press is one row.** The reviewed-OK mark is stored per sector,
  so a two-sector flight showed two rows for one click. `audit_events`
  (`backend/app/queries.py`) now merges marks with the same time, user, flight and stage
  into one row; the detail reads "Sector 1 version 2, sector 2 version 1" and the sector
  column is empty. Nothing is stored differently. New test
  `test_one_review_press_is_one_audit_event`.
- **Audit detail available for an audit:** who (the extraction rows show the workflow
  name, and every action shows `dev-user` while `AUTH_DEV_MODE` is on), when, flight,
  stage, sector, and a short detail (version, error code and resolution, file names or
  failure reason). Not kept: before and after values of an edit (the old versions exist, so
  a diff can be built; the page does not show one), history of return-flight and airline
  setting changes, source IP or session, protection against edits to the records.
- **Dashboard filters are remembered.** They live in the URL, and links back to the
  dashboard used plain `/`, which dropped them. The last filters are kept in
  `sessionStorage` (`frontend/src/lib/dashboardSearch.ts`) and used by the sidebar Flights
  item and the stage page's back link. Reset filters clears them. Per browser tab.
- **Stage page layout (`c0fedb4`).** The action bar's message started from zero width, so at
  medium widths it wrapped to one word per line; it and the review item rows now have a
  minimum starting width.
- **Messages page (gap 1 below).** `GET /api/emails` and `/messages`, with 4 backend tests
  (59 pass on SQLite; not run on PostgreSQL as a suite, but the endpoint was checked
  against the real-data copy there: counts match the database, 34 emails). Fits without
  sideways scroll at 640 and 900 px; about 20 px over at 480 px.
- **Dashboard table at middle widths (`b0e30a7`).** The table needed 679 px where
  558 px were available at a 640 px window, so the stage columns scrolled out of view. The
  return row's label now wraps, the date can wrap, and below 768 px the Plant column is
  hidden and shown under the flight number. No sideways scroll at 560 to 900 px; at 480 px
  it still overflows by about 17 px.

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
- Browser click-through on 13 Nov, against the real-data copy in `scat_console_dev`: all of
  these worked: adding a return-flight mapping (SQ 856 to SQ 857, next day, nested on the
  dashboard), adding an airline and saving hold time and the automatic switch, Resolve
  (Accepted needs remarks; the button stays disabled without them), Do not release, saving
  a sector edit as a new version (review state became amended, AMF regenerated), and the
  Send confirm. Send failed cleanly with "Sending to SAP is not configured on this server"
  (no Dify key), leaving the stage Pending and creating no send record. A real send, and
  the Send success and failure screens, are untested. That click-through left test changes
  in the dev copy (return mapping SQ 856 to 857, an airline setting for QR, SQ 38 P24H item
  resolved, QR 943 P06H not released, QR 943 P24H at version 2, SQ 12 P24H reviewed).
- The dashboard has no "Missing" status: that needs departure times, which are not stored.
  They are to come from another MSSQL database (see "Departure times" under Next steps).
- No amendments report yet (see "Amendments report" under Next steps).

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

- Step 1: turn the console SQL into an Alembic migration and agree with the intern who
  runs it on the shared database.
- First real Dify send, once the workflow is published and its target folder is confirmed.

Departure times (for the dashboard's "Missing" status, RFQ Annex 12 section 2.2):

- Departure times are to be read from another MSSQL database. That database is reachable
  only on the SATS network (office wifi or VPN). The Azure PostgreSQL server is not
  reachable from SATS wifi, only from the owner's phone hotspot, so the two cannot be
  reached from one laptop at the same time over wifi.
- Whether both can be reached over the VPN has not been tested. Test that first; the
  design depends on it (a console that must reach both, or a copy of the departure times
  into PostgreSQL by a separate job).
- Nothing is built. Still to decide: which MSSQL server, database and table or view, a
  read-only account, and the "missing thresholds" per airline (RFQ 2.3, stored in the
  airline settings that nothing reads yet).
- The return flight can depart the next day (RFQ 2.2 item 5), so match departures to the
  outbound flight through the return-flight map, not by date.

Amendments report (later, not started; RFQ Annex 12 section 2.4 item 2):

- A report listing selected airline flights within a date range, to show how accurate the
  I033/I034 extraction was and how many user amendments were made. Its purpose is to show
  whether the mapping rules need improving or a scenario is unhandled.
- The data already exists: versions with `created_source` of `SYSTEM` or `USER`, so an
  amendment is a `USER` version after a `SYSTEM` one. The audit trail (`/audit`) shows the
  raw events but does not summarise them.
- RFQ 2.4 also asks that an AMF be traceable to the P24H and P06H versions it was built
  from. Check that the AMF record keeps those version references.
- Possible content, to agree with the owner: per airline and period, flights processed,
  flights amended, amendments per flight, which classes or meal codes were changed most.
  The RFQ also asks (section 2.2) for export to Excel or PDF of dashboard and reports.

## Gaps against the requirement document (RFQ Annex 12)

Checked on 13 Nov 2026 against sections 2.1 to 2.5 and 3.1 to 3.8, apart from departure
times (above). Ordered by importance. Items marked "workflow" mostly belong to the Logic App
or Dify workflows owned by the intern; the console part is what is listed.

1. **Failed and rejected emails were invisible (2.1.2, 2.1.8, 2.2). Partly done.** In the
   13 Nov copy of the real data, 20 of 34 emails have no I033 row (5 `PROCESSED_FAILED`, 2
   `REJECTED`, 8 `PROCESSED_PARTIAL`, 5 `PROCESSED_OK`), so no flight row exists for them.
   Built on 13 Nov: a Messages page (`/messages`, `GET /api/emails`) listing every email
   newest first with its processing status, rejection reason, the flights it produced
   (linked) and its open and blocking review items; filters for status and airline.
   Emails with no airline are visible to every signed-in user; the flights shown are
   plant-scoped. Still missing: the RFQ dashboard statuses "Received/Processing",
   "Processed OK", "Processed Failed" and "Processed Partially" on the flight rows
   themselves, status counts, and a date filter on the messages list.
2. **The source email text is never shown (2.1.8).** `body_preview` is empty for all 34
   emails, so the evidence highlight, which marks the part of the email that could not be
   processed, works only on synthetic data. Needs the `eml_uri` / `text_uri` format from the
   intern and a read from Blob storage.
3. **Dashboard filters (2.2).** Built: date, airline, plant. Missing: flight number,
   status, time range, and the default window of past 5 hours to next 24 hours (the
   default is today and tomorrow by date).
4. **Configuration (2.5).** Stored per airline: auto-release and its hold time only.
   Missing: missing-email thresholds (X for P24H, Y for P06H), whether to expect a P06H
   email, cabin class mapping to I033 and I034 classes, the default dashboard period, and
   a managed list of airlines.
5. **Export to Excel or PDF (3.1)** of the dashboard and reports: not built.
6. **Audit by field (3.4).** The RFQ wants original and changed values by transaction,
   date and field, plus a report, including changes by automated interfaces. The trail
   shows events and version numbers. A page that compares two versions field by field is
   not built, and AMF-to-version traceability (2.4) is not checked.
7. **Amendments report (2.4):** see Next steps.
8. **User administration and roles (3.2, 3.3).** The RFQ asks for in-app management of
   user ids and roles, roles configurable by an administrator, an access display and
   report, and roles such as reporting users and restricted vendors. The console uses Entra
   groups with a plant split and one admin role. Decision for the owner: are Entra groups
   enough?
9. **Interface monitoring (3.5).** Not in the console: a job status view, an email alert
   per job with summary statistics, manual download of the I033 and I034 files, and
   re-processing of a failed email (workflow). Only the send retry exists.
10. **Archival and retention (3.6):** no configurable retention period, no archive or
    purge.
11. **Missing-email alerts (2.3, optional)** depend on departure times and the Flight
    Information Hub. **Auto-release (step 6)** is also still open.

Also: the RFQ expects at least 340 flights a day. The dashboard has not been tried at that
size; the default two-day view could be about 700 rows.

Not visible from this repo and worth confirming with the intern (workflow): the other meal
request types (2.1.3), no I034 for ex-sector flights (2.1.6), the add-on pax Z (2.1.7), and
mail intake (2.1.1).

## Open

With the owner:

- Whether Entra groups are enough for roles, or an in-app user and role administration is
  needed (RFQ 3.2, 3.3; gap 8 above).
- Accept or change the proposed table `scatdd_i033_review_test` in the draft SQL.
- Provide the list of valid special meal codes (reminder owed).
- Whether `.claude/launch.json` stays in the repo.
- Whether to open a pull request (the branch is on GitHub).

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
- Read-only access to the MSSQL departure-time database, and a network route to it from
  wherever the console runs (it is SATS-network only; the VPN test is still to do).
- Which Dify instance production uses; the current one is a dev instance.

With the users:

- Missing return flight at Send: block, or warn and allow (built as warn and allow).

## Engineering rules

Follow the SATS engineering baseline (the `sats-engineering` skill) and, for UI, the SATS
design package vendored in `frontend/src/styles/sats/`. Deviations are listed in the
README. Test data is synthetic only. Real operational samples (the `.dat` file, telex
samples) stay out of the repo; `.gitignore` excludes `*.dat` and `*.eml`.
