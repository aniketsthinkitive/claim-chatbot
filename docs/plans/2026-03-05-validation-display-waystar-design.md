# Design: Fix Validation Display + Waystar Submission Response

**Date:** 2026-03-05
**Status:** Approved

## Problem

1. Validation results do not appear in the chatbot after all fields are collected.
2. Waystar submission response is not shown because (a) `WaystarClient.submit_claim()` is unimplemented and (b) the chatbot does not pass `clearinghouse_config` to the library.

## Principle

The chatbot is a thin UI layer. It collects data and displays results. All validation and submission logic lives in the claim-validator library.

## Flow

```
User provides claim data (chat + PDF)
  → Chatbot calls claim-validator validate(payload, clearinghouse_config=...)
    → Library Phase 1: Rule-based validators
    → Library Phase 2: Clearinghouse submit (Waystar)
    → Library Phase 3: Deidentify → AI validators
  → Library returns PipelineResult
  → Chatbot displays the full result (findings + clearinghouse response)
```

## Changes

### 1. claim-validator: Implement `WaystarClient.submit_claim()`

**File:** `claim-validator/src/claim_validator/clearinghouse/providers/waystar.py`

Replace the placeholder `submit_claim()` with a real implementation that calls the Waystar claim submission endpoint. Follow existing patterns (auth, retry, error mapping). Return `SubmissionResult`.

### 2. chatbot/app/config.py: Add clearinghouse config

Add env vars for clearinghouse provider and credentials so they can be passed to `validate()`:
- `CLEARINGHOUSE_PROVIDER` (default: "waystar")
- `WAYSTAR_API_KEY`, `WAYSTAR_SECRET`, `WAYSTAR_USER_ID`, `WAYSTAR_PASSWORD`, `WAYSTAR_CUST_ID`

### 3. chatbot/app/validation/validator.py: Fix and simplify

- Fix `claim_validator` import handling (resolve Pylance errors).
- Pass `clearinghouse_config` through to `validate()` so the library's Phase 2 runs.
- Ensure `_fallback_validate()` always returns a valid result.
- Add logging at each step for debugging.

### 4. chatbot/app/chat/controller.py: Fix `_build_summary()`

- Ensure `validation_result` type message is always sent to the frontend.
- Add error logging so failures are visible.
- Include clearinghouse response data from `PipelineResult` in the result payload.

### 5. chatbot/app/static/chat.js: Fix and enhance display

- Fix `addValidationResult()` to handle all pipeline result shapes.
- Add display section for clearinghouse submission data (status, reference_id, errors) when present in the result.
- Handle edge cases: empty findings, missing fields, error states.

### 6. chatbot/app/static/style.css: Submission result styles

- Styles for clearinghouse response section within the validation result display.

## Out of Scope

- No submission logic in the chatbot itself.
- No new WebSocket message types for submission (everything comes back in `validation_result`).
- No changes to the chat conversation flow or field collection.
