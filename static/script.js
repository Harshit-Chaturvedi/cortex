// ===== DOM Elements =====
const chatContainer = document.getElementById("chatContainer");
const chatForm = document.getElementById("chatForm");
const questionInput = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");
const welcome = document.getElementById("welcome");
const uploadZone = document.getElementById("uploadZone");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const serverStatus = document.getElementById("serverStatus");
const apiKeyInput = document.getElementById("apiKeyInput");
const sidebar = document.getElementById("sidebar");
const sidebarOpen = document.getElementById("sidebarOpen");
const sidebarClose = document.getElementById("sidebarClose");

// ===== State =====
let isWaiting = false;

// ===== API Key =====
function getApiKey() {
    return apiKeyInput.value.trim() || "dev-key-change-me";
}

// ===== Health Check =====
async function checkHealth() {
    try {
        const res = await fetch("/health");
        if (res.ok) {
            serverStatus.textContent = "Online";
            serverStatus.className = "status-badge online";
        } else {
            throw new Error();
        }
    } catch {
        serverStatus.textContent = "Offline";
        serverStatus.className = "status-badge offline";
    }
}

// ===== Chat =====
function hideWelcome() {
    if (welcome) {
        welcome.style.display = "none";
    }
}

function addUserMessage(text) {
    hideWelcome();
    const div = document.createElement("div");
    div.className = "message user";
    div.innerHTML = `
        <div class="msg-header">
            <div class="msg-avatar">Y</div>
            <span class="msg-name">You</span>
        </div>
        <div class="msg-bubble">${escapeHtml(text)}</div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function addLoadingMessage() {
    const div = document.createElement("div");
    div.className = "message bot";
    div.id = "loadingMsg";
    div.innerHTML = `
        <div class="msg-header">
            <div class="msg-avatar">C</div>
            <span class="msg-name">Cortex</span>
        </div>
        <div class="msg-bubble">
            <div class="loading-dots">
                <span></span><span></span><span></span>
            </div>
        </div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function removeLoadingMessage() {
    const el = document.getElementById("loadingMsg");
    if (el) el.remove();
}

function addBotMessage(data) {
    removeLoadingMessage();

    const answer = data.answer || "No answer received.";
    const sources = data.sources || [];
    const provider = data.provider || "unknown";
    const latency = data.latency_ms || 0;

    let sourcesHtml = "";
    if (sources.length > 0) {
        const sourceItems = sources.map((s, i) => {
            const file = s.metadata?.source || "unknown";
            const score = s.score !== undefined ? (s.score * 100).toFixed(0) + "% match" : "";
            const content = escapeHtml(s.content || "").substring(0, 200);
            return `
                <div class="source-item">
                    <div class="source-header">
                        <span class="source-file">📄 ${escapeHtml(file)}</span>
                        <span class="source-score">${score}</span>
                    </div>
                    <div class="source-content">${content}...</div>
                </div>
            `;
        }).join("");

        const sourceId = "sources-" + Date.now();
        sourcesHtml = `
            <div class="sources">
                <button class="sources-toggle" onclick="toggleSources('${sourceId}', this)">
                    📎 ${sources.length} source${sources.length > 1 ? "s" : ""} used
                </button>
                <div class="sources-list" id="${sourceId}">
                    ${sourceItems}
                </div>
            </div>
        `;
    }

    const div = document.createElement("div");
    div.className = "message bot";
    div.innerHTML = `
        <div class="msg-header">
            <div class="msg-avatar">C</div>
            <span class="msg-name">Cortex</span>
            <div class="msg-meta">
                <span class="provider-badge">${escapeHtml(provider)}</span>
                <span>${(latency / 1000).toFixed(1)}s</span>
            </div>
        </div>
        <div class="msg-bubble">${formatAnswer(answer)}</div>
        ${sourcesHtml}
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

function addErrorMessage(error) {
    removeLoadingMessage();
    const div = document.createElement("div");
    div.className = "message bot";
    div.innerHTML = `
        <div class="msg-header">
            <div class="msg-avatar">C</div>
            <span class="msg-name">Cortex</span>
        </div>
        <div class="msg-bubble" style="border-color: var(--error); color: var(--error);">
            ⚠️ ${escapeHtml(error)}
        </div>
    `;
    chatContainer.appendChild(div);
    scrollToBottom();
}

async function sendQuestion(question) {
    if (isWaiting || !question.trim()) return;

    isWaiting = true;
    sendBtn.disabled = true;
    addUserMessage(question);
    addLoadingMessage();

    try {
        const res = await fetch("/ask", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-API-Key": getApiKey(),
            },
            body: JSON.stringify({ question: question.trim() }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Server returned ${res.status}`);
        }

        const data = await res.json();
        addBotMessage(data);
    } catch (err) {
        addErrorMessage(err.message || "Something went wrong. Check if the server is running.");
    } finally {
        isWaiting = false;
        sendBtn.disabled = false;
        questionInput.focus();
    }
}

// ===== File Upload =====
async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);

    const msgDiv = document.createElement("div");
    msgDiv.className = "upload-msg";
    msgDiv.textContent = `Uploading ${file.name}...`;
    uploadStatus.appendChild(msgDiv);

    try {
        const res = await fetch("/upload", {
            method: "POST",
            headers: { "X-API-Key": getApiKey() },
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Upload failed: ${res.status}`);
        }

        const data = await res.json();
        msgDiv.className = "upload-msg success";
        msgDiv.textContent = `✓ ${file.name} — ${data.chunks_added || "?"} chunks added`;
    } catch (err) {
        msgDiv.className = "upload-msg error";
        msgDiv.textContent = `✗ ${file.name} — ${err.message}`;
    }

    // auto-clear after 8 seconds
    setTimeout(() => msgDiv.remove(), 8000);
}

// ===== Helpers =====
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function formatAnswer(text) {
    // basic markdown-ish formatting
    return escapeHtml(text)
        .replace(/\n- /g, "\n• ")
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`(.*?)`/g, '<code style="background:var(--bg-primary);padding:2px 6px;border-radius:4px;font-family:var(--font-mono);font-size:12px;">$1</code>');
}

function scrollToBottom() {
    requestAnimationFrame(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    });
}

function toggleSources(id, btn) {
    const list = document.getElementById(id);
    if (list) {
        list.classList.toggle("open");
        if (list.classList.contains("open")) {
            btn.innerHTML = "📎 Hide sources";
        } else {
            btn.innerHTML = btn.dataset.original || "📎 Show sources";
        }
    }
}

function askSuggestion(btn) {
    const text = btn.textContent.trim();
    questionInput.value = text;
    sendQuestion(text);
    questionInput.value = "";

    // close sidebar on mobile
    sidebar.classList.remove("open");
}

// ===== Textarea auto-resize =====
questionInput.addEventListener("input", () => {
    questionInput.style.height = "auto";
    questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + "px";
});

// ===== Form submit =====
chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = questionInput.value.trim();
    if (q) {
        sendQuestion(q);
        questionInput.value = "";
        questionInput.style.height = "auto";
    }
});

// Enter to send (Shift+Enter for newline)
questionInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit"));
    }
});

// ===== Upload events =====
uploadZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", (e) => {
    for (const file of e.target.files) {
        uploadFile(file);
    }
    fileInput.value = "";
});

uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("drag-over");
});

uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("drag-over");
});

uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("drag-over");
    for (const file of e.dataTransfer.files) {
        uploadFile(file);
    }
});

// ===== Sidebar mobile toggle =====
sidebarOpen.addEventListener("click", () => sidebar.classList.add("open"));
sidebarClose.addEventListener("click", () => sidebar.classList.remove("open"));

// ===== Init =====
checkHealth();
setInterval(checkHealth, 30000);
