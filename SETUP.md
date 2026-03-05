# Claim Chatbot — Setup Guide

## Prerequisites

- Python 3.12+
- Git

## 1. Clone Both Repos

```bash
# Chatbot
git clone git@github.com:aniketsthinkitive/claim-chatbot.git
cd claim-chatbot

# Claim Validator (separate repo — required dependency)
cd ..
git clone git@github.com:aniket4206/claim-validator.git
```

Your folder structure should look like:

```
Documents/
  claim-chatbot/        # This project
  claim-validator/
    claim-validator/     # The library (has pyproject.toml)
```

## 2. Create Virtual Environment

```bash
cd claim-chatbot
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
```

## 3. Install Dependencies

```bash
# Install chatbot dependencies
pip install -r requirements.txt

# Install claim-validator in editable mode (from local clone)
pip install -e ../claim-validator/claim-validator
```

## 4. Configure Environment

Copy the example below to `.env` in the chatbot root and fill in your keys:

```env
# OpenAI (required — powers the chat)
OPENAI_API_KEY=sk-proj-your-key-here
PAGEINDEX_API_KEY=your-pageindex-key

# Clearinghouse / Waystar (required for eligibility checks)
CLEARINGHOUSE_PROVIDER=waystar
CLEARINGHOUSE_API_KEY=your-waystar-api-key
CLEARINGHOUSE_USER_ID=your-user-id
CLEARINGHOUSE_PASSWORD=your-password
CLEARINGHOUSE_CUST_ID=your-cust-id
CLEARINGHOUSE_BASE_URL=https://claimsapi.zirmed.com
CLEARINGHOUSE_ELIGIBILITY_BASE_URL=https://eligibilityapi.zirmed.com
CLEARINGHOUSE_PRIOR_AUTH_BASE_URL=https://priorauthorizationapi.waystar.com

# AI validation phase (optional — adds AI-powered claim checks)
CLAIM_VALIDATOR_AI_PROVIDER=openai
CLAIM_VALIDATOR_AI_API_KEY=sk-proj-your-key-here
CLAIM_VALIDATOR_AI_MODEL=gpt-4o
```

## 5. Run Tests

```bash
# All tests (includes live Waystar API tests if creds configured)
python -m pytest tests/ -v

# Quick eligibility test
python scripts/test_eligibility.py
```

## 6. Start the Server

```bash
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in your browser.

## How It Works

1. **Chat** — User enters claim fields via conversation or uploads a PDF
2. **Eligibility** — Checks patient eligibility with Waystar (270/271)
3. **Validation** — Runs 8 rule-based validators via claim-validator library
4. **Results** — Shows eligibility status + validation findings in the UI

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: claim_validator` | Run `pip install -e ../claim-validator/claim-validator` |
| `OPENAI_API_KEY` error | Check `.env` file exists and has valid key |
| Eligibility shows "unavailable" | Check `CLEARINGHOUSE_*` vars in `.env` |
| Tests skip Waystar tests | Set `CLEARINGHOUSE_API_KEY` in `.env` |
