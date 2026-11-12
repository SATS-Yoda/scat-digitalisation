from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Query
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from . import queries, schemas

Airline = Annotated[str, Path(pattern=r"^[A-Z0-9]{2,3}$")]
FltNbr = Annotated[str, Path(pattern=r"^[A-Z0-9]{1,5}$")]


def create_app(engine: Engine) -> FastAPI:
    app = FastAPI(title="Meal request console API")

    def get_conn() -> Iterator[Connection]:
        with engine.connect() as conn:
            yield conn

    Conn = Annotated[Connection, Depends(get_conn)]

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/ready")
    def ready(conn: Conn) -> dict:
        conn.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/api/flights", response_model=list[schemas.FlightSummary])
    def list_flights(
        conn: Conn,
        date_from: date | None = None,
        date_to: date | None = None,
        airline: Annotated[str | None, Query(pattern=r"^[A-Z0-9]{2,3}$")] = None,
        plant: schemas.Plant | None = None,
    ):
        return queries.list_flights(conn, date_from, date_to, airline, plant)

    @app.get(
        "/api/flights/{airline}/{flt_nbr}/{actdate}/stages/{status}",
        response_model=schemas.StageDetail,
    )
    def get_stage(
        conn: Conn, airline: Airline, flt_nbr: FltNbr, actdate: date, status: schemas.Status
    ):
        stage = queries.get_stage(conn, airline, flt_nbr, actdate, status)
        if stage is None:
            raise HTTPException(404, f"No {status} data for {airline} {flt_nbr} on {actdate}")
        return stage

    @app.get(
        "/api/flights/{airline}/{flt_nbr}/{actdate}/stages/{status}"
        "/sectors/{sector_nbr}/versions/{version_no}",
        response_model=schemas.VersionDetail,
    )
    def get_version(
        conn: Conn,
        airline: Airline,
        flt_nbr: FltNbr,
        actdate: date,
        status: schemas.Status,
        sector_nbr: int,
        version_no: int,
    ):
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
    def get_amf(conn: Conn, airline: Airline, flt_nbr: FltNbr, actdate: date):
        return queries.get_amf(conn, airline, flt_nbr, actdate)

    @app.get("/api/emails/{email_id}", response_model=schemas.Email)
    def get_email(conn: Conn, email_id: int):
        email = queries.get_email(conn, email_id)
        if email is None:
            raise HTTPException(404, f"No email with id {email_id}")
        return email

    return app
