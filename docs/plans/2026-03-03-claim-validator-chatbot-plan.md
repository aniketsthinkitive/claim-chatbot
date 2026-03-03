# Insurance Claim Validator Chatbot — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a conversational chatbot that collects insurance claim data through dialogue and document upload, processes documents with PageIndex, and validates claims using a pluggable validator library.

**Architecture:** Monolithic FastAPI app with WebSocket chat, HTML/JS frontend. PageIndex (cloud API via `pip install pageindex`) indexes uploaded PDFs and extracts structured data. OpenAI GPT-4 powers natural language conversation. Claim validator is wrapped in an adapter for pluggability.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, WebSockets, OpenAI SDK, PageIndex SDK, pytest, httpx

**Design Doc:** `docs/plans/2026-03-03-claim-validator-chatbot-design.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/chat/__init__.py`
- Create: `app/documents/__init__.py`
- Create: `app/validation/__init__.py`
- Create: `tests/__init__.py`
- Create: `uploads/.gitkeep`

**Step 1: Initialize git repo**

```bash
cd /home/lnv-20/Documents/chatbot
git init
```

**Step 2: Create requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
websockets==12.0
openai==1.101.0
pageindex>=0.1.0
python-dotenv==1.1.0
python-multipart==0.0.9
pydantic==2.9.0
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

**Step 3: Create .env.example**

```
OPENAI_API_KEY=sk-your-openai-key-here
PAGEINDEX_API_KEY=your-pageindex-api-key-here
```

**Step 4: Create .gitignore**

```
__pycache__/
*.pyc
.env
uploads/*
!uploads/.gitkeep
.pytest_cache/
*.egg-info/
dist/
build/
.venv/
venv/
```

**Step 5: Create directory structure with __init__.py files**

```bash
mkdir -p app/chat app/documents app/validation app/static tests uploads
touch app/__init__.py app/chat/__init__.py app/documents/__init__.py app/validation/__init__.py tests/__init__.py uploads/.gitkeep
```

**Step 6: Install dependencies**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Step 7: Commit**

```bash
git add requirements.txt .env.example .gitignore app/ tests/ uploads/.gitkeep docs/
git commit -m "feat: project scaffolding with dependencies and directory structure"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `app/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

```python
# tests/test_config.py
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

**Step 3: Write minimal implementation**

```python
# app/config.py
import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    pageindex_api_key: str = os.getenv("PAGEINDEX_API_KEY", "")
    openai_model: str = "gpt-4o"
    upload_dir: str = "uploads"
    required_claim_fields: list[str] = [
        "policy_number",
        "claim_type",
        "incident_date",
        "claim_amount",
        "incident_description",
    ]


settings = Settings()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: add Settings configuration with required claim fields"
```

---

## Task 3: Session Model

**Files:**
- Create: `app/chat/session.py`
- Create: `tests/test_session.py`

**Step 1: Write the failing test**

```python
# tests/test_session.py
from app.chat.session import ClaimSession, SessionStore


def test_claim_session_defaults():
    session = ClaimSession(session_id="abc")
    assert session.session_id == "abc"
    assert session.status == "collecting"
    assert session.collected_fields == {}
    assert session.missing_fields == [
        "policy_number",
        "claim_type",
        "incident_date",
        "claim_amount",
        "incident_description",
    ]
    assert session.uploaded_documents == []
    assert session.pageindex_extractions == {}
    assert session.validation_result is None
    assert session.chat_history == []


def test_session_update_field():
    session = ClaimSession(session_id="abc")
    session.update_field("policy_number", "POL-123")
    assert session.collected_fields["policy_number"] == "POL-123"
    assert "policy_number" not in session.missing_fields


def test_session_all_fields_collected():
    session = ClaimSession(session_id="abc")
    assert not session.all_fields_collected()
    for field in list(session.missing_fields):
        session.update_field(field, "test")
    assert session.all_fields_collected()


def test_session_add_chat_message():
    session = ClaimSession(session_id="abc")
    session.add_message("user", "hello")
    session.add_message("bot", "hi there")
    assert len(session.chat_history) == 2
    assert session.chat_history[0] == {"role": "user", "content": "hello"}
    assert session.chat_history[1] == {"role": "bot", "content": "hi there"}


def test_session_store_create_and_get():
    store = SessionStore()
    session = store.create()
    assert session.session_id is not None
    retrieved = store.get(session.session_id)
    assert retrieved is session


def test_session_store_get_missing_returns_none():
    store = SessionStore()
    assert store.get("nonexistent") is None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_session.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# app/chat/session.py
import uuid
from pydantic import BaseModel, Field
from app.config import settings


class ClaimSession(BaseModel):
    session_id: str
    status: str = "collecting"
    collected_fields: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(
        default_factory=lambda: list(settings.required_claim_fields)
    )
    uploaded_documents: list[str] = Field(default_factory=list)
    pageindex_extractions: dict = Field(default_factory=dict)
    validation_result: dict | None = None
    chat_history: list[dict] = Field(default_factory=list)

    def update_field(self, field_name: str, value: str) -> None:
        self.collected_fields[field_name] = value
        if field_name in self.missing_fields:
            self.missing_fields.remove(field_name)

    def all_fields_collected(self) -> bool:
        return len(self.missing_fields) == 0

    def add_message(self, role: str, content: str) -> None:
        self.chat_history.append({"role": role, "content": content})


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, ClaimSession] = {}

    def create(self) -> ClaimSession:
        session_id = str(uuid.uuid4())
        session = ClaimSession(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> ClaimSession | None:
        return self._sessions.get(session_id)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_session.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/chat/session.py tests/test_session.py
git commit -m "feat: add ClaimSession model and SessionStore"
```

---

## Task 4: Claim Validator Adapter

**Files:**
- Create: `app/validation/validator.py`
- Create: `tests/test_validator.py`

**Step 1: Write the failing test**

```python
# tests/test_validator.py
import pytest
from app.validation.validator import ClaimValidator, ValidationResult


def test_validation_result_model():
    result = ValidationResult(
        status="pass",
        issues=[],
        recommendations=["All checks passed."],
        raw_output={},
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
    """The stub validator always returns a placeholder result."""
    validator = ClaimValidator()
    result = validator.validate(
        {
            "policy_number": "POL-123",
            "claim_type": "auto",
            "incident_date": "2026-01-15",
            "claim_amount": "5000",
            "incident_description": "Fender bender",
        }
    )
    assert isinstance(result, ValidationResult)
    assert result.status in ("pass", "fail", "needs_review")


def test_validator_validate_with_documents():
    validator = ClaimValidator()
    result = validator.validate(
        {"policy_number": "POL-123", "claim_type": "health"},
        document_extractions={"diagnosis": "flu"},
    )
    assert isinstance(result, ValidationResult)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_validator.py -v
```
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# app/validation/validator.py
from pydantic import BaseModel


class ValidationResult(BaseModel):
    status: str  # "pass", "fail", "needs_review"
    issues: list[str]
    recommendations: list[str]
    raw_output: dict


class ClaimValidator:
    """Adapter for the claim validator package.

    Replace the validate() body with your real package integration:
        from your_package import validate_claim
        result = validate_claim(fields, **kwargs)
    """

    def validate(
        self,
        fields: dict,
        document_extractions: dict | None = None,
    ) -> ValidationResult:
        # Stub implementation — replace with real package call
        issues = []
        recommendations = []

        if not fields.get("policy_number"):
            issues.append("Missing policy number")
        if not fields.get("incident_date"):
            issues.append("Missing incident date")

        amount = fields.get("claim_amount", "0")
        try:
            if float(amount) > 50000:
                issues.append("Claim amount exceeds standard threshold")
                recommendations.append("Requires manual review for high-value claims")
        except (ValueError, TypeError):
            issues.append("Invalid claim amount format")

        if issues:
            status = "needs_review" if len(issues) < 3 else "fail"
        else:
            status = "pass"
            recommendations.append("All automated checks passed.")

        return ValidationResult(
            status=status,
            issues=issues,
            recommendations=recommendations,
            raw_output={"fields_checked": list(fields.keys())},
        )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_validator.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/validation/validator.py tests/test_validator.py
git commit -m "feat: add ClaimValidator adapter with stub implementation"
```

---

## Task 5: GPT-4 Prompts

**Files:**
- Create: `app/chat/prompts.py`
- Create: `tests/test_prompts.py`

**Step 1: Write the failing test**

```python
# tests/test_prompts.py
from app.chat.prompts import (
    get_system_prompt,
    get_extraction_prompt,
    get_field_question_prompt,
)


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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_prompts.py -v
```
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# app/chat/prompts.py
from app.config import settings


def get_system_prompt() -> str:
    fields = ", ".join(settings.required_claim_fields)
    return f"""You are a friendly insurance claim validation assistant. Your job is to help users validate their insurance claims by collecting required information through natural conversation.

Required fields you need to collect: {fields}

Guidelines:
- Ask for ONE missing field at a time in a natural, conversational way
- When the user provides information, extract the relevant field value
- If the user's answer is ambiguous, ask for clarification
- Convert natural language dates (e.g., "last Tuesday") to YYYY-MM-DD format
- Be helpful and professional but concise
- When all fields are collected, confirm the data with the user before validation

Always respond with a JSON object:
{{"message": "your conversational response", "extracted_fields": {{"field_name": "value"}} }}

Only include extracted_fields if the user's message contains information for a required field."""


def get_extraction_prompt(document_text: str) -> str:
    fields = ", ".join(settings.required_claim_fields)
    return f"""Extract insurance claim information from this document text. Return a JSON object with any fields you can find.

Required fields: {fields}

Document text:
{document_text}

Return ONLY a JSON object mapping field names to their values. Only include fields you can confidently extract. Example:
{{"policy_number": "POL-12345", "claim_type": "auto", "claim_amount": "5000"}}"""


def get_field_question_prompt(missing_field: str, collected_fields: dict) -> str:
    collected_str = ", ".join(f"{k}: {v}" for k, v in collected_fields.items())
    context = f"Already collected: {collected_str}" if collected_str else "No fields collected yet"
    return f"""The user is filling out an insurance claim. {context}

Ask them naturally for: {missing_field}

Respond with a JSON object:
{{"message": "your question", "extracted_fields": {{}}}}"""
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_prompts.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/chat/prompts.py tests/test_prompts.py
git commit -m "feat: add GPT-4 system prompts for chat, extraction, and field questions"
```

---

## Task 6: PageIndex Document Processor

**Files:**
- Create: `app/documents/processor.py`
- Create: `tests/test_processor.py`

**Step 1: Write the failing test**

```python
# tests/test_processor.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
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
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_processor.py -v
```
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# app/documents/processor.py
from pageindex import PageIndexClient


class DocumentProcessor:
    def __init__(self, api_key: str):
        self.client = PageIndexClient(api_key=api_key)

    def index_document(self, pdf_path: str) -> str:
        result = self.client.submit_document(pdf_path)
        return result["doc_id"]

    def get_document_tree(self, doc_id: str) -> dict:
        result = self.client.get_tree(doc_id, node_summary=True)
        return result["result"]

    def get_document_text(self, doc_id: str) -> str:
        tree = self.get_document_tree(doc_id)
        return self._tree_to_text(tree)

    def _tree_to_text(self, node: dict, depth: int = 0) -> str:
        lines = []
        indent = "  " * depth
        title = node.get("title", "")
        summary = node.get("summary", "")
        if title:
            lines.append(f"{indent}{title}")
        if summary:
            lines.append(f"{indent}  {summary}")
        for child in node.get("children", []):
            lines.append(self._tree_to_text(child, depth + 1))
        return "\n".join(lines)
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_processor.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/documents/processor.py tests/test_processor.py
git commit -m "feat: add PageIndex document processor for indexing and tree retrieval"
```

---

## Task 7: Field Extractor

**Files:**
- Create: `app/documents/extractor.py`
- Create: `tests/test_extractor.py`

**Step 1: Write the failing test**

```python
# tests/test_extractor.py
import pytest
from unittest.mock import AsyncMock, patch
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
```

Note: Add `from unittest.mock import MagicMock` at top of file.

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_extractor.py -v
```
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# app/documents/extractor.py
import json
from openai import AsyncOpenAI
from app.chat.prompts import get_extraction_prompt
from app.config import settings


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
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {}
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_extractor.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/documents/extractor.py tests/test_extractor.py
git commit -m "feat: add FieldExtractor for LLM-based field extraction from documents"
```

---

## Task 8: Chat Controller

**Files:**
- Create: `app/chat/controller.py`
- Create: `tests/test_controller.py`

**Step 1: Write the failing test**

```python
# tests/test_controller.py
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
                content='{"message": "Got it! Policy POL-123.", "extracted_fields": {"policy_number": "POL-123"}}'
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
    assert len(session.chat_history) == 2  # user msg + bot msg


@pytest.mark.asyncio
async def test_handle_message_extracts_field(session, mock_openai_with_extraction):
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_with_extraction)

    with patch("app.chat.controller.AsyncOpenAI", return_value=mock_client):
        controller = ChatController(openai_api_key="test-key")
        response = await controller.handle_message(session, "My policy is POL-123")

    assert session.collected_fields.get("policy_number") == "POL-123"
    assert "policy_number" not in session.missing_fields


@pytest.mark.asyncio
async def test_handle_message_triggers_validation():
    session = ClaimSession(session_id="test")
    # Pre-fill all but one field
    for field in ["policy_number", "claim_type", "incident_date", "claim_amount"]:
        session.update_field(field, "test-value")

    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content='{"message": "Got it!", "extracted_fields": {"incident_description": "car crash"}}'
            )
        )
    ]
    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch("app.chat.controller.AsyncOpenAI", return_value=mock_client):
        controller = ChatController(openai_api_key="test-key")
        response = await controller.handle_message(session, "A car crash on the highway")

    assert session.status == "complete"
    assert session.validation_result is not None
    assert response["type"] == "validation_result"


def test_get_welcome_message():
    controller = ChatController(openai_api_key="test-key")
    msg = controller.get_welcome_message()
    assert "claim" in msg["content"].lower()
    assert msg["type"] == "bot_message"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_controller.py -v
```
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# app/chat/controller.py
import json
from openai import AsyncOpenAI
from app.chat.session import ClaimSession
from app.chat.prompts import get_system_prompt
from app.validation.validator import ClaimValidator
from app.config import settings


class ChatController:
    def __init__(self, openai_api_key: str | None = None):
        self.openai = AsyncOpenAI(api_key=openai_api_key or settings.openai_api_key)
        self.validator = ClaimValidator()

    def get_welcome_message(self) -> dict:
        return {
            "type": "bot_message",
            "content": (
                "Welcome! I can help you validate your insurance claim. "
                "You can upload a claim document (PDF) or tell me about your claim, "
                "and I'll guide you through the process."
            ),
        }

    async def handle_message(self, session: ClaimSession, user_message: str) -> dict:
        session.add_message("user", user_message)

        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "system", "content": self._build_state_context(session)},
        ]
        for msg in session.chat_history:
            role = "user" if msg["role"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["content"]})

        response = await self.openai.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.3,
        )

        content = response.choices[0].message.content.strip()
        parsed = self._parse_response(content)

        bot_message = parsed.get("message", content)
        extracted = parsed.get("extracted_fields", {})

        for field, value in extracted.items():
            if field in session.missing_fields:
                session.update_field(field, value)

        session.add_message("bot", bot_message)

        if session.all_fields_collected():
            return self._run_validation(session, bot_message)

        return {"type": "bot_message", "content": bot_message}

    async def handle_document_upload(
        self, session: ClaimSession, extracted_fields: dict
    ) -> dict:
        for field, value in extracted_fields.items():
            if field in session.missing_fields:
                session.update_field(field, value)
        session.pageindex_extractions.update(extracted_fields)

        if extracted_fields:
            summary = ", ".join(f"{k}: {v}" for k, v in extracted_fields.items())
            msg = f"I extracted the following from your document: {summary}."
            if session.missing_fields:
                next_field = session.missing_fields[0]
                msg += f" I still need your {next_field.replace('_', ' ')}."
        else:
            msg = "I couldn't extract claim details from this document. Let's fill in the information manually."

        session.add_message("bot", msg)

        if session.all_fields_collected():
            return self._run_validation(session, msg)

        return {"type": "bot_message", "content": msg}

    def _run_validation(self, session: ClaimSession, preceding_message: str) -> dict:
        session.status = "validating"
        result = self.validator.validate(
            session.collected_fields,
            document_extractions=session.pageindex_extractions or None,
        )
        session.validation_result = result.model_dump()
        session.status = "complete"

        return {
            "type": "validation_result",
            "content": preceding_message,
            "result": session.validation_result,
        }

    def _build_state_context(self, session: ClaimSession) -> str:
        collected = ", ".join(f"{k}: {v}" for k, v in session.collected_fields.items())
        missing = ", ".join(session.missing_fields)
        return f"Collected so far: {collected or 'none'}. Still need: {missing or 'none'}."

    def _parse_response(self, content: str) -> dict:
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"message": content, "extracted_fields": {}}
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_controller.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/chat/controller.py tests/test_controller.py
git commit -m "feat: add ChatController with message handling, extraction, and validation"
```

---

## Task 9: FastAPI Application

**Files:**
- Create: `app/main.py`
- Create: `tests/test_main.py`

**Step 1: Write the failing test**

```python
# tests/test_main.py
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_root_serves_html():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_upload_no_file_returns_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/upload")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_session_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/session/nonexistent")
    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_main.py -v
```
Expected: FAIL

**Step 3: Write minimal implementation**

```python
# app/main.py
import os
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.chat.session import SessionStore
from app.chat.controller import ChatController
from app.documents.processor import DocumentProcessor
from app.documents.extractor import FieldExtractor

app = FastAPI(title="Claim Validator Chatbot")

session_store = SessionStore()
chat_controller = ChatController()

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), session_id: str = ""):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    os.makedirs(settings.upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "doc.pdf")[1]
    file_path = os.path.join(settings.upload_dir, f"{file_id}{ext}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    session.uploaded_documents.append(file_path)

    extracted_fields = {}
    try:
        processor = DocumentProcessor(api_key=settings.pageindex_api_key)
        doc_id = processor.index_document(file_path)
        doc_text = processor.get_document_text(doc_id)

        extractor = FieldExtractor()
        extracted_fields = await extractor.extract_fields(doc_text)
    except Exception:
        pass  # Fall back to manual entry

    response = await chat_controller.handle_document_upload(session, extracted_fields)
    return {"file_id": file_id, "response": response}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    session = session_store.create()

    welcome = chat_controller.get_welcome_message()
    await websocket.send_json({
        "type": welcome["type"],
        "content": welcome["content"],
        "session_id": session.session_id,
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                response = await chat_controller.handle_message(
                    session, data.get("content", "")
                )
                await websocket.send_json(response)

            elif msg_type == "upload_complete":
                file_id = data.get("file_id", "")
                await websocket.send_json({
                    "type": "bot_message",
                    "content": "Document received! Analyzing...",
                })

    except WebSocketDisconnect:
        pass
```

**Step 4: Create a minimal static/index.html placeholder so tests pass**

```html
<!-- app/static/index.html -->
<!DOCTYPE html>
<html><head><title>Claim Validator</title></head><body>Loading...</body></html>
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_main.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add app/main.py tests/test_main.py app/static/index.html
git commit -m "feat: add FastAPI app with WebSocket chat, file upload, and session endpoints"
```

---

## Task 10: Chat Frontend

**Files:**
- Modify: `app/static/index.html` (replace placeholder)
- Create: `app/static/style.css`
- Create: `app/static/chat.js`

**Step 1: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claim Validator Chatbot</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h1>Insurance Claim Validator</h1>
        </div>
        <div id="chat-messages" class="chat-messages"></div>
        <div class="chat-input-area">
            <div class="upload-bar">
                <label for="file-upload" class="upload-btn" title="Upload claim document">
                    📎
                    <input type="file" id="file-upload" accept=".pdf,.png,.jpg,.jpeg" hidden>
                </label>
                <span id="file-name" class="file-name"></span>
            </div>
            <div class="input-row">
                <input type="text" id="message-input" placeholder="Type your message..." autocomplete="off">
                <button id="send-btn">Send</button>
            </div>
        </div>
    </div>
    <script src="/static/chat.js"></script>
</body>
</html>
```

**Step 2: Write style.css**

```css
/* app/static/style.css */
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f0f2f5;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
}

.chat-container {
    width: 100%;
    max-width: 700px;
    height: 90vh;
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.1);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.chat-header {
    background: #2563eb;
    color: #fff;
    padding: 16px 20px;
}

.chat-header h1 {
    font-size: 18px;
    font-weight: 600;
}

.chat-messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.message {
    max-width: 80%;
    padding: 10px 16px;
    border-radius: 16px;
    line-height: 1.5;
    font-size: 14px;
    word-wrap: break-word;
}

.message.user {
    align-self: flex-end;
    background: #2563eb;
    color: #fff;
    border-bottom-right-radius: 4px;
}

.message.bot {
    align-self: flex-start;
    background: #f0f2f5;
    color: #1a1a1a;
    border-bottom-left-radius: 4px;
}

.message.validation {
    align-self: flex-start;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    max-width: 90%;
}

.validation-header {
    font-weight: 600;
    padding: 8px 0;
    font-size: 15px;
}

.validation-header.pass { color: #16a34a; }
.validation-header.fail { color: #dc2626; }
.validation-header.needs_review { color: #d97706; }

.validation-issues, .validation-recommendations {
    margin: 6px 0;
    padding-left: 16px;
    font-size: 13px;
}

.validation-issues li { color: #dc2626; }
.validation-recommendations li { color: #4b5563; }

.chat-input-area {
    border-top: 1px solid #e5e7eb;
    padding: 12px 16px;
}

.upload-bar {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}

.upload-btn {
    cursor: pointer;
    font-size: 20px;
    padding: 4px;
}

.file-name {
    font-size: 12px;
    color: #6b7280;
}

.input-row {
    display: flex;
    gap: 8px;
}

#message-input {
    flex: 1;
    padding: 10px 16px;
    border: 1px solid #d1d5db;
    border-radius: 24px;
    font-size: 14px;
    outline: none;
}

#message-input:focus {
    border-color: #2563eb;
}

#send-btn {
    padding: 10px 20px;
    background: #2563eb;
    color: #fff;
    border: none;
    border-radius: 24px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 500;
}

#send-btn:hover { background: #1d4ed8; }
#send-btn:disabled { background: #93c5fd; cursor: not-allowed; }

.typing-indicator {
    align-self: flex-start;
    padding: 10px 16px;
    background: #f0f2f5;
    border-radius: 16px;
    font-size: 14px;
    color: #6b7280;
}
```

**Step 3: Write chat.js**

```javascript
// app/static/chat.js
const messagesDiv = document.getElementById("chat-messages");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const fileUpload = document.getElementById("file-upload");
const fileName = document.getElementById("file-name");

let ws = null;
let sessionId = null;

function connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);

    ws.onopen = () => {
        sendBtn.disabled = false;
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.session_id) {
            sessionId = data.session_id;
        }
        removeTypingIndicator();

        if (data.type === "bot_message") {
            addMessage(data.content, "bot");
        } else if (data.type === "validation_result") {
            if (data.content) {
                addMessage(data.content, "bot");
            }
            addValidationResult(data.result);
        } else if (data.type === "extraction_result") {
            addMessage("Extracted fields from your document.", "bot");
        }
    };

    ws.onclose = () => {
        sendBtn.disabled = true;
        addMessage("Connection lost. Please refresh the page.", "bot");
    };
}

function addMessage(text, role) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.textContent = text;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function addValidationResult(result) {
    const div = document.createElement("div");
    div.classList.add("message", "validation");

    const statusLabel = {
        pass: "Claim Validated Successfully",
        fail: "Claim Validation Failed",
        needs_review: "Claim Needs Review",
    };

    let html = `<div class="validation-header ${result.status}">${statusLabel[result.status] || result.status}</div>`;

    if (result.issues && result.issues.length > 0) {
        html += `<div><strong>Issues:</strong><ul class="validation-issues">`;
        result.issues.forEach((issue) => {
            html += `<li>${escapeHtml(issue)}</li>`;
        });
        html += `</ul></div>`;
    }

    if (result.recommendations && result.recommendations.length > 0) {
        html += `<div><strong>Recommendations:</strong><ul class="validation-recommendations">`;
        result.recommendations.forEach((rec) => {
            html += `<li>${escapeHtml(rec)}</li>`;
        });
        html += `</ul></div>`;
    }

    div.innerHTML = html;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function showTypingIndicator() {
    const div = document.createElement("div");
    div.classList.add("typing-indicator");
    div.id = "typing";
    div.textContent = "Thinking...";
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById("typing");
    if (el) el.remove();
}

function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    addMessage(text, "user");
    ws.send(JSON.stringify({ type: "message", content: text }));
    messageInput.value = "";
    showTypingIndicator();
}

async function uploadFile(file) {
    if (!sessionId) return;

    fileName.textContent = `Uploading: ${file.name}...`;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", sessionId);

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();
        fileName.textContent = `Uploaded: ${file.name}`;

        if (data.response) {
            if (data.response.type === "validation_result") {
                addMessage(data.response.content, "bot");
                addValidationResult(data.response.result);
            } else {
                addMessage(data.response.content, "bot");
            }
        }
    } catch (err) {
        fileName.textContent = "Upload failed";
        addMessage("Failed to upload document. Please try again.", "bot");
    }
}

// Event listeners
sendBtn.addEventListener("click", sendMessage);

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

fileUpload.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) uploadFile(file);
    e.target.value = "";
});

// Connect on load
connect();
```

**Step 4: Manually verify by opening browser**

```bash
cd /home/lnv-20/Documents/chatbot
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 — verify chat UI loads, WebSocket connects, messages render.

**Step 5: Commit**

```bash
git add app/static/
git commit -m "feat: add chat frontend with WebSocket messaging, file upload, and validation display"
```

---

## Task 11: Run All Tests

**Files:** None (verification only)

**Step 1: Run full test suite**

```bash
pytest tests/ -v
```
Expected: All tests PASS

**Step 2: If any failures, fix and re-run**

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve test failures from integration"
```

---

## Task 12: End-to-End Manual Test

**Files:** None (verification only)

**Step 1: Create .env with real keys**

```bash
cp .env.example .env
# Edit .env with real OPENAI_API_KEY and PAGEINDEX_API_KEY
```

**Step 2: Start the server**

```bash
uvicorn app.main:app --reload --port 8000
```

**Step 3: Test conversation flow**

1. Open http://localhost:8000
2. Verify welcome message appears
3. Type "My policy number is POL-12345" — verify bot extracts it and asks next question
4. Continue providing: claim_type, incident_date, claim_amount, incident_description
5. Verify validation results display after all fields collected

**Step 4: Test document upload**

1. Upload a sample PDF claim document
2. Verify PageIndex processes it and fields are extracted
3. Verify bot asks only for remaining missing fields

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: complete MVP implementation of claim validator chatbot"
```
