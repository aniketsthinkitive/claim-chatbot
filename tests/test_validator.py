from app.validation.validator import create_validator, ValidationResult

def test_validation_result_model():
    result = ValidationResult(
        status="pass", issues=[], recommendations=["All checks passed."], raw_output={},
    )
    assert result.status == "pass"
    assert result.issues == []

def test_validation_result_fail():
    result = ValidationResult(
        status="fail",
        issues=["Missing documentation", "Amount exceeds limit"],
        recommendations=["Upload supporting docs"],
        raw_output={},
    )
    assert result.status == "fail"
    assert len(result.issues) == 2

def test_validator_validate_returns_result():
    validator = create_validator()
    result = validator.validate({
        "subscriber_first_name": "John",
        "subscriber_last_name": "Doe",
        "subscriber_dob": "1985-03-15",
        "subscriber_gender": "M",
        "subscriber_id": "XYZ123",
        "patient_relationship": "self",
        "patient_first_name": "John",
        "patient_last_name": "Doe",
        "patient_dob": "1985-03-15",
        "patient_gender": "M",
        "payer_name": "Aetna",
        "payer_id": "00001",
        "billing_provider_npi": "1245319599",
        "billing_provider_taxonomy": "207Q00000X",
        "claim_type": "professional",
        "place_of_service": "11",
        "total_charge": "150.00",
        "diagnosis_codes": [{"code": "J06.9", "pointer": 1, "type": "principal"}],
        "lines": [{"procedure_code": "99213", "charge_amount": 150.00, "units": 1.0, "service_date_from": "2026-03-01", "diagnosis_pointers": [1], "place_of_service": "11"}],
    })
    assert isinstance(result, ValidationResult)
    assert result.status in ("pass", "fail", "needs_review")

def test_validator_validate_with_documents():
    """Validator works with a partial ClaimMD payload (some fields missing)."""
    validator = create_validator()
    result = validator.validate({
        "subscriber_first_name": "Jane",
        "subscriber_last_name": "Smith",
        "subscriber_dob": "1990-05-20",
        "subscriber_gender": "F",
        "subscriber_id": "ABC456",
        "patient_relationship": "self",
        "patient_first_name": "Jane",
        "patient_last_name": "Smith",
        "patient_gender": "F",
        "payer_name": "BlueCross",
        "payer_id": "00002",
        "billing_provider_npi": "1234567890",
        "billing_provider_taxonomy": "207Q00000X",
        "claim_type": "professional",
        "place_of_service": "11",
        "total_charge": "200.00",
        "diagnosis_codes": [{"code": "J20.9", "pointer": 1, "type": "principal"}],
    })
    assert isinstance(result, ValidationResult)
    # Should have issues since service lines are missing
    assert result.status in ("fail", "needs_review")
