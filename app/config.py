import os

from dotenv import load_dotenv
from pydantic import BaseModel

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
