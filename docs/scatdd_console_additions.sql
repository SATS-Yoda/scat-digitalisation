-- Console additions for the scatdd_*_test tables (draft for review).
-- Additive only: three new tables. No existing table is touched, so the
-- extraction workflow keeps working unchanged.
-- Send unit = outbound flight + date + status (P24H / P06H). A return-sector
-- flight has no send row of its own; it travels in its outbound flight's files
-- (see scatdd_return_sector_map_test).

BEGIN;

-- Return-sector mapping: which return flight travels in which outbound
-- flight's files. Read by the console (grouping, release check) and by the
-- SAP-send workflow (which return rows to include). Maintained by an admin.
-- day_offset = return flight date minus outbound flight date,
-- e.g. SQ 856 on 9 Nov -> SQ 857 on 10 Nov is day_offset 1.
CREATE TABLE scatdd_return_sector_map_test (
    airline          varchar(3)  NOT NULL,
    return_flt_nbr   varchar(5)  NOT NULL,
    outbound_flt_nbr varchar(5)  NOT NULL,
    day_offset       smallint    NOT NULL DEFAULT 0 CHECK (day_offset IN (0, 1)),
    is_active        boolean     NOT NULL DEFAULT true,
    updated_by       varchar(100) NOT NULL,
    updated_at       timestamptz  NOT NULL DEFAULT now(),
    PRIMARY KEY (airline, return_flt_nbr),
    CHECK (return_flt_nbr <> outbound_flt_nbr)
);

-- One row per send unit, written by the console backend only.
-- The unique key is the "exactly one file" guard: the backend inserts the row
-- as SENDING before it calls the SAP-send workflow, so a second release of the
-- same unit fails on the constraint instead of producing a second file.
CREATE TABLE scatdd_sap_send_test (
    send_id        bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    airline        varchar(3)  NOT NULL,
    flt_nbr        varchar(5)  NOT NULL,
    actdate        date        NOT NULL,
    status         char(4)     NOT NULL CHECK (status IN ('P24H', 'P06H')),
    state          varchar(12) NOT NULL
                   CHECK (state IN ('NOT_RELEASED', 'SENDING', 'SENT', 'FAILED')),
    release_mode   varchar(6)  NOT NULL CHECK (release_mode IN ('MANUAL', 'AUTO')),
    decided_by     varchar(100) NOT NULL,   -- Entra object id, or 'auto-release'
    decided_at     timestamptz NOT NULL DEFAULT now(),
    i033_file_name varchar(100),
    i034_file_name varchar(100),
    sent_at        timestamptz,
    failure_reason text,
    dify_run_id    varchar(64),
    CONSTRAINT uq_sap_send_unit_test UNIQUE (airline, flt_nbr, actdate, status)
);

-- Per-airline auto-release switch. No row = manual release.
CREATE TABLE scatdd_airline_config_test (
    airline               varchar(3) PRIMARY KEY,
    auto_release          boolean  NOT NULL DEFAULT false,
    auto_release_hold_min integer  NOT NULL DEFAULT 60 CHECK (auto_release_hold_min >= 0),
    updated_by            varchar(100) NOT NULL,
    updated_at            timestamptz  NOT NULL DEFAULT now()
);

-- PROPOSED 2026-11-12 (not in the original draft): the "Reviewed OK" button.
-- One row per I033 version a user confirmed without changing it. Keyed by
-- version, so a newer version (later email or user edit) is unreviewed again.
CREATE TABLE scatdd_i033_review_test (
    i033_id     bigint PRIMARY KEY REFERENCES scatdd_i033_test (i033_id),
    reviewed_by varchar(100) NOT NULL,   -- Entra object id
    reviewed_at timestamptz  NOT NULL DEFAULT now()
);

COMMIT;
