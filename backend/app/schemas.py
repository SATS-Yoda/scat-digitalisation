"""Response models. These are the contract the frontend types are generated from."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["P24H", "P06H"]
Plant = Literal["ICC1", "ICC2"]
StageState = Literal["NO_DATA", "PENDING", "NOT_RELEASED", "SENDING", "SENT", "FAILED"]
ReviewState = Literal["NOT_REVIEWED", "REVIEWED_OK", "REVIEWED_AMENDED"]
Slot = Literal[
    "p", "jm", "ju", "jf", "ja", "sm", "su", "sf", "sa",
    "yu", "yf", "ya", "y", "staff_p", "staff_j", "staff_s", "staff_y",
]  # fmt: skip
_Edit = ConfigDict(str_strip_whitespace=True, extra="forbid")


class FlightRef(BaseModel):
    airline: str
    flt_nbr: str
    actdate: date


class StageSummary(BaseModel):
    status: Status
    state: StageState
    sectors: int
    review_state: ReviewState
    open_review_items: int
    blocking_review_items: int
    sent_at: datetime | None
    updated_at: datetime | None
    send_error: str | None


class ReturnFlightSummary(FlightRef):
    stages: list[StageSummary]


class FlightSummary(FlightRef):
    plant: Plant
    stages: list[StageSummary]
    return_flight: ReturnFlightSummary | None


class ClassCount(BaseModel):
    slot: str
    code: str | None
    pax: int | None


class I033(BaseModel):
    i033_id: int
    sector_nbr: int
    version_no: int
    is_current: bool
    created_source: str
    created_by: str
    created_at: datetime
    source_email_id: int | None
    is_ex_sector: bool
    sent_to_sap_at: datetime | None
    classes: list[ClassCount]


class I034(BaseModel):
    i034_id: int
    sector_nbr: int
    class_code: str
    meal_type: str | None
    spml_id: str
    qnty: int
    pname: str | None
    meal_nr: str | None
    txt: str | None


class VersionInfo(BaseModel):
    version_no: int
    is_current: bool
    created_source: str
    created_by: str
    created_at: datetime
    source_email_id: int | None


class SectorDetail(BaseModel):
    sector_nbr: int
    i033: I033
    i034: list[I034]
    versions: list[VersionInfo]


class ReviewItem(BaseModel):
    review_item_id: int
    error_code: str
    severity: str
    blocks_release: bool
    email_id: int | None
    sector_nbr: int | None
    i033_id: int | None
    i034_id: int | None
    field_name: str | None
    text_start: int | None
    text_end: int | None
    text_snippet: str | None
    message: str
    created_at: datetime


class SendInfo(BaseModel):
    send_id: int
    state: str
    release_mode: str | None
    decided_by: str
    decided_at: datetime
    i033_file_name: str | None
    i034_file_name: str | None
    sent_at: datetime | None
    failure_reason: str | None


class StageDetail(FlightRef):
    status: Status
    plant: Plant
    state: StageState
    locked: bool
    review_state: ReviewState
    return_flight_missing: bool
    sent_at: datetime | None
    return_of: FlightRef | None
    return_flight: FlightRef | None
    send: SendInfo | None
    sectors: list[SectorDetail]
    review_items: list[ReviewItem]


class VersionDetail(BaseModel):
    i033: I033
    i034: list[I034]


class AmfLine(BaseModel):
    amf_line_id: int
    line_type: str
    cabin: str
    source_class: str
    meal_type: str | None
    pax_p06h: int | None
    spml_id: str | None
    delta_qty: int | None


class Amf(BaseModel):
    amf_id: int
    sector_nbr: int
    amf_version: int
    p24h_i033_id: int
    p06h_i033_id: int
    generated_at: datetime
    lines: list[AmfLine]


class Email(BaseModel):
    email_id: int
    sender: str | None
    subject: str | None
    received_at: datetime
    airline: str | None
    detected_status: str | None
    confidence: Decimal | None
    pipeline_status: str
    rejection_reason: str | None
    body_preview: str | None


# --- Requests and results of the write side ---------------------------------------------


class ClassEdit(BaseModel):
    model_config = _Edit
    slot: Slot
    code: str | None = Field(None, max_length=3)
    pax: int | None = Field(None, ge=0)


class I034Edit(BaseModel):
    model_config = _Edit
    class_code: str = Field(min_length=1, max_length=3)
    meal_type: str | None = Field(None, max_length=2)
    spml_id: str = Field(min_length=1, max_length=40)
    qnty: int = Field(ge=0)
    pname: str | None = Field(None, max_length=40)
    meal_nr: str | None = Field(None, max_length=2)
    txt: str | None = Field(None, max_length=255)


class SectorEdit(BaseModel):
    """A save. Class slots left out keep their current value; `i034` replaces every special
    meal line of the sector."""

    model_config = _Edit
    base_version_no: int
    classes: list[ClassEdit] = []
    i034: list[I034Edit]


class SaveResult(BaseModel):
    version_no: int
    warnings: list[str]


class ResolveRequest(BaseModel):
    model_config = _Edit
    resolution_type: Literal["AMENDED", "ACCEPTED"]
    remarks: str | None = None

    @model_validator(mode="after")
    def accepted_needs_remarks(self):
        if self.resolution_type == "ACCEPTED" and not self.remarks:
            raise ValueError("Remarks are required when an item is accepted as extracted")
        return self


class SendResult(BaseModel):
    state: Literal["SENT", "FAILED"]
    failure_reason: str | None
    warnings: list[str]


# --- Admin ------------------------------------------------------------------------------


class ReturnFlightIn(BaseModel):
    model_config = _Edit
    outbound_flt_nbr: str = Field(pattern=r"^[A-Z0-9]{1,5}$")
    day_offset: Literal[0, 1]
    is_active: bool = True


class ReturnFlight(ReturnFlightIn):
    airline: str
    return_flt_nbr: str
    updated_by: str
    updated_at: datetime


class AirlineSettingIn(BaseModel):
    model_config = _Edit
    auto_release: bool
    auto_release_hold_min: int = Field(ge=0, le=1440)


class AirlineSetting(AirlineSettingIn):
    airline: str
    updated_by: str
    updated_at: datetime
