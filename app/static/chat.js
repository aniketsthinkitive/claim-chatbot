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

        if (data.type === "progress") {
            showProgress(data);
            return;
        }
        if (data.type === "progress_done") {
            hideProgress(data.message);
            return;
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

function showProgress(data) {
    let container = document.getElementById("progress-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "progress-container";
        container.classList.add("message", "bot", "progress-box");
        container.innerHTML =
            '<div class="progress-title">Processing Document</div>' +
            '<div class="progress-steps"></div>' +
            '<div class="progress-bar-track"><div class="progress-bar-fill"></div></div>' +
            '<div class="progress-message"></div>';
        messagesDiv.appendChild(container);
    }

    const steps = container.querySelector(".progress-steps");
    const fill = container.querySelector(".progress-bar-fill");
    const msg = container.querySelector(".progress-message");

    // Build step indicators
    let stepsHtml = "";
    for (let i = 1; i <= data.total_steps; i++) {
        let cls = "step-dot";
        if (i < data.step) cls += " done";
        else if (i === data.step) cls += " active";
        stepsHtml += '<span class="' + cls + '">' + i + "</span>";
    }
    steps.innerHTML = stepsHtml;

    // Overall progress: each step is 25%, with sub-percent for step 2
    let pct;
    if (data.percent !== undefined && data.step === 2) {
        pct = 25 + (data.percent / 100) * 25;
    } else {
        pct = (data.step / data.total_steps) * 100;
    }
    fill.style.width = Math.min(pct, 95) + "%";
    msg.textContent = data.message;

    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function hideProgress(doneMessage) {
    const container = document.getElementById("progress-container");
    if (container) {
        const fill = container.querySelector(".progress-bar-fill");
        const msg = container.querySelector(".progress-message");
        if (fill) fill.style.width = "100%";
        if (msg) msg.textContent = doneMessage || "Done!";

        // Remove after a short delay
        setTimeout(() => {
            container.remove();
        }, 1500);
    }
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

        // Trigger extraction via WebSocket with progress
        if (data.file_path && ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                type: "process_document",
                file_path: data.file_path,
            }));
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
