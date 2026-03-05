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
            if (data.eligibility) {
                addEligibilityResult(data.eligibility);
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

    const statusIcon = { pass: "\u2705", fail: "\u274C", needs_review: "\u26A0\uFE0F" };

    let html = '<div class="validation-header ' + result.status + '">' +
        (statusIcon[result.status] || "") + " " +
        (statusLabel[result.status] || result.status) + '</div>';

    // Summary stats
    if (result.total_findings !== undefined) {
        html += '<div class="validation-stats">' +
            '<span>' + result.total_findings + ' finding(s)</span>' +
            (result.total_errors ? ' &middot; <span class="stat-errors">' + result.total_errors + ' error(s)</span>' : '') +
            (result.total_warnings ? ' &middot; <span class="stat-warnings">' + result.total_warnings + ' warning(s)</span>' : '') +
            (result.execution_time ? ' &middot; <span>' + result.execution_time.toFixed(3) + 's</span>' : '') +
            '</div>';
    }

    // Detailed findings with suggestions
    if (result.findings && result.findings.length > 0) {
        html += '<div class="validation-findings">';
        result.findings.forEach(function (f) {
            var sevClass = f.severity === "error" ? "finding-error" : "finding-warning";
            var sevLabel = f.severity === "error" ? "ERROR" : "WARNING";
            html += '<div class="finding-item ' + sevClass + '">' +
                '<div class="finding-header"><span class="finding-severity">' + sevLabel + '</span> ' +
                '<span class="finding-code">' + escapeHtml(f.code) + '</span></div>' +
                '<div class="finding-message">' + escapeHtml(f.message) + '</div>';
            if (f.field_name) {
                html += '<div class="finding-field">Field: ' + escapeHtml(f.field_name) + '</div>';
            }
            if (f.suggestion) {
                html += '<div class="finding-suggestion">\uD83D\uDCA1 ' + escapeHtml(f.suggestion) + '</div>';
            }
            html += '</div>';
        });
        html += '</div>';
    }

    // Phase results (shows which pipeline phases ran)
    if (result.phase_results && result.phase_results.length > 0) {
        html += '<div class="validation-phases">';
        result.phase_results.forEach(function (pr) {
            var phaseLabel = pr.phase === "rule_based" ? "Rule-Based" :
                pr.phase === "clearinghouse" ? "Clearinghouse" :
                pr.phase === "ai" ? "AI Analysis" :
                pr.phase === "fallback" ? "Basic Checks" : pr.phase;
            html += '<span class="phase-badge">' + escapeHtml(phaseLabel) +
                ' (' + pr.findings_count + ')</span>';
        });
        html += '</div>';
    }

    // Recommendations (shown for passing claims)
    if (result.recommendations && result.recommendations.length > 0) {
        html += '<div><strong>Recommendations:</strong><ul class="validation-recommendations">';
        result.recommendations.forEach(function (rec) {
            html += "<li>" + escapeHtml(rec) + "</li>";
        });
        html += "</ul></div>";
    }

    div.innerHTML = html;
    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function addEligibilityResult(elig) {
    const div = document.createElement("div");
    div.classList.add("message", "eligibility");

    var statusIcon = elig.eligible === true ? "\u2705" :
        elig.eligible === false ? "\u274C" : "\u2753";
    var statusText = elig.eligible === true ? "Patient is Eligible" :
        elig.eligible === false ? "Patient is NOT Eligible" :
        elig.status === "error" ? "Eligibility Check Failed" : "Eligibility Unknown";
    var statusClass = elig.eligible === true ? "elig-active" :
        elig.eligible === false ? "elig-inactive" : "elig-unknown";

    var html = '<div class="elig-header ' + statusClass + '">' +
        statusIcon + ' ' + statusText + '</div>';

    // Subscriber info
    if (elig.subscriber && elig.subscriber.first) {
        html += '<div class="elig-subscriber">' +
            '<strong>Subscriber:</strong> ' +
            escapeHtml(elig.subscriber.first + ' ' + elig.subscriber.last) +
            ' (ID: ' + escapeHtml(elig.subscriber.member_id || '') + ')' +
            '</div>';
    }

    // Plan info
    if (elig.plan_name) {
        html += '<div class="elig-plan-name"><strong>Plan:</strong> ' +
            escapeHtml(elig.plan_name) + '</div>';
    }

    // Plan details
    if (elig.plans && elig.plans.length > 0) {
        html += '<div class="elig-plans">';
        elig.plans.forEach(function (p) {
            if (!p.plan_name && !p.deductible_in) return;
            html += '<div class="elig-plan-card">';
            if (p.plan_name) {
                html += '<div class="elig-plan-title">' + escapeHtml(p.plan_name) +
                    ' <span class="elig-plan-status ' +
                    (p.active ? 'active' : 'inactive') + '">' +
                    escapeHtml(p.status || (p.active ? 'ACTIVE' : 'INACTIVE')) +
                    '</span></div>';
            }
            var details = [];
            if (p.deductible_in) details.push('Deductible In: $' + escapeHtml(p.deductible_in));
            if (p.deductible_remaining) details.push('Remaining: $' + escapeHtml(p.deductible_remaining));
            if (p.oop_remaining) details.push('OOP Remaining: $' + escapeHtml(p.oop_remaining));
            if (p.coinsurance_in) details.push('CoIns In: ' + (parseFloat(p.coinsurance_in) * 100) + '%');
            if (details.length > 0) {
                html += '<div class="elig-plan-details">' + details.join(' &middot; ') + '</div>';
            }
            html += '</div>';
        });
        html += '</div>';
    }

    // Errors
    if (elig.errors && elig.errors.length > 0) {
        html += '<div class="elig-errors">';
        elig.errors.forEach(function (e) {
            html += '<div class="elig-error">' + escapeHtml(e) + '</div>';
        });
        html += '</div>';
    }

    if (elig.reference_id) {
        html += '<div class="elig-ref">Ref: ' + escapeHtml(elig.reference_id) + '</div>';
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
