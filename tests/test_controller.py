import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.chat.controller import ChatController
from app.chat.session import ClaimSession

@pytest.fixture
def session():
    return ClaimSession(session_id="test-session")

@pytest.fixture
def mock_openai_response():
    mock = MagicMock()
    mock.choices = [
        MagicMock(
            message=MagicMock(
                content='{"message": "What is your policy number?", "extracted_fields": {}}'
            )
        )
    ]
    return mock

@pytest.fixture
def mock_openai_with_extraction():
    mock = MagicMock()
    mock.choices = [
        MagicMock(
            message=MagicMock(
                content='{"message": "Got it! Your subscriber ID is XYZ123.", "extracted_fields": {"subscriber_id": "XYZ123"}}'
            )
        )
    ]
    return mock

@pytest.mark.asyncio
async def test_handle_message_asks_question(session, mock_openai_response):
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
    with patch("app.chat.controller.AsyncOpenAI", return_value=mock_client):
        controller = ChatController(openai_api_key="test-key")
        response = await controller.handle_message(session, "hello")
    assert response["type"] == "bot_message"
    assert "policy number" in response["content"].lower()
    assert len(session.chat_history) == 2

@pytest.mark.asyncio
async def test_handle_message_extracts_field(session, mock_openai_with_extraction):
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_with_extraction)
    with patch("app.chat.controller.AsyncOpenAI", return_value=mock_client):
        controller = ChatController(openai_api_key="test-key")
        response = await controller.handle_message(session, "My subscriber ID is XYZ123")
    assert session.collected_fields.get("subscriber_id") == "XYZ123"
    assert "subscriber_id" not in session.missing_fields

@pytest.mark.asyncio
async def test_handle_message_triggers_validation():
    session = ClaimSession(session_id="test")
    # Fill all fields except subscriber_id
    all_except_one = {
        "subscriber_first_name": "John",
        "subscriber_last_name": "Doe",
        "subscriber_dob": "1985-03-15",
        "subscriber_gender": "M",
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
        "service_lines": [{"procedure_code": "99213", "charge_amount": 150.00, "units": 1.0, "service_date_from": "2026-03-01", "diagnosis_pointers": [1], "place_of_service": "11"}],
    }
    for field, value in all_except_one.items():
        session.update_field(field, value)

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"message": "Got your ID!", "extracted_fields": {"subscriber_id": "XYZ123"}}'
            )
        )
    ]
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    with patch("app.chat.controller.AsyncOpenAI", return_value=mock_client):
        controller = ChatController(openai_api_key="test-key")
        response = await controller.handle_message(session, "My ID is XYZ123")
    assert session.status == "confirming"
    assert session.validation_result is not None
    assert response["type"] == "validation_result"

def test_get_welcome_message():
    controller = ChatController(openai_api_key="test-key")
    msg = controller.get_welcome_message()
    assert "claim" in msg["content"].lower()
    assert msg["type"] == "bot_message"


@pytest.mark.asyncio
async def test_handle_document_upload_shows_grouped_summary():
    session = ClaimSession(session_id="test-upload")
    extracted = {
        "subscriber_first_name": "John",
        "subscriber_last_name": "Doe",
        "subscriber_dob": "1985-03-15",
        "subscriber_gender": "M",
        "subscriber_id": "XYZ123",
        "payer_name": "Aetna",
        "billing_provider_npi": "1245319599",
    }
    controller = ChatController(openai_api_key="test-key")
    response = await controller.handle_document_upload(session, extracted)

    assert response["type"] == "bot_message"
    content = response["content"]
    # Should contain grouped headers
    assert "Subscriber" in content
    assert "John" in content
    assert "Doe" in content
    # Should mention what's still missing
    assert "still need" in content.lower() or "missing" in content.lower()
    # Extracted fields should be in session
    assert session.collected_fields["subscriber_first_name"] == "John"
    assert "subscriber_first_name" not in session.missing_fields


@pytest.mark.asyncio
async def test_handle_document_upload_all_fields_extracted():
    session = ClaimSession(session_id="test-full")
    all_fields = {
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
        "total_charge": 150.00,
        "diagnosis_codes": [{"code": "J06.9", "pointer": 1, "type": "principal"}],
        "service_lines": [{"procedure_code": "99213", "charge_amount": 150.00, "units": 1.0, "service_date_from": "2026-03-01", "diagnosis_pointers": [1], "place_of_service": "11"}],
    }
    controller = ChatController(openai_api_key="test-key")
    response = await controller.handle_document_upload(session, all_fields)

    # Should trigger validation since all fields present
    assert response["type"] == "validation_result"
    assert session.status == "confirming"


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
