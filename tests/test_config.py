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


def test_clearinghouse_config_defaults(monkeypatch):
    monkeypatch.delenv("CLEARINGHOUSE_PROVIDER", raising=False)
    monkeypatch.delenv("CLEARINGHOUSE_API_KEY", raising=False)
    from app.config import Settings
    s = Settings()
    assert s.clearinghouse_provider == ""
    assert s.clearinghouse_api_key == ""

def test_clearinghouse_config_dict_empty_when_no_provider(monkeypatch):
    monkeypatch.delenv("CLEARINGHOUSE_PROVIDER", raising=False)
    from app.config import Settings
    s = Settings()
    assert s.clearinghouse_config is None

def test_clearinghouse_config_dict_with_provider(monkeypatch):
    monkeypatch.setenv("CLEARINGHOUSE_PROVIDER", "waystar")
    monkeypatch.setenv("CLEARINGHOUSE_API_KEY", "test-key")
    monkeypatch.setenv("CLEARINGHOUSE_USER_ID", "test-user")
    monkeypatch.setenv("CLEARINGHOUSE_PASSWORD", "test-pass")
    monkeypatch.setenv("CLEARINGHOUSE_CUST_ID", "test-cust")
    from app.config import Settings
    s = Settings()
    cfg = s.clearinghouse_config
    assert cfg is not None
    assert cfg["provider"] == "waystar"
    assert cfg["api_key"] == "test-key"
    assert cfg["user_id"] == "test-user"
