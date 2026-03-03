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
