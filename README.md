# Meal request console

Console for reviewing, editing and sending airline meal requests (I033 and I034) to SAP.
Design and open questions: [docs/HANDOVER.md](docs/HANDOVER.md). Columns of the existing
tables: [docs/result_export.json](docs/result_export.json).

Status: build order steps 2 to 4 (backend read side, edits and Send, frontend) are in
place. Not built yet: the migration for the console tables (step 1), Entra sign-in (5),
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

Tests run on in-memory SQLite. To run them on PostgreSQL, point `DATABASE_URL` at the test
server and set `TEST_ON_POSTGRES=1`. They use only the `scat_console_dev` database on that
server, which is wiped and re-seeded for every test; the shared `postgres` database with
the Dify workflows' tables is never written to.

On a SATS laptop set these first (user environment variables are simplest):

| Variable | Value | Why |
| --- | --- | --- |
| `UV_SYSTEM_CERTS` | `true` | Corporate TLS inspection; uses the Windows certificate store |
| `UV_LINK_MODE` | `copy` | OneDrive folders reject hard links |
| `UV_PROJECT_ENVIRONMENT` | `%LOCALAPPDATA%\scat-console\venv` | Keeps the virtual environment out of OneDrive sync |

## Run the frontend locally

Needs Node 18 or later and the backend running on port 8000. From `frontend/`:

```powershell
npm install
npm run dev
```

Then open http://localhost:5173. The dev server forwards `/api` to the backend. The seed
flights are dated 13 and 14 Nov 2026, so set the dashboard dates to that range. Checks:

```powershell
npm run typecheck
npm test
npm run build
```

On a SATS laptop npm needs the corporate root certificates. Export the Windows trusted
roots to a PEM file once and set `NODE_EXTRA_CA_CERTS` to its path (user environment
variable). Do not turn off `strict-ssl`.

Screens: flight list with filters kept in the URL; flight-stage page with the source email
beside editable I033 and I034, review items, version history, the AMF on P06H, and the
Send, Do not release and Mark reviewed actions; admin pages for return flights and airline
settings. Design tokens and fonts are vendored unchanged in `frontend/src/styles/sats/`.

## Endpoints

`{stage}` is `/api/flights/{airline}/{flt_nbr}/{actdate}/stages/{status}`.

| Method and path | Does |
| --- | --- |
| `GET /api/flights?date_from&date_to&airline&plant` | Outbound flights in date order, state per stage, return flight nested |
| `GET {stage}` | Current I033 and I034 per sector, version history, open review items, send state |
| `GET {stage}/sectors/{sector_nbr}/versions/{version_no}` | One stored version |
| `GET /api/flights/{airline}/{flt_nbr}/{actdate}/amf` | Current AMF per sector with lines |
| `GET /api/emails/{email_id}` | Email metadata and `body_preview` |
| `GET /api/audit` | Who extracted, edited, reviewed, resolved and sent what, newest first. Filters `airline`, `date_from`, `date_to` (flight date), `limit` (max 500). Scoped to the user's plants |
| `PUT {stage}/sectors/{sector_nbr}` | Saves an edit as a new version and regenerates the AMF |
| `POST {stage}/review` | Marks the current versions as reviewed without changes |
| `POST {stage}/send` | Sends the outbound flight and its return flight to SAP through Dify |
| `POST {stage}/not-released` | Records the decision not to send (can still be sent later) |
| `POST /api/review-items/{id}/resolve` | Closes a review item as `AMENDED` or `ACCEPTED` |
| `GET`, `PUT /api/admin/return-flights[/{airline}/{return_flt_nbr}]` | Lists and saves return-flight mappings (admin) |
| `GET`, `PUT /api/admin/airline-settings[/{airline}]` | Lists and saves auto-release settings (admin) |
| `GET /health`, `GET /ready` | Liveness; readiness (checks the database) |

Write rules, in short: a stage that was sent, or is being sent, refuses every change (409).
A save must name the version it was based on. Send is refused while blocking review items
are open on the flight or its return flight; a missing return flight only warns. A failed
send can be retried and reuses its file number.

## Deviations and assumptions

- **No migrations yet.** The baseline asks for Alembic. The local and dev databases are
  built from `backend/app/tables.py`, which mirrors the shared test database as read on
  12 Nov 2026. Step 1 turns [docs/scatdd_console_additions.sql](docs/scatdd_console_additions.sql)
  into a migration for shared environments.
- **One table added to the draft SQL:** `scatdd_i033_review_test`, for the "Reviewed OK"
  button. Marked as proposed in the file.
- **Sign-in is built but has never run against Entra or Redis.** Sessions, CSRF,
  group-to-plant mapping and plant-scoped reads are in `backend/app/auth.py`; the MSAL and
  Redis adapters are in `backend/app/adapters.py`. Tests use a fake provider and stubs. Set
  the `ENTRA_*` and `REDIS_URL` values (see `backend/.env.example`) for real sign-in; with
  none set, the server starts only with `AUTH_DEV_MODE=true`, a fixed admin with no sign-in.
  The frontend does not send the CSRF token yet, so browser writes fail under real sign-in.
- **Dify output shape is unconfirmed.** `backend/app/dify.py` reads the shape proposed in
  the handover. Tests use a fake workflow; the real one has not been called.
- **A send interrupted by a process crash stays `SENDING`** and needs a manual reset until a
  sweep is added with auto-release.
- **Edited codes are free text.** Class and special meal codes are checked for length only,
  and a class must start with P, J, S or Y so it can be placed on the AMF. A list of valid
  special meal codes is still to come.
- **AMF.** Rules follow the requirement document (Annex 12, Appendix C). Crew (staff) pax
  are left off the form.
- **One return flight per outbound flight.** The mapping table's key would allow several;
  the admin endpoint refuses a second active one.
- **Node 18, not 20.** The development laptop has Node 18, so the frontend uses Vite 5,
  Tailwind 3 and React Router 6, which run on it. Move to Node 20 with the container image.
- **shadcn/ui components are written by hand** in `frontend/src/components/ui/` (Button,
  Input, Label, Textarea, Dialog) in the shadcn form on Radix, instead of being pulled with
  the shadcn CLI. Tables are the dense custom table the design standard allows.
- **No ESLint or component tests yet.** The frontend has type checking and unit tests for
  its pure helpers only.
- **The frontend is not served by FastAPI yet.** In development Vite serves it; serving the
  built files from the backend comes with the container image.
- **Airline settings are stored but not used** until auto-release (step 6) is built.
- **Source email shows `body_preview` only.** Reading the full text from Blob storage needs
  the URI format of `eml_uri` / `text_uri` and an identity for the storage account.
- **Seed data is synthetic.** Class codes in the I033 slot columns are placeholders.
