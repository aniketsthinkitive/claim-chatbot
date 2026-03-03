# Insurance Claim Validator Chatbot — Design Document

**Date:** 2026-03-03
**Status:** Approved

## Problem

Users need to validate insurance claims but the process requires collecting structured data and parsing claim documents. A conversational interface makes this accessible — the chatbot gathers data through natural dialogue, extracts information from uploaded documents, and runs validation automatically.

## Architecture

**Approach:** Monolithic FastAPI application with an HTML/JS chat frontend.

```
Browser (HTML/CSS/JS Chat UI)
    │
    │  WebSocket + REST
    ▼
FastAPI Backend
    ├── Chat Controller (conversation orchestration)
    ├── OpenAI GPT-4 (natural language understanding)
    ├── PageIndex (document indexing + extraction)
    └── Claim Validator (your pip package)
```

### Components

| Component | Role |
|-----------|------|
| Chat UI | Browser-based chat interface with file upload |
| Chat Controller | Tracks conversation state, determines missing fields, orchestrates flow |
| OpenAI GPT-4 | Powers conversational questions and understands free-form user responses |
| PageIndex | Indexes uploaded claim documents (PDFs), extracts structured data via tree-based reasoning |
| Claim Validator | Your existing pip package — called once all required data is collected |

## Conversation Flow

1. User opens chat
2. Bot welcomes user, asks if they have a document or want to enter details manually
3. If document uploaded: PageIndex indexes it, extracts fields, shows what it found
4. Bot asks for any missing required fields one at a time
5. Once all data collected: bot runs claim validator
6. Bot displays validation results (pass/fail/needs review, issues, recommendations)

Key behaviors:
- PageIndex extracts what it can from documents; bot asks only for missing fields
- GPT-4 makes questions natural and parses free-form answers (e.g., "last Tuesday" → date)
- Users can correct extracted data before validation runs

## API Design

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Serve chat UI |
| WS | `/ws/chat` | Real-time chat via WebSocket |
| POST | `/api/upload` | Upload claim documents (PDF/images) |
| GET | `/api/session/{id}` | Get session state |

### WebSocket Messages

```
Client → Server:
  {"type": "message", "content": "..."}
  {"type": "upload_complete", "file_id": "..."}

Server → Client:
  {"type": "bot_message", "content": "..."}
  {"type": "extraction_result", "fields": {...}}
  {"type": "validation_result", "status": "...", "details": {...}}
```

## Data Model

```python
class ClaimSession:
    session_id: str
    status: str  # "collecting", "validating", "complete"
    collected_fields: dict
    missing_fields: list[str]
    uploaded_documents: list[str]
    pageindex_extractions: dict
    validation_result: dict | None
    chat_history: list[dict]

REQUIRED_FIELDS = [
    "policy_number",
    "claim_type",
    "incident_date",
    "claim_amount",
    "incident_description",
]
```

## Project Structure

```
chatbot/
├── app/
│   ├── main.py              # FastAPI app, routes, WebSocket
│   ├── config.py            # Settings
│   ├── chat/
│   │   ├── controller.py    # Conversation orchestration
│   │   ├── session.py       # Session model and storage
│   │   └── prompts.py       # GPT-4 system prompts
│   ├── documents/
│   │   ├── processor.py     # PageIndex integration
│   │   └── extractor.py     # Field extraction from PageIndex results
│   ├── validation/
│   │   └── validator.py     # Adapter for claim validator package
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── chat.js
├── uploads/
├── requirements.txt
├── .env
└── .gitignore
```

## Tech Stack

- Python 3.11+, FastAPI, uvicorn, WebSockets
- OpenAI GPT-4 via `openai` SDK
- PageIndex (vendored from GitHub)
- Claim validator (pip package, pluggable adapter)
- Vanilla HTML/CSS/JS frontend
- In-memory session storage (MVP)

## Design Decisions

- **PageIndex vendored** — not on PyPI, clone into project and import directly
- **Pluggable validator** — adapter pattern so the real package plugs in with minimal changes
- **In-memory sessions** — no DB overhead for MVP; upgrade to Redis/DB later
- **No auth for MVP** — add when needed
- **WebSocket for chat** — real-time messaging without polling
