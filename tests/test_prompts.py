from app.chat.prompts import get_system_prompt, get_extraction_prompt, get_field_question_prompt


def test_system_prompt_contains_role():
    prompt = get_system_prompt()
    assert "insurance claim" in prompt.lower()
    assert isinstance(prompt, str)
    assert len(prompt) > 50


def test_extraction_prompt_includes_fields():
    prompt = get_extraction_prompt("Some document text about policy POL-123")
    assert "policy_number" in prompt
    assert "claim_type" in prompt
    assert "JSON" in prompt


def test_field_question_prompt():
    prompt = get_field_question_prompt("incident_date", {"policy_number": "POL-123"})
    assert "incident_date" in prompt
    assert "POL-123" in prompt
