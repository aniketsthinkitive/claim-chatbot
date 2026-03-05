import json
import logging

from openai import AsyncOpenAI

from app.chat.prompts import get_system_prompt
from app.chat.session import ClaimSession
from app.config import settings
from app.validation.validator import check_eligibility, validate_claim

logger = logging.getLogger(__name__)


class ChatController:
    def __init__(self, openai_api_key: str | None = None):
        self.openai = AsyncOpenAI(api_key=openai_api_key or settings.openai_api_key)

    def get_welcome_message(self) -> dict:
        return {
            "type": "bot_message",
            "content": (
                "Welcome! I'm your insurance claim assistant. I'll help you collect "
                "all the information needed to submit your claim to the clearing house.\n\n"
                "Let's start with the insurance subscriber's information. "
                "Could you please provide the subscriber's first and last name?"
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
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content.strip()
        parsed = self._parse_response(content)
        bot_message = parsed.get("message", content)
        extracted = parsed.get("extracted_fields", {})

        # Handle patient_relationship=self: auto-copy subscriber fields to patient
        if extracted.get("patient_relationship", "").lower() == "self":
            for sub_field, pat_field in [
                ("subscriber_first_name", "patient_first_name"),
                ("subscriber_last_name", "patient_last_name"),
                ("subscriber_dob", "patient_dob"),
                ("subscriber_gender", "patient_gender"),
            ]:
                val = session.collected_fields.get(sub_field) or extracted.get(sub_field)
                if val:
                    extracted[pat_field] = val

        for field, value in extracted.items():
            if field in session.missing_fields:
                session.update_field(field, value)

        session.add_message("bot", bot_message)

        if session.all_fields_collected():
            return self._build_summary(session, bot_message)

        logger.debug(
            "Fields still missing after extraction: %s (extracted: %s)",
            session.missing_fields,
            list(extracted.keys()),
        )
        return {"type": "bot_message", "content": bot_message}

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

    def _build_summary(self, session: ClaimSession, preceding_message: str) -> dict:
        """Build and return the validation result for the frontend."""
        session.status = "confirming"
        payload = session.build_claim_payload()

        # Check eligibility first (if clearinghouse configured)
        eligibility = None
        if settings.clearinghouse_config:
            eligibility = check_eligibility(payload, settings.clearinghouse_config)

        result = validate_claim(
            payload,
            ai_config=settings.ai_config,
        )
        session.validation_result = result

        response = {
            "type": "validation_result",
            "content": preceding_message,
            "result": result,
            "claim_payload": payload,
        }
        if eligibility:
            response["eligibility"] = eligibility
        return response

    def _build_state_context(self, session: ClaimSession) -> str:
        collected_parts = []
        for k, v in session.collected_fields.items():
            if isinstance(v, (list, dict)):
                collected_parts.append(f"{k}: {json.dumps(v)}")
            else:
                collected_parts.append(f"{k}: {v}")
        collected = ", ".join(collected_parts) if collected_parts else "none"

        missing = ", ".join(session.missing_fields) if session.missing_fields else "none"
        return (
            f"Collected so far: {collected}. "
            f"Still need: {missing}."
        )

    def _parse_response(self, content: str) -> dict:
        # 1. Try direct JSON parse
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

        # 2. Try JSON inside ```json ... ``` or ``` ... ``` code blocks
        for marker in ("```json", "```"):
            if marker in content:
                try:
                    start = content.index(marker) + len(marker)
                    end = content.index("```", start)
                    return json.loads(content[start:end].strip())
                except (json.JSONDecodeError, ValueError, IndexError):
                    pass

        # 3. Try to find a JSON object anywhere in the response (handles
        #    cases where OpenAI prefixes/suffixes plain text around JSON)
        brace_start = content.find("{")
        if brace_start != -1:
            # Find the matching closing brace by scanning from the end
            brace_end = content.rfind("}")
            if brace_end > brace_start:
                try:
                    return json.loads(content[brace_start : brace_end + 1])
                except (json.JSONDecodeError, ValueError):
                    pass

        logger.warning("Could not parse JSON from OpenAI response: %.200s", content)
        return {"message": content, "extracted_fields": {}}
