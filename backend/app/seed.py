"""Synthetic data for local development and tests. Nothing here is real operational data.

    uv run python -m app.seed

rebuilds the local SQLite database named by DATABASE_URL. It refuses any other database.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from . import tables as t

T0 = datetime(2026, 11, 12, 2, 0, tzinfo=UTC)
D13 = date(2026, 11, 13)
D14 = date(2026, 11, 14)
D15 = date(2026, 11, 15)


def _i033(conn, i033_id, airline, flt_nbr, actdate, status, pax: dict, **overrides):
    values = {
        "i033_id": i033_id,
        "airline": airline,
        "flt_nbr": flt_nbr,
        "actdate": actdate,
        "status": status,
        "sector_nbr": 1,
        "version_no": 1,
        "is_current": True,
        "created_source": "SYSTEM",
        "created_by": "dify-extraction",
        "created_at": T0,
        **overrides,
    }
    for slot, count in pax.items():
        values[slot] = slot.upper()
        values[f"pax_{slot}"] = count
    conn.execute(t.i033.insert().values(values))


def _i034(conn, airline, flt_nbr, actdate, status, cls, spml_id, qnty, **overrides):
    conn.execute(
        t.i034.insert().values(
            {
                "airln": airline,
                "fltnr": flt_nbr,
                "acdate": actdate,
                "status": status,
                "secnr": 1,
                "version_no": 1,
                "class": cls,
                "spml_id": spml_id,
                "qnty": qnty,
                **overrides,
            }
        )
    )


def _email(conn, email_id, airline, status, subject, body):
    conn.execute(
        t.email.insert().values(
            email_id=email_id,
            eml_uri=f"synthetic/{email_id}.eml",
            sender=f"catering.ops@{airline.lower()}.example",
            subject=subject,
            received_at=T0,
            body_preview=body,
            airline=airline,
            detected_status=status,
            confidence=0.97,
            pipeline_status="EXTRACTED",
            extracted_at=T0,
            inserted_at=T0,
            updated_at=T0,
        )
    )


def seed(conn: Connection) -> None:
    conn.execute(
        t.error_type.insert(),
        [
            {
                "error_code": "PAX_MISMATCH",
                "description": "Class totals do not add up to the stated total",
                "severity": "ERROR",
                "blocks_release": True,
                "message_template": "Class totals differ from the stated total",
            },
            {
                "error_code": "LOW_CONFIDENCE",
                "description": "A field was extracted with low confidence",
                "severity": "WARNING",
                "blocks_release": False,
                "message_template": "Check {field}",
            },
        ],
    )
    conn.execute(
        t.return_map.insert(),
        [
            {
                "airline": a,
                "outbound_flt_nbr": out,
                "return_flt_nbr": ret,
                "day_offset": 1,
                "is_active": active,
                "updated_by": "synthetic.admin",
                "updated_at": T0,
            }
            for a, out, ret, active in [
                ("SQ", "856", "857", True),
                ("SQ", "12", "11", True),
                ("TR", "508", "509", False),  # inactive: must be ignored
            ]
        ],  # fmt: skip
    )

    _email(conn, 1, "SQ", "P24H", "SQ856/13NOV LTK", "SYNTHETIC SQ856/13NOV SIN P4 J28 Y180")
    _email(conn, 2, "SQ", "P06H", "SQ856/13NOV FINAL", "SYNTHETIC SQ856/13NOV SIN P4 J30 Y176")
    _email(conn, 3, "QR", "P24H", "QR943/13NOV", "SYNTHETIC QR943/13NOV SIN J20 Y210 TTL 240")

    # SQ 856 on 13 Nov with return SQ 857 on 14 Nov: P24H sent, P06H under review after a
    # user edit (two versions).
    sent = T0 + timedelta(hours=3)
    _i033(conn, 1, "SQ", "856", D13, "P24H", {"p": 4, "jf": 28, "y": 180},
          source_email_id=1, sent_to_sap_at=sent)  # fmt: skip
    _i033(conn, 2, "SQ", "857", D14, "P24H", {"p": 2, "jf": 25, "y": 170},
          source_email_id=1, sent_to_sap_at=sent)  # fmt: skip
    _i033(conn, 3, "SQ", "856", D13, "P06H", {"p": 4, "jf": 30, "y": 176},
          source_email_id=2, is_current=False, created_at=T0 + timedelta(hours=18))  # fmt: skip
    _i033(conn, 4, "SQ", "856", D13, "P06H", {"p": 4, "jf": 30, "y": 178},
          version_no=2, created_source="USER", created_by="synthetic.user",
          source_email_id=2, created_at=T0 + timedelta(hours=19))  # fmt: skip
    _i033(conn, 5, "SQ", "857", D14, "P06H", {"p": 2, "jf": 26, "y": 171},
          source_email_id=2, created_at=T0 + timedelta(hours=18))  # fmt: skip
    _i034(conn, "SQ", "856", D13, "P24H", "Y", "VGML", 3)
    _i034(conn, "SQ", "856", D13, "P06H", "Y", "VGML", 3)
    _i034(conn, "SQ", "856", D13, "P06H", "Y", "VGML", 4, version_no=2)
    _i034(conn, "SQ", "856", D13, "P06H", "JF", "KSML", 1, version_no=2,
          pname="TEST/PASSENGER MR")  # fmt: skip
    _i034(conn, "SQ", "857", D14, "P24H", "Y", "CHML", 2)
    conn.execute(
        t.sap_send.insert().values(
            send_id=1,
            airline="SQ",
            flt_nbr="856",
            actdate=D13,
            status="P24H",
            state="SENT",
            sent_at=sent,
            i033_file_name="I033_SYNTHETIC_1.dat",
            i034_file_name="I034_SYNTHETIC_1.dat",
            release_mode="MANUAL",
            decided_by="synthetic.user",
            decided_at=sent,
        )  # fmt: skip
    )
    conn.execute(
        t.review_item.insert().values(
            review_item_id=1,
            error_code="LOW_CONFIDENCE",
            email_id=2,
            airline="SQ",
            flt_nbr="856",
            actdate=D13,
            sector_nbr=1,
            status="P06H",
            i033_id=3,
            field_name="pax_y",
            text_snippet="Y176",
            message="Check pax_y",
            created_at=T0,
        )  # fmt: skip
    )
    conn.execute(
        t.amf.insert().values(
            amf_id=1,
            airline="SQ",
            flt_nbr="856",
            actdate=D13,
            sector_nbr=1,
            p24h_i033_id=1,
            p06h_i033_id=4,
            amf_version=2,
            generated_at=T0 + timedelta(hours=19),
        )  # fmt: skip
    )
    conn.execute(
        t.amf_line.insert(),
        [
            {
                "amf_id": 1,
                "line_type": "PAX",
                "cabin": "J",
                "source_class": "JF",
                "pax_p06h": 30,
                "spml_id": None,
                "delta_qty": 2,
            },
            {
                "amf_id": 1,
                "line_type": "PAX",
                "cabin": "Y",
                "source_class": "Y",
                "pax_p06h": 178,
                "spml_id": None,
                "delta_qty": -2,
            },
            {
                "amf_id": 1,
                "line_type": "SPML",
                "cabin": "Y",
                "source_class": "Y",
                "pax_p06h": None,
                "spml_id": "VGML",
                "delta_qty": 1,
            },
        ],
    )

    # QR 943 on 13 Nov, two sectors, held by a blocking review item.
    _i033(conn, 6, "QR", "943", D13, "P24H", {"jf": 20, "y": 210}, source_email_id=3)
    _i033(conn, 7, "QR", "943", D13, "P24H", {"jf": 12, "y": 150},
          sector_nbr=2, source_email_id=3)  # fmt: skip
    _i034(conn, "QR", "943", D13, "P24H", "Y", "MOML", 12)
    _i034(conn, "QR", "943", D13, "P24H", "Y", "MOML", 8, secnr=2)
    conn.execute(
        t.review_item.insert().values(
            review_item_id=2,
            error_code="PAX_MISMATCH",
            email_id=3,
            airline="QR",
            flt_nbr="943",
            actdate=D13,
            sector_nbr=1,
            status="P24H",
            i033_id=6,
            text_snippet="TTL 240",
            message="Class totals differ from the stated total",
            created_at=T0,
        )  # fmt: skip
    )

    # TR 508 on 13 Nov: the send failed and can be retried.
    _i033(conn, 8, "TR", "508", D13, "P24H", {"y": 168})
    conn.execute(
        t.sap_send.insert().values(
            send_id=2,
            airline="TR",
            flt_nbr="508",
            actdate=D13,
            status="P24H",
            state="FAILED",
            release_mode="MANUAL",
            failure_reason="SFTP upload timed out after 3 attempts",
            decided_by="synthetic.user",
            decided_at=sent,
        )  # fmt: skip
    )

    # SQ 12 on 14 Nov: mapped return SQ 11 on 15 Nov has no data yet.
    _i033(conn, 9, "SQ", "12", D14, "P24H", {"p": 6, "jf": 40, "y": 190})

    # An older resolved item must not count anywhere.
    conn.execute(
        t.review_item.insert().values(
            review_item_id=3,
            error_code="PAX_MISMATCH",
            airline="SQ",
            flt_nbr="12",
            actdate=D14,
            status="P24H",
            message="Class totals differ from the stated total",
            state="RESOLVED",
            resolved_by="synthetic.user",
            resolved_at=T0,
            created_at=T0,
        )  # fmt: skip
    )


def main() -> None:
    from .config import Settings

    url = Settings().database_url
    if not url.startswith("sqlite:"):
        raise SystemExit("Refusing to seed: DATABASE_URL is not a local SQLite database")
    engine = create_engine(url)
    with engine.begin() as conn:
        t.metadata.drop_all(conn)
        t.metadata.create_all(conn)
        seed(conn)
    print("Seeded synthetic data")


if __name__ == "__main__":
    main()
