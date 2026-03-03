from app.chat.session import ClaimSession, SessionStore


def test_claim_session_defaults():
    session = ClaimSession(session_id="abc")
    assert session.session_id == "abc"
    assert session.status == "collecting"
    assert session.collected_fields == {}
    assert session.missing_fields == [
        "policy_number",
        "claim_type",
        "incident_date",
        "claim_amount",
        "incident_description",
    ]
    assert session.uploaded_documents == []
    assert session.pageindex_extractions == {}
    assert session.validation_result is None
    assert session.chat_history == []


def test_session_update_field():
    session = ClaimSession(session_id="abc")
    session.update_field("policy_number", "POL-123")
    assert session.collected_fields["policy_number"] == "POL-123"
    assert "policy_number" not in session.missing_fields


def test_session_all_fields_collected():
    session = ClaimSession(session_id="abc")
    assert not session.all_fields_collected()
    for field in list(session.missing_fields):
        session.update_field(field, "test")
    assert session.all_fields_collected()


def test_session_add_chat_message():
    session = ClaimSession(session_id="abc")
    session.add_message("user", "hello")
    session.add_message("bot", "hi there")
    assert len(session.chat_history) == 2
    assert session.chat_history[0] == {"role": "user", "content": "hello"}
    assert session.chat_history[1] == {"role": "bot", "content": "hi there"}


def test_session_store_create_and_get():
    store = SessionStore()
    session = store.create()
    assert session.session_id is not None
    retrieved = store.get(session.session_id)
    assert retrieved is session


def test_session_store_get_missing_returns_none():
    store = SessionStore()
    assert store.get("nonexistent") is None
