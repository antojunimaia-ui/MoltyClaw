const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const inputWrapper = document.querySelector('.input-wrapper');
const agentStatus = document.getElementById('agent-status');

// Helper to escape HTML to prevent XSS (if we weren't using DOMPurify, but we are)
const escapeHTML = (str) => str.replace(/[&<>'"]/g,
    tag => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
    }[tag] || tag)
);

function formatTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function appendUserMessage(text, imgData = null) {
    const row = document.createElement('div');
    row.className = 'message-row user-row';

    let htmlDisplay = escapeHTML(text);
    if (imgData) {
        htmlDisplay += `<div style="margin-top: 10px;"><img src="${imgData}" style="max-width: 100%; border-radius: 8px; max-height: 250px; object-fit: contain;"></div>`;
    }

    row.innerHTML = `
        <div class="user-metadata">
            <div class="user-avatar">U</div>
            <div class="user-timestamp">You ${formatTime()}</div>
        </div>
        <div class="message-bubble user-bubble">
            ${htmlDisplay}
        </div>
    `;
    chatContainer.appendChild(row);
    scrollToBottom();
}

function appendAssistantMessage(htmlContent) {
    const row = document.createElement('div');
    row.className = 'message-row assistant-row';

    row.innerHTML = `
        <div class="message-bubble assistant-bubble">
            ${htmlContent}
        </div>
    `;
    chatContainer.appendChild(row);
    scrollToBottom();
}

function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function createAssistantMessage() {
    const row = document.createElement('div');
    row.className = 'message-row assistant-row';
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble assistant-bubble';
    row.appendChild(bubble);
    chatContainer.appendChild(row);
    scrollToBottom();
    return bubble;
}

function renderMarkdownWithMedia(text) {
    let safeHtml = DOMPurify.sanitize(marked.parse(text));

    // Converte chamadas de arquivo bruto de audio injetadas em tag real HTML5
    let tempHtml = safeHtml.replace(/<p>\[AUDIO_REPLY:\s*([^\]]+)\]<\/p>/g, "[AUDIO_REPLY:$1]");
    tempHtml = tempHtml.replace(/\[AUDIO_REPLY:\s*([^\]]+)\]/g, (match, filename) => {
        return `<div class="audio-player-wrapper" style="margin-top: 15px; margin-bottom: 15px; padding: 15px; background: #f0f0f0; border-radius: 12px; border: 1px solid #ccc; display: block; width: 100%; min-width: 350px;">
            <div style="font-size: 12px; font-weight: bold; margin-bottom: 8px; color: #333;">🎙️ Áudio Gerado</div>
            <audio controls style="width: 100%; display: block;" src="/temp/${filename.trim()}"></audio>
            <div style="font-size: 10px; color: #666; margin-top: 8px; font-family: monospace;">📂 ${filename.trim()}</div>
        </div>`;
    });

    // Converte Screenhots tirados
    tempHtml = tempHtml.replace(/<p>\[SCREENSHOT_TAKEN:\s*([^\]]+)\]<\/p>/g, "[SCREENSHOT_TAKEN:$1]");
    tempHtml = tempHtml.replace(/\[SCREENSHOT_TAKEN:\s*([^\]]+)\]/g, (match, filename) => {
        return `<div class="image-wrapper" style="margin-top: 15px; margin-bottom: 15px; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; display: inline-block; max-width: 100%;">
            <div style="background: #f8fafc; padding: 8px 12px; font-size: 10px; color: #64748b; font-family: monospace; border-bottom: 1px solid #e2e8f0;">📸 Captura de Tela (${filename.trim()})</div>
            <a href="/temp/${filename.trim()}" target="_blank"><img src="/temp/${filename.trim()}" style="width: 100%; display: block; max-height: 400px; object-fit: cover;"></a>
        </div>`;
    });

    return tempHtml;
}

async function sendMessage() {
    const text = messageInput.value.trim();
    const fileInput = document.getElementById('fileAttachment');
    const file = fileInput ? fileInput.files[0] : null;

    if (!text && !file) return;

    let userDisplay = text;
    let localPreviewUrl = null;

    if (file) {
        if (file.type.startsWith('image/')) {
            localPreviewUrl = URL.createObjectURL(file);
        } else {
            userDisplay += `\n\n*(📎 Anexo: ${file.name})*`;
        }
    }

    // UI Updates
    appendUserMessage(userDisplay, localPreviewUrl);
    messageInput.value = '';
    if (fileInput) fileInput.value = '';
    sendBtn.disabled = true;
    inputWrapper.classList.add('loading');

    // Simulate thinking state on status badge
    agentStatus.className = 'status-badge typing';
    agentStatus.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="margin-right:4px;"></i>Thinking...';

    const formData = new FormData();
    formData.append("message", text);
    if (file) {
        formData.append("file", file);
    }

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json();
            appendAssistantMessage(`<span style="color:red">Error: ${errData.error || 'Server error.'}</span>`);
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");

        let assistantBubble = createAssistantMessage();
        let cumulativeText = "";
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            const lines = buffer.split('\n');

            buffer = lines.pop(); // Guarda o restante (linha incompleta) para o próximo ciclo

            for (let line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.substring(6);
                    if (!dataStr) continue;

                    try {
                        const evt = JSON.parse(dataStr);
                        if (evt.type === 'token') {
                            cumulativeText += evt.content;
                            assistantBubble.innerHTML = renderMarkdownWithMedia(cumulativeText);
                            scrollToBottom();
                        } else if (evt.type === 'tool') {
                            cumulativeText += `\n> ⚙️ [\`${evt.content}\`]\n\n`;
                            assistantBubble.innerHTML = renderMarkdownWithMedia(cumulativeText);
                            scrollToBottom();
                        } else if (evt.type === 'error') {
                            cumulativeText += `\n<span style="color:red">Error API: ${evt.content}</span>`;
                            assistantBubble.innerHTML = renderMarkdownWithMedia(cumulativeText);
                            scrollToBottom();
                        } else if (evt.type === 'done') {
                            // Finished stream
                        }
                    } catch (e) {
                        // Ignora erros temporarios
                    }
                }
            }
        }
    } catch (err) {
        appendAssistantMessage(`<span style="color:red">Network connection failed.</span>`);
        console.error(err);
    } finally {
        sendBtn.disabled = false;
        inputWrapper.classList.remove('loading');
        // Restore ready state
        agentStatus.className = 'status-badge ready';
        agentStatus.innerHTML = '<i class="fa-solid fa-circle" style="color: #22c55e; font-size: 8px; margin-right:6px;"></i>Health OK';
    }
}

// Enter to send
messageInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!sendBtn.disabled) {
            sendMessage();
        }
    }
});

function clearSession() {
    chatContainer.innerHTML = `<div class="system-welcome">Session Cleared. Starting fresh context.</div>`;
}

// Polling status on startup to update "Ready" dot
async function checkStatus() {
    try {
        const res = await fetch('/api/status');
        const data = await res.json();
        if (data.ready) {
            agentStatus.className = 'status-badge ready';
            agentStatus.innerHTML = '<i class="fa-solid fa-circle" style="color: #22c55e; font-size: 8px; margin-right:6px;"></i>Health OK';
        } else {
            setTimeout(checkStatus, 3000);
        }
    } catch (e) {
        setTimeout(checkStatus, 5000);
    }
}

// Start polling
checkStatus();

// Tab Switching Logic
function switchTab(tabId) {
    // Hide all views
    document.querySelectorAll('.view-content').forEach(view => {
        view.style.display = 'none';
        view.classList.remove('active');
    });

    // Remove active state from nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });

    // Show selected view
    const targetView = document.getElementById(`view-${tabId}`);
    if (targetView) {
        targetView.style.display = 'block';
        targetView.classList.add('active');
    }

    // Set active state on nav item
    const targetNav = document.getElementById(`nav-${tabId}`);
    if (targetNav) {
        targetNav.classList.add('active');
    }

    if (tabId === 'integrations') {
        fetchIntegrations();
    } else if (tabId === 'agent') {
        loadAgentFiles();
    }
}

// Agent Files Logic
let currentAgentFile = 'soul';
let agentFilesContent = {
    soul: '',
    memory: ''
};

async function loadAgentFiles() {
    try {
        const memRes = await fetch('/api/agent/memory');
        const memData = await memRes.json();
        agentFilesContent['memory'] = memData.content || '';

        const soulRes = await fetch('/api/agent/soul');
        const soulData = await soulRes.json();
        agentFilesContent['soul'] = soulData.content || '';

        selectAgentFile(currentAgentFile);
    } catch (e) {
        console.error('Failed to load agent files', e);
    }
}

function selectAgentFile(fileId) {
    const activeEditor = document.getElementById('active-editor');
    if (activeEditor && currentAgentFile) {
        agentFilesContent[currentAgentFile] = activeEditor.value;
    }

    currentAgentFile = fileId;

    document.querySelectorAll('.studio-file-card').forEach(card => card.classList.remove('active'));
    document.getElementById(`card-${fileId}`).classList.add('active');

    if (activeEditor) {
        activeEditor.value = agentFilesContent[fileId];
    }

    const titleEl = document.getElementById('current-editor-title');
    const pathEl = document.getElementById('current-editor-path');

    if (fileId === 'soul') {
        titleEl.innerText = 'SOUL.md';
        pathEl.innerText = 'c:\\Users\\Cliente\\OpenPy\\SOUL.md';
    } else {
        titleEl.innerText = 'MEMORY.md';
        pathEl.innerText = 'c:\\Users\\Cliente\\OpenPy\\MEMORY.md';
    }
}

async function saveCurrentAgentFile() {
    const activeEditor = document.getElementById('active-editor');
    if (!activeEditor || !currentAgentFile) return;

    const content = activeEditor.value;
    agentFilesContent[currentAgentFile] = content; // sync dict

    const btn = event.target || document.querySelector('.editor-actions .btn-primary');
    const originalText = btn.innerText;

    btn.disabled = true;
    btn.innerText = "Salvando...";

    try {
        const res = await fetch(`/api/agent/${currentAgentFile}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });

        if (res.ok) {
            btn.innerText = "Salvo!";
            setTimeout(() => {
                btn.innerText = originalText;
            }, 2000);
        } else {
            alert(`Erro ao salvar ${currentAgentFile.toUpperCase()}.md`);
            btn.innerText = originalText;
        }
    } catch (e) {
        console.error(`Error saving ${currentAgentFile}`, e);
        alert(`Erro de conexão ao salvar ${currentAgentFile.toUpperCase()}.md`);
        btn.innerText = originalText;
    } finally {
        btn.disabled = false;
    }
}

// Integrations Logic
async function fetchIntegrations() {
    try {
        const res = await fetch('/api/integrations');
        const data = await res.json();

        // Update toggles based on status map
        for (const [key, active] of Object.entries(data)) {
            const toggle = document.getElementById(`toggle-${key}`);
            if (toggle) toggle.checked = active;
        }
    } catch (e) {
        console.error('Failed to fetch integrations', e);
    }
}

async function toggleIntegration(name) {
    const toggle = document.getElementById(`toggle-${name}`);
    const action = toggle.checked ? 'start' : 'stop';

    toggle.disabled = true; // Prevent spamming
    try {
        const res = await fetch(`/api/integrations/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });

        if (!res.ok) {
            // Revert on fail
            toggle.checked = !toggle.checked;
            alert("Erro ao alterar o status do conector.");
        }
    } catch (e) {
        toggle.checked = !toggle.checked;
        console.error(e);
    } finally {
        toggle.disabled = false;
        // Refetch to ensure state
        setTimeout(fetchIntegrations, 1000);
    }
}

// Initial fetch to sync states
fetchIntegrations();
