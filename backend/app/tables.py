"""Table definitions the console reads.

The seven existing tables mirror docs/result_export.json and are owned by the Dify
workflows; the console never alters them. The export has columns only, so primary keys
here are assumed (HANDOVER.md, Open).

The three console tables at the bottom follow docs/scatdd_console_additions.sql.
"""

from sqlalchemy import (
    CHAR,
    JSON,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

# SQLite (local synthetic database only) autoincrements INTEGER keys, not BIGINT.
_Id = BigInteger().with_variant(Integer, "sqlite")
_Ts = DateTime(timezone=True)

# I033 holds one (class code, pax count) column pair per slot: `p` + `pax_p`, and so on.
CLASS_SLOTS = [
    "p", "jm", "ju", "jf", "ja", "sm", "su", "sf", "sa",
    "yu", "yf", "ya", "y", "staff_p", "staff_j", "staff_s", "staff_y",
]  # fmt: skip

email = Table(
    "scatdd_email_test",
    metadata,
    Column("email_id", _Id, primary_key=True),
    Column("message_id", Text),
    Column("eml_uri", Text, nullable=False),
    Column("text_uri", Text),
    Column("content_sha256", CHAR(64)),
    Column("sender", Text),
    Column("subject", Text),
    Column("received_at_raw", Text),
    Column("received_at", _Ts, nullable=False),
    Column("body_preview", Text),
    Column("airline", String),
    Column("detected_status", CHAR(4)),
    Column("confidence", Numeric),
    Column("pipeline_status", String, nullable=False),
    Column("rejection_reason", Text),
    Column("raw_record", JSON),
    Column("extracted_at", _Ts),
    Column("inserted_at", _Ts, nullable=False),
    Column("updated_at", _Ts, nullable=False),
)

i033 = Table(
    "scatdd_i033_test",
    metadata,
    Column("i033_id", _Id, primary_key=True),
    Column("record_type", String, nullable=False, default="10"),
    Column("airline", String, nullable=False),
    Column("flt_nbr", String, nullable=False),
    Column("actdate", Date, nullable=False),
    Column("sector_nbr", SmallInteger, nullable=False, default=1),
    Column("status", CHAR(4), nullable=False),
    *[c for s in CLASS_SLOTS for c in (Column(s, String), Column(f"pax_{s}", Integer))],
    Column("version_no", Integer, nullable=False, default=1),
    Column("is_current", Boolean, nullable=False, default=True),
    Column("created_source", String, nullable=False, default="SYSTEM"),
    Column("is_ex_sector", Boolean, nullable=False, default=False),
    Column("source_email_id", BigInteger),
    Column("created_by", String, nullable=False),
    Column("created_at", _Ts, nullable=False),
    Column("sent_to_sap_at", _Ts),
)

i034 = Table(
    "scatdd_i034_test",
    metadata,
    Column("i034_id", _Id, primary_key=True),
    Column("record_type", String, nullable=False, default="10"),
    Column("airln", String, nullable=False),
    Column("fltnr", String, nullable=False),
    Column("acdate", Date, nullable=False),
    Column("secnr", SmallInteger, nullable=False, default=1),
    Column("status", CHAR(4), nullable=False),
    Column("class", String, nullable=False),
    Column("meal_type", String),
    Column("spml_id", String, nullable=False),
    Column("qnty", Integer, nullable=False),
    Column("pname", String),
    Column("meal_nr", String),
    Column("txt", String),
    Column("version_no", Integer, nullable=False),
)

amf = Table(
    "scatdd_amf_test",
    metadata,
    Column("amf_id", _Id, primary_key=True),
    Column("airline", String, nullable=False),
    Column("flt_nbr", String, nullable=False),
    Column("actdate", Date, nullable=False),
    Column("sector_nbr", SmallInteger, nullable=False, default=1),
    Column("p24h_i033_id", BigInteger, nullable=False),
    Column("p06h_i033_id", BigInteger, nullable=False),
    Column("amf_version", Integer, nullable=False, default=1),
    Column("is_current", Boolean, nullable=False, default=True),
    Column("generated_at", _Ts, nullable=False),
)

amf_line = Table(
    "scatdd_amf_line_test",
    metadata,
    Column("amf_line_id", _Id, primary_key=True),
    Column("amf_id", BigInteger, nullable=False),
    Column("line_type", String, nullable=False),
    Column("cabin", String, nullable=False),
    Column("source_class", String, nullable=False),
    Column("meal_type", String),
    Column("pax_p06h", Integer),
    Column("spml_id", String),
    Column("delta_qty", Integer),
)

error_type = Table(
    "scatdd_error_type_test",
    metadata,
    Column("error_code", String, primary_key=True),
    Column("description", Text, nullable=False),
    Column("severity", String, nullable=False),
    Column("blocks_release", Boolean, nullable=False, default=True),
    Column("message_template", Text, nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
)

review_item = Table(
    "scatdd_review_item_test",
    metadata,
    Column("review_item_id", _Id, primary_key=True),
    Column("error_code", String, nullable=False),
    Column("email_id", BigInteger),
    Column("airline", String),
    Column("flt_nbr", String),
    Column("actdate", Date),
    Column("sector_nbr", SmallInteger),
    Column("status", CHAR(4)),
    Column("i033_id", BigInteger),
    Column("i034_id", BigInteger),
    Column("field_name", String),
    Column("text_start", Integer),
    Column("text_end", Integer),
    Column("text_snippet", Text),
    Column("message", Text, nullable=False),
    Column("state", String, nullable=False, default="OPEN"),
    Column("resolution_type", String),
    Column("resolution_remarks", Text),
    Column("resolved_by", String),
    Column("resolved_at", _Ts),
    Column("created_at", _Ts, nullable=False),
)

# --- Console tables, as in docs/scatdd_console_additions.sql ------------------------------

return_map = Table(
    "scatdd_return_sector_map_test",
    metadata,
    Column("airline", String(3), primary_key=True),
    Column("return_flt_nbr", String(5), primary_key=True),
    Column("outbound_flt_nbr", String(5), nullable=False),
    # Return flight date minus outbound flight date: 0 or 1.
    Column("day_offset", SmallInteger, nullable=False, default=0),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("updated_by", String(100), nullable=False),
    Column("updated_at", _Ts, nullable=False),
)

sap_send = Table(
    "scatdd_sap_send_test",
    metadata,
    Column("send_id", _Id, primary_key=True),
    Column("airline", String, nullable=False),
    Column("flt_nbr", String, nullable=False),
    Column("actdate", Date, nullable=False),
    Column("status", CHAR(4), nullable=False),
    Column("state", String(12), nullable=False),
    Column("release_mode", String(6), nullable=False),
    Column("decided_by", String(100), nullable=False),
    Column("decided_at", _Ts, nullable=False),
    Column("i033_file_name", String(100)),
    Column("i034_file_name", String(100)),
    Column("sent_at", _Ts),
    Column("failure_reason", Text),
    Column("dify_run_id", String(64)),
    UniqueConstraint("airline", "flt_nbr", "actdate", "status", name="uq_sap_send_unit_test"),
)

airline_config = Table(
    "scatdd_airline_config_test",
    metadata,
    Column("airline", String(3), primary_key=True),
    Column("auto_release", Boolean, nullable=False, default=False),
    Column("auto_release_hold_min", Integer, nullable=False, default=60),
    Column("updated_by", String(100), nullable=False),
    Column("updated_at", _Ts, nullable=False),
)
