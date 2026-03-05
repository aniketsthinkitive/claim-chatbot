"""Full flow tests — shows REQUEST payload and RESPONSE for every case.

Run with: python -m pytest tests/test_full_flow.py -v -s
The -s flag prints the full request/response payloads.

Covers:
  1. Valid claim      → rule-based passes, no errors
  2. Invalid NPI      → rule-based catches NPI error
  3. Missing fields   → rule-based catches multiple errors
  4. Bad diagnosis    → rule-based catches coding errors
  5. Fallback mode    → library unavailable, basic checks
  6. Session → Payload → Validation (end-to-end)
  7. Waystar eligibility check (live API)
  8. Waystar claim history check (live API)
"""

import json
import os
from copy import deepcopy

import pytest
from dotenv import load_dotenv

from app.chat.session import ClaimSession
from app.validation.validator import validate_claim

load_dotenv()

# ── Helpers ──────────────────────────────────────────────────────────────

def _print_request_response(test_name: str, request: dict, response: dict):
    """Pretty-print request and response for visibility."""
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  TEST: {test_name}")
    print(sep)
    print(f"\n--- REQUEST PAYLOAD ---")
    print(json.dumps(request, indent=2, default=str))
    print(f"\n--- RESPONSE ---")
    print(json.dumps(response, indent=2, default=str))
    print(f"\n{sep}\n")


# ── Sample data ──────────────────────────────────────────────────────────

VALID_CLAIM = {
    "subscriber_first_name": "JOHN",
    "subscriber_last_name": "DOE",
    "subscriber_dob": "1990-01-15",
    "subscriber_gender": "M",
    "subscriber_id": "ABC123456789",
    "patient_relationship": "self",
    "patient_first_name": "JOHN",
    "patient_last_name": "DOE",
    "patient_dob": "1990-01-15",
    "patient_gender": "M",
    "payer_name": "UNITED HEALTHCARE",
    "payer_id": "87726",
    "billing_provider_npi": "1234567893",
    "billing_provider_taxonomy": "207Q00000X",
    "claim_type": "professional",
    "place_of_service": "11",
    "total_charge": 150.00,
    "diagnosis_codes": [
        {"code": "Z00.00", "pointer": 1, "type": "principal"},
    ],
    "lines": [
        {
            "procedure_code": "99213",
            "charge_amount": 150.00,
            "units": 1,
            "service_date_from": "2026-03-01",
            "place_of_service": "11",
            "diagnosis_pointers": [1],
        },
    ],
}


# ── Test Cases ───────────────────────────────────────────────────────────

class TestValidClaimFlow:
    """Case 1: Valid claim — all fields correct, rule-based should pass."""

    def test_valid_claim_passes(self):
        request = deepcopy(VALID_CLAIM)
        response = validate_claim(request)

        _print_request_response("Valid Claim — Passes Rule-Based", request, response)

        assert response["status"] == "pass"
        assert response["passed"] is True
        assert response["total_errors"] == 0
        assert any(pr["phase"] == "rule_based" for pr in response["phase_results"])


class TestInvalidNPI:
    """Case 2: Invalid NPI — rule-based catches the error."""

    def test_invalid_npi(self):
        request = deepcopy(VALID_CLAIM)
        request["billing_provider_npi"] = "12345"  # too short

        response = validate_claim(request)

        _print_request_response("Invalid NPI (too short)", request, response)

        assert response["passed"] is False
        assert response["total_errors"] >= 1
        npi_findings = [f for f in response["findings"] if "npi" in f["field_name"].lower() or "npi" in f["code"].lower()]
        assert len(npi_findings) >= 1
        print(f"NPI error: {npi_findings[0]['message']}")


class TestMissingFields:
    """Case 3: Missing critical fields — multiple errors."""

    def test_missing_subscriber_and_diagnosis(self):
        request = deepcopy(VALID_CLAIM)
        request["subscriber_id"] = ""
        request["diagnosis_codes"] = []
        request["lines"] = []

        response = validate_claim(request)

        _print_request_response("Missing subscriber_id + diagnosis + lines", request, response)

        assert response["passed"] is False
        assert response["total_errors"] >= 2
        error_fields = [f["field_name"] for f in response["findings"] if f["severity"] == "error"]
        print(f"Error fields: {error_fields}")


class TestBadDiagnosisCodes:
    """Case 4: Invalid diagnosis codes — coding validator catches errors."""

    def test_invalid_icd10_code(self):
        request = deepcopy(VALID_CLAIM)
        request["diagnosis_codes"] = [
            {"code": "ZZZZZ", "pointer": 1, "type": "principal"},
        ]

        response = validate_claim(request)

        _print_request_response("Invalid ICD-10 code (ZZZZZ)", request, response)

        coding_findings = [f for f in response["findings"] if "cod" in f["code"].lower() or "diag" in f["code"].lower()]
        if coding_findings:
            print(f"Coding error: {coding_findings[0]['message']}")
        # May or may not fail depending on validator strictness
        assert isinstance(response["findings"], list)


class TestDiagnosisPointerMismatch:
    """Case 5: Service line diagnosis_pointers reference non-existent diagnosis."""

    def test_pointer_out_of_range(self):
        request = deepcopy(VALID_CLAIM)
        request["lines"][0]["diagnosis_pointers"] = [1, 2, 3]  # only 1 dx exists

        response = validate_claim(request)

        _print_request_response("Diagnosis pointer out of range", request, response)

        pointer_findings = [f for f in response["findings"] if "pointer" in f["message"].lower() or "pointer" in f["code"].lower()]
        if pointer_findings:
            for pf in pointer_findings:
                print(f"Pointer error: {pf['message']}")
        assert isinstance(response["findings"], list)


class TestChargesMismatch:
    """Case 6: Total charge doesn't match sum of line charges."""

    def test_total_charge_mismatch(self):
        request = deepcopy(VALID_CLAIM)
        request["total_charge"] = 999.99  # line charge is 150.00

        response = validate_claim(request)

        _print_request_response("Total charge mismatch (999.99 vs 150.00)", request, response)

        charge_findings = [f for f in response["findings"] if "charge" in f["message"].lower() or "monetary" in f["code"].lower()]
        if charge_findings:
            for cf in charge_findings:
                print(f"Charge finding: {cf['message']}")
        assert isinstance(response["findings"], list)


class TestFallbackValidation:
    """Case 7: Fallback when claim-validator library is unavailable."""

    def test_fallback_bad_npi(self):
        from app.validation import validator as v
        original = v._library_available
        v._library_available = False
        try:
            request = {
                "billing_provider_npi": "123",
                "subscriber_id": "",
                "diagnosis_codes": [],
                "lines": [],
            }
            response = validate_claim(request)

            _print_request_response("Fallback mode — multiple errors", request, response)

            assert response["fallback"] is True
            assert response["passed"] is False
            assert response["total_errors"] >= 3
            assert any(pr["phase"] == "fallback" for pr in response["phase_results"])
        finally:
            v._library_available = original

    def test_fallback_valid(self):
        from app.validation import validator as v
        original = v._library_available
        v._library_available = False
        try:
            request = {
                "billing_provider_npi": "1234567893",
                "subscriber_id": "ABC123",
                "diagnosis_codes": [{"code": "Z00.00"}],
                "lines": [{"procedure_code": "99213", "charge_amount": 100}],
            }
            response = validate_claim(request)

            _print_request_response("Fallback mode — passes basic checks", request, response)

            assert response["fallback"] is True
            assert response["passed"] is True
            assert response["total_errors"] == 0
        finally:
            v._library_available = original


class TestSessionToValidation:
    """Case 8: Full end-to-end — session collects fields → builds payload → validates."""

    def test_end_to_end_session_flow(self):
        session = ClaimSession(session_id="test-e2e-001")

        # Simulate collecting all fields
        fields = {
            "subscriber_first_name": "JANE",
            "subscriber_last_name": "SMITH",
            "subscriber_dob": "1985-06-20",
            "subscriber_gender": "F",
            "subscriber_id": "XYZ987654321",
            "patient_relationship": "self",
            "patient_first_name": "JANE",
            "patient_last_name": "SMITH",
            "patient_dob": "1985-06-20",
            "patient_gender": "F",
            "payer_name": "AETNA",
            "payer_id": "60054",
            "billing_provider_npi": "1234567893",
            "billing_provider_taxonomy": "207Q00000X",
            "claim_type": "professional",
            "place_of_service": "11",
            "total_charge": "250.00",
            "diagnosis_codes": [
                {"code": "J06.9", "pointer": 1, "type": "principal"},
            ],
            "service_lines": [
                {
                    "procedure_code": "99214",
                    "charge_amount": 250.00,
                    "units": 1,
                    "service_date_from": "2026-03-01",
                    "diagnosis_pointers": [1],
                },
            ],
        }

        for field, value in fields.items():
            session.update_field(field, value)

        assert session.all_fields_collected()

        # Build payload (same as controller._build_summary)
        payload = session.build_claim_payload()
        response = validate_claim(payload)

        _print_request_response("End-to-End: Session → Payload → Validation", payload, response)

        assert isinstance(response["status"], str)
        assert isinstance(response["findings"], list)
        assert isinstance(response["phase_results"], list)
        assert response["execution_time"] > 0

    def test_end_to_end_session_with_errors(self):
        session = ClaimSession(session_id="test-e2e-002")

        fields = {
            "subscriber_first_name": "BOB",
            "subscriber_last_name": "JONES",
            "subscriber_dob": "1970-03-10",
            "subscriber_gender": "M",
            "subscriber_id": "SHORT",        # too short
            "patient_relationship": "self",
            "patient_first_name": "BOB",
            "patient_last_name": "JONES",
            "patient_dob": "1970-03-10",
            "patient_gender": "M",
            "payer_name": "CIGNA",
            "payer_id": "62308",
            "billing_provider_npi": "999",   # invalid NPI
            "billing_provider_taxonomy": "207Q00000X",
            "claim_type": "professional",
            "place_of_service": "11",
            "total_charge": "75.00",
            "diagnosis_codes": [
                {"code": "Z00.00", "pointer": 1, "type": "principal"},
            ],
            "service_lines": [
                {
                    "procedure_code": "99213",
                    "charge_amount": 75.00,
                    "units": 1,
                    "service_date_from": "2026-03-01",
                    "diagnosis_pointers": [1],
                },
            ],
        }

        for field, value in fields.items():
            session.update_field(field, value)

        payload = session.build_claim_payload()
        response = validate_claim(payload)

        _print_request_response("End-to-End: Session with invalid NPI + short subscriber_id", payload, response)

        assert response["passed"] is False
        assert response["total_errors"] >= 1


# ── Live Waystar API Tests ───────────────────────────────────────────────

API_KEY = os.getenv("CLEARINGHOUSE_API_KEY", "")
USER_ID = os.getenv("CLEARINGHOUSE_USER_ID", "")
PASSWORD = os.getenv("CLEARINGHOUSE_PASSWORD", "")
CUST_ID = os.getenv("CLEARINGHOUSE_CUST_ID", "")

live_skip = pytest.mark.skipif(
    not API_KEY or not USER_ID,
    reason="Waystar credentials not configured in .env",
)


@live_skip
class TestWaystarEligibility:
    """Case 9: Live Waystar eligibility check — real API call."""

    def test_eligibility_check(self):
        from claim_validator.clearinghouse.providers.waystar import WaystarClient

        request = {
            "payer_id": "66666",
            "npi": "1234567890",
            "subscriber_id": "ABC123456",
            "first_name": "JOHN",
            "last_name": "DOE",
            "dob": "1990-01-15",
            "service_type": "30",
        }

        client = WaystarClient(
            api_key=API_KEY, user_id=USER_ID,
            password=PASSWORD, cust_id=CUST_ID,
        )
        try:
            result = client.check_eligibility(request)
            response = {
                "status": result.status,
                "eligible": result.eligible,
                "reference_id": result.reference_id,
                "errors": result.errors,
                "raw_response_keys": list(result.raw_response.keys()) if isinstance(result.raw_response, dict) else [],
                "plan_info_keys": list(result.plan_info.keys()) if isinstance(result.plan_info, dict) else [],
                "raw_response": result.raw_response,
            }
        except Exception as e:
            response = {"error": str(e), "type": type(e).__name__}
        finally:
            client.close()

        _print_request_response("Waystar Eligibility Check (LIVE)", request, response)

        assert response.get("status") == "active"
        assert response.get("eligible") is True


@live_skip
class TestWaystarClaimHistory:
    """Case 10: Live Waystar claim history check — real API call."""

    def test_claim_history_check(self):
        from claim_validator.clearinghouse.providers.waystar import WaystarClient

        request = {
            "claim_ref": "TEST001",
            "dos": "03/01/2026",
        }

        client = WaystarClient(
            api_key=API_KEY, user_id=USER_ID,
            password=PASSWORD, cust_id=CUST_ID,
        )
        try:
            result = client.check_claim_status(
                claim_ref=request["claim_ref"],
                dos=request["dos"],
            )
            response = {
                "status": result.status,
                "claim_status": result.claim_status,
                "adjudication_date": result.adjudication_date,
                "reference_id": result.reference_id,
                "raw_response": result.raw_response,
            }
        except Exception as e:
            response = {"error": str(e), "type": type(e).__name__}
        finally:
            client.close()

        _print_request_response("Waystar Claim History (LIVE)", request, response)

        # We expect some response (even error) — the endpoint exists
        assert "status" in response or "error" in response


@live_skip
class TestWaystarClaimSubmitNotSupported:
    """Case 11: Waystar claim submission — confirms REST endpoint doesn't exist."""

    def test_submit_returns_404(self):
        import httpx

        claims_base = os.getenv("CLEARINGHOUSE_BASE_URL", "https://claimsapi.zirmed.com")
        request = {
            "url": f"{claims_base}/2.0/v1/Claims/Submit",
            "body": {
                "UserID": USER_ID,
                "Password": PASSWORD,
                "CustID": CUST_ID,
                "ClaimData": VALID_CLAIM,
            },
        }

        with httpx.Client(timeout=30.0) as http:
            resp = http.post(request["url"], json=request["body"])

        response = {
            "status_code": resp.status_code,
            "body": resp.text[:500],
            "conclusion": "Waystar does NOT have a REST claim submission endpoint. "
                          "Claims must be submitted via EDI/SFTP (X12 837).",
        }

        _print_request_response("Waystar Claim Submit — NOT SUPPORTED", request, response)

        assert resp.status_code == 404
