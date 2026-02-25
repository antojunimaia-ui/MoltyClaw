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

function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user-row';

    row.innerHTML = `
        <div class="user-metadata">
            <div class="user-avatar">U</div>
            <div class="user-timestamp">You ${formatTime()}</div>
        </div>
        <div class="message-bubble user-bubble">
            ${escapeHTML(text)}
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

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text) return;

    // UI Updates
    appendUserMessage(text);
    messageInput.value = '';
    sendBtn.disabled = true;
    inputWrapper.classList.add('loading');

    // Simulate thinking state on status badge
    agentStatus.className = 'status-badge typing';
    agentStatus.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" style="margin-right:4px;"></i>Thinking...';

    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });

        const data = await response.json();

        if (response.ok && data.reply) {
            // Render markdown to HTML and sanitize
            const rawHtml = marked.parse(data.reply);
            const safeHtml = DOMPurify.sanitize(rawHtml);
            appendAssistantMessage(safeHtml);
        } else {
            appendAssistantMessage(`<span style="color:red">Error: ${data.error || 'Server disconnected.'}</span>`);
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
