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
    clearinghouse_provider: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_PROVIDER", ""))
    clearinghouse_api_key: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_API_KEY", ""))
    clearinghouse_secret: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_SECRET", ""))
    clearinghouse_user_id: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_USER_ID", ""))
    clearinghouse_password: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_PASSWORD", ""))
    clearinghouse_cust_id: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_CUST_ID", ""))
    clearinghouse_base_url: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_BASE_URL", ""))
    clearinghouse_eligibility_base_url: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_ELIGIBILITY_BASE_URL", ""))
    clearinghouse_prior_auth_base_url: str = Field(default_factory=lambda: os.getenv("CLEARINGHOUSE_PRIOR_AUTH_BASE_URL", ""))

    # AI config for claim-validator's AI validation phase
    ai_provider: str = Field(default_factory=lambda: os.getenv("CLAIM_VALIDATOR_AI_PROVIDER", ""))
    ai_api_key: str = Field(default_factory=lambda: os.getenv("CLAIM_VALIDATOR_AI_API_KEY", ""))
    ai_model: str = Field(default_factory=lambda: os.getenv("CLAIM_VALIDATOR_AI_MODEL", ""))

    @property
    def clearinghouse_config(self) -> dict | None:
        """Build clearinghouse config dict for claim-validator, or None if not configured."""
        if not self.clearinghouse_provider:
            return None
        config: dict = {
            "provider": self.clearinghouse_provider,
            "api_key": self.clearinghouse_api_key,
            "user_id": self.clearinghouse_user_id,
            "password": self.clearinghouse_password,
            "cust_id": self.clearinghouse_cust_id,
        }
        if self.clearinghouse_secret:
            config["secret"] = self.clearinghouse_secret
        if self.clearinghouse_base_url:
            config["base_url"] = self.clearinghouse_base_url
        if self.clearinghouse_eligibility_base_url:
            config["eligibility_base_url"] = self.clearinghouse_eligibility_base_url
        if self.clearinghouse_prior_auth_base_url:
            config["prior_auth_base_url"] = self.clearinghouse_prior_auth_base_url
        return config

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
