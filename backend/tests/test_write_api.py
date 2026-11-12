import threading

from fastapi.testclient import TestClient

from app.api import create_app
from app.auth import User, current_user
from app.commands import amf_lines
from app.dify import SapSendResult

SQ856_P06H = "/api/flights/SQ/856/2026-11-13/stages/P06H"
TR508_P24H = "/api/flights/TR/508/2026-11-13/stages/P24H"
QR943_P24H = "/api/flights/QR/943/2026-11-13/stages/P24H"
SQ12_P24H = "/api/flights/SQ/12/2026-11-14/stages/P24H"


def meal(spml_id, qnty, class_code="Y", **extra):
    return {"class_code": class_code, "spml_id": spml_id, "qnty": qnty, **extra}


def save(client, stage_url, base, meals, classes=(), sector=1):
    return client.put(
        f"{stage_url}/sectors/{sector}",
        json={"base_version_no": base, "classes": list(classes), "i034": meals},
    )


def amf(client, flight):
    return client.get(f"/api/flights/{flight}/amf").json()


def summary(client, airline, flt_nbr, status):
    flights = client.get("/api/flights", params={"airline": airline}).json()
    flight = next(f for f in flights if f["flt_nbr"] == flt_nbr)
    return next(s for s in flight["stages"] if s["status"] == status)


# --- Save -------------------------------------------------------------------------------


def test_save_creates_a_new_current_version(client):
    response = save(
        client, SQ856_P06H, 2, [meal("VGML", 1)], [{"slot": "y", "code": "Y", "pax": 175}]
    )
    assert response.status_code == 200
    assert response.json() == {"version_no": 3, "warnings": []}

    detail = client.get(SQ856_P06H).json()
    [sector] = detail["sectors"]
    i033 = sector["i033"]
    assert (i033["version_no"], i033["created_source"], i033["created_by"]) == (
        3,
        "USER",
        "dev-user",
    )
    pax = {c["slot"]: c["pax"] for c in i033["classes"]}
    assert (pax["y"], pax["jf"], pax["p"]) == (175, 30, 4)  # untouched slots carry over
    assert [(m["spml_id"], m["qnty"]) for m in sector["i034"]] == [("VGML", 1)]
    assert [v["version_no"] for v in sector["versions"]] == [3, 2, 1]
    assert detail["review_state"] == "REVIEWED_AMENDED"

    # The replaced version stays readable.
    old = client.get(f"{SQ856_P06H}/sectors/1/versions/2").json()
    assert [(m["spml_id"], m["qnty"]) for m in old["i034"]] == [("VGML", 2), ("KSML", 1)]


def test_save_regenerates_the_amf(client):
    save(client, SQ856_P06H, 2, [meal("VGML", 1)], [{"slot": "y", "code": "Y", "pax": 175}])
    [form] = amf(client, "SQ/856/2026-11-13")
    assert (form["amf_version"], form["p24h_i033_id"], form["p06h_i033_id"]) == (3, 1, 11)
    lines = [(x["line_type"], x["cabin"], x["source_class"], x["pax_p06h"], x["spml_id"],
              x["delta_qty"]) for x in form["lines"]]  # fmt: skip
    assert lines == [
        ("PAX", "P", "P", 4, None, None),
        ("PAX", "J", "JF", 30, None, None),
        ("PAX", "Y", "Y", 175, None, None),
        ("SPML", "Y", "Y", None, "VGML", -2),
    ]


def test_sq_increase_at_p06h_warns_and_stays_off_the_amf(client):
    response = save(client, SQ856_P06H, 2, [meal("VGML", 5)])
    assert response.status_code == 200
    [warning] = response.json()["warnings"]
    assert "VGML" in warning and "above the P24H quantity of 3" in warning
    [form] = amf(client, "SQ/856/2026-11-13")
    assert [x for x in form["lines"] if x["line_type"] == "SPML"] == []


def test_other_airline_amf_shows_increases_and_reductions(client):
    assert amf(client, "TR/508/2026-11-13") == []
    response = save(client, "/api/flights/TR/508/2026-11-13/stages/P06H", 1,
                    [meal("VGML", 7), meal("CHML", 1)])  # fmt: skip
    assert response.json()["warnings"] == []
    [form] = amf(client, "TR/508/2026-11-13")
    assert form["amf_version"] == 1
    assert [(x["spml_id"], x["delta_qty"]) for x in form["lines"] if x["line_type"] == "SPML"] == [
        ("CHML", -1),
        ("VGML", 2),
    ]


def test_amf_lines_match_the_requirement_sample():
    # Requirement document, Appendix C (SQ 207): increases are ignored for SQ.
    p24h = {("JM", "R", "AVML"): 6, ("JM", "R", "VOML"): 1, ("JM", "L", "AVML"): 6,
            ("Y", "R", "AVML"): 18, ("Y", "R", "CHML"): 2, ("Y", "L", "AVML"): 18,
            ("Y", "L", "CHML"): 2}  # fmt: skip
    p06h = {("JM", "R", "AVML"): 5, ("JM", "R", "VOML"): 2, ("JM", "L", "AVML"): 5,
            ("Y", "R", "AVML"): 15, ("Y", "R", "CHML"): 5, ("Y", "L", "AVML"): 16,
            ("Y", "L", "CHML"): 1}  # fmt: skip
    row = {f"pax_{s}": None for s in ("p", "jm", "ju", "jf", "ja", "sm", "su", "sf", "sa",
                                       "yu", "yf", "ya", "y")}  # fmt: skip
    row.update(pax_jm=40, pax_sm=24, pax_y=173)
    lines = amf_lines("SQ", row, p24h, p06h)
    assert [(x["cabin"], x["pax_p06h"]) for x in lines if x["line_type"] == "PAX"] == [
        ("J", 40),
        ("YD", 24),
        ("Y", 173),
    ]
    spml = {(x["source_class"], x["meal_type"], x["spml_id"]): x["delta_qty"]
            for x in lines if x["line_type"] == "SPML"}  # fmt: skip
    assert spml == {
        ("JM", "R", "AVML"): -1,
        ("JM", "L", "AVML"): -1,
        ("Y", "R", "AVML"): -3,
        ("Y", "L", "AVML"): -2,
        ("Y", "L", "CHML"): -1,
    }


def test_save_on_a_stale_version_is_refused(client):
    response = save(client, SQ856_P06H, 1, [meal("VGML", 1)])
    assert response.status_code == 409
    assert "changed since it was opened" in response.json()["detail"]
    assert client.get(SQ856_P06H).json()["sectors"][0]["i033"]["version_no"] == 2


def test_sent_stage_cannot_be_edited(client):
    for flight in ("SQ/856/2026-11-13", "SQ/857/2026-11-14"):  # outbound and its return
        response = save(client, f"/api/flights/{flight}/stages/P24H", 1, [])
        assert response.status_code == 409
        assert "sent to SAP" in response.json()["detail"]


def test_invalid_edits_are_refused(client):
    assert save(client, SQ856_P06H, 2, [meal("VGML", 1), meal("VGML", 2)]).status_code == 422
    assert save(client, SQ856_P06H, 2, [meal("VGML", -1)]).status_code == 422
    assert save(client, SQ856_P06H, 2, [meal("VGML", 1, class_code="X")]).status_code == 422
    bad_slot = [{"slot": "zz", "code": "Z", "pax": 1}]
    assert save(client, SQ856_P06H, 2, [], bad_slot).status_code == 422
    assert save(client, "/api/flights/SQ/999/2026-11-13/stages/P24H", 1, []).status_code == 404
    assert client.get(SQ856_P06H).json()["sectors"][0]["i033"]["version_no"] == 2


def test_user_of_another_plant_is_refused(app, client):
    app.dependency_overrides[current_user] = lambda: User("icc2-user", frozenset({"ICC2"}))
    assert save(client, SQ856_P06H, 2, [meal("VGML", 1)]).status_code == 403
    assert client.post(f"{SQ12_P24H}/send").status_code == 403
    assert client.post(f"{SQ12_P24H}/review").status_code == 403
    assert save(client, QR943_P24H, 1, [meal("MOML", 9)], sector=2).status_code == 200


# --- Review -----------------------------------------------------------------------------


def test_reviewed_ok_then_amended(client):
    assert summary(client, "QR", "943", "P24H")["review_state"] == "NOT_REVIEWED"
    assert client.post(f"{QR943_P24H}/review").status_code == 204
    assert client.post(f"{QR943_P24H}/review").status_code == 204  # repeatable
    assert summary(client, "QR", "943", "P24H")["review_state"] == "REVIEWED_OK"
    assert client.get(QR943_P24H).json()["review_state"] == "REVIEWED_OK"

    save(client, QR943_P24H, 1, [meal("MOML", 9)], sector=2)
    assert summary(client, "QR", "943", "P24H")["review_state"] == "REVIEWED_AMENDED"


def test_resolving_a_review_item(client):
    url = "/api/review-items/2/resolve"
    assert client.post(url, json={"resolution_type": "ACCEPTED"}).status_code == 422
    assert client.post(url, json={"resolution_type": "REPROCESSED"}).status_code == 422
    assert client.post(url, json={"resolution_type": "AMENDED"}).status_code == 204
    assert summary(client, "QR", "943", "P24H")["blocking_review_items"] == 0
    assert client.post(url, json={"resolution_type": "AMENDED"}).status_code == 409
    missing = client.post("/api/review-items/99/resolve", json={"resolution_type": "AMENDED"})
    assert missing.status_code == 404


# --- Send -------------------------------------------------------------------------------


def test_blocking_review_item_stops_send_until_resolved(client, sender):
    response = client.post(f"{QR943_P24H}/send")
    assert response.status_code == 409
    assert "block sending" in response.json()["detail"]
    assert sender.calls == []

    resolve = {"resolution_type": "ACCEPTED", "remarks": "Total confirmed with the airline"}
    client.post("/api/review-items/2/resolve", json=resolve)
    response = client.post(f"{QR943_P24H}/send")
    assert response.json() == {"state": "SENT", "failure_reason": None, "warnings": []}
    assert sender.calls == [
        {"airline": "QR", "flt_nbr": "943", "actdate": "2026-11-13", "status": "P24H",
         "file_seq": 3, "send_i033": True, "send_i034": True}
    ]  # fmt: skip

    detail = client.get(QR943_P24H).json()
    assert (detail["state"], detail["locked"]) == ("SENT", True)
    assert detail["send"]["i034_file_name"] == "I034_SYNTHETIC.dat"
    assert detail["send"]["decided_by"] == "dev-user"

    # Sent is final: no second file, no edits.
    assert client.post(f"{QR943_P24H}/send").status_code == 409
    assert save(client, QR943_P24H, 1, [meal("MOML", 1)]).status_code == 409
    assert len(sender.calls) == 1


def test_return_flight_has_no_send_of_its_own(client, sender):
    response = client.post("/api/flights/SQ/857/2026-11-14/stages/P06H/send")
    assert response.status_code == 409
    assert "SQ 856" in response.json()["detail"]
    assert sender.calls == []


def test_missing_return_flight_warns_and_allows(client):
    assert client.get(SQ12_P24H).json()["return_flight_missing"] is True
    body = client.post(f"{SQ12_P24H}/send").json()
    assert body["state"] == "SENT"
    [warning] = body["warnings"]
    assert "SQ 11 on 2026-11-15" in warning


def test_failed_send_can_be_retried_and_skips_the_uploaded_file(client, sender):
    sender.result = SapSendResult(
        i033_uploaded=True, i033_file_name="I033_SYNTHETIC.dat", error="SFTP refused the I034 file"
    )
    body = client.post(f"{TR508_P24H}/send").json()
    assert body == {"state": "FAILED", "failure_reason": "SFTP refused the I034 file",
                    "warnings": []}  # fmt: skip
    assert summary(client, "TR", "508", "P24H")["state"] == "FAILED"
    assert save(client, TR508_P24H, 1, [meal("VGML", 4)]).status_code == 200  # still editable

    sender.result = SapSendResult(i034_uploaded=True, i034_file_name="I034_SYNTHETIC.dat")
    assert client.post(f"{TR508_P24H}/send").json()["state"] == "SENT"
    retry = sender.calls[1]
    # Same send row, so the same file number; the I033 file is not sent twice.
    assert (retry["file_seq"], retry["send_i033"], retry["send_i034"]) == (2, False, True)
    send = client.get(TR508_P24H).json()["send"]
    assert (send["i033_file_name"], send["failure_reason"]) == ("I033_SYNTHETIC.dat", None)


def test_not_released_can_still_be_sent_later(client):
    assert client.post(f"{SQ12_P24H}/not-released").status_code == 204
    assert summary(client, "SQ", "12", "P24H")["state"] == "NOT_RELEASED"
    assert client.post(f"{SQ12_P24H}/send").json()["state"] == "SENT"
    assert client.post(f"{SQ12_P24H}/not-released").status_code == 409


def test_send_is_refused_when_not_configured(engine):
    client = TestClient(create_app(engine, sap_sender=None))
    assert client.post(f"{SQ12_P24H}/send").status_code == 503
    assert summary(client, "SQ", "12", "P24H")["state"] == "PENDING"


def test_second_send_during_a_send_is_refused(client, sender):
    entered, release = threading.Event(), threading.Event()

    def hold():
        entered.set()
        assert release.wait(30)

    sender.before_return = hold
    first = {}
    thread = threading.Thread(
        target=lambda: first.update(response=client.post(f"{SQ12_P24H}/send"))
    )
    thread.start()
    assert entered.wait(30)
    try:
        assert summary(client, "SQ", "12", "P24H")["state"] == "SENDING"
        assert client.post(f"{SQ12_P24H}/send").status_code == 409
        assert save(client, SQ12_P24H, 1, []).status_code == 409
    finally:
        release.set()
        thread.join(30)
    assert first["response"].json()["state"] == "SENT"
    assert len(sender.calls) == 1
