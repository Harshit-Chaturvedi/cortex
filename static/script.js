// ===== Elements =====
const feed = document.getElementById("feed");
const chatForm = document.getElementById("chatForm");
const questionInput = document.getElementById("questionInput");
const sendBtn = document.getElementById("sendBtn");
const hero = document.getElementById("hero");
const uploadZone = document.getElementById("uploadZone");
const fileInput = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");
const serverStatus = document.getElementById("serverStatus");
const statusDot = document.getElementById("statusDot");
const apiKeyInput = document.getElementById("apiKeyInput");
const sidebar = document.getElementById("sidebar");
const sidebarOpen = document.getElementById("sidebarOpen");
const sidebarClose = document.getElementById("sidebarClose");

let busy = false;

function apiKey() {
    return apiKeyInput.value.trim() || "dev-key-change-me";
}

// ===== Health =====
async function checkHealth() {
    try {
        const r = await fetch("/health");
        if (r.ok) {
            serverStatus.textContent = "Connected";
            statusDot.className = "stat-dot online";
        } else { throw 0; }
    } catch {
        serverStatus.textContent = "Offline";
        statusDot.className = "stat-dot offline";
    }
}

// ===== Chat =====
function hideHero() {
    if (hero) hero.style.display = "none";
}

function userBubble(text) {
    hideHero();
    const el = document.createElement("div");
    el.className = "msg user";
    el.innerHTML = `
        <div class="msg-top">
            <span class="msg-dot"></span>
            <span class="msg-who">You</span>
        </div>
        <div class="msg-body">${esc(text)}</div>
    `;
    feed.appendChild(el);
    scroll();
}

function loadingBubble() {
    const el = document.createElement("div");
    el.className = "msg bot";
    el.id = "typing";
    el.innerHTML = `
        <div class="msg-top">
            <span class="msg-dot"></span>
            <span class="msg-who">Cortex</span>
        </div>
        <div class="msg-body">
            <div class="loader"><span></span><span></span><span></span></div>
        </div>
    `;
    feed.appendChild(el);
    scroll();
}

function removeLoading() {
    const el = document.getElementById("typing");
    if (el) el.remove();
}

function botBubble(data) {
    removeLoading();
    const answer = data.answer || "No answer.";
    const sources = data.sources || [];
    const provider = data.provider || "?";
    const ms = data.latency_ms || 0;

    let srcHtml = "";
    if (sources.length) {
        const id = "src-" + Date.now();
        const items = sources.map(s => {
            const file = s.metadata?.source || "?";
            const score = s.score !== undefined ? (s.score * 100).toFixed(0) + "%" : "";
            return `<div class="src-item">
                <div class="src-head">
                    <span class="src-file">${esc(file)}</span>
                    <span class="src-score">${score}</span>
                </div>
                <div class="src-text">${esc((s.content || "").slice(0, 180))}…</div>
            </div>`;
        }).join("");

        srcHtml = `<div class="src-wrap">
            <button class="src-toggle" onclick="toggleSrc('${id}', this)">
                ▸ ${sources.length} source${sources.length > 1 ? "s" : ""}
            </button>
            <div class="src-list" id="${id}">${items}</div>
        </div>`;
    }

    const el = document.createElement("div");
    el.className = "msg bot";
    el.innerHTML = `
        <div class="msg-top">
            <span class="msg-dot"></span>
            <span class="msg-who">Cortex</span>
            <div class="msg-info">
                <span class="msg-provider">${esc(provider)}</span>
                <span>${(ms / 1000).toFixed(1)}s</span>
            </div>
        </div>
        <div class="msg-body">${fmt(answer)}</div>
        ${srcHtml}
    `;
    feed.appendChild(el);
    scroll();
}

function errorBubble(msg) {
    removeLoading();
    const el = document.createElement("div");
    el.className = "msg bot";
    el.innerHTML = `
        <div class="msg-top">
            <span class="msg-dot"></span>
            <span class="msg-who">Cortex</span>
        </div>
        <div class="msg-body" style="border-color:var(--red);color:var(--red);">
            ${esc(msg)}
        </div>
    `;
    feed.appendChild(el);
    scroll();
}

async function ask(q) {
    if (busy || !q.trim()) return;
    busy = true;
    sendBtn.disabled = true;
    userBubble(q);
    loadingBubble();

    try {
        const r = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-API-Key": apiKey() },
            body: JSON.stringify({ question: q.trim() }),
        });
        if (!r.ok) {
            const e = await r.json().catch(() => ({}));
            throw new Error(e.detail || `Error ${r.status}`);
        }
        botBubble(await r.json());
    } catch (e) {
        errorBubble(e.message || "Something went wrong.");
    } finally {
        busy = false;
        sendBtn.disabled = false;
        questionInput.focus();
    }
}

// ===== Upload =====
async function upload(file) {
    const fd = new FormData();
    fd.append("file", file);

    const m = document.createElement("div");
    m.className = "upload-msg";
    m.textContent = `Uploading ${file.name}…`;
    uploadStatus.appendChild(m);

    try {
        const r = await fetch("/upload", {
            method: "POST",
            headers: { "X-API-Key": apiKey() },
            body: fd,
        });
        if (!r.ok) {
            const e = await r.json().catch(() => ({}));
            throw new Error(e.detail || `Failed: ${r.status}`);
        }
        const d = await r.json();
        m.className = "upload-msg success";
        m.textContent = `✓ ${file.name} ingested`;
    } catch (e) {
        m.className = "upload-msg error";
        m.textContent = `✗ ${file.name} — ${e.message}`;
    }
    setTimeout(() => m.remove(), 6000);
}

// ===== Helpers =====
function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}

function fmt(t) {
    return esc(t)
        .replace(/\n- /g, "\n• ")
        .replace(/\n/g, "<br>")
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`(.*?)`/g, '<code style="background:var(--bg-0);padding:1px 5px;border-radius:4px;font-family:var(--mono);font-size:12px;">$1</code>');
}

function scroll() {
    requestAnimationFrame(() => feed.scrollTop = feed.scrollHeight);
}

function toggleSrc(id, btn) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle("open");
    btn.textContent = el.classList.contains("open")
        ? `▾ Hide sources`
        : `▸ ${el.children.length} source${el.children.length > 1 ? "s" : ""}`;
}

function askChip(btn) {
    const t = btn.textContent.trim();
    questionInput.value = t;
    ask(t);
    questionInput.value = "";
    sidebar.classList.remove("open");
}

// ===== Events =====
questionInput.addEventListener("input", () => {
    questionInput.style.height = "auto";
    questionInput.style.height = Math.min(questionInput.scrollHeight, 120) + "px";
});

chatForm.addEventListener("submit", e => {
    e.preventDefault();
    const q = questionInput.value.trim();
    if (q) { ask(q); questionInput.value = ""; questionInput.style.height = "auto"; }
});

questionInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event("submit"));
    }
});

uploadZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", e => {
    for (const f of e.target.files) upload(f);
    fileInput.value = "";
});

uploadZone.addEventListener("dragover", e => { e.preventDefault(); uploadZone.classList.add("drag-over"); });
uploadZone.addEventListener("dragleave", () => uploadZone.classList.remove("drag-over"));
uploadZone.addEventListener("drop", e => {
    e.preventDefault();
    uploadZone.classList.remove("drag-over");
    for (const f of e.dataTransfer.files) upload(f);
});

sidebarOpen.addEventListener("click", () => sidebar.classList.add("open"));
sidebarClose.addEventListener("click", () => sidebar.classList.remove("open"));

// ===== Init =====
checkHealth();
setInterval(checkHealth, 30000);
