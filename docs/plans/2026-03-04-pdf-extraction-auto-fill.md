# PDF Auto-Extraction for ClaimMD Fields — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When a user uploads a PDF, automatically extract all ClaimMD fields using PageIndex (tree + OCR) and LLM, show a summary of extracted data, and only ask the user for missing fields.

**Architecture:** PageIndex processes the PDF into structured tree text and raw OCR text. Both are combined and sent to GPT-4o with a ClaimMD-specific extraction prompt. The extracted fields auto-populate the session. The controller builds a grouped summary and identifies remaining gaps.

**Tech Stack:** FastAPI, PageIndex SDK (tree + OCR), OpenAI GPT-4o, Pydantic

---

### Task 1: Add OCR support to DocumentProcessor

**Files:**
- Modify: `app/documents/processor.py`
- Test: `tests/test_processor.py`

**Step 1: Write the failing test**

Add to `tests/test_processor.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_processor.py::test_processor_get_document_ocr -v`
Expected: FAIL — `AttributeError: 'DocumentProcessor' object has no attribute 'get_document_ocr'`

**Step 3: Write minimal implementation**

Add to `app/documents/processor.py` after `get_document_text`:

```python
def get_document_ocr(self, doc_id: str) -> str:
    result = self.client.get_ocr(doc_id, format="raw")
    return result.get("result", "")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_processor.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/documents/processor.py tests/test_processor.py
git commit -m "feat: add OCR support to DocumentProcessor"
```

---

### Task 2: Rewrite extraction prompt for ClaimMD fields

**Files:**
- Modify: `app/chat/prompts.py` (the `get_extraction_prompt` function)
- Test: `tests/test_prompts.py`

**Step 1: Write the failing test**

Add to `tests/test_prompts.py`:

```python
def test_extraction_prompt_contains_claimmd_fields():
    prompt = get_extraction_prompt("some document text")
    # Must mention all ClaimMD field names
    assert "billing_provider_npi" in prompt
    assert "subscriber_id" in prompt
    assert "diagnosis_codes" in prompt
    assert "service_lines" in prompt
    assert "procedure_code" in prompt
    # Must contain example JSON structure
    assert "J06.9" in prompt or "ICD-10" in prompt
    assert "99213" in prompt or "CPT" in prompt


def test_extraction_prompt_includes_document_text():
    prompt = get_extraction_prompt("Patient John Doe NPI 1234567890")
    assert "Patient John Doe NPI 1234567890" in prompt
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_prompts.py -v`
Expected: FAIL — current prompt doesn't mention `billing_provider_npi`, `procedure_code`, etc.

**Step 3: Write the implementation**

Replace `get_extraction_prompt` in `app/chat/prompts.py`:

```python
def get_extraction_prompt(document_text: str) -> str:
    return f"""You are a medical claim data extraction specialist. Extract ALL insurance claim fields from the document text below.

Return a JSON object with ONLY the fields you can confidently find. Use these exact field names and formats:

## Subscriber / Patient Information
- "subscriber_first_name": string (legal first name)
- "subscriber_last_name": string (legal last name)
- "subscriber_dob": string (YYYY-MM-DD format)
- "subscriber_gender": "M" or "F"
- "subscriber_id": string (insurance member/subscriber ID)
- "patient_relationship": "self", "spouse", "child", or "other"
- "patient_first_name": string
- "patient_last_name": string
- "patient_dob": string (YYYY-MM-DD)
- "patient_gender": "M" or "F"

## Payer Information
- "payer_name": string (insurance company name, e.g. "Aetna", "Blue Cross")
- "payer_id": string (clearinghouse payer ID, e.g. "00001")

## Billing Provider
- "billing_provider_npi": string (10-digit NPI number)
- "billing_provider_taxonomy": string (taxonomy code, e.g. "207Q00000X")

## Claim Details
- "claim_type": "professional" or "institutional"
- "place_of_service": string (2-digit code, e.g. "11" for Office)
- "total_charge": number (total dollar amount)

## Diagnosis Codes
- "diagnosis_codes": array of objects, each with:
  - "code": string (ICD-10 code, e.g. "J06.9")
  - "pointer": integer (sequential, starting at 1)
  - "type": "principal" (first one) or "secondary"

## Service Lines
- "service_lines": array of objects, each with:
  - "procedure_code": string (CPT code, e.g. "99213")
  - "charge_amount": number (dollar amount)
  - "units": number (default 1.0)
  - "service_date_from": string (YYYY-MM-DD)
  - "diagnosis_pointers": array of integers referencing diagnosis pointer numbers
  - "place_of_service": string (2-digit code)

## Document Text:
{document_text}

## Rules:
- Return ONLY valid JSON — no markdown, no explanation
- Only include fields you can confidently extract
- Convert dates to YYYY-MM-DD
- Convert gender to "M" or "F"
- NPI must be exactly 10 digits
- If patient is the subscriber, set patient_relationship to "self" and copy subscriber info to patient fields

Example output:
{{"subscriber_first_name": "John", "subscriber_last_name": "Doe", "subscriber_dob": "1985-03-15", "subscriber_gender": "M", "subscriber_id": "XYZ123456789", "patient_relationship": "self", "patient_first_name": "John", "patient_last_name": "Doe", "patient_dob": "1985-03-15", "patient_gender": "M", "payer_name": "Aetna", "payer_id": "00001", "billing_provider_npi": "1245319599", "billing_provider_taxonomy": "207Q00000X", "claim_type": "professional", "place_of_service": "11", "total_charge": 150.00, "diagnosis_codes": [{{"code": "J06.9", "pointer": 1, "type": "principal"}}], "service_lines": [{{"procedure_code": "99213", "charge_amount": 150.00, "units": 1.0, "service_date_from": "2026-03-01", "diagnosis_pointers": [1], "place_of_service": "11"}}]}}"""
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_prompts.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/chat/prompts.py tests/test_prompts.py
git commit -m "feat: ClaimMD-aware extraction prompt with all field definitions"
```

---

### Task 3: Add robust JSON parsing to FieldExtractor

**Files:**
- Modify: `app/documents/extractor.py`
- Test: `tests/test_extractor.py`

**Step 1: Write the failing test**

Add to `tests/test_extractor.py`:

```python
@pytest.mark.asyncio
async def test_extract_fields_handles_markdown_json():
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content='```json\n{"subscriber_id": "ABC123"}\n```'))
    ]
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.documents.extractor.AsyncOpenAI", return_value=mock_client):
        extractor = FieldExtractor(api_key="test-key")
        fields = await extractor.extract_fields("some text")
        assert fields["subscriber_id"] == "ABC123"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_extractor.py::test_extract_fields_handles_markdown_json -v`
Expected: FAIL — current parser doesn't strip markdown code blocks

**Step 3: Write the implementation**

Replace `app/documents/extractor.py`:

```python
import json
import logging

from openai import AsyncOpenAI

from app.chat.prompts import get_extraction_prompt
from app.config import settings

logger = logging.getLogger(__name__)


class FieldExtractor:
    def __init__(self, api_key: str | None = None):
        self.client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)

    async def extract_fields(self, document_text: str) -> dict:
        prompt = get_extraction_prompt(document_text)
        response = await self.client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        content = response.choices[0].message.content.strip()
        return self._parse_json(content)

    def _parse_json(self, content: str) -> dict:
        # Try direct parse first
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting from ```json ... ``` blocks
        if "```json" in content:
            try:
                start = content.index("```json") + 7
                end = content.index("```", start)
                return json.loads(content[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass
        elif "```" in content:
            try:
                start = content.index("```") + 3
                end = content.index("```", start)
                return json.loads(content[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass

        logger.warning(f"Failed to parse extraction response: {content[:200]}")
        return {}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_extractor.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add app/documents/extractor.py tests/test_extractor.py
git commit -m "feat: robust JSON parsing in FieldExtractor with markdown block support"
```

---

### Task 4: Combine tree + OCR in upload endpoint

**Files:**
- Modify: `app/main.py` (the `/api/upload` handler)

**Step 1: Write the implementation**

Replace lines 55-63 in `app/main.py` (the extraction block):

```python
    extracted_fields = {}
    try:
        processor = DocumentProcessor(api_key=settings.pageindex_api_key)
        doc_id = processor.index_document(file_path)

        # Get both tree text and OCR for maximum extraction context
        tree_text = processor.get_document_text(doc_id)
        ocr_text = processor.get_document_ocr(doc_id)

        # Combine both sources for the LLM
        combined_text = f"=== DOCUMENT STRUCTURE ===\n{tree_text}\n\n=== RAW OCR TEXT ===\n{ocr_text}"

        extractor = FieldExtractor()
        extracted_fields = await extractor.extract_fields(combined_text)
        logger.info(f"Extracted {len(extracted_fields)} fields from document")
    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `pytest tests/test_main.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add app/main.py
git commit -m "feat: combine PageIndex tree + OCR for richer field extraction"
```

---

### Task 5: Rich extraction summary in controller

**Files:**
- Modify: `app/chat/controller.py` (the `handle_document_upload` method)
- Test: `tests/test_controller.py`

**Step 1: Write the failing test**

Add to `tests/test_controller.py`:

```python
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
    # Fill ALL required fields via extraction
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_controller.py::test_handle_document_upload_shows_grouped_summary -v`
Expected: FAIL — current `handle_document_upload` doesn't produce grouped output

**Step 3: Write the implementation**

Replace `handle_document_upload` method in `app/chat/controller.py`:

```python
    async def handle_document_upload(
        self, session: ClaimSession, extracted_fields: dict
    ) -> dict:
        # Handle patient_relationship=self: auto-copy subscriber to patient
        if extracted_fields.get("patient_relationship", "").lower() == "self":
            for sub_field, pat_field in [
                ("subscriber_first_name", "patient_first_name"),
                ("subscriber_last_name", "patient_last_name"),
                ("subscriber_dob", "patient_dob"),
                ("subscriber_gender", "patient_gender"),
            ]:
                val = extracted_fields.get(sub_field)
                if val and pat_field not in extracted_fields:
                    extracted_fields[pat_field] = val

        for field, value in extracted_fields.items():
            if field in session.missing_fields:
                session.update_field(field, value)
        session.pageindex_extractions.update(extracted_fields)

        if extracted_fields:
            msg = self._format_extraction_summary(extracted_fields, session.missing_fields)
        else:
            msg = (
                "I couldn't extract claim details from this document. "
                "Let's fill in the information manually."
            )
            if session.missing_fields:
                next_field = session.missing_fields[0]
                msg += f"\n\nCould you please provide your {next_field.replace('_', ' ')}?"

        session.add_message("bot", msg)

        if session.all_fields_collected():
            return self._build_summary(session, msg)

        return {"type": "bot_message", "content": msg}

    def _format_extraction_summary(self, extracted: dict, missing: list[str]) -> str:
        """Build a grouped summary of extracted fields."""
        groups = {
            "Subscriber Information": [
                "subscriber_first_name", "subscriber_last_name",
                "subscriber_dob", "subscriber_gender", "subscriber_id",
            ],
            "Patient Information": [
                "patient_relationship", "patient_first_name",
                "patient_last_name", "patient_dob", "patient_gender",
            ],
            "Payer/Insurance": ["payer_name", "payer_id"],
            "Billing Provider": [
                "billing_provider_npi", "billing_provider_taxonomy",
            ],
            "Claim Details": [
                "claim_type", "place_of_service", "total_charge",
            ],
            "Diagnosis Codes": ["diagnosis_codes"],
            "Service Lines": ["service_lines"],
        }

        field_labels = {
            "subscriber_first_name": "First Name",
            "subscriber_last_name": "Last Name",
            "subscriber_dob": "Date of Birth",
            "subscriber_gender": "Gender",
            "subscriber_id": "Member ID",
            "patient_relationship": "Relationship",
            "patient_first_name": "First Name",
            "patient_last_name": "Last Name",
            "patient_dob": "Date of Birth",
            "patient_gender": "Gender",
            "payer_name": "Insurance Company",
            "payer_id": "Payer ID",
            "billing_provider_npi": "NPI",
            "billing_provider_taxonomy": "Taxonomy",
            "claim_type": "Claim Type",
            "place_of_service": "Place of Service",
            "total_charge": "Total Charge",
            "diagnosis_codes": "Diagnosis Codes",
            "service_lines": "Service Lines",
        }

        lines = ["I extracted the following from your document:\n"]

        for group_name, group_fields in groups.items():
            found = {f: extracted[f] for f in group_fields if f in extracted}
            if not found:
                continue
            lines.append(f"\n{group_name}:")
            for field, value in found.items():
                label = field_labels.get(field, field.replace("_", " ").title())
                if isinstance(value, list):
                    if field == "diagnosis_codes":
                        for dx in value:
                            lines.append(f"  - {dx.get('code', '?')} ({dx.get('type', 'unknown')})")
                    elif field == "service_lines":
                        for sl in value:
                            lines.append(f"  - CPT {sl.get('procedure_code', '?')}: ${sl.get('charge_amount', 0):.2f} x{sl.get('units', 1)} on {sl.get('service_date_from', '?')}")
                else:
                    lines.append(f"  - {label}: {value}")

        if missing:
            missing_labels = [field_labels.get(f, f.replace("_", " ").title()) for f in missing]
            lines.append(f"\nI still need the following: {', '.join(missing_labels)}.")
            next_field = missing[0]
            next_label = field_labels.get(next_field, next_field.replace("_", " ").title())
            lines.append(f"\nCould you please provide the {next_label}?")
        else:
            lines.append("\nAll fields have been extracted! Proceeding to validation...")

        return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_controller.py -v`
Expected: ALL PASS (old tests may need updating — see Task 6)

**Step 5: Commit**

```bash
git add app/chat/controller.py tests/test_controller.py
git commit -m "feat: rich grouped extraction summary in document upload handler"
```

---

### Task 6: Fix existing tests for new field structure

**Files:**
- Modify: `tests/test_controller.py` (update old fixtures to use new ClaimMD field names)
- Modify: `tests/test_session.py` (update if field names changed)

**Step 1: Update test fixtures**

The old tests reference `policy_number`, `incident_date`, etc. These need updating to the new ClaimMD field names. Update `test_handle_message_extracts_field`:

```python
@pytest.fixture
def mock_openai_with_extraction():
    mock = MagicMock()
    mock.choices = [
        MagicMock(
            message=MagicMock(
                content='{"message": "Got it! Subscriber ID XYZ123.", "extracted_fields": {"subscriber_id": "XYZ123"}}'
            )
        )
    ]
    return mock
```

Update the assertion in `test_handle_message_extracts_field`:

```python
assert session.collected_fields.get("subscriber_id") == "XYZ123"
assert "subscriber_id" not in session.missing_fields
```

Update `test_handle_message_triggers_validation` to fill all 18 ClaimMD fields.

**Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/
git commit -m "test: update tests for ClaimMD field structure"
```

---

### Task 7: End-to-end verification

**Step 1: Start the server**

```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Step 2: Test the flow**

1. Open http://localhost:8000
2. Upload a PDF with insurance claim data
3. Verify the bot shows a grouped summary of extracted fields
4. Verify it only asks for missing fields
5. Fill in missing fields via chat
6. Verify validation triggers when all fields are collected

**Step 3: Run full test suite**

```bash
pytest tests/ -v
```

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: PDF auto-extraction for ClaimMD fields with grouped summary"
```
