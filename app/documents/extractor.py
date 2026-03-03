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
