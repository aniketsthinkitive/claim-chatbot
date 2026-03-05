import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    pageindex_api_key: str = os.getenv("PAGEINDEX_API_KEY", "")
    openai_model: str = "gpt-4o"
    upload_dir: str = "uploads"

    # Clearinghouse config (passed through to claim-validator library)
    # Using default_factory so env vars are read at instantiation time, not class definition time
    clearinghouse_provider: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_PROVIDER", ""))
    waystar_api_key: str = Field(default_factory=lambda: os.getenv("WAYSTAR_API_KEY", ""))
    waystar_secret: str = Field(default_factory=lambda: os.getenv("WAYSTAR_SECRET", ""))
    waystar_user_id: str = Field(default_factory=lambda: os.getenv("WAYSTAR_USER_ID", ""))
    waystar_password: str = Field(default_factory=lambda: os.getenv("WAYSTAR_PASSWORD", ""))
    waystar_cust_id: str = Field(default_factory=lambda: os.getenv("WAYSTAR_CUST_ID", ""))

    # AI config for claim-validator's AI validation phase
    ai_provider: str = Field(default_factory=lambda: os.getenv("AI_PROVIDER", ""))
    ai_api_key: str = Field(default_factory=lambda: os.getenv("AI_API_KEY", ""))
    ai_model: str = Field(default_factory=lambda: os.getenv("AI_MODEL", ""))

    @property
    def clearinghouse_config(self) -> dict | None:
        """Build clearinghouse config dict for claim-validator, or None if not configured."""
        if not self.clearinghouse_provider:
            return None
        return {
            "provider": self.clearinghouse_provider,
            "api_key": self.waystar_api_key,
            "secret": self.waystar_secret,
            "user_id": self.waystar_user_id,
            "password": self.waystar_password,
            "cust_id": self.waystar_cust_id,
        }

    @property
    def ai_config(self) -> dict | None:
        """Build AI config dict for claim-validator, or None if not configured."""
        if not self.ai_provider:
            return None
        return {
            "provider": self.ai_provider,
            "api_key": self.ai_api_key or self.openai_api_key,
            "model": self.ai_model,
        }

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
