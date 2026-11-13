"""Client for the Dify SAP-send workflow, which builds the I033 and I034 files and uploads
them to the SFTP server. The API key stays in this process."""

import httpx
from pydantic import BaseModel, ValidationError


class SapSendResult(BaseModel):
    """Workflow output. The shape is the one proposed in docs/HANDOVER.md; the workflow
    owner has not confirmed it yet."""

    i033_uploaded: bool = False
    i033_file_name: str | None = None
    i034_uploaded: bool = False
    i034_file_name: str | None = None
    error: str = ""
    run_id: str | None = None


class DifySapSender:
    def __init__(self, base_url: str, api_key: str, timeout_s: float = 120):
        self._url = base_url.rstrip("/") + "/workflows/run"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = timeout_s

    def __call__(self, inputs: dict, user_id: str) -> SapSendResult:
        """Run the workflow in blocking mode. Never raises: an unreachable or failing
        workflow comes back as a result with `error` set, so the send row always gets a
        final state."""
        try:
            response = httpx.post(
                self._url,
                headers=self._headers,
                json={"inputs": inputs, "response_mode": "blocking", "user": user_id},
                timeout=self._timeout,
            )
        except httpx.TimeoutException:
            return SapSendResult(
                error=f"No answer from the SAP-send workflow within {self._timeout:.0f} s; "
                "the files may or may not have been uploaded"
            )
        except httpx.HTTPError as exc:
            return SapSendResult(
                error=f"SAP-send workflow could not be reached ({type(exc).__name__})"
            )
        if response.status_code != 200:
            return SapSendResult(error=f"SAP-send workflow returned HTTP {response.status_code}")
        try:
            data = response.json()["data"]
            result = SapSendResult.model_validate(data.get("outputs") or {})
        except (ValueError, KeyError, TypeError, ValidationError):
            return SapSendResult(
                error="SAP-send workflow returned an answer that could not be read"
            )
        result.run_id = data.get("id")
        if data.get("status") != "succeeded" and not result.error:
            result.error = str(data.get("error") or f"Workflow run {data.get('status')}")
        return result
