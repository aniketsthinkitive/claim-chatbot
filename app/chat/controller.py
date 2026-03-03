import json

from openai import AsyncOpenAI

from app.chat.prompts import get_system_prompt
from app.chat.session import ClaimSession
from app.config import settings
from app.validation.validator import ClaimValidator


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
            msg = (
                "I couldn't extract claim details from this document. "
                "Let's fill in the information manually."
            )

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
        collected = ", ".join(
            f"{k}: {v}" for k, v in session.collected_fields.items()
        )
        missing = ", ".join(session.missing_fields)
        return (
            f"Collected so far: {collected or 'none'}. "
            f"Still need: {missing or 'none'}."
        )

    def _parse_response(self, content: str) -> dict:
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return {"message": content, "extracted_fields": {}}
