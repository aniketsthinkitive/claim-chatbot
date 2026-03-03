from app.validation.validator import ClaimValidator, ValidationResult

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
    validator = ClaimValidator()
    result = validator.validate({
        "policy_number": "POL-123", "claim_type": "auto",
        "incident_date": "2026-01-15", "claim_amount": "5000",
        "incident_description": "Fender bender",
    })
    assert isinstance(result, ValidationResult)
    assert result.status in ("pass", "fail", "needs_review")

def test_validator_validate_with_documents():
    validator = ClaimValidator()
    result = validator.validate(
        {"policy_number": "POL-123", "claim_type": "health"},
        document_extractions={"diagnosis": "flu"},
    )
    assert isinstance(result, ValidationResult)
