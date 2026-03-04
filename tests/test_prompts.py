from app.chat.prompts import get_system_prompt, get_extraction_prompt, get_field_question_prompt


def test_system_prompt_contains_role():
    prompt = get_system_prompt()
    assert "insurance claim" in prompt.lower()
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_extraction_prompt_includes_fields():
    prompt = get_extraction_prompt("Some document text about policy POL-123")
    assert "claim_type" in prompt
    assert "JSON" in prompt


def test_extraction_prompt_contains_claimmd_fields():
    prompt = get_extraction_prompt("some document text")
    assert "billing_provider_npi" in prompt
    assert "subscriber_id" in prompt
    assert "diagnosis_codes" in prompt
    assert "service_lines" in prompt
    assert "procedure_code" in prompt
    assert "J06.9" in prompt or "ICD-10" in prompt
    assert "99213" in prompt or "CPT" in prompt


def test_extraction_prompt_includes_document_text():
    prompt = get_extraction_prompt("Patient John Doe NPI 1234567890")
    assert "Patient John Doe NPI 1234567890" in prompt


def test_field_question_prompt():
    prompt = get_field_question_prompt("incident_date", {"policy_number": "POL-123"})
    assert "incident_date" in prompt
    assert "POL-123" in prompt
