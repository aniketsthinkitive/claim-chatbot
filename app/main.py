import os
import json
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.config import settings
from app.chat.session import SessionStore
from app.chat.controller import ChatController
from app.documents.processor import DocumentProcessor
from app.documents.extractor import FieldExtractor

app = FastAPI(title="Claim Validator Chatbot")

session_store = SessionStore()
chat_controller = ChatController()

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.model_dump()


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), session_id: str = ""):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    os.makedirs(settings.upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "doc.pdf")[1]
    file_path = os.path.join(settings.upload_dir, f"{file_id}{ext}")

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    session.uploaded_documents.append(file_path)

    extracted_fields = {}
    try:
        processor = DocumentProcessor(api_key=settings.pageindex_api_key)
        doc_id = processor.index_document(file_path)
        doc_text = processor.get_document_text(doc_id)
        extractor = FieldExtractor()
        extracted_fields = await extractor.extract_fields(doc_text)
    except Exception:
        pass

    response = await chat_controller.handle_document_upload(session, extracted_fields)
    return {"file_id": file_id, "response": response}


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    session = session_store.create()

    welcome = chat_controller.get_welcome_message()
    await websocket.send_json({
        "type": welcome["type"],
        "content": welcome["content"],
        "session_id": session.session_id,
    })

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")

            if msg_type == "message":
                response = await chat_controller.handle_message(
                    session, data.get("content", "")
                )
                await websocket.send_json(response)
            elif msg_type == "upload_complete":
                file_id = data.get("file_id", "")
                await websocket.send_json({
                    "type": "bot_message",
                    "content": "Document received! Analyzing...",
                })
    except WebSocketDisconnect:
        pass
