# Meal request console

Console for reviewing, editing and sending airline meal requests (I033 and I034) to SAP.
Design and open questions: [docs/HANDOVER.md](docs/HANDOVER.md). Columns of the existing
tables: [docs/result_export.json](docs/result_export.json).

Status: build order step 2 (backend read side) is in place. Not built yet: the migration for
the console tables (step 1), edits and Send (3), frontend (4), Entra sign-in (5),
auto-release (6).

## Run the backend locally

Needs `uv` and Python 3.12. From `backend/`:

```powershell
Copy-Item .env.example .env
uv sync
uv run python -m app.seed
uv run python -m uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000/docs. Tests and lint:

```powershell
uv run python -m pytest
uv run ruff check .
```

On a SATS laptop set these first (user environment variables are simplest):

| Variable | Value | Why |
| --- | --- | --- |
| `UV_SYSTEM_CERTS` | `true` | Corporate TLS inspection; uses the Windows certificate store |
| `UV_LINK_MODE` | `copy` | OneDrive folders reject hard links |
| `UV_PROJECT_ENVIRONMENT` | `%LOCALAPPDATA%\scat-console\venv` | Keeps the virtual environment out of OneDrive sync |

## Endpoints

| Method and path | Returns |
| --- | --- |
| `GET /api/flights?date_from&date_to&airline&plant` | Outbound flights in date order, state per stage, return flight nested |
| `GET /api/flights/{airline}/{flt_nbr}/{actdate}/stages/{status}` | Current I033 and I034 per sector, version history, open review items, send state |
| `GET .../stages/{status}/sectors/{sector_nbr}/versions/{version_no}` | One stored version |
| `GET /api/flights/{airline}/{flt_nbr}/{actdate}/amf` | Current AMF per sector with lines |
| `GET /api/emails/{email_id}` | Email metadata and `body_preview` |
| `GET /health`, `GET /ready` | Liveness; readiness (checks the database) |

## Deviations and assumptions

- **Local database is SQLite, not PostgreSQL.** No Docker or PostgreSQL on the development
  laptop. The read queries are plain SQL that runs on both; shared environments use
  PostgreSQL. `app.seed` refuses to run against anything but SQLite. Tests should move to
  PostgreSQL in CI once a pipeline exists.
- **Console tables are not in any database yet.** `backend/app/tables.py` follows
  [docs/scatdd_console_additions.sql](docs/scatdd_console_additions.sql); running it as a
  migration is step 1.
- **One return flight per outbound flight.** The mapping table's key would allow several;
  the console shows one.
- **No sign-in yet.** Every endpoint is open until step 5. Do not deploy to a shared
  environment before then.
- **Source email shows `body_preview` only.** Reading the full text from Blob storage needs
  the URI format of `eml_uri` / `text_uri` and an identity for the storage account.
- **Seed data is synthetic.** Class codes in the I033 slot columns are placeholders.
