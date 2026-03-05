import os
import json
import uuid
import asyncio
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException

logger = logging.getLogger(__name__)
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
async def upload_document(file: UploadFile = File(...), session_id: str = Form("")):
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

    # Return immediately — extraction happens via WebSocket
    return {"file_id": file_id, "file_path": file_path}


async def process_document_with_progress(websocket: WebSocket, session, file_path: str):
    """Process uploaded document with real-time progress updates via WebSocket."""
    try:
        # Step 1: Submit to PageIndex
        await websocket.send_json({
            "type": "progress",
            "step": 1,
            "total_steps": 4,
            "message": "Submitting document for processing...",
        })

        processor = DocumentProcessor(api_key=settings.pageindex_api_key)
        doc_id = processor.index_document(file_path)

        # Step 2: Wait for processing with progress updates
        await websocket.send_json({
            "type": "progress",
            "step": 2,
            "total_steps": 4,
            "message": "Processing document (this takes ~10-15 seconds)...",
        })

        max_wait = 60
        poll_interval = 3
        elapsed = 0
        ready = False
        while elapsed < max_wait:
            result = processor.client.get_tree(doc_id, node_summary=False)
            status = result.get("status", "")
            if status == "completed" and result.get("retrieval_ready"):
                ready = True
                break
            if status == "failed":
                break
            elapsed += poll_interval
            pct = min(95, int((elapsed / 15) * 100))
            await websocket.send_json({
                "type": "progress",
                "step": 2,
                "total_steps": 4,
                "message": f"Processing document... {pct}%",
                "percent": pct,
            })
            await asyncio.sleep(poll_interval)

        if not ready:
            await websocket.send_json({
                "type": "bot_message",
                "content": "Document processing timed out. Let's fill in the information manually.",
            })
            return

        # Step 3: Extract text
        await websocket.send_json({
            "type": "progress",
            "step": 3,
            "total_steps": 4,
            "message": "Reading document content...",
        })

        tree_text = processor.get_document_text(doc_id)
        ocr_text = processor.get_document_ocr(doc_id)
        combined_text = f"=== DOCUMENT STRUCTURE ===\n{tree_text}\n\n=== RAW OCR TEXT ===\n{ocr_text}"

        # Step 4: LLM extraction
        await websocket.send_json({
            "type": "progress",
            "step": 4,
            "total_steps": 4,
            "message": "Extracting claim fields with AI...",
        })

        extractor = FieldExtractor()
        extracted_fields = await extractor.extract_fields(combined_text)

        # Done — send extraction complete
        await websocket.send_json({
            "type": "progress_done",
            "message": f"Extracted {len(extracted_fields)} fields from document!",
        })

        # Process extracted fields through controller
        response = await chat_controller.handle_document_upload(session, extracted_fields, websocket=websocket)
        await websocket.send_json(response)

    except Exception as e:
        logger.error(f"Document processing failed: {e}", exc_info=True)
        await websocket.send_json({
            "type": "progress_done",
            "message": "Processing failed",
        })
        await websocket.send_json({
            "type": "bot_message",
            "content": f"Sorry, document processing failed: {e}. Let's fill in the information manually.",
        })


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

            try:
                if msg_type == "message":
                    response = await chat_controller.handle_message(
                        session, data.get("content", ""), websocket=websocket
                    )
                    await websocket.send_json(response)
                elif msg_type == "process_document":
                    file_path = data.get("file_path", "")
                    await process_document_with_progress(
                        websocket, session, file_path
                    )
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await websocket.send_json({
                    "type": "bot_message",
                    "content": f"Sorry, an error occurred: {e}",
                })
    except WebSocketDisconnect:
        pass
