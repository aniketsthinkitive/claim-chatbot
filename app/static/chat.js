const messagesDiv = document.getElementById("chat-messages");
const messageInput = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const fileUpload = document.getElementById("file-upload");
const fileName = document.getElementById("file-name");

let ws = null;
let sessionId = null;

function connect() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${window.location.host}/ws/chat`);

    ws.onopen = () => {
        sendBtn.disabled = false;
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.session_id) {
            sessionId = data.session_id;
        }
        removeTypingIndicator();

        if (data.type === "bot_message") {
            addMessage(data.content, "bot");
        } else if (data.type === "validation_result") {
            if (data.content) {
                addMessage(data.content, "bot");
            }
            addValidationResult(data.result);
        } else if (data.type === "extraction_result") {
            addMessage("Extracted fields from your document.", "bot");
        }
    };

    ws.onclose = () => {
        sendBtn.disabled = true;
        addMessage("Connection lost. Please refresh the page.", "bot");
    };
}

function addMessage(text, role) {
    const div = document.createElement("div");
    div.classList.add("message", role);
    div.textContent = text;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function addValidationResult(result) {
    const div = document.createElement("div");
    div.classList.add("message", "validation");

    const statusLabel = {
        pass: "Claim Validated Successfully",
        fail: "Claim Validation Failed",
        needs_review: "Claim Needs Review",
    };

    let html = '<div class="validation-header ' + result.status + '">' + (statusLabel[result.status] || result.status) + '</div>';

    if (result.issues && result.issues.length > 0) {
        html += '<div><strong>Issues:</strong><ul class="validation-issues">';
        result.issues.forEach((issue) => {
            html += "<li>" + escapeHtml(issue) + "</li>";
        });
        html += "</ul></div>";
    }

    if (result.recommendations && result.recommendations.length > 0) {
        html += '<div><strong>Recommendations:</strong><ul class="validation-recommendations">';
        result.recommendations.forEach((rec) => {
            html += "<li>" + escapeHtml(rec) + "</li>";
        });
        html += "</ul></div>";
    }

    div.innerHTML = html;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function showTypingIndicator() {
    const div = document.createElement("div");
    div.classList.add("typing-indicator");
    div.id = "typing";
    div.textContent = "Thinking...";
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function removeTypingIndicator() {
    const el = document.getElementById("typing");
    if (el) el.remove();
}

function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

    addMessage(text, "user");
    ws.send(JSON.stringify({ type: "message", content: text }));
    messageInput.value = "";
    showTypingIndicator();
}

async function uploadFile(file) {
    if (!sessionId) return;

    fileName.textContent = "Uploading: " + file.name + "...";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("session_id", sessionId);

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData,
        });
        const data = await response.json();
        fileName.textContent = "Uploaded: " + file.name;

        if (data.response) {
            if (data.response.type === "validation_result") {
                addMessage(data.response.content, "bot");
                addValidationResult(data.response.result);
            } else {
                addMessage(data.response.content, "bot");
            }
        }
    } catch (err) {
        fileName.textContent = "Upload failed";
        addMessage("Failed to upload document. Please try again.", "bot");
    }
}

sendBtn.addEventListener("click", sendMessage);

messageInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

fileUpload.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) uploadFile(file);
    e.target.value = "";
});

connect();
