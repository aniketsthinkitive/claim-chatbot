import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.documents.extractor import FieldExtractor


@pytest.mark.asyncio
async def test_extract_fields_from_text():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='{"policy_number": "POL-789", "claim_type": "auto"}'))
    ]
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.documents.extractor.AsyncOpenAI", return_value=mock_client):
        extractor = FieldExtractor(api_key="test-key")
        fields = await extractor.extract_fields("Policy POL-789, auto insurance claim")
        assert fields["policy_number"] == "POL-789"
        assert fields["claim_type"] == "auto"


@pytest.mark.asyncio
async def test_extract_fields_handles_empty():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="{}"))
    ]
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.documents.extractor.AsyncOpenAI", return_value=mock_client):
        extractor = FieldExtractor(api_key="test-key")
        fields = await extractor.extract_fields("Random unrelated text")
        assert fields == {}


@pytest.mark.asyncio
async def test_extract_fields_handles_invalid_json():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content="not valid json"))
    ]
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.documents.extractor.AsyncOpenAI", return_value=mock_client):
        extractor = FieldExtractor(api_key="test-key")
        fields = await extractor.extract_fields("some text")
        assert fields == {}
