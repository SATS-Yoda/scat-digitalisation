import httpx
import pytest

from app.dify import DifySapSender

INPUTS = {"airline": "ZZ", "flt_nbr": "1", "actdate": "2099-01-01", "status": "P24H",
          "file_seq": 1, "send_i033": True, "send_i034": True}  # fmt: skip


@pytest.fixture
def post(monkeypatch):
    """Replace the HTTP call; tests never reach a real Dify server."""
    seen = {}

    def install(answer):
        def fake_post(url, **kwargs):
            seen.update(url=url, **kwargs)
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(httpx, "post", fake_post)
        return seen

    return install


def send():
    return DifySapSender("https://dify.example/v1/", "synthetic-key")(INPUTS, "user-1")


def test_successful_run(post):
    outputs = {"i033_uploaded": True, "i033_file_name": "a.dat", "i034_uploaded": True,
               "i034_file_name": "b.dat", "error": ""}  # fmt: skip
    seen = post(httpx.Response(200, json={"data": {"id": "run-1", "status": "succeeded",
                                                   "outputs": outputs}}))  # fmt: skip
    result = send()
    assert (result.i033_uploaded, result.i034_file_name, result.error) == (True, "b.dat", "")
    assert result.run_id == "run-1"
    assert seen["url"] == "https://dify.example/v1/workflows/run"
    assert seen["json"] == {"inputs": INPUTS, "response_mode": "blocking", "user": "user-1"}
    assert seen["headers"] == {"Authorization": "Bearer synthetic-key"}


def test_failed_run_reports_the_workflow_error(post):
    data = {"id": "run-2", "status": "failed", "error": "node SFTP failed", "outputs": None}
    post(httpx.Response(200, json={"data": data}))
    result = send()
    assert (result.i033_uploaded, result.error) == (False, "node SFTP failed")


def test_http_error_timeout_and_unreadable_answer(post):
    post(httpx.Response(401, json={"message": "unauthorized"}))
    assert send().error == "SAP-send workflow returned HTTP 401"
    post(httpx.ReadTimeout("slow"))
    assert "may or may not have been uploaded" in send().error
    post(httpx.Response(200, json={"unexpected": True}))
    assert "could not be read" in send().error
    assert "synthetic-key" not in send().error
