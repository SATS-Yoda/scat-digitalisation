from collections.abc import Callable, Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine

from . import commands, queries, schemas
from . import tables as t
from .auth import (
    SESSION_COOKIE,
    AuthConfig,
    Forbidden,
    IdentityError,
    Unauthenticated,
    User,
    current_user,
    require_admin,
    require_plant,
    start_session,
    user_from_identity,
)
from .dify import SapSendResult

Airline = Annotated[str, Path(pattern=r"^[A-Z0-9]{2,3}$")]
FltNbr = Annotated[str, Path(pattern=r"^[A-Z0-9]{1,5}$")]
SapSender = Callable[[dict, str], SapSendResult]

_STAGE = "/api/flights/{airline}/{flt_nbr}/{actdate}/stages/{status}"
_ERRORS = {
    commands.NotFound: 404,
    commands.Conflict: 409,
    commands.Invalid: 422,
    Forbidden: 403,
    Unauthenticated: 401,
}


def create_app(
    engine: Engine, sap_sender: SapSender | None = None, auth: AuthConfig | None = None
) -> FastAPI:
    app = FastAPI(title="Meal request console API")
    app.state.auth = auth

    for exc_type, code in _ERRORS.items():

        @app.exception_handler(exc_type)
        def handle(_: Request, exc: Exception, code: int = code) -> JSONResponse:
            return JSONResponse({"detail": str(exc)}, status_code=code)

    def get_conn() -> Iterator[Connection]:
        with engine.connect() as conn:
            yield conn

    def get_tx() -> Iterator[Connection]:
        """A connection whose work commits when the request succeeds and rolls back when
        it raises."""
        with engine.begin() as conn:
            yield conn

    Conn = Annotated[Connection, Depends(get_conn)]
    Tx = Annotated[Connection, Depends(get_tx)]
    Me = Annotated[User, Depends(current_user)]

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(conn: Conn) -> dict:
        conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    # --- Sign-in -------------------------------------------------------------------------

    if auth is not None:

        @app.get("/auth/login")
        def login() -> RedirectResponse:
            url, flow = auth.provider.begin()
            auth.store.put(f"flow:{flow['state']}", flow, 600)
            return RedirectResponse(url)

        @app.get("/auth/callback")
        def callback(request: Request) -> RedirectResponse:
            params = dict(request.query_params)
            flow = auth.store.pop(f"flow:{params.get('state', '')}")
            if flow is None:
                raise Unauthenticated("Sign-in expired or unknown; start again")
            try:
                identity = auth.provider.complete(flow, params)
            except IdentityError as exc:
                raise Unauthenticated(f"Sign-in refused: {exc}") from exc
            user = user_from_identity(identity, auth.groups)
            if not user.plants and not user.is_admin:
                raise Forbidden("This account is not in any console group")
            session_id, _ = start_session(auth, user)
            response = RedirectResponse("/")
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=auth.session_ttl_s,
                httponly=True,
                secure=auth.secure_cookie,
                samesite="lax",
            )
            return response

        @app.post("/auth/logout", status_code=204)
        def logout(request: Request, me: Me) -> JSONResponse:
            auth.store.delete(f"session:{request.cookies.get(SESSION_COOKIE)}")
            response = JSONResponse(None, status_code=204)
            response.delete_cookie(SESSION_COOKIE)
            return response

    @app.get("/api/me")
    def me_(request: Request, me: Me) -> dict:
        data = {"id": me.id, "plants": sorted(me.plants), "is_admin": me.is_admin}
        if auth is not None:
            session = auth.store.get(f"session:{request.cookies.get(SESSION_COOKIE)}")
            data["csrf_token"] = session["csrf"] if session else None
        return data

    # --- Read ----------------------------------------------------------------------------

    @app.get("/api/flights", response_model=list[schemas.FlightSummary])
    def list_flights(
        conn: Conn,
        me: Me,
        date_from: date | None = None,
        date_to: date | None = None,
        airline: Annotated[str | None, Query(pattern=r"^[A-Z0-9]{2,3}$")] = None,
        plant: schemas.Plant | None = None,
    ):
        flights = queries.list_flights(conn, date_from, date_to, airline, plant)
        return [f for f in flights if f["plant"] in me.plants]

    @app.get(_STAGE, response_model=schemas.StageDetail)
    def get_stage(
        conn: Conn,
        me: Me,
        airline: Airline,
        flt_nbr: FltNbr,
        actdate: date,
        status: schemas.Status,
    ):
        require_plant(me, airline)
        stage = queries.get_stage(conn, airline, flt_nbr, actdate, status)
        if stage is None:
            raise HTTPException(404, f"No {status} data for {airline} {flt_nbr} on {actdate}")
        return stage

    @app.get(
        _STAGE + "/sectors/{sector_nbr}/versions/{version_no}",
        response_model=schemas.VersionDetail,
    )
    def get_version(
        conn: Conn,
        me: Me,
        airline: Airline,
        flt_nbr: FltNbr,
        actdate: date,
        status: schemas.Status,
        sector_nbr: int,
        version_no: int,
    ):
        require_plant(me, airline)
        version = queries.get_version(
            conn, airline, flt_nbr, actdate, status, sector_nbr, version_no
        )
        if version is None:
            raise HTTPException(
                404,
                f"No version {version_no} of sector {sector_nbr} for "
                f"{airline} {flt_nbr} on {actdate} ({status})",
            )
        return version

    @app.get("/api/flights/{airline}/{flt_nbr}/{actdate}/amf", response_model=list[schemas.Amf])
    def get_amf(conn: Conn, me: Me, airline: Airline, flt_nbr: FltNbr, actdate: date):
        require_plant(me, airline)
        return queries.get_amf(conn, airline, flt_nbr, actdate)

    @app.get("/api/emails/{email_id}", response_model=schemas.Email)
    def get_email(conn: Conn, me: Me, email_id: int):
        email = queries.get_email(conn, email_id)
        if email is None:
            raise HTTPException(404, f"No email with id {email_id}")
        if email["airline"]:  # an email not yet matched to an airline has no plant to check
            require_plant(me, email["airline"])
        return email

    @app.get("/api/audit", response_model=list[schemas.AuditEvent])
    def audit(
        conn: Conn,
        me: Me,
        date_from: date | None = None,
        date_to: date | None = None,
        airline: Annotated[str | None, Query(pattern=r"^[A-Z0-9]{2,3}$")] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 200,
    ):
        return queries.audit_events(conn, me.plants, date_from, date_to, airline, limit)

    # --- Write ---------------------------------------------------------------------------

    @app.put(_STAGE + "/sectors/{sector_nbr}", response_model=schemas.SaveResult)
    def save_sector(
        tx: Tx,
        me: Me,
        airline: Airline,
        flt_nbr: FltNbr,
        actdate: date,
        status: schemas.Status,
        sector_nbr: int,
        edit: schemas.SectorEdit,
    ):
        return commands.save_sector(tx, me, airline, flt_nbr, actdate, status, sector_nbr, edit)

    @app.post(_STAGE + "/review", status_code=204)
    def mark_reviewed(
        tx: Tx, me: Me, airline: Airline, flt_nbr: FltNbr, actdate: date, status: schemas.Status
    ) -> None:
        commands.mark_reviewed(tx, me, airline, flt_nbr, actdate, status)

    @app.post(_STAGE + "/not-released", status_code=204)
    def mark_not_released(
        tx: Tx, me: Me, airline: Airline, flt_nbr: FltNbr, actdate: date, status: schemas.Status
    ) -> None:
        commands.mark_not_released(tx, me, airline, flt_nbr, actdate, status)

    @app.post("/api/review-items/{review_item_id}/resolve", status_code=204)
    def resolve_review_item(
        tx: Tx, me: Me, review_item_id: int, body: schemas.ResolveRequest
    ) -> None:
        commands.resolve_review_item(tx, me, review_item_id, body.resolution_type, body.remarks)

    @app.post(_STAGE + "/send", response_model=schemas.SendResult)
    def send(me: Me, airline: Airline, flt_nbr: FltNbr, actdate: date, status: schemas.Status):
        if sap_sender is None:
            raise HTTPException(503, "Sending to SAP is not configured on this server")
        # Three steps, each committed on its own: claim the unit, call the workflow, record
        # the outcome. The claim must be visible to other requests while the workflow runs.
        with engine.begin() as conn:
            claim = commands.begin_send(conn, me, airline, flt_nbr, actdate, status)
        # ceiling: if the process dies here the row stays SENDING and needs a manual reset;
        # add a stale-claim sweep with auto-release (build order step 6).
        result = sap_sender(claim["inputs"], me.id)
        with engine.begin() as conn:
            outcome = commands.finish_send(conn, claim["send_id"], claim["inputs"], result)
        return {**outcome, "warnings": claim["warnings"]}

    # --- Admin ---------------------------------------------------------------------------

    @app.get("/api/admin/return-flights", response_model=list[schemas.ReturnFlight])
    def list_return_flights(conn: Conn, me: Me):
        require_admin(me)
        m = t.return_map.c
        rows = conn.execute(
            select(t.return_map).order_by(m.airline, m.outbound_flt_nbr, m.return_flt_nbr)
        )
        return rows.mappings().all()

    @app.put("/api/admin/return-flights/{airline}/{flt_nbr}", status_code=204)
    def save_return_flight(
        tx: Tx, me: Me, airline: Airline, flt_nbr: FltNbr, body: schemas.ReturnFlightIn
    ) -> None:
        commands.save_return_flight(
            tx, me, airline, flt_nbr, body.outbound_flt_nbr, body.day_offset, body.is_active
        )

    @app.get("/api/admin/airline-settings", response_model=list[schemas.AirlineSetting])
    def list_airline_settings(conn: Conn, me: Me):
        require_admin(me)
        rows = conn.execute(select(t.airline_config).order_by(t.airline_config.c.airline))
        return rows.mappings().all()

    @app.put("/api/admin/airline-settings/{airline}", status_code=204)
    def save_airline_setting(
        tx: Tx, me: Me, airline: Airline, body: schemas.AirlineSettingIn
    ) -> None:
        commands.save_airline_setting(
            tx, me, airline, body.auto_release, body.auto_release_hold_min
        )

    return app
