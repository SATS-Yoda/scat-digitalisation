# Meal request console: design handover

State of the design as of 11 Nov 2026, carried over from a claude.ai chat.
Read this before writing code. Items under "Open" are not decided; do not guess them.

Files that belong next to this one in the repo:

- `scatdd_console_additions.sql`: three new tables for the console (parses, not yet run on a database).
- `result_export.json`: column export of the existing `scatdd_*_test` tables (columns only, no constraints).
- `I034202611017512.dat`: a real I034 file from SAP, as a format sample.

## What the system does

Airlines email meal requests (telexes) for flights catered by SATS. The system extracts them into two SAP interface record sets, I033 (pax counts per class) and I034 (special meals), lets a user review and edit them, and sends them to SAP as fixed-width text files over SFTP. Each flight has two stages, `P24H` and `P06H`. The AMF (amendment form) compares P24H with P06H and is for the user's view only; it never goes to SAP.

## Flow

1. Azure Logic App is triggered by the email, saves it to Blob storage and triggers the Dify extraction workflow.
2. Dify extraction workflow writes versions of I033 and I034 rows to PostgreSQL. One email can hold several flights.
3. Console (this repo): React frontend and FastAPI backend. Users review, edit and press Send.
4. Backend calls the Dify SAP-send workflow, which builds the files and uploads them to the SATS SFTP server (username and password).
5. Upload succeeded = "Sent" on the dashboard. There is no acknowledgement from SAP.

Out of scope for this repo: the Logic App and both Dify workflows (owned by the user's intern). This repo is the console backend and frontend only.

## Decisions

- **Send unit:** outbound flight + date + status (`P24H` or `P06H`). Exactly one I033 file and one I034 file per send unit, ever, however many emails arrived.
- **Sent is final:** once sent, the flight stage is locked. No edits, no resend. A later email for a sent stage must surface as a review item for the user to fix in SAP by hand.
- **Return sector:** the return flight (for example SQ 857 for SQ 856) is sent inside the outbound flight's files, under its own flight number and date. On the dashboard it shows as its own row, linked to and grouped under the outbound flight. It has no Send of its own.
- **Return link:** held in the mapping table `scatdd_return_sector_map_test` (outbound flight, return flight, day offset), not on each record. Read by the console and by the SAP-send workflow.
- **Edits:** users can edit I033 and I034 in the console. Each save creates a new version (`version_no`, `is_current`, `created_source`, `created_by`); old versions are kept.
- **AMF:** use the existing `scatdd_amf_test` and `scatdd_amf_line_test` tables. The backend writes a new AMF version whenever the current P24H or P06H version changes.
- **Plant:** SQ is ICC1, every other airline is ICC2. Derived from the airline code; no column.
- **Send button:** browser calls the backend; the backend calls Dify. The Dify API key never reaches the browser.
- **Release blocking:** open rows in `scatdd_review_item_test` whose error type has `blocks_release = true` block Send.
- **Missing return flight at Send:** proposed rule is warn and allow. Not yet confirmed by the users.

## Existing tables (do not alter)

`scatdd_email_test`, `scatdd_i033_test`, `scatdd_i034_test`, `scatdd_amf_test`, `scatdd_amf_line_test`, `scatdd_review_item_test`, `scatdd_error_type_test`. See `result_export.json` for columns.

Things to know:

- I033 key columns are `airline, flt_nbr, actdate, sector_nbr, status`. I034 names the same things `airln, fltnr, acdate, secnr, status`.
- I034 has no `is_current`; it links to I033 by those key columns plus `version_no`.
- `sent_to_sap_at` on I033 is written by the SAP-send workflow. The backend only reads it and treats a non-null value as locked.
- Only the date is stored (`actdate`), no departure time (STD).
- Primary keys and the "one current version" unique index are assumed but not confirmed (see Open).

## New tables (`scatdd_console_additions.sql`)

- `scatdd_return_sector_map_test`: the return-flight mapping.
- `scatdd_sap_send_test`: one row per send unit, written by the backend only. The backend inserts the row as `SENDING` before calling Dify; the unique key on the send unit is the "exactly one file" guard. States: `NOT_RELEASED`, `SENDING`, `SENT`, `FAILED`.
- `scatdd_airline_config_test`: per-airline auto-release switch and hold time in minutes. No row means manual.

## SAP-send workflow contract

Input (agreed with the intern, who is updating the workflow to it):

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

- One call covers the whole outbound flight: all its sectors plus the return flight's rows. There is no `sector_nbr` input.
- `file_seq` is the `send_id` of the send row, so a retry reuses the same number and file name.
- `send_i033` / `send_i034` let a retry skip a file that already uploaded.

Output (proposed; the intern said the answer can be customised, but has not confirmed this shape):

```json
{
  "i033_uploaded": true,
  "i033_file_name": "...",
  "i034_uploaded": true,
  "i034_file_name": "...",
  "error": ""
}
```

The workflow writes `sent_to_sap_at` only after both files uploaded, on the outbound and the return rows.

## Backend scope (FastAPI)

- Read: flight list with return flights grouped under their outbound flight; flight-stage detail (current I033 and I034, version history, open review items); AMF; source email from Blob.
- Write: save edits as a new version and regenerate the AMF; refuse edits on a sent stage.
- Send: check role and plant, blocking review items and not already sent; insert the send row; call Dify in blocking mode; record `SENT` or `FAILED` with the reason; allow retry of a failed send.
- Mark a flight stage as not released.
- Admin: maintain the return-flight mapping and the airline settings.
- Sign-in: Entra SSO, with groups for ICC1, ICC2 and admin. A user acts only on flights of their plant.

## Frontend scope (React + TypeScript)

- Dashboard: flights in date order with a status per stage (P24H, P06H), return flights nested under their outbound flight, filters kept in the URL.
- Flight-stage page: source email beside editable I033 and I034 tables, review items, version history, read-only AMF on P06H.
- Send: confirmation naming the flight and stage; then Sent, or the failure reason with a retry.
- Admin pages for the mapping and the airline settings.

## Auto-release (build last, off by default)

A scheduled check in the backend, every few minutes. A send unit is sent automatically only when all of these hold:

- the airline's `auto_release` is on;
- no send row exists for the unit;
- the current version was created by the system, not edited by a user;
- no open review items of any severity;
- `auto_release_hold_min` minutes have passed since the latest current version was created (a revised email restarts the clock);
- if the mapping lists a return flight, its data is present and meets the same conditions.

It then runs the same send path as the button, with `release_mode = 'AUTO'`. Anything else stays for manual review. STD-based timing is not possible until departure times are available.

## Build order

1. Run `scatdd_console_additions.sql` on the dev database (as a migration).
2. Backend read side, runnable locally with synthetic data.
3. Backend write side and Send.
4. Frontend.
5. Entra sign-in and roles.
6. Auto-release.

## Open

With the intern:

- Confirmation of the output shape above.
- Maximum digits for `file_seq`.
- Result of `SELECT tablename, indexdef FROM pg_indexes WHERE tablename LIKE 'scatdd_%';` to confirm keys and the current-version index.
- Reading the mapping table in the SAP-send workflow.

With SAP (blocks the SAP-send workflow, not the console):

- Status codes for P24H and P06H (the file's status field is three characters; the sample shows `03D`).
- File naming rule (sample: `I034202611017512.dat`, repeated in the header line).
- An I033 sample file.
- Target folder on the SFTP server.

With IT:

- Deployment owner for AKS.
- Entra app registration and the ICC1, ICC2 and admin groups.

With the users:

- Missing return flight at Send: block, or warn and allow.

## Engineering rules

Follow the SATS engineering baseline (the `sats-engineering` skill): React + TypeScript, FastAPI, PostgreSQL, Entra SSO, AKS and Helm, no secrets in the repo, synthetic test data only. The sample `.dat` file is real operational data; keep it out of automated tests and replace it with a synthetic one before the repo is shared more widely.
