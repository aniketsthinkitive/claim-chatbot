# Fix Validation Display + Waystar Submission Response — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the broken validation result display in the chatbot and enable the claim-validator library's clearinghouse phase so Waystar submission responses flow through to the UI.

**Architecture:** The chatbot is a thin UI layer — it collects claim data and displays results. All validation and submission logic lives in the claim-validator library (`validate()` with `clearinghouse_config`). The chatbot passes collected fields to the library, gets back a `PipelineResult`, and renders it.

**Tech Stack:** Python/FastAPI (backend), claim-validator library, vanilla JS (frontend), WebSockets

---

## Task 1: Fix broken test imports in test_validator.py

The test file imports `ClaimValidator` which was renamed to `LibraryClaimValidator`. Tests cannot run at all.

**Files:**
- Modify: `tests/test_validator.py:1`

**Step 1: Fix the import and class references**

Change line 1 from:
```python
from app.validation.validator import ClaimValidator, ValidationResult
```
to:
```python
from app.validation.validator import create_validator, ValidationResult
```

Change `test_validator_validate_returns_result` and `test_validator_validate_with_documents` to use `create_validator()` instead of `ClaimValidator()`:
```python
def test_validator_validate_returns_result():
    validator = create_validator()
    result = validator.validate({...})
    ...

def test_validator_validate_with_documents():
    validator = create_validator()
    result = validator.validate({...})
    ...
```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_validator.py -v`
Expected: All 4 tests PASS

**Step 3: Commit**

```bash
git add tests/test_validator.py
git commit -m "fix: update test_validator imports for refactored validator classes"
```

---

## Task 2: Add clearinghouse config to app/config.py

The chatbot needs to pass Waystar credentials through to the claim-validator library. Add env vars.

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_config.py`

**Step 1: Write the failing test**

Add to `tests/test_config.py`:
```python
def test_clearinghouse_config_defaults():
    from app.config import Settings
    s = Settings()
    assert s.clearinghouse_provider == ""
    assert s.waystar_api_key == ""

def test_clearinghouse_config_dict_empty_when_no_provider():
    from app.config import Settings
    s = Settings()
    assert s.clearinghouse_config is None

def test_clearinghouse_config_dict_with_provider(monkeypatch):
    monkeypatch.setenv("CLEARINGHOUSE_PROVIDER", "waystar")
    monkeypatch.setenv("WAYSTAR_API_KEY", "test-key")
    from app.config import Settings
    s = Settings()
    cfg = s.clearinghouse_config
    assert cfg is not None
    assert cfg["provider"] == "waystar"
    assert cfg["api_key"] == "test-key"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py::test_clearinghouse_config_defaults -v`
Expected: FAIL — `Settings` has no `clearinghouse_provider`

**Step 3: Add clearinghouse fields to Settings**

In `app/config.py`, add after `upload_dir`:
```python
    # Clearinghouse config (passed through to claim-validator library)
    clearinghouse_provider: str = os.getenv("CLEARINGHOUSE_PROVIDER", "")
    waystar_api_key: str = os.getenv("WAYSTAR_API_KEY", "")
    waystar_secret: str = os.getenv("WAYSTAR_SECRET", "")
    waystar_user_id: str = os.getenv("WAYSTAR_USER_ID", "")
    waystar_password: str = os.getenv("WAYSTAR_PASSWORD", "")
    waystar_cust_id: str = os.getenv("WAYSTAR_CUST_ID", "")

    @property
    def clearinghouse_config(self) -> dict | None:
        """Build clearinghouse config dict for claim-validator, or None if not configured."""
        if not self.clearinghouse_provider:
            return None
        return {
            "provider": self.clearinghouse_provider,
            "api_key": self.waystar_api_key,
            "secret": self.waystar_secret,
            "user_id": self.waystar_user_id,
            "password": self.waystar_password,
            "cust_id": self.waystar_cust_id,
        }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_config.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: add clearinghouse config settings for Waystar credentials"
```

---

## Task 3: Simplify validator.py — use library directly

The current `validator.py` has custom `LibraryClaimValidator` and `APIClaimValidator` wrappers with their own `ValidationResult` model. This duplicates what the library already provides. Simplify to call `claim_validator.validate()` directly and pass through the library's `PipelineResult`.

**Files:**
- Modify: `app/validation/validator.py`
- Modify: `tests/test_validator.py`

**Step 1: Write the failing test**

Replace `tests/test_validator.py` entirely:
```python
from unittest.mock import patch
from app.validation.validator import validate_claim


def test_validate_claim_returns_dict():
    """validate_claim() returns a dict with status, passed, findings keys."""
    result = validate_claim({
        "billing_provider_npi": "1245319599",
        "subscriber_id": "XYZ123",
        "subscriber_first_name": "John",
        "subscriber_last_name": "Doe",
        "subscriber_dob": "1985-03-15",
        "patient_first_name": "John",
        "patient_last_name": "Doe",
        "patient_dob": "1985-03-15",
        "patient_gender": "M",
        "patient_relationship": "self",
        "payer_id": "00001",
        "claim_type": "professional",
        "place_of_service": "11",
        "total_charge": 150.00,
        "diagnosis_codes": [{"code": "J06.9", "pointer": 1, "type": "principal"}],
        "lines": [{"procedure_code": "99213", "charge_amount": 150.00, "units": 1.0,
                    "service_date_from": "2026-03-01", "diagnosis_pointers": [1],
                    "place_of_service": "11"}],
    })
    assert isinstance(result, dict)
    assert "status" in result
    assert "passed" in result
    assert "findings" in result
    assert "phase_results" in result
    assert result["status"] in ("pass", "fail", "needs_review")


def test_validate_claim_missing_fields():
    """Incomplete payload produces error findings."""
    result = validate_claim({
        "subscriber_first_name": "Jane",
        "billing_provider_npi": "bad",
    })
    assert result["status"] in ("fail", "needs_review")
    assert len(result["findings"]) > 0


def test_validate_claim_fallback_on_import_error():
    """If claim_validator library is unavailable, fallback validation runs."""
    with patch("app.validation.validator._library_available", False):
        result = validate_claim({
            "billing_provider_npi": "1245319599",
            "subscriber_id": "XYZ123",
            "diagnosis_codes": [{"code": "J06.9"}],
            "lines": [{"procedure_code": "99213"}],
        })
    assert isinstance(result, dict)
    assert result["status"] in ("pass", "fail", "needs_review")
    assert result.get("fallback") is True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_validator.py -v`
Expected: FAIL — `validate_claim` does not exist

**Step 3: Rewrite validator.py**

Replace `app/validation/validator.py` with:
```python
"""Claim validation — thin wrapper around claim-validator library."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Check if claim-validator library is available
_library_available = False
try:
    from claim_validator import validate as _cv_validate
    _library_available = True
except ImportError:
    logger.warning("claim-validator library not installed, using fallback validation")


def validate_claim(payload: dict, *, clearinghouse_config: dict | None = None) -> dict:
    """Validate a claim payload and return results as a plain dict.

    Uses the claim-validator library if available, otherwise falls back
    to basic field checks. The chatbot treats the return value as opaque
    data to display in the frontend.

    Args:
        payload: Claim data from session.build_claim_payload().
        clearinghouse_config: Optional clearinghouse settings passed
            through to the library (enables Waystar submission phase).

    Returns:
        Dict with keys: status, passed, findings, phase_results,
        execution_time, and optionally fallback.
    """
    if not _library_available:
        logger.info("Using fallback validation (library unavailable)")
        return _fallback_validate(payload)

    try:
        kwargs: dict[str, Any] = {}
        if clearinghouse_config:
            kwargs["clearinghouse_config"] = clearinghouse_config
        result = _cv_validate(payload, **kwargs)

        findings = []
        for f in result.findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            findings.append({
                "code": f.code,
                "message": f.message,
                "severity": sev,
                "field_name": getattr(f, "field_name", None) or "",
                "suggestion": getattr(f, "suggestion", None) or "",
            })

        errors = [f for f in findings if f["severity"] == "error"]
        warnings = [f for f in findings if f["severity"] == "warning"]

        if result.passed:
            status = "pass"
        elif len(errors) <= 3:
            status = "needs_review"
        else:
            status = "fail"

        return {
            "status": status,
            "passed": result.passed,
            "findings": findings,
            "total_findings": len(findings),
            "total_errors": len(errors),
            "total_warnings": len(warnings),
            "execution_time": result.execution_time,
            "phase_results": [
                {
                    "phase": pr.phase,
                    "findings_count": len(pr.findings),
                    "execution_time": pr.execution_time,
                }
                for pr in result.phase_results
            ],
        }
    except Exception as e:
        logger.error("Validator error, using fallback: %s", e, exc_info=True)
        return _fallback_validate(payload)


def _fallback_validate(payload: dict) -> dict:
    """Basic field checks when claim-validator library is unavailable."""
    issues = []
    npi = payload.get("billing_provider_npi", "")
    if not npi or len(str(npi)) != 10:
        issues.append({
            "code": "BASIC_INVALID_NPI",
            "message": f"Invalid NPI: must be exactly 10 digits (got '{npi}')",
            "severity": "error",
            "field_name": "billing_provider_npi",
            "suggestion": "Provide a valid 10-digit NPI number",
        })
    if not payload.get("subscriber_id"):
        issues.append({
            "code": "BASIC_MISSING_SUBSCRIBER_ID",
            "message": "Missing subscriber/member ID",
            "severity": "error",
            "field_name": "subscriber_id",
            "suggestion": "Provide the subscriber's member ID",
        })
    if not payload.get("diagnosis_codes"):
        issues.append({
            "code": "BASIC_MISSING_DIAGNOSIS",
            "message": "At least one diagnosis code is required",
            "severity": "error",
            "field_name": "diagnosis_codes",
            "suggestion": "Add at least one ICD-10 diagnosis code",
        })
    if not payload.get("lines"):
        issues.append({
            "code": "BASIC_MISSING_LINES",
            "message": "At least one service line is required",
            "severity": "error",
            "field_name": "lines",
            "suggestion": "Add at least one service line with CPT code",
        })

    errors = [f for f in issues if f["severity"] == "error"]
    status = "pass" if not errors else ("needs_review" if len(errors) <= 3 else "fail")

    return {
        "status": status,
        "passed": len(errors) == 0,
        "findings": issues,
        "total_findings": len(issues),
        "total_errors": len(errors),
        "total_warnings": 0,
        "execution_time": 0.0,
        "phase_results": [{"phase": "fallback", "findings_count": len(issues), "execution_time": 0.0}],
        "fallback": True,
    }
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validator.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add app/validation/validator.py tests/test_validator.py
git commit -m "refactor: simplify validator to thin wrapper around claim-validator library"
```

---

## Task 4: Update controller.py to use new validate_claim()

The controller imports `create_validator` and `_fallback_validate`. Update it to use the new `validate_claim()` function.

**Files:**
- Modify: `app/chat/controller.py`
- Modify: `tests/test_controller.py`

**Step 1: Update the controller**

In `app/chat/controller.py`:

Change line 9 import from:
```python
from app.validation.validator import create_validator, _fallback_validate
```
to:
```python
from app.validation.validator import validate_claim
from app.config import settings
```

Remove `self.validator = create_validator()` from `__init__` (line 17).

Replace `_build_summary` method (lines 193-210) with:
```python
    def _build_summary(self, session: ClaimSession, preceding_message: str) -> dict:
        """Build and return the validation result for the frontend."""
        session.status = "confirming"
        payload = session.build_claim_payload()

        result = validate_claim(payload, clearinghouse_config=settings.clearinghouse_config)
        session.validation_result = result

        return {
            "type": "validation_result",
            "content": preceding_message,
            "result": result,
            "claim_payload": payload,
        }
```

**Step 2: Run controller tests**

Run: `python -m pytest tests/test_controller.py -v`
Expected: All tests PASS (the mock structure means validation is called on complete payloads)

**Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add app/chat/controller.py
git commit -m "refactor: use validate_claim() in controller, pass clearinghouse config"
```

---

## Task 5: Fix frontend validation result display

The `addValidationResult()` function in `chat.js` already handles the display. But we need to verify it matches the new dict shape from `validate_claim()`. The key fields are: `status`, `findings` (array of `{code, message, severity, field_name, suggestion}`), `total_findings`, `total_errors`, `total_warnings`, `execution_time`, `phase_results`.

Also add a section to show clearinghouse phase info when present.

**Files:**
- Modify: `app/static/chat.js`
- Modify: `app/static/style.css`

**Step 1: Update addValidationResult in chat.js**

The current function already handles `status`, `findings`, `total_findings`, `total_errors`, `total_warnings`, `execution_time`, and `recommendations`. The new dict shape drops `recommendations` and `issues` (replaced by `findings`). Update:

After the findings section (after line 106 `html += '</div>';`), add phase results section:
```javascript
    // Phase results (shows which pipeline phases ran)
    if (result.phase_results && result.phase_results.length > 0) {
        html += '<div class="validation-phases">';
        result.phase_results.forEach(function (pr) {
            var phaseLabel = pr.phase === "rule_based" ? "Rule-Based" :
                pr.phase === "clearinghouse" ? "Clearinghouse" :
                pr.phase === "ai" ? "AI Analysis" :
                pr.phase === "fallback" ? "Basic Checks" : pr.phase;
            html += '<span class="phase-badge">' + escapeHtml(phaseLabel) +
                ' (' + pr.findings_count + ')</span>';
        });
        html += '</div>';
    }
```

Also update the recommendations section (lines 109-115) to handle when `recommendations` is missing:
```javascript
    // Recommendations (if present)
    if (result.recommendations && result.recommendations.length > 0) {
        html += '<div><strong>Recommendations:</strong><ul class="validation-recommendations">';
        result.recommendations.forEach(function (rec) {
            html += "<li>" + escapeHtml(rec) + "</li>";
        });
        html += "</ul></div>";
    }
```

**Step 2: Add CSS for phase badges**

Add to `app/static/style.css`:
```css
.validation-phases {
    margin: 8px 0;
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}
.phase-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.75em;
    background: #e8eaf6;
    color: #3949ab;
}
```

**Step 3: Test manually**

1. Start the chatbot: `uvicorn app.main:app --reload`
2. Fill in all claim fields via chat
3. Verify validation result displays with status, findings, and phase badges
4. Check browser console for any JS errors

**Step 4: Commit**

```bash
git add app/static/chat.js app/static/style.css
git commit -m "feat: update frontend to display full pipeline result with phase badges"
```

---

## Task 6: Implement WaystarClient.submit_claim() in claim-validator library

The `submit_claim()` method is a placeholder. Implement it using the Waystar claim submission endpoint. This enables `BasePipeline`'s Phase 2 clearinghouse step for the "claim" domain.

**Files:**
- Modify: `/home/lnv-20/Documents/claim-validator/claim-validator/src/claim_validator/clearinghouse/providers/waystar.py:163-183`
- Test: `/home/lnv-20/Documents/claim-validator/claim-validator/tests/test_waystar_submit.py` (new)

**Step 1: Write the failing test**

Create `/home/lnv-20/Documents/claim-validator/claim-validator/tests/test_waystar_submit.py`:
```python
import pytest
from unittest.mock import MagicMock, patch
from claim_validator.clearinghouse.providers.waystar import WaystarClient
from claim_validator.clearinghouse.models import SubmissionResult


@pytest.fixture
def client():
    return WaystarClient(
        api_key="test-key",
        secret="test-secret",
        user_id="test-user",
        password="test-pass",
        cust_id="12345",
    )


def test_submit_claim_returns_submission_result(client):
    """submit_claim() should return a SubmissionResult, not raise."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Status": "Accepted",
        "ReferenceId": "REF-001",
        "ErrorMessage": "",
    }
    mock_response.text = '{"Status": "Accepted"}'
    mock_response.headers = {"content-type": "application/json"}

    with patch.object(client, "_post_json_with_retry", return_value=mock_response):
        result = client.submit_claim({
            "billing_provider_npi": "1245319599",
            "subscriber_id": "XYZ123",
            "payer_id": "00001",
            "claim_type": "professional",
            "diagnosis_codes": [{"code": "J06.9"}],
            "lines": [{"procedure_code": "99213", "charge_amount": 150.0}],
        })

    assert isinstance(result, SubmissionResult)
    assert result.accepted is True
    assert result.reference_id == "REF-001"


def test_submit_claim_handles_rejection(client):
    """submit_claim() handles rejection response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "Status": "Rejected",
        "ReferenceId": "",
        "ErrorMessage": "Invalid payer ID",
    }
    mock_response.text = '{"Status": "Rejected"}'
    mock_response.headers = {"content-type": "application/json"}

    with patch.object(client, "_post_json_with_retry", return_value=mock_response):
        result = client.submit_claim({"billing_provider_npi": "1234567890"})

    assert isinstance(result, SubmissionResult)
    assert result.accepted is False
    assert "Invalid payer ID" in result.errors
```

**Step 2: Run test to verify it fails**

Run: `cd /home/lnv-20/Documents/claim-validator/claim-validator && python -m pytest tests/test_waystar_submit.py -v`
Expected: FAIL — `submit_claim()` raises `ClearinghouseError`

**Step 3: Implement submit_claim()**

In `waystar.py`, replace the `submit_claim` method (lines 163-183) with:
```python
    def submit_claim(self, claim_data: dict[str, Any]) -> SubmissionResult:
        """Submit a claim to Waystar.

        Uses the Waystar claims submission endpoint with JSON body
        and UserID/Password authentication (same pattern as prior auth).

        Args:
            claim_data: Claim data dictionary (ClaimData-compatible fields).

        Returns:
            SubmissionResult with acceptance status and reference ID.
        """
        url = f"{self._claims_base_url}/2.0/v1/Claims/Submit"
        json_body: dict[str, Any] = {
            "UserID": self._user_id,
            "Password": self._password,
            "CustID": self._cust_id,
            "ClaimData": claim_data,
        }
        response = self._post_json_with_retry(url, json_body)
        self._handle_response(response)
        return self._parse_submission_response(response)

    def _parse_submission_response(self, response: httpx.Response) -> SubmissionResult:
        """Parse Waystar claim submission response."""
        try:
            data = response.json()
        except Exception:
            return SubmissionResult(
                status="unknown",
                accepted=False,
                raw_response={"raw_text": response.text},
                errors=["Could not parse submission response"],
            )

        status = data.get("Status", data.get("status", "unknown"))
        accepted = str(status).lower() in ("accepted", "received", "queued")
        ref_id = data.get("ReferenceId", data.get("referenceId"))
        error_msg = data.get("ErrorMessage", data.get("errorMessage", ""))
        errors = [error_msg] if error_msg else []

        return SubmissionResult(
            status=str(status),
            accepted=accepted,
            reference_id=str(ref_id) if ref_id else None,
            raw_response=data,
            errors=errors,
        )
```

**Step 4: Run tests to verify they pass**

Run: `cd /home/lnv-20/Documents/claim-validator/claim-validator && python -m pytest tests/test_waystar_submit.py -v`
Expected: Both tests PASS

**Step 5: Run existing waystar tests to check no regressions**

Run: `cd /home/lnv-20/Documents/claim-validator/claim-validator && python -m pytest tests/ -k waystar -v`
Expected: All PASS

**Step 6: Commit**

```bash
cd /home/lnv-20/Documents/claim-validator/claim-validator
git add src/claim_validator/clearinghouse/providers/waystar.py tests/test_waystar_submit.py
git commit -m "feat: implement WaystarClient.submit_claim() for claim submission"
```

---

## Task 7: End-to-end integration test

Verify the full chatbot flow: fields collected → validate_claim() called with clearinghouse_config → result displayed.

**Files:**
- Modify: `tests/test_controller.py`

**Step 1: Add integration test**

Add to `tests/test_controller.py`:
```python
@pytest.mark.asyncio
async def test_build_summary_returns_validation_result():
    """_build_summary returns validation_result type with result dict."""
    session = ClaimSession(session_id="test-summary")
    all_fields = {
        "subscriber_first_name": "John", "subscriber_last_name": "Doe",
        "subscriber_dob": "1985-03-15", "subscriber_gender": "M",
        "subscriber_id": "XYZ123",
        "patient_relationship": "self",
        "patient_first_name": "John", "patient_last_name": "Doe",
        "patient_dob": "1985-03-15", "patient_gender": "M",
        "payer_name": "Aetna", "payer_id": "00001",
        "billing_provider_npi": "1245319599",
        "billing_provider_taxonomy": "207Q00000X",
        "claim_type": "professional", "place_of_service": "11",
        "total_charge": 150.00,
        "diagnosis_codes": [{"code": "J06.9", "pointer": 1, "type": "principal"}],
        "service_lines": [{"procedure_code": "99213", "charge_amount": 150.00,
                           "units": 1.0, "service_date_from": "2026-03-01",
                           "diagnosis_pointers": [1], "place_of_service": "11"}],
    }
    for field, value in all_fields.items():
        session.update_field(field, value)

    controller = ChatController(openai_api_key="test-key")
    result = controller._build_summary(session, "Here is your summary.")

    assert result["type"] == "validation_result"
    assert result["content"] == "Here is your summary."
    assert isinstance(result["result"], dict)
    assert "status" in result["result"]
    assert "findings" in result["result"]
    assert "phase_results" in result["result"]
    assert isinstance(result["claim_payload"], dict)
    assert session.status == "confirming"
    assert session.validation_result is not None
```

**Step 2: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add tests/test_controller.py
git commit -m "test: add integration test for _build_summary validation result shape"
```

---

## Task 8: Manual end-to-end test

**Step 1: Start the chatbot**

Run: `uvicorn app.main:app --reload --port 8080`

**Step 2: Test the flow**

1. Open `http://localhost:8080` in browser
2. Chat through all 20 required fields (or upload a PDF)
3. After all fields collected, verify:
   - Validation result appears with status badge (pass/fail/needs_review)
   - Findings list shows with severity, code, message, suggestion
   - Phase badges show which pipeline phases ran
   - No JS errors in browser console
   - No Python errors in server logs

**Step 3: Test with clearinghouse (if credentials available)**

Set env vars in `.env`:
```
CLEARINGHOUSE_PROVIDER=waystar
WAYSTAR_API_KEY=...
WAYSTAR_SECRET=...
WAYSTAR_USER_ID=...
WAYSTAR_PASSWORD=...
WAYSTAR_CUST_ID=...
```

Restart and verify:
- Phase badges show "Clearinghouse" phase
- Clearinghouse findings appear if submission fails/succeeds

---

## Summary

| Task | Description | Estimated |
|------|-------------|-----------|
| 1 | Fix broken test imports | 2 min |
| 2 | Add clearinghouse config to Settings | 5 min |
| 3 | Simplify validator.py to thin wrapper | 5 min |
| 4 | Update controller to use validate_claim() | 3 min |
| 5 | Fix frontend display + add phase badges | 5 min |
| 6 | Implement WaystarClient.submit_claim() | 5 min |
| 7 | Integration test | 3 min |
| 8 | Manual end-to-end test | 5 min |
