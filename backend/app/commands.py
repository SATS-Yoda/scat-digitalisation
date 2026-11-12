"""Write-side operations. Each takes a connection inside a transaction that the caller
commits, and raises NotFound, Conflict or Invalid when the request cannot be honoured."""

from datetime import UTC, date, datetime

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from . import tables as t
from .auth import User, require_plant
from .dify import SapSendResult
from .queries import outbound_for, return_for, return_maps
from .schemas import SectorEdit

_CABINS = {"P": "P", "J": "J", "S": "YD", "Y": "Y"}


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


class Invalid(Exception):
    pass


def _name(airline: str, flt_nbr: str, actdate: date, status: str) -> str:
    return f"{airline} {flt_nbr} on {actdate} ({status})"


def _current_rows(conn: Connection, airline, flt_nbr, actdate, status, sector_nbr=None):
    """Current I033 rows of a stage, locked. Every write to a stage takes this lock first,
    so a save and a send of the same stage cannot interleave (no-op on SQLite)."""
    i = t.i033.c
    query = (
        select(t.i033)
        .where(
            i.airline == airline,
            i.flt_nbr == flt_nbr,
            i.actdate == actdate,
            i.status == status,
            i.is_current,
        )
        .order_by(i.sector_nbr)
        .with_for_update()
    )
    if sector_nbr is not None:
        query = query.where(i.sector_nbr == sector_nbr)
    return conn.execute(query).mappings().all()


def _send_row(conn: Connection, unit: dict, status: str):
    s = t.sap_send.c
    return (
        conn.execute(
            select(t.sap_send)
            .where(
                s.airline == unit["airline"],
                s.flt_nbr == unit["flt_nbr"],
                s.actdate == unit["actdate"],
                s.status == status,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )


def _was_sent(conn: Connection, airline, flt_nbr, actdate, status) -> bool:
    i = t.i033.c
    return bool(
        conn.execute(
            select(func.count()).where(
                i.airline == airline,
                i.flt_nbr == flt_nbr,
                i.actdate == actdate,
                i.status == status,
                i.sent_to_sap_at.is_not(None),
            )
        ).scalar()
    )


def _require_unlocked(conn: Connection, airline, flt_nbr, actdate, status) -> None:
    """Sent is final, and nothing changes while a send is in flight. A return flight is
    locked by its outbound flight's send."""
    _, by_return = return_maps(conn)
    unit = outbound_for(by_return, airline, flt_nbr, actdate) or {
        "airline": airline,
        "flt_nbr": flt_nbr,
        "actdate": actdate,
    }
    send = _send_row(conn, unit, status)
    if _was_sent(conn, airline, flt_nbr, actdate, status) or (send and send["state"] == "SENT"):
        raise Conflict(
            f"{_name(airline, flt_nbr, actdate, status)} has been sent to SAP and can no "
            "longer be changed; correct it in SAP"
        )
    if send and send["state"] == "SENDING":
        raise Conflict(f"{_name(airline, flt_nbr, actdate, status)} is being sent to SAP")


def _meals(conn: Connection, row) -> dict[tuple, int]:
    """Special meal quantities of one I033 version, by (class, meal type, code)."""
    m = t.i034.c
    rows = conn.execute(
        select(m["class"], m.meal_type, m.spml_id, m.qnty).where(
            m.airln == row["airline"],
            m.fltnr == row["flt_nbr"],
            m.acdate == row["actdate"],
            m.secnr == row["sector_nbr"],
            m.status == row["status"],
            m.version_no == row["version_no"],
        )
    )
    return {(cls, meal_type, spml_id): qnty for cls, meal_type, spml_id, qnty in rows}


def _cabin(code: str) -> str:
    cabin = _CABINS.get(code[:1].upper())
    if cabin is None:
        raise Invalid(
            f"Class {code!r} cannot be placed on the additional meal form; "
            "classes start with P, J, S or Y"
        )
    return cabin


def amf_lines(airline: str, p06h_row, p24h_meals: dict, p06h_meals: dict) -> list[dict]:
    """Additional meal form content (requirement document, Annex 12 2.1.4-5, Appendix C).

    Pax lines carry the P06H pax count per class, not a delta. Special meal lines carry the
    change from P24H to P06H; for SQ only reductions are shown, for other airlines both.
    Crew (staff) slots are left out: the form has no crew cabin.
    """
    lines = [
        {"line_type": "PAX", "cabin": _cabin(slot), "source_class": slot.upper(),
         "meal_type": None, "pax_p06h": p06h_row[f"pax_{slot}"], "spml_id": None,
         "delta_qty": None}
        for slot in t.CLASS_SLOTS
        if not slot.startswith("staff_") and p06h_row[f"pax_{slot}"] is not None
    ]  # fmt: skip
    for key in sorted(
        p24h_meals.keys() | p06h_meals.keys(), key=lambda k: (k[0], k[1] or "", k[2])
    ):
        delta = p06h_meals.get(key, 0) - p24h_meals.get(key, 0)
        if delta == 0 or (airline == "SQ" and delta > 0):
            continue
        cls, meal_type, spml_id = key
        lines.append(
            {"line_type": "SPML", "cabin": _cabin(cls), "source_class": cls,
             "meal_type": meal_type, "pax_p06h": None, "spml_id": spml_id, "delta_qty": delta}
        )  # fmt: skip
    return lines


def regenerate_amf(conn: Connection, airline, flt_nbr, actdate, sector_nbr) -> int | None:
    """Write a new current AMF version for a sector from its current P24H and P06H data.
    Returns the new version, or None when one of the two stages has no data yet."""
    p24h = _current_rows(conn, airline, flt_nbr, actdate, "P24H", sector_nbr)
    p06h = _current_rows(conn, airline, flt_nbr, actdate, "P06H", sector_nbr)
    if not p24h or not p06h:
        return None
    lines = amf_lines(airline, p06h[0], _meals(conn, p24h[0]), _meals(conn, p06h[0]))

    a = t.amf.c
    key = (a.airline == airline, a.flt_nbr == flt_nbr, a.actdate == actdate,
           a.sector_nbr == sector_nbr)  # fmt: skip
    version = (conn.execute(select(func.max(a.amf_version)).where(*key)).scalar() or 0) + 1
    conn.execute(update(t.amf).where(*key, a.is_current).values(is_current=False))
    amf_id = conn.execute(
        insert(t.amf)
        .values(
            airline=airline,
            flt_nbr=flt_nbr,
            actdate=actdate,
            sector_nbr=sector_nbr,
            p24h_i033_id=p24h[0]["i033_id"],
            p06h_i033_id=p06h[0]["i033_id"],
            amf_version=version,
        )
        .returning(a.amf_id)
    ).scalar()
    if lines:
        conn.execute(insert(t.amf_line), [{**line, "amf_id": amf_id} for line in lines])
    return version


def save_sector(
    conn: Connection,
    user: User,
    airline: str,
    flt_nbr: str,
    actdate: date,
    status: str,
    sector_nbr: int,
    edit: SectorEdit,
) -> dict:
    """Save a user's edit of one sector as a new current version and regenerate the AMF."""
    require_plant(user, airline)
    name = f"Sector {sector_nbr} of {_name(airline, flt_nbr, actdate, status)}"
    rows = _current_rows(conn, airline, flt_nbr, actdate, status, sector_nbr)
    if not rows:
        raise NotFound(f"{name} has no data to edit")
    current = rows[0]
    _require_unlocked(conn, airline, flt_nbr, actdate, status)
    if edit.base_version_no != current["version_no"]:
        raise Conflict(
            f"{name} changed since it was opened (now version {current['version_no']}); "
            "reload and apply the edit again"
        )

    slots = [c.slot for c in edit.classes]
    if len(slots) != len(set(slots)):
        raise Invalid("A class slot appears more than once")
    meal_keys = [(m.class_code, m.meal_type or None, m.spml_id) for m in edit.i034]
    if len(meal_keys) != len(set(meal_keys)):
        raise Invalid("A special meal line (class, meal type, code) appears more than once")
    if edit.i034 and current["is_ex_sector"]:
        raise Invalid("An ex-sector uplift carries pax counts only, no special meals")
    for m in edit.i034:
        _cabin(m.class_code)

    i = t.i033.c
    carried = [
        c.name for c in t.i033.c if c.name not in ("i033_id", "created_at", "sent_to_sap_at")
    ]
    values = {k: current[k] for k in carried}
    for c in edit.classes:
        values[c.slot] = c.code or None
        values[f"pax_{c.slot}"] = c.pax
    values.update(
        version_no=current["version_no"] + 1,
        is_current=True,
        created_source="USER",
        created_by=user.id[:50],
    )
    # The old row is retired first: only one current version may exist per sector.
    conn.execute(update(t.i033).where(i.i033_id == current["i033_id"]).values(is_current=False))
    conn.execute(insert(t.i033).values(values))
    if edit.i034:
        conn.execute(
            insert(t.i034),
            [
                {
                    "airln": airline,
                    "fltnr": flt_nbr,
                    "acdate": actdate,
                    "secnr": sector_nbr,
                    "status": status,
                    "version_no": values["version_no"],
                    "class": m.class_code,
                    "meal_type": m.meal_type or None,
                    "spml_id": m.spml_id,
                    "qnty": m.qnty,
                    "pname": m.pname or None,
                    "meal_nr": m.meal_nr or None,
                    "txt": m.txt or None,
                }
                for m in edit.i034
            ],
        )

    warnings = []
    if airline == "SQ" and status == "P06H":
        p24h = _current_rows(conn, airline, flt_nbr, actdate, "P24H", sector_nbr)
        before = _meals(conn, p24h[0]) if p24h else {}
        for key, m in zip(meal_keys, edit.i034, strict=True):
            if p24h and m.qnty > before.get(key, 0):
                warnings.append(
                    f"{m.spml_id} in class {m.class_code} is {m.qnty}, above the P24H quantity "
                    f"of {before.get(key, 0)}; SQ increases at P06H are normally not uplifted"
                )
    regenerate_amf(conn, airline, flt_nbr, actdate, sector_nbr)
    return {"version_no": values["version_no"], "warnings": warnings}


def mark_reviewed(conn: Connection, user: User, airline, flt_nbr, actdate, status) -> None:
    """Record that the user checked the current versions of a stage and changed nothing."""
    require_plant(user, airline)
    rows = _current_rows(conn, airline, flt_nbr, actdate, status)
    if not rows:
        raise NotFound(f"{_name(airline, flt_nbr, actdate, status)} has no data to review")
    _require_unlocked(conn, airline, flt_nbr, actdate, status)
    ids = [r["i033_id"] for r in rows]
    rv = t.i033_review.c
    done = set(conn.execute(select(rv.i033_id).where(rv.i033_id.in_(ids))).scalars())
    todo = [{"i033_id": x, "reviewed_by": user.id} for x in ids if x not in done]
    if todo:
        conn.execute(insert(t.i033_review), todo)


def resolve_review_item(
    conn: Connection, user: User, review_item_id: int, resolution_type: str, remarks: str | None
) -> None:
    r = t.review_item.c
    item = (
        conn.execute(
            select(t.review_item).where(r.review_item_id == review_item_id).with_for_update()
        )
        .mappings()
        .first()
    )
    if item is None:
        raise NotFound(f"No review item with id {review_item_id}")
    if item["airline"]:
        require_plant(user, item["airline"])
    if item["state"] != "OPEN":
        raise Conflict(f"Review item {review_item_id} is already {item['state'].lower()}")
    conn.execute(
        update(t.review_item)
        .where(r.review_item_id == review_item_id)
        .values(
            state="RESOLVED",
            resolution_type=resolution_type,
            resolution_remarks=remarks,
            resolved_by=user.id[:50],
            resolved_at=datetime.now(UTC),
        )
    )


def _send_unit(conn: Connection, user: User, airline, flt_nbr, actdate, status):
    """Checks shared by Send and Not released; returns (unit, return flight, send row)."""
    require_plant(user, airline)
    name = _name(airline, flt_nbr, actdate, status)
    by_outbound, by_return = return_maps(conn)
    outbound = outbound_for(by_return, airline, flt_nbr, actdate)
    if outbound:
        raise Conflict(
            f"{name} is a return flight and is sent with "
            f"{outbound['airline']} {outbound['flt_nbr']} on {outbound['actdate']}"
        )
    if not _current_rows(conn, airline, flt_nbr, actdate, status):
        raise NotFound(f"{name} has no data")
    unit = {"airline": airline, "flt_nbr": flt_nbr, "actdate": actdate}
    send = _send_row(conn, unit, status)
    if _was_sent(conn, airline, flt_nbr, actdate, status) or (send and send["state"] == "SENT"):
        raise Conflict(f"{name} has already been sent to SAP")
    if send and send["state"] == "SENDING":
        raise Conflict(f"{name} is already being sent to SAP")
    return unit, return_for(by_outbound, airline, flt_nbr, actdate), send


def mark_not_released(conn: Connection, user: User, airline, flt_nbr, actdate, status) -> None:
    """Record the decision not to send a stage. It can still be sent later."""
    unit, _, send = _send_unit(conn, user, airline, flt_nbr, actdate, status)
    decision = {"state": "NOT_RELEASED", "release_mode": "MANUAL", "decided_by": user.id,
                "decided_at": datetime.now(UTC)}  # fmt: skip
    if send:
        conn.execute(
            update(t.sap_send).where(t.sap_send.c.send_id == send["send_id"]).values(decision)
        )
    else:
        conn.execute(insert(t.sap_send).values(**unit, status=status, **decision))


def begin_send(conn: Connection, user: User, airline, flt_nbr, actdate, status) -> dict:
    """Claim the send unit as SENDING. The caller commits before calling the workflow, so
    the claim is visible to every other request; the unique key on the unit makes a second
    claim fail."""
    unit, ret, send = _send_unit(conn, user, airline, flt_nbr, actdate, status)
    name = _name(airline, flt_nbr, actdate, status)

    flights = [unit] + ([ret] if ret else [])
    r, e = t.review_item.c, t.error_type.c
    blocking = conn.execute(
        select(func.count())
        .select_from(t.review_item)
        .join(t.error_type, r.error_code == e.error_code)
        .where(
            r.state == "OPEN",
            e.blocks_release,
            or_(r.status == status, r.status.is_(None)),
            or_(
                *[
                    (r.airline == f["airline"])
                    & (r.flt_nbr == f["flt_nbr"])
                    & (r.actdate == f["actdate"])
                    for f in flights
                ]
            ),
        )
    ).scalar()
    if blocking:
        raise Conflict(f"{name} has {blocking} open review item(s) that block sending")

    warnings = []
    if ret:
        ret_rows = _current_rows(conn, ret["airline"], ret["flt_nbr"], ret["actdate"], status)
        if not ret_rows:
            warnings.append(
                f"Return flight {ret['airline']} {ret['flt_nbr']} on {ret['actdate']} had no "
                f"{status} data and was not included"
            )

    claim = {"state": "SENDING", "release_mode": "MANUAL", "decided_by": user.id,
             "decided_at": datetime.now(UTC), "failure_reason": None}  # fmt: skip
    if send:  # FAILED or NOT_RELEASED: reuse the row, so a retry keeps its file number
        send_id = send["send_id"]
        conn.execute(update(t.sap_send).where(t.sap_send.c.send_id == send_id).values(claim))
    else:
        try:
            send_id = conn.execute(
                insert(t.sap_send)
                .values(**unit, status=status, **claim)
                .returning(t.sap_send.c.send_id)
            ).scalar()
        except IntegrityError as exc:
            raise Conflict(f"{name} is already being sent to SAP") from exc
    return {
        "send_id": send_id,
        "warnings": warnings,
        "inputs": {
            "airline": airline,
            "flt_nbr": flt_nbr,
            "actdate": actdate.isoformat(),
            "status": status,
            "file_seq": send_id,
            # A retry skips a file that already uploaded.
            "send_i033": not (send and send["i033_file_name"]),
            "send_i034": not (send and send["i034_file_name"]),
        },
    }


def finish_send(conn: Connection, send_id: int, inputs: dict, result: SapSendResult) -> dict:
    """Record the workflow's answer on the send row: SENT only when both files are up."""
    i033_done = result.i033_uploaded or not inputs["send_i033"]
    i034_done = result.i034_uploaded or not inputs["send_i034"]
    sent = i033_done and i034_done and not result.error
    values = {
        "state": "SENT" if sent else "FAILED",
        "sent_at": datetime.now(UTC) if sent else None,
        "failure_reason": None
        if sent
        else (result.error or "The workflow did not upload both files")[:2000],
        "dify_run_id": result.run_id,
    }
    if result.i033_uploaded:
        values["i033_file_name"] = result.i033_file_name
    if result.i034_uploaded:
        values["i034_file_name"] = result.i034_file_name
    conn.execute(update(t.sap_send).where(t.sap_send.c.send_id == send_id).values(values))
    return {"state": values["state"], "failure_reason": values["failure_reason"]}
