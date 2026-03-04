import os

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    pageindex_api_key: str = os.getenv("PAGEINDEX_API_KEY", "")
    openai_model: str = "gpt-4o"
    upload_dir: str = "uploads"

    # Fields collected from the patient/user in conversation order
    required_claim_fields: list[str] = [
        # Subscriber info
        "subscriber_first_name",
        "subscriber_last_name",
        "subscriber_dob",
        "subscriber_gender",
        "subscriber_id",
        # Patient relationship
        "patient_relationship",
        # Patient info (may be copied from subscriber if relationship=self)
        "patient_first_name",
        "patient_last_name",
        "patient_dob",
        "patient_gender",
        # Payer info
        "payer_name",
        "payer_id",
        # Billing provider
        "billing_provider_npi",
        "billing_provider_taxonomy",
        # Claim details
        "claim_type",
        "place_of_service",
        "total_charge",
        # Diagnosis
        "diagnosis_codes",
        # Service lines
        "service_lines",
    ]


settings = Settings()
