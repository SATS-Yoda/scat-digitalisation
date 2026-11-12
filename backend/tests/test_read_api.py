def flights(client, **params):
    response = client.get("/api/flights", params=params)
    assert response.status_code == 200
    return {f"{f['airline']}{f['flt_nbr']}": f for f in response.json()}


def stage(flight, status):
    return next(s for s in flight["stages"] if s["status"] == status)


def test_ready(client):
    assert client.get("/ready").json() == {"status": "ready"}


def test_return_flights_are_nested_not_listed(client):
    result = flights(client)
    assert list(result) == ["QR943", "SQ856", "TR508", "SQ12"]  # date, then airline
    assert result["SQ856"]["return_flight"]["flt_nbr"] == "857"
    assert result["SQ856"]["return_flight"]["actdate"] == "2026-11-14"
    assert result["TR508"]["return_flight"] is None


def test_stage_states(client):
    result = flights(client)
    assert stage(result["SQ856"], "P24H")["state"] == "SENT"
    assert stage(result["SQ856"], "P06H")["state"] == "PENDING"
    assert stage(result["QR943"], "P06H")["state"] == "NO_DATA"
    failed = stage(result["TR508"], "P24H")
    assert failed["state"] == "FAILED"
    assert failed["send_error"] == "SFTP upload timed out after 3 attempts"


def test_return_flight_follows_outbound_send(client):
    ret = flights(client)["SQ856"]["return_flight"]
    assert stage(ret, "P24H")["state"] == "SENT"
    assert stage(ret, "P06H")["state"] == "PENDING"


def test_missing_return_flight_is_shown_without_data(client):
    ret = flights(client)["SQ12"]["return_flight"]
    assert (ret["flt_nbr"], ret["actdate"]) == ("11", "2026-11-15")
    assert [s["state"] for s in ret["stages"]] == ["NO_DATA", "NO_DATA"]


def test_review_counts_only_open_items(client):
    result = flights(client)
    blocked = stage(result["QR943"], "P24H")
    assert (blocked["open_review_items"], blocked["blocking_review_items"]) == (1, 1)
    assert blocked["sectors"] == 2
    warned = stage(result["SQ856"], "P06H")
    assert (warned["open_review_items"], warned["blocking_review_items"]) == (1, 0)
    assert stage(result["SQ12"], "P24H")["open_review_items"] == 0


def test_date_filter_applies_to_outbound_and_keeps_return(client):
    result = flights(client, date_from="2026-11-13", date_to="2026-11-13")
    assert set(result) == {"QR943", "SQ856", "TR508"}
    assert stage(result["SQ856"]["return_flight"], "P24H")["state"] == "SENT"
    assert set(flights(client, date_from="2026-11-14")) == {"SQ12"}


def test_plant_and_airline_filters(client):
    assert set(flights(client, plant="ICC1")) == {"SQ856", "SQ12"}
    assert set(flights(client, plant="ICC2")) == {"QR943", "TR508"}
    assert set(flights(client, airline="QR")) == {"QR943"}
    assert client.get("/api/flights", params={"plant": "ICC9"}).status_code == 422


def test_stage_detail_uses_current_version(client):
    detail = client.get("/api/flights/SQ/856/2026-11-13/stages/P06H").json()
    assert (detail["state"], detail["locked"], detail["plant"]) == ("PENDING", False, "ICC1")
    assert detail["return_flight"] == {"airline": "SQ", "flt_nbr": "857", "actdate": "2026-11-14"}
    [sector] = detail["sectors"]
    assert sector["i033"]["version_no"] == 2
    assert sector["i033"]["created_source"] == "USER"
    pax = {c["slot"]: c["pax"] for c in sector["i033"]["classes"]}
    assert (pax["y"], pax["jf"], pax["sm"]) == (178, 30, None)
    assert [(m["spml_id"], m["qnty"]) for m in sector["i034"]] == [("VGML", 2), ("KSML", 1)]
    assert [v["version_no"] for v in sector["versions"]] == [2, 1]
    assert [r["error_code"] for r in detail["review_items"]] == ["LOW_CONFIDENCE"]


def test_sent_stage_is_locked(client):
    detail = client.get("/api/flights/SQ/856/2026-11-13/stages/P24H").json()
    assert (detail["state"], detail["locked"]) == ("SENT", True)
    assert detail["send"]["state"] == "SENT"
    assert detail["send"]["i034_file_name"] == "I034_SYNTHETIC_1.dat"
    assert detail["sent_at"] is not None


def test_return_stage_detail_points_at_outbound(client):
    detail = client.get("/api/flights/SQ/857/2026-11-14/stages/P24H").json()
    assert detail["return_of"] == {"airline": "SQ", "flt_nbr": "856", "actdate": "2026-11-13"}
    assert detail["send"]["send_id"] == 1
    assert detail["locked"] is True


def test_stage_detail_splits_sectors(client):
    detail = client.get("/api/flights/QR/943/2026-11-13/stages/P24H").json()
    assert [(s["sector_nbr"], s["i034"][0]["qnty"]) for s in detail["sectors"]] == [(1, 12), (2, 8)]
    assert detail["review_items"][0]["blocks_release"] is True


def test_stage_not_found(client):
    response = client.get("/api/flights/SQ/999/2026-11-13/stages/P24H")
    assert response.status_code == 404
    assert client.get("/api/flights/SQ/856/2026-11-13/stages/P12H").status_code == 422


def test_old_version_is_readable(client):
    url = "/api/flights/SQ/856/2026-11-13/stages/P06H/sectors/1/versions/"
    old = client.get(url + "1").json()
    assert old["i033"]["is_current"] is False
    assert [(m["spml_id"], m["qnty"]) for m in old["i034"]] == [("VGML", 3)]
    assert client.get(url + "9").status_code == 404


def test_amf(client):
    [amf] = client.get("/api/flights/SQ/856/2026-11-13/amf").json()
    assert (amf["amf_version"], amf["p06h_i033_id"]) == (2, 4)
    assert [(x["cabin"], x["pax_p06h"], x["delta_qty"]) for x in amf["lines"]] == [
        ("P", 4, None),
        ("J", 30, None),
        ("Y", 178, None),
        ("Y", None, -1),
    ]
    assert client.get("/api/flights/TR/508/2026-11-13/amf").json() == []


def test_email(client):
    email = client.get("/api/emails/2").json()
    assert email["subject"] == "SQ856-13NOV-FINAL"
    assert "raw_record" not in email
    assert client.get("/api/emails/99").status_code == 404


def test_audit_trail_lists_who_did_what_newest_first(client):
    events = client.get("/api/audit").json()
    assert events
    assert [e["at"] for e in events] == sorted((e["at"] for e in events), reverse=True)
    actions = {e["action"] for e in events}
    assert {"EXTRACTED", "SENT"} <= actions
    sent = next(e for e in events if e["action"] == "SENT")
    assert sent["actor"] and (sent["airline"], sent["flt_nbr"]) == ("SQ", "856")


def test_audit_trail_filters_and_limits(client):
    qr = client.get("/api/audit", params={"airline": "QR"}).json()
    assert qr and {e["airline"] for e in qr} == {"QR"}
    assert len(client.get("/api/audit", params={"limit": 2}).json()) == 2
    assert client.get("/api/audit", params={"limit": 501}).status_code == 422
    assert client.get("/api/audit", params={"date_from": "2030-01-01"}).json() == []
