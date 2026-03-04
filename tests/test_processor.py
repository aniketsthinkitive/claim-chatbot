import pytest
from unittest.mock import MagicMock, patch
from app.documents.processor import DocumentProcessor

@pytest.fixture
def mock_pi_client():
    client = MagicMock()
    client.submit_document.return_value = {"doc_id": "doc-123"}
    client.get_tree.return_value = {
        "result": {
            "title": "Claim Form",
            "children": [
                {
                    "title": "Policy Information",
                    "summary": "Policy number POL-456, type: auto",
                    "physical_index": 1,
                },
                {
                    "title": "Incident Details",
                    "summary": "Car accident on 2026-01-15, damage: $3000",
                    "physical_index": 2,
                },
            ],
        }
    }
    return client

def test_processor_index_document(mock_pi_client):
    with patch("app.documents.processor.PageIndexClient", return_value=mock_pi_client):
        processor = DocumentProcessor(api_key="test-key")
        doc_id = processor.index_document("/path/to/claim.pdf")
        assert doc_id == "doc-123"
        mock_pi_client.submit_document.assert_called_once_with("/path/to/claim.pdf")

def test_processor_get_tree(mock_pi_client):
    with patch("app.documents.processor.PageIndexClient", return_value=mock_pi_client):
        processor = DocumentProcessor(api_key="test-key")
        tree = processor.get_document_tree("doc-123")
        assert tree["title"] == "Claim Form"
        assert len(tree["children"]) == 2

def test_processor_get_document_text(mock_pi_client):
    with patch("app.documents.processor.PageIndexClient", return_value=mock_pi_client):
        processor = DocumentProcessor(api_key="test-key")
        text = processor.get_document_text("doc-123")
        assert "Policy Information" in text
        assert "Incident Details" in text

def test_processor_get_document_ocr(mock_pi_client):
    mock_pi_client.get_ocr.return_value = {
        "result": "Patient: John Doe\nDOB: 1985-03-15\nNPI: 1245319599\nDiagnosis: J06.9"
    }
    with patch("app.documents.processor.PageIndexClient", return_value=mock_pi_client):
        processor = DocumentProcessor(api_key="test-key")
        ocr_text = processor.get_document_ocr("doc-123")
        assert "John Doe" in ocr_text
        assert "1245319599" in ocr_text
        mock_pi_client.get_ocr.assert_called_once_with("doc-123", format="raw")
