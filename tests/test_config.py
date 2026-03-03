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
    assert "policy_number" in settings.required_claim_fields


def test_settings_required_claim_fields():
    settings = Settings(
        openai_api_key="k",
        pageindex_api_key="k",
    )
    expected = [
        "policy_number",
        "claim_type",
        "incident_date",
        "claim_amount",
        "incident_description",
    ]
    assert settings.required_claim_fields == expected
