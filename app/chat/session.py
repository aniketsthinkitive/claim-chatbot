import uuid

from pydantic import BaseModel, Field

from app.config import settings


class ClaimSession(BaseModel):
    session_id: str
    status: str = "collecting"
    collected_fields: dict = Field(default_factory=dict)
    missing_fields: list[str] = Field(
        default_factory=lambda: list(settings.required_claim_fields)
    )
    uploaded_documents: list[str] = Field(default_factory=list)
    pageindex_extractions: dict = Field(default_factory=dict)
    validation_result: dict | None = None
    chat_history: list[dict] = Field(default_factory=list)

    def update_field(self, field_name: str, value) -> None:
        self.collected_fields[field_name] = value
        if field_name in self.missing_fields:
            self.missing_fields.remove(field_name)

    def all_fields_collected(self) -> bool:
        return len(self.missing_fields) == 0

    def add_message(self, role: str, content: str) -> None:
        self.chat_history.append({"role": role, "content": content})

    def build_claim_payload(self) -> dict:
        """Build the final ClaimMD API payload from collected fields."""
        f = self.collected_fields

        diagnosis_codes = f.get("diagnosis_codes", [])
        lines = f.get("service_lines", [])

        # Ensure place_of_service is on each line
        default_pos = f.get("place_of_service", "11")
        for line in lines:
            if "place_of_service" not in line:
                line["place_of_service"] = default_pos

        return {
            "billing_provider_npi": f.get("billing_provider_npi", ""),
            "billing_provider_taxonomy": f.get("billing_provider_taxonomy", ""),
            "subscriber_id": f.get("subscriber_id", ""),
            "subscriber_first_name": f.get("subscriber_first_name", ""),
            "subscriber_last_name": f.get("subscriber_last_name", ""),
            "subscriber_dob": f.get("subscriber_dob", ""),
            "subscriber_gender": f.get("subscriber_gender", ""),
            "patient_first_name": f.get("patient_first_name", ""),
            "patient_last_name": f.get("patient_last_name", ""),
            "patient_dob": f.get("patient_dob", ""),
            "patient_gender": f.get("patient_gender", ""),
            "patient_relationship": f.get("patient_relationship", ""),
            "payer_id": f.get("payer_id", ""),
            "payer_name": f.get("payer_name", ""),
            "claim_type": f.get("claim_type", ""),
            "place_of_service": default_pos,
            "total_charge": float(f.get("total_charge", 0)),
            "diagnosis_codes": diagnosis_codes,
            "lines": lines,
        }


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, ClaimSession] = {}

    def create(self) -> ClaimSession:
        session_id = str(uuid.uuid4())
        session = ClaimSession(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> ClaimSession | None:
        return self._sessions.get(session_id)
