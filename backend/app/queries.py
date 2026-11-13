"""Read-side queries. Each function takes an open connection and returns plain dicts."""

from datetime import date, timedelta

from sqlalchemy import Integer, String, and_, case, cast, false, func, or_, select
from sqlalchemy.engine import Connection, RowMapping

from . import tables as t

STATUSES = ("P24H", "P06H")


def plant_for(airline: str) -> str:
    return "ICC1" if airline == "SQ" else "ICC2"


def stage_state(has_data: bool, sent_at: object, send_state: str | None) -> str:
    """Dashboard state of one flight stage. `sent_to_sap_at` wins: sent is final."""
    if sent_at is not None or send_state == "SENT":
        return "SENT"
    if send_state:
        return send_state
    return "PENDING" if has_data else "NO_DATA"


def review_state(sectors: int, edited: int, reviewed: int) -> str:
    """Reviewed amended once a user has edited any current sector; reviewed OK once every
    current sector has been confirmed unchanged."""
    if edited:
        return "REVIEWED_AMENDED"
    return "REVIEWED_OK" if sectors and reviewed == sectors else "NOT_REVIEWED"


def return_maps(conn: Connection) -> tuple[dict, dict]:
    rows = conn.execute(select(t.return_map).where(t.return_map.c.is_active)).mappings().all()
    # ceiling: one return flight per outbound flight, as the handover describes. The table's
    # key would allow several; the last one read wins here.
    by_outbound = {(r["airline"], r["outbound_flt_nbr"]): r for r in rows}
    by_return = {(r["airline"], r["return_flt_nbr"]): r for r in rows}
    return by_outbound, by_return


def outbound_for(by_return: dict, airline: str, flt_nbr: str, actdate: date) -> dict | None:
    m = by_return.get((airline, flt_nbr))
    if m is None:
        return None
    return {
        "airline": airline,
        "flt_nbr": m["outbound_flt_nbr"],
        "actdate": actdate - timedelta(days=m["day_offset"]),
    }


def return_for(by_outbound: dict, airline: str, flt_nbr: str, actdate: date) -> dict | None:
    m = by_outbound.get((airline, flt_nbr))
    if m is None:
        return None
    return {
        "airline": airline,
        "flt_nbr": m["return_flt_nbr"],
        "actdate": actdate + timedelta(days=m["day_offset"]),
    }


def list_flights(
    conn: Connection,
    date_from: date | None = None,
    date_to: date | None = None,
    airline: str | None = None,
    plant: str | None = None,
) -> list[dict]:
    """Outbound flights in date order, each with its return flight nested under it.

    The date range applies to the outbound flight; a return flight on a later day still
    comes back under its outbound flight.
    """
    by_outbound, by_return = return_maps(conn)
    pad = timedelta(days=max((abs(m["day_offset"]) for m in by_outbound.values()), default=0))

    def scope(airline_col, date_col) -> list:
        conds = []
        if date_from:
            conds.append(date_col >= date_from - pad)
        if date_to:
            conds.append(date_col <= date_to + pad)
        if airline:
            conds.append(airline_col == airline)
        if plant == "ICC1":
            conds.append(airline_col == "SQ")
        elif plant == "ICC2":
            conds.append(airline_col != "SQ")
        return conds

    i = t.i033.c
    data_rows = conn.execute(
        select(
            i.airline,
            i.flt_nbr,
            i.actdate,
            i.status,
            func.sum(case((i.is_current, 1), else_=0)).label("sectors"),
            # Over every version, not only the current one: a stage stays locked even if a
            # later email produced a newer unsent version.
            func.max(i.sent_to_sap_at).label("sent_at"),
            func.max(case((i.is_current, i.created_at))).label("updated_at"),
            func.sum(case((and_(i.is_current, i.created_source == "USER"), 1), else_=0)).label(
                "edited"
            ),
            func.sum(
                case((and_(i.is_current, t.i033_review.c.i033_id.is_not(None)), 1), else_=0)
            ).label("reviewed"),
        )
        .join_from(t.i033, t.i033_review, isouter=True)
        .where(*scope(i.airline, i.actdate))
        .group_by(i.airline, i.flt_nbr, i.actdate, i.status)
    ).mappings()
    data = {(r["airline"], r["flt_nbr"], r["actdate"], r["status"].rstrip()): r for r in data_rows}

    r, e = t.review_item.c, t.error_type.c
    review_rows = conn.execute(
        select(
            r.airline,
            r.flt_nbr,
            r.actdate,
            r.status,
            func.count().label("open"),
            func.sum(case((e.blocks_release, 1), else_=0)).label("blocking"),
        )
        .join_from(t.review_item, t.error_type, r.error_code == e.error_code)
        .where(
            r.state == "OPEN",
            r.airline.is_not(None),
            r.flt_nbr.is_not(None),
            r.actdate.is_not(None),
            *scope(r.airline, r.actdate),
        )
        .group_by(r.airline, r.flt_nbr, r.actdate, r.status)
    ).mappings()
    reviews = {
        (x["airline"], x["flt_nbr"], x["actdate"], x["status"] and x["status"].rstrip()): x
        for x in review_rows
    }

    s = t.sap_send.c
    send_rows = conn.execute(select(t.sap_send).where(*scope(s.airline, s.actdate))).mappings()
    sends = {(x["airline"], x["flt_nbr"], x["actdate"], x["status"].rstrip()): x for x in send_rows}

    def stages(flight: tuple, send_flight: tuple) -> list[dict]:
        out = []
        for status in STATUSES:
            row = data.get((*flight, status))
            send = sends.get((*send_flight, status))
            # A review item with no status applies to both stages of the flight.
            counts = [reviews[k] for k in ((*flight, status), (*flight, None)) if k in reviews]
            sent_at = row["sent_at"] if row else None
            out.append(
                {
                    "status": status,
                    "state": stage_state(row is not None, sent_at, send and send["state"]),
                    "sectors": row["sectors"] if row else 0,
                    "review_state": review_state(row["sectors"], row["edited"], row["reviewed"])
                    if row
                    else "NOT_REVIEWED",
                    "open_review_items": sum(c["open"] for c in counts),
                    "blocking_review_items": sum(c["blocking"] for c in counts),
                    "sent_at": sent_at,
                    "updated_at": row["updated_at"] if row else None,
                    "send_error": send["failure_reason"] if send else None,
                }
            )
        return out

    # Flights with extracted data or with open review items (an email can fail extraction
    # and leave only a review item), folded onto their outbound flight.
    outbound_flights = set()
    for airline_, flt_nbr, actdate, _ in [*data, *reviews]:
        ob = outbound_for(by_return, airline_, flt_nbr, actdate)
        outbound_flights.add(tuple(ob.values()) if ob else (airline_, flt_nbr, actdate))

    result = []
    for flight in sorted(outbound_flights, key=lambda f: (f[2], f[0], f[1])):
        airline_, flt_nbr, actdate = flight
        if (date_from and actdate < date_from) or (date_to and actdate > date_to):
            continue
        ret = return_for(by_outbound, *flight)
        if ret:
            ret["stages"] = stages(tuple(ret.values()), flight)
        result.append(
            {
                "airline": airline_,
                "flt_nbr": flt_nbr,
                "actdate": actdate,
                "plant": plant_for(airline_),
                "stages": stages(flight, flight),
                "return_flight": ret,
            }
        )
    return result


def _i033_out(row: RowMapping) -> dict:
    out = {
        k: row[k]
        for k in (
            "i033_id",
            "sector_nbr",
            "version_no",
            "is_current",
            "created_source",
            "created_by",
            "created_at",
            "source_email_id",
            "is_ex_sector",
            "sent_to_sap_at",
        )
    }
    out["classes"] = [{"slot": s, "code": row[s], "pax": row[f"pax_{s}"]} for s in t.CLASS_SLOTS]
    return out


def _i034_out(row: RowMapping) -> dict:
    out = {
        k: row[k] for k in ("i034_id", "meal_type", "spml_id", "qnty", "pname", "meal_nr", "txt")
    }
    out["sector_nbr"] = row["secnr"]
    out["class_code"] = row["class"]
    return out


def _i034_rows(conn: Connection, airline, flt_nbr, actdate, status, versions: list[tuple]):
    """I034 rows of the given (sector_nbr, version_no) pairs. I034 has no is_current."""
    if not versions:
        return []
    m = t.i034.c
    return (
        conn.execute(
            select(t.i034)
            .where(
                m.airln == airline,
                m.fltnr == flt_nbr,
                m.acdate == actdate,
                m.status == status,
                or_(*[and_(m.secnr == s, m.version_no == v) for s, v in versions]),
            )
            .order_by(m.secnr, m.i034_id)
        )
        .mappings()
        .all()
    )


def get_stage(conn: Connection, airline: str, flt_nbr: str, actdate: date, status: str):
    """Current I033 and I034, version history, open review items and send state of one
    flight stage. None when the stage has no I033 rows."""
    i = t.i033.c
    rows = (
        conn.execute(
            select(t.i033)
            .where(
                i.airline == airline,
                i.flt_nbr == flt_nbr,
                i.actdate == actdate,
                i.status == status,
            )
            .order_by(i.sector_nbr, i.version_no.desc())
        )
        .mappings()
        .all()
    )
    if not rows:
        return None

    by_outbound, by_return = return_maps(conn)
    return_of = outbound_for(by_return, airline, flt_nbr, actdate)
    return_flight = return_for(by_outbound, airline, flt_nbr, actdate)

    # A return flight has no send of its own; it follows its outbound flight's send row.
    unit = return_of or {"airline": airline, "flt_nbr": flt_nbr, "actdate": actdate}
    s = t.sap_send.c
    send = (
        conn.execute(
            select(t.sap_send).where(
                s.airline == unit["airline"],
                s.flt_nbr == unit["flt_nbr"],
                s.actdate == unit["actdate"],
                s.status == status,
            )
        )
        .mappings()
        .first()
    )

    current = [r for r in rows if r["is_current"]]
    meals = _i034_rows(
        conn,
        airline,
        flt_nbr,
        actdate,
        status,
        [(r["sector_nbr"], r["version_no"]) for r in current],
    )

    r, e = t.review_item.c, t.error_type.c
    review_items = (
        conn.execute(
            select(
                r.review_item_id,
                r.error_code,
                e.severity,
                e.blocks_release,
                r.email_id,
                r.sector_nbr,
                r.i033_id,
                r.i034_id,
                r.field_name,
                r.text_start,
                r.text_end,
                r.text_snippet,
                r.message,
                r.created_at,
            )
            .join_from(t.review_item, t.error_type, r.error_code == e.error_code)
            .where(
                r.state == "OPEN",
                r.airline == airline,
                r.flt_nbr == flt_nbr,
                r.actdate == actdate,
                or_(r.status == status, r.status.is_(None)),
            )
            .order_by(r.review_item_id)
        )
        .mappings()
        .all()
    )

    reviewed = conn.execute(
        select(func.count()).where(t.i033_review.c.i033_id.in_([x["i033_id"] for x in current]))
    ).scalar()
    edited = sum(x["created_source"] == "USER" for x in current)

    return_flight_missing = False
    if return_flight:
        return_flight_missing = not conn.execute(
            select(func.count()).where(
                i.airline == return_flight["airline"],
                i.flt_nbr == return_flight["flt_nbr"],
                i.actdate == return_flight["actdate"],
                i.status == status,
                i.is_current,
            )
        ).scalar()

    sent_at = max((x["sent_to_sap_at"] for x in rows if x["sent_to_sap_at"]), default=None)
    state = stage_state(True, sent_at, send and send["state"])
    return {
        "airline": airline,
        "flt_nbr": flt_nbr,
        "actdate": actdate,
        "status": status,
        "plant": plant_for(airline),
        "state": state,
        # No edits once sent, or while a send is in flight.
        "locked": state in ("SENT", "SENDING"),
        "review_state": review_state(len(current), edited, reviewed),
        "return_flight_missing": return_flight_missing,
        "sent_at": sent_at,
        "return_of": return_of,
        "return_flight": return_flight,
        "send": dict(send) if send else None,
        "sectors": [
            {
                "sector_nbr": cur["sector_nbr"],
                "i033": _i033_out(cur),
                "i034": [_i034_out(m) for m in meals if m["secnr"] == cur["sector_nbr"]],
                "versions": [
                    {
                        k: x[k]
                        for k in (
                            "version_no",
                            "is_current",
                            "created_source",
                            "created_by",
                            "created_at",
                            "source_email_id",
                        )
                    }
                    for x in rows
                    if x["sector_nbr"] == cur["sector_nbr"]
                ],
            }
            for cur in current
        ],
        "review_items": [dict(x) for x in review_items],
    }


def get_version(
    conn: Connection,
    airline: str,
    flt_nbr: str,
    actdate: date,
    status: str,
    sector_nbr: int,
    version_no: int,
):
    """One stored version of a sector's I033 and I034, current or not."""
    i = t.i033.c
    row = (
        conn.execute(
            select(t.i033).where(
                i.airline == airline,
                i.flt_nbr == flt_nbr,
                i.actdate == actdate,
                i.status == status,
                i.sector_nbr == sector_nbr,
                i.version_no == version_no,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    meals = _i034_rows(conn, airline, flt_nbr, actdate, status, [(sector_nbr, version_no)])
    return {"i033": _i033_out(row), "i034": [_i034_out(m) for m in meals]}


def get_amf(conn: Connection, airline: str, flt_nbr: str, actdate: date) -> list[dict]:
    """Current AMF of each sector, with its lines. Empty until both stages exist."""
    a = t.amf.c
    heads = (
        conn.execute(
            select(t.amf)
            .where(a.airline == airline, a.flt_nbr == flt_nbr, a.actdate == actdate, a.is_current)
            .order_by(a.sector_nbr)
        )
        .mappings()
        .all()
    )
    if not heads:
        return []
    ln = t.amf_line.c
    lines = (
        conn.execute(
            select(t.amf_line)
            .where(ln.amf_id.in_([h["amf_id"] for h in heads]))
            .order_by(ln.amf_line_id)
        )
        .mappings()
        .all()
    )
    return [{**h, "lines": [dict(x) for x in lines if x["amf_id"] == h["amf_id"]]} for h in heads]


def get_email(conn: Connection, email_id: int):
    m = t.email.c
    row = (
        conn.execute(
            select(
                m.email_id,
                m.sender,
                m.subject,
                m.received_at,
                m.airline,
                m.detected_status,
                m.confidence,
                m.pipeline_status,
                m.rejection_reason,
                m.body_preview,
            ).where(m.email_id == email_id)
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def list_emails(
    conn: Connection,
    plants: frozenset[str],
    pipeline_status: str | None,
    airline: str | None,
    limit: int,
) -> list[dict]:
    """Every email the pipeline has seen, newest first, with the flights it produced and its
    open review items. An email not yet matched to an airline has no plant, so everyone
    signed in sees it (as with a single email read); the flights listed are plant-scoped."""
    m = t.email.c
    conditions = [or_(m.airline.is_(None), _plant_condition(m.airline, plants))]
    if pipeline_status:
        conditions.append(m.pipeline_status == pipeline_status)
    if airline:
        conditions.append(m.airline == airline)
    rows = (
        conn.execute(
            select(
                m.email_id,
                m.received_at,
                m.sender,
                m.subject,
                m.airline,
                m.detected_status,
                m.confidence,
                m.pipeline_status,
                m.rejection_reason,
            )  # fmt: skip
            .where(and_(*conditions))
            .order_by(m.received_at.desc(), m.email_id.desc())
            .limit(limit)
        )
        .mappings()
        .all()
    )
    ids = [r["email_id"] for r in rows]
    flights: dict[int, list[dict]] = {i: [] for i in ids}
    open_items: dict[int, int] = {}
    blocking: dict[int, int] = {}
    if ids:
        v = t.i033.c
        for f in conn.execute(
            select(v.source_email_id, v.airline, v.flt_nbr, v.actdate, v.status)
            .where(v.source_email_id.in_(ids), _plant_condition(v.airline, plants))
            .distinct()
            .order_by(v.actdate, v.flt_nbr, v.status)
        ).mappings():
            flights[f["source_email_id"]].append(
                {k: f[k] for k in ("airline", "flt_nbr", "actdate", "status")}
            )
        i, e = t.review_item.c, t.error_type.c
        for r in conn.execute(
            select(i.email_id, func.count().label("n"), func.sum(cast(e.blocks_release, Integer)))
            .join(t.error_type, e.error_code == i.error_code)
            .where(i.email_id.in_(ids), i.state == "OPEN")
            .group_by(i.email_id)
        ):
            open_items[r[0]], blocking[r[0]] = r[1], int(r[2] or 0)
    return [
        {
            **r,
            "flights": flights[r["email_id"]],
            "open_review_items": open_items.get(r["email_id"], 0),
            "blocking_review_items": blocking.get(r["email_id"], 0),
        }
        for r in rows
    ]


def _plant_condition(airline_col, plants: frozenset[str]):
    """Rows of the airlines belonging to these plants (SQ is ICC1, all others ICC2)."""
    conditions = []
    if "ICC1" in plants:
        conditions.append(airline_col == "SQ")
    if "ICC2" in plants:
        conditions.append(airline_col != "SQ")
    return or_(*conditions) if conditions else false()


def audit_events(
    conn: Connection,
    plants: frozenset[str],
    date_from: date | None,
    date_to: date | None,
    airline: str | None,
    limit: int,
) -> list[dict]:
    """Who did what to which flight, newest first, from the records the console already
    keeps: I033 versions, reviewed-OK marks, resolved review items and send decisions.
    Return flight and airline setting changes keep only their latest editor, so they are
    not part of this trail."""
    events: list[dict] = []

    def scope(c):
        parts = [_plant_condition(c.airline, plants)]
        if date_from:
            parts.append(c.actdate >= date_from)
        if date_to:
            parts.append(c.actdate <= date_to)
        if airline:
            parts.append(c.airline == airline)
        return and_(*parts)

    def add(rows, **fixed):
        events.extend({**fixed, **row} for row in rows)

    v = t.i033.c
    versions = conn.execute(
        select(
            v.created_at.label("at"),
            v.created_by.label("actor"),
            case((v.created_source == "USER", "EDITED"), else_="EXTRACTED").label("action"),
            v.airline, v.flt_nbr, v.actdate, v.status, v.sector_nbr,
            ("Version " + cast(v.version_no, String)).label("detail"),
        )
        .where(scope(v))
        .order_by(v.created_at.desc())
        .limit(limit)
    )  # fmt: skip
    add(versions.mappings())

    r = t.i033_review.c
    reviewed = conn.execute(
        select(
            r.reviewed_at.label("at"),
            r.reviewed_by.label("actor"),
            v.airline, v.flt_nbr, v.actdate, v.status, v.sector_nbr,
            ("Version " + cast(v.version_no, String)).label("detail"),
        )
        .join(t.i033, t.i033.c.i033_id == r.i033_id)
        .where(scope(v))
        .order_by(r.reviewed_at.desc())
        .limit(limit)
    )  # fmt: skip
    # The mark is stored per sector, but a user pressed one button: one event per press.
    presses: dict[tuple, list[dict]] = {}
    for row in reviewed.mappings():
        key = tuple(row[k] for k in ("at", "actor", "airline", "flt_nbr", "actdate", "status"))
        presses.setdefault(key, []).append(dict(row))
    for rows in presses.values():
        if len(rows) == 1:
            events.append({**rows[0], "action": "REVIEWED_OK"})
            continue
        rows.sort(key=lambda r: r["sector_nbr"])
        detail = ", ".join(f"sector {r['sector_nbr']} {r['detail'].lower()}" for r in rows)
        events.append(
            {**rows[0], "action": "REVIEWED_OK", "sector_nbr": None, "detail": detail.capitalize()}
        )

    i = t.review_item.c
    resolved = conn.execute(
        select(
            i.resolved_at.label("at"),
            func.coalesce(i.resolved_by, "system").label("actor"),
            i.airline, i.flt_nbr, i.actdate, i.status, i.sector_nbr,
            (
                i.error_code + ": " + func.coalesce(i.resolution_type, i.state)
                + func.coalesce(", " + i.resolution_remarks, "")
            ).label("detail"),
        )
        .where(i.resolved_at.is_not(None), i.airline.is_not(None), scope(i))
        .order_by(i.resolved_at.desc())
        .limit(limit)
    )  # fmt: skip
    add(resolved.mappings(), action="REVIEW_ITEM_RESOLVED")

    s = t.sap_send.c
    sends = conn.execute(
        select(
            s.decided_at.label("at"),
            s.decided_by.label("actor"),
            s.state.label("action"),
            s.airline, s.flt_nbr, s.actdate, s.status,
            case(
                (s.failure_reason.is_not(None), s.failure_reason),
                (
                    s.i033_file_name.is_not(None),
                    s.i033_file_name + func.coalesce(", " + s.i034_file_name, ""),
                ),
                else_=None,
            ).label("detail"),
        )
        .where(scope(s))
        .order_by(s.decided_at.desc())
        .limit(limit)
    )  # fmt: skip
    add(sends.mappings(), sector_nbr=None)

    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]
