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
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

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
