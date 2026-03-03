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

    def update_field(self, field_name: str, value: str) -> None:
        self.collected_fields[field_name] = value
        if field_name in self.missing_fields:
            self.missing_fields.remove(field_name)

    def all_fields_collected(self) -> bool:
        return len(self.missing_fields) == 0

    def add_message(self, role: str, content: str) -> None:
        self.chat_history.append({"role": role, "content": content})


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
