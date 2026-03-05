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
