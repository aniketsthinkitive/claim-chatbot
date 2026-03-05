from app.chat.session import ClaimSession, SessionStore


def test_claim_session_defaults():
    session = ClaimSession(session_id="abc")
    assert session.session_id == "abc"
    assert session.status == "collecting"
    assert session.collected_fields == {}
    assert len(session.missing_fields) == 20
    assert session.missing_fields == [
        "subscriber_first_name",
        "subscriber_last_name",
        "subscriber_dob",
        "subscriber_gender",
        "subscriber_id",
        "patient_relationship",
        "patient_first_name",
        "patient_last_name",
        "patient_dob",
        "patient_gender",
        "payer_name",
        "payer_id",
        "billing_provider_name",
        "billing_provider_npi",
        "billing_provider_taxonomy",
        "claim_type",
        "place_of_service",
        "total_charge",
        "diagnosis_codes",
        "service_lines",
    ]
    assert session.uploaded_documents == []
    assert session.pageindex_extractions == {}
    assert session.validation_result is None
    assert session.chat_history == []


def test_session_update_field():
    session = ClaimSession(session_id="abc")
    session.update_field("subscriber_id", "XYZ123")
    assert session.collected_fields["subscriber_id"] == "XYZ123"
    assert "subscriber_id" not in session.missing_fields


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
