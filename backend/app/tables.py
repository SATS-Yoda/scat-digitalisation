"""Table definitions the console uses.

The seven existing tables mirror the shared test database as read on 2026-11-12 (columns,
keys, checks and indexes). They are owned by the Dify workflows; the console never alters
their structure. The console tables at the bottom follow docs/scatdd_console_additions.sql.

`metadata.create_all` is used only to build the local SQLite database and the separate
`scat_console_dev` PostgreSQL database. Shared environments get their schema from
migrations (build order step 1).
"""

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
    true,
)

metadata = MetaData()

# SQLite (local synthetic database only) autoincrements INTEGER keys, not BIGINT.
_Id = BigInteger().with_variant(Integer, "sqlite")
_Ts = DateTime(timezone=True)
_STATUS = "status IN ('P24H', 'P06H')"


def _pk(name: str) -> Column:
    return Column(name, _Id, Identity(always=True), primary_key=True)


def _now(name: str) -> Column:
    return Column(name, _Ts, nullable=False, server_default=func.now())


def _partial_unique(name: str, *cols: str, where: str) -> Index:
    return Index(name, *cols, unique=True, postgresql_where=text(where), sqlite_where=text(where))


# I033 holds one (class code, pax count) column pair per slot: `p` + `pax_p`, and so on.
CLASS_SLOTS = [
    "p", "jm", "ju", "jf", "ja", "sm", "su", "sf", "sa",
    "yu", "yf", "ya", "y", "staff_p", "staff_j", "staff_s", "staff_y",
]  # fmt: skip

email = Table(
    "scatdd_email_test",
    metadata,
    _pk("email_id"),
    Column("message_id", Text),
    Column("eml_uri", Text, nullable=False),
    Column("text_uri", Text),
    Column("content_sha256", CHAR(64)),
    Column("sender", Text),
    Column("subject", Text),
    Column("received_at_raw", Text),
    Column("received_at", _Ts, nullable=False),
    Column("body_preview", Text),
    Column("airline", String(3)),
    Column("detected_status", CHAR(4)),
    Column("confidence", Numeric(4, 3)),
    Column("pipeline_status", String(20), nullable=False, server_default="RECEIVED"),
    Column("rejection_reason", Text),
    Column("raw_record", JSON),
    Column("extracted_at", _Ts),
    _now("inserted_at"),
    _now("updated_at"),
    CheckConstraint(
        "pipeline_status IN ('RECEIVED', 'PROCESSING', 'PROCESSED_OK', 'PROCESSED_PARTIAL', "
        "'PROCESSED_FAILED', 'REJECTED')"
    ),
)

i033 = Table(
    "scatdd_i033_test",
    metadata,
    _pk("i033_id"),
    Column("record_type", String(2), nullable=False, server_default="10"),
    Column("airline", String(3), nullable=False),
    Column("flt_nbr", String(5), nullable=False),
    Column("actdate", Date, nullable=False),
    Column("sector_nbr", SmallInteger, nullable=False, server_default="1"),
    Column("status", CHAR(4), nullable=False),
    *[
        c
        for s in CLASS_SLOTS
        for c in (
            Column(s, String(3)),
            Column(f"pax_{s}", Integer, CheckConstraint(f"pax_{s} >= 0")),
        )
    ],
    Column("version_no", Integer, nullable=False, server_default="1"),
    Column("is_current", Boolean, nullable=False, server_default=true()),
    Column("created_source", String(10), nullable=False, server_default="SYSTEM"),
    Column("is_ex_sector", Boolean, nullable=False, server_default=false()),
    Column("source_email_id", BigInteger, ForeignKey("scatdd_email_test.email_id")),
    Column("created_by", String(50), nullable=False),
    _now("created_at"),
    Column("sent_to_sap_at", _Ts),
    CheckConstraint(_STATUS),
    CheckConstraint("created_source IN ('SYSTEM', 'USER')"),
    CheckConstraint("version_no >= 1"),
    UniqueConstraint(
        "airline",
        "flt_nbr",
        "actdate",
        "sector_nbr",
        "status",
        "version_no",
        name="uq_i033_version",
    ),  # fmt: skip
    _partial_unique(
        "uq_i033_current_test",
        "airline",
        "flt_nbr",
        "actdate",
        "sector_nbr",
        "status",
        where="is_current",
    ),  # fmt: skip
)

i034 = Table(
    "scatdd_i034_test",
    metadata,
    _pk("i034_id"),
    Column("record_type", String(2), nullable=False, server_default="10"),
    Column("airln", String(3), nullable=False),
    Column("fltnr", String(5), nullable=False),
    Column("acdate", Date, nullable=False),
    Column("secnr", SmallInteger, nullable=False, server_default="1"),
    Column("status", CHAR(4), nullable=False),
    Column("class", String(3), nullable=False),
    Column("meal_type", String(2)),
    Column("spml_id", String(40), nullable=False),
    Column("qnty", Integer, CheckConstraint("qnty >= 0"), nullable=False),
    Column("pname", String(40)),
    Column("meal_nr", String(2)),
    Column("txt", String(255)),
    Column("version_no", Integer, nullable=False),
    CheckConstraint(_STATUS),
    ForeignKeyConstraint(
        ["airln", "fltnr", "acdate", "secnr", "status", "version_no"],
        [
            i033.c.airline,
            i033.c.flt_nbr,
            i033.c.actdate,
            i033.c.sector_nbr,
            i033.c.status,
            i033.c.version_no,
        ],
        name="fk_i034_i033",
        ondelete="CASCADE",
    ),  # fmt: skip
    UniqueConstraint(
        "airln",
        "fltnr",
        "acdate",
        "secnr",
        "status",
        "version_no",
        "class",
        "meal_type",
        "spml_id",
        name="uq_i034_line",
        postgresql_nulls_not_distinct=True,
    ),  # fmt: skip
)

amf = Table(
    "scatdd_amf_test",
    metadata,
    _pk("amf_id"),
    Column("airline", String(3), nullable=False),
    Column("flt_nbr", String(5), nullable=False),
    Column("actdate", Date, nullable=False),
    Column("sector_nbr", SmallInteger, nullable=False, server_default="1"),
    Column("p24h_i033_id", BigInteger, ForeignKey(i033.c.i033_id), nullable=False),
    Column("p06h_i033_id", BigInteger, ForeignKey(i033.c.i033_id), nullable=False),
    Column("amf_version", Integer, nullable=False, server_default="1"),
    Column("is_current", Boolean, nullable=False, server_default=true()),
    _now("generated_at"),
    CheckConstraint("p24h_i033_id <> p06h_i033_id", name="ck_amf_distinct_sources"),
    UniqueConstraint(
        "airline", "flt_nbr", "actdate", "sector_nbr", "amf_version", name="uq_amf_version"
    ),
    _partial_unique(
        "uq_amf_current_test", "airline", "flt_nbr", "actdate", "sector_nbr", where="is_current"
    ),
)

amf_line = Table(
    "scatdd_amf_line_test",
    metadata,
    _pk("amf_line_id"),
    Column("amf_id", BigInteger, ForeignKey(amf.c.amf_id, ondelete="CASCADE"), nullable=False),
    Column("line_type", String(4), nullable=False),
    Column("cabin", String(2), nullable=False),
    Column("source_class", String(3), nullable=False),
    Column("meal_type", String(2)),
    Column("pax_p06h", Integer),
    Column("spml_id", String(40)),
    Column("delta_qty", Integer),
    CheckConstraint("cabin IN ('P', 'J', 'YD', 'Y')"),
    CheckConstraint(
        "(line_type = 'PAX' AND pax_p06h IS NOT NULL AND spml_id IS NULL "
        "AND delta_qty IS NULL AND meal_type IS NULL) OR "
        "(line_type = 'SPML' AND spml_id IS NOT NULL AND delta_qty IS NOT NULL "
        "AND delta_qty <> 0 AND pax_p06h IS NULL)",
        name="ck_amf_line_shape",
    ),
    UniqueConstraint(
        "amf_id",
        "line_type",
        "source_class",
        "meal_type",
        "spml_id",
        name="uq_amf_line",
        postgresql_nulls_not_distinct=True,
    ),  # fmt: skip
)

error_type = Table(
    "scatdd_error_type_test",
    metadata,
    Column("error_code", String(50), primary_key=True),
    Column("description", Text, nullable=False),
    Column("severity", String(10), nullable=False),
    Column("blocks_release", Boolean, nullable=False, server_default=true()),
    Column("message_template", Text, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default=true()),
    CheckConstraint("severity IN ('ERROR', 'WARNING', 'INFO')"),
)

review_item = Table(
    "scatdd_review_item_test",
    metadata,
    _pk("review_item_id"),
    Column("error_code", String(50), ForeignKey(error_type.c.error_code), nullable=False),
    Column("email_id", BigInteger, ForeignKey(email.c.email_id)),
    Column("airline", String(3)),
    Column("flt_nbr", String(5)),
    Column("actdate", Date),
    Column("sector_nbr", SmallInteger),
    Column("status", CHAR(4)),
    Column("i033_id", BigInteger, ForeignKey(i033.c.i033_id)),
    Column("i034_id", BigInteger, ForeignKey(i034.c.i034_id)),
    Column("field_name", String(50)),
    Column("text_start", Integer),
    Column("text_end", Integer),
    Column("text_snippet", Text),
    Column("message", Text, nullable=False),
    Column("state", String(10), nullable=False, server_default="OPEN"),
    Column("resolution_type", String(15)),
    Column("resolution_remarks", Text),
    Column("resolved_by", String(50)),
    Column("resolved_at", _Ts),
    _now("created_at"),
    CheckConstraint("resolution_type IN ('AMENDED', 'ACCEPTED', 'REPROCESSED')"),
    CheckConstraint("email_id IS NOT NULL OR i033_id IS NOT NULL", name="ck_review_has_anchor"),
    CheckConstraint(
        "(state = 'OPEN' AND resolution_type IS NULL AND resolved_by IS NULL "
        "AND resolved_at IS NULL) OR "
        "(state = 'RESOLVED' AND resolution_type IS NOT NULL AND resolved_at IS NOT NULL) OR "
        "(state = 'DISMISSED' AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)",
        name="ck_review_closed_fields",
    ),
)

# --- Console tables, as in docs/scatdd_console_additions.sql ------------------------------

return_map = Table(
    "scatdd_return_sector_map_test",
    metadata,
    Column("airline", String(3), primary_key=True),
    Column("return_flt_nbr", String(5), primary_key=True),
    Column("outbound_flt_nbr", String(5), nullable=False),
    # Return flight date minus outbound flight date: 0 or 1.
    Column("day_offset", SmallInteger, nullable=False, server_default="0"),
    Column("is_active", Boolean, nullable=False, server_default=true()),
    Column("updated_by", String(100), nullable=False),
    _now("updated_at"),
    CheckConstraint("day_offset IN (0, 1)"),
    CheckConstraint("return_flt_nbr <> outbound_flt_nbr"),
)

sap_send = Table(
    "scatdd_sap_send_test",
    metadata,
    _pk("send_id"),
    Column("airline", String(3), nullable=False),
    Column("flt_nbr", String(5), nullable=False),
    Column("actdate", Date, nullable=False),
    Column("status", CHAR(4), nullable=False),
    Column("state", String(12), nullable=False),
    Column("release_mode", String(6), nullable=False),
    Column("decided_by", String(100), nullable=False),
    _now("decided_at"),
    Column("i033_file_name", String(100)),
    Column("i034_file_name", String(100)),
    Column("sent_at", _Ts),
    Column("failure_reason", Text),
    Column("dify_run_id", String(64)),
    CheckConstraint(_STATUS),
    CheckConstraint("state IN ('NOT_RELEASED', 'SENDING', 'SENT', 'FAILED')"),
    CheckConstraint("release_mode IN ('MANUAL', 'AUTO')"),
    # The "exactly one file" guard: a second send of the same unit fails here.
    UniqueConstraint("airline", "flt_nbr", "actdate", "status", name="uq_sap_send_unit_test"),
)

airline_config = Table(
    "scatdd_airline_config_test",
    metadata,
    Column("airline", String(3), primary_key=True),
    Column("auto_release", Boolean, nullable=False, server_default=false()),
    Column("auto_release_hold_min", Integer, nullable=False, server_default="60"),
    Column("updated_by", String(100), nullable=False),
    _now("updated_at"),
    CheckConstraint("auto_release_hold_min >= 0"),
)

# "Reviewed OK": a user confirmed one I033 version (and its I034 rows) without changing it.
# Keyed by version, so a newer version from a later email or an edit is unreviewed again.
i033_review = Table(
    "scatdd_i033_review_test",
    metadata,
    Column("i033_id", BigInteger, ForeignKey(i033.c.i033_id), primary_key=True),
    Column("reviewed_by", String(100), nullable=False),
    _now("reviewed_at"),
)
