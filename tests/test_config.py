from app.config import Settings


def test_settings_has_required_fields():
    """Settings loads with defaults for non-secret fields."""
    settings = Settings(
        openai_api_key="test-key",
        pageindex_api_key="test-pi-key",
    )
    assert settings.openai_api_key == "test-key"
    assert settings.pageindex_api_key == "test-pi-key"
    assert settings.openai_model == "gpt-4o"
    assert settings.upload_dir == "uploads"
    assert isinstance(settings.required_claim_fields, list)
    assert "subscriber_id" in settings.required_claim_fields


def test_settings_required_claim_fields():
    settings = Settings(
        openai_api_key="k",
        pageindex_api_key="k",
    )
    expected = [
        "subscriber_first_name",
        "subscriber_last_name",
        "subscriber_dob",
        "subscriber_gender",
        "subscriber_id",
        "patient_relationship",
        "patient_first_name",
        "patient_last_name",
        "patient_dob",
        "patient_gender",
        "payer_name",
        "payer_id",
        "billing_provider_npi",
        "billing_provider_taxonomy",
        "claim_type",
        "place_of_service",
        "total_charge",
        "diagnosis_codes",
        "service_lines",
    ]
    assert settings.required_claim_fields == expected
