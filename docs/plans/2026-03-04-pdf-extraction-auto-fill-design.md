# PDF Auto-Extraction for ClaimMD Fields

## Problem
When a user uploads a PDF containing insurance claim data, the chatbot should extract all available fields automatically using PageIndex + LLM and only ask the user for missing fields. Currently the extraction prompt is generic and doesn't target ClaimMD fields, and the upload response doesn't clearly show what was extracted.

## Design

### 1. DocumentProcessor — Add OCR support
- Add `get_document_ocr(doc_id)` method using `client.get_ocr(doc_id, format="raw")`
- Combine tree text (structural) + OCR text (raw content) for maximum extraction context
- Tree gives hierarchy; OCR gives exact values (NPI numbers, dates, codes)

### 2. Extraction Prompt — ClaimMD-aware
- Rewrite `get_extraction_prompt()` to list every ClaimMD field with exact expected format
- Include examples for complex nested fields (diagnosis_codes, service_lines)
- Instruct LLM to return exact JSON structure matching ClaimMD API payload

### 3. FieldExtractor — Robust JSON parsing
- Handle JSON wrapped in markdown code blocks
- Handle partial extraction (return what was found)

### 4. Upload Endpoint — Combine tree + OCR
- Pass both tree text and OCR raw text to extractor
- Add error logging instead of silent `pass`

### 5. Controller — Rich extraction summary
- `handle_document_upload()` shows grouped summary of all extracted fields
- Identifies missing fields and asks for first one
- If all fields extracted, proceed directly to validation

### Files Changed
| File | Change |
|------|--------|
| `app/documents/processor.py` | Add `get_document_ocr()` |
| `app/chat/prompts.py` | Rewrite `get_extraction_prompt()` |
| `app/documents/extractor.py` | Robust JSON parsing |
| `app/main.py` | Combine tree+OCR, add logging |
| `app/chat/controller.py` | Rich extraction summary |

### UX Flow
1. User uploads PDF
2. PageIndex processes document (tree + OCR)
3. LLM extracts all ClaimMD fields from combined text
4. Bot shows summary: "I extracted the following from your document:" with grouped fields
5. If missing fields remain: "I still need the following: ..." and asks for first one
6. If all fields found: proceed to validation/confirmation
