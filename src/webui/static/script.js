const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const inputWrapper = document.querySelector('.input-wrapper');
const agentStatus = document.getElementById('agent-status-nav');
const sidebarToggle = document.getElementById('sidebar-toggle');
const appSidebar = document.getElementById('app-sidebar');
const themeToggle = document.getElementById('theme-toggle');
const themeBtns = document.querySelectorAll('.theme-btn');

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
    const textInput = messageInput.value.trim();
    const fileInput = document.getElementById('fileAttachment');
    const file = fileInput ? fileInput.files[0] : null;

    if (!textInput && !file) return;

    const currentAgentId = document.getElementById('chat-agent-select').value;
    let userDisplay = textInput;
    if (currentAgentId !== 'MoltyClaw') {
        userDisplay = `**[Talking to ${currentAgentId}]**\n` + userDisplay;
    }

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
    formData.append("message", textInput);
    formData.append("agent_id", currentAgentId);
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

        let renderTimer = null;
        const flushRender = () => {
            assistantBubble.innerHTML = renderMarkdownWithMedia(cumulativeText);
            scrollToBottom();
            renderTimer = null;
        };

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
                            if (!renderTimer) renderTimer = setTimeout(flushRender, 100);
                        } else if (evt.type === 'tool') {
                            cumulativeText += `\n> ⚙️ [\`${evt.content}\`]\n\n`;
                            flushRender();
                        } else if (evt.type === 'error') {
                            cumulativeText += `\n<span style="color:red">Error API: ${evt.content}</span>`;
                            flushRender();
                        } else if (evt.type === 'done') {
                            if (renderTimer) {
                                clearTimeout(renderTimer);
                                flushRender();
                            }
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

// ─── Mobile Sidebar Functions ───────────────────────────────────────────────
function openSidebar() {
    document.querySelector('.sidebar').classList.add('open');
    document.getElementById('sidebar-overlay').classList.add('active');
}

function closeSidebar() {
    document.querySelector('.sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('active');
}

// Sidebar Toggle Logic
if (sidebarToggle) {
    sidebarToggle.addEventListener('click', () => {
        appSidebar.classList.toggle('collapsed');
        // Save preference
        localStorage.setItem('sidebar-collapsed', appSidebar.classList.contains('collapsed'));
    });
}

// Restore sidebar state
if (localStorage.getItem('sidebar-collapsed') === 'true') {
    appSidebar.classList.add('collapsed');
}

// Mobile Overlay
const menuToggle = document.querySelector('.menu-toggle');
if (menuToggle) {
    menuToggle.addEventListener('click', () => {
        openSidebar();
    });
}

// Theme Switching Logic
function applyTheme(theme) {
    const body = document.body;
    themeToggle.setAttribute('data-selected', theme);

    // Update button states
    themeBtns.forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('data-theme') === theme);
    });

    if (theme === 'system') {
        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        body.setAttribute('data-theme', isDark ? 'dark' : 'light');
    } else {
        body.setAttribute('data-theme', theme);
    }

    localStorage.setItem('molty-theme', theme);
}

// Listen for system theme changes
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (localStorage.getItem('molty-theme') === 'system') {
        document.body.setAttribute('data-theme', e.matches ? 'dark' : 'light');
    }
});

// Wire up theme buttons
themeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        applyTheme(btn.getAttribute('data-theme'));
    });
});

// Initial Theme Load
const savedTheme = localStorage.getItem('molty-theme') || 'light';
applyTheme(savedTheme);

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
    } else if (tabId === 'routing') {
        fetchBindings();
    } else if (tabId === 'agent') {
        loadAgentList();
    } else if (tabId === 'mcp') {
        loadMCPList();
    } else if (tabId === 'heartbeat') {
        fetchSchedulerJobs();
    }

    // Sync mobile bottom nav active state
    document.querySelectorAll('.mobile-nav-item').forEach(item => item.classList.remove('active'));
    const mobileActive = document.getElementById(`mobile-nav-${tabId}`);
    if (mobileActive) mobileActive.classList.add('active');

    // Close sidebar on mobile after switching tab
    closeSidebar();
}

async function fetchSchedulerJobs() {
    try {
        const res = await fetch('/api/scheduler/jobs');
        const data = await res.json();
        renderSchedulerJobs(data.jobs || []);
    } catch(e) { console.error('Error fetching jobs', e); }
}

function renderSchedulerJobs(jobs) {
    const list = document.getElementById('scheduler-jobs-list');
    if (!list) return;
    
    if (jobs.length === 0) {
        list.innerHTML = `<div class="card"><p class="muted">Nenhuma tarefa agendada.</p></div>`;
        return;
    }

    list.innerHTML = jobs.map(job => `
        <div class="card" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-left: 4px solid ${job.enabled ? '#22c55e' : '#94a3b8'};">
            <div style="flex: 1;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <h4 style="margin:0">${escapeHTML(job.name)}</h4>
                    ${job.enabled ? '<span class="status-badge ready" style="font-size:9px; padding: 2px 6px;">Ativo</span>' : '<span class="status-badge" style="font-size:9px; padding: 2px 6px;">Pausado</span>'}
                </div>
                <p class="card-sub" style="margin: 4px 0;">Intervalo: <strong>${job.interval / 60} min</strong></p>
                <div style="font-size: 11px; color: var(--text-dim); margin-top: 5px; font-family: monospace; background: var(--bg-hover); padding: 6px; border-radius: 4px;">
                    <i class="fa-solid fa-terminal" style="font-size: 9px; margin-right: 4px;"></i> ${escapeHTML(job.payload.substring(0, 80))}${job.payload.length > 80 ? '...' : ''}
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px; margin-left: 20px;">
                <label class="toggle-switch">
                    <input type="checkbox" ${job.enabled ? 'checked' : ''} onchange="toggleSchedulerJob('${job.id}', this.checked)">
                    <span class="slider"></span>
                </label>
                <button class="btn danger" style="padding: 6px 10px;" onclick="removeSchedulerJob('${job.id}')" title="Excluir">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function addSchedulerJob() {
    const name = document.getElementById('sched-name').value;
    const interval_min = document.getElementById('sched-interval').value;
    const payload = document.getElementById('sched-payload').value;

    if (!name || !payload) return alert("Por favor, preencha o nome e o o comando de voz/texto da tarefa.");

    try {
        const res = await fetch('/api/scheduler/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name, interval_min, payload })
        });
        const data = await res.json();
        if (data.success) {
            fetchSchedulerJobs();
            document.getElementById('sched-name').value = '';
            document.getElementById('sched-payload').value = '';
        }
    } catch(e) { console.error('Error adding job', e); }
}

async function toggleSchedulerJob(id, enabled) {
    try {
        await fetch('/api/scheduler/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ id, enabled })
        });
        fetchSchedulerJobs(); // Refresh visual state (badges)
    } catch(e) { console.error('Error toggling job', e); }
}

async function removeSchedulerJob(id) {
    if (!confirm("Tem certeza que deseja excluir esta tarefa de monitoramento?")) return;
    try {
        await fetch(`/api/scheduler/remove/${id}`, { method: 'POST' });
        fetchSchedulerJobs();
    } catch(e) { console.error('Error removing job', e); }
}

// Agent Files & Multi-Agent Logic
let activeAgentId = 'MoltyClaw';
let agentListCache = [];

async function loadAgentList() {
    try {
        const res = await fetch('/api/agents');
        const data = await res.json();
        agentListCache = data.agents || [];
        renderAgentList();
        updateChatAgentSelector();
        
        // Ensure an agent is selected
        if (!agentListCache.find(a => a.id === activeAgentId) && activeAgentId !== '__NEW__') {
            activeAgentId = 'MoltyClaw';
        }
        selectAgent(activeAgentId);
        // Populate all select elements that need agent list
        document.querySelectorAll('.all-agents-select').forEach(sel => {
            const currentVal = sel.value;
            sel.innerHTML = '<option value="MoltyClaw">MoltyClaw</option>';
            agentListCache.forEach(agent => {
                const opt = document.createElement('option');
                opt.value = agent.id;
                opt.textContent = agent.name || agent.id;
                sel.appendChild(opt);
            });
            if (currentVal) sel.value = currentVal;
        });
    } catch(e) { console.error('Error fetching agents', e); }
}

function updateChatAgentSelector() {
    const select = document.getElementById('chat-agent-select');
    if (!select) return;
    
    const currentVal = select.value;
    select.innerHTML = '<option value="MoltyClaw">MoltyClaw (Master)</option>';
    
    agentListCache.forEach(agent => {
        if (!agent.is_master) {
            const opt = document.createElement('option');
            opt.value = agent.id;
            opt.textContent = `${agent.name} (${agent.id})`;
            select.appendChild(opt);
        }
    });
    
    // Update all integration selectors too
    document.querySelectorAll('.agent-select-small').forEach(intSelect => {
        const intVal = intSelect.value;
        intSelect.innerHTML = '<option value="MoltyClaw">MoltyClaw</option>';
        agentListCache.forEach(a => {
            if (!a.is_master) {
                const opt = document.createElement('option');
                opt.value = a.id;
                opt.textContent = a.name;
                intSelect.appendChild(opt);
            }
        });
        if (Array.from(intSelect.options).some(o => o.value === intVal)) intSelect.value = intVal;
    });

    if (Array.from(select.options).some(o => o.value === currentVal)) {
        select.value = currentVal;
    }
}

function onChatAgentChange() {
    const agentId = document.getElementById('chat-agent-select').value;
    chatContainer.innerHTML += `<div class="system-welcome">Switching context to ${agentId}...</div>`;
    scrollToBottom();
}

function renderAgentList() {
    const container = document.getElementById('agent-list-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    // Update count
    const countEl = document.getElementById('agents-count-text');
    if (countEl) countEl.innerText = `${agentListCache.length} configured.`;
    
    agentListCache.forEach(agent => {
        const row = document.createElement('div');
        row.className = `agent-row ${agent.id === activeAgentId ? 'active' : ''}`;
        row.onclick = () => selectAgent(agent.id);
        
        // Pick an icon/emoji based on agent name or role for flair
        let avatar = agent.is_master ? '🤖' : '👤';
        if (agent.name.toLowerCase().includes('don')) avatar = '🎨';
        if (agent.name.toLowerCase().includes('harry')) avatar = '📊';
        if (agent.name.toLowerCase().includes('pete')) avatar = '💻';
        if (agent.name.toLowerCase().includes('peggy')) avatar = '👱‍♀️';

        row.innerHTML = `
            <div class="agent-avatar">${avatar}</div>
            <div class="agent-info" style="flex: 1;">
                <div class="agent-title">${escapeHTML(agent.name)}</div>
                <div class="agent-sub mono">${escapeHTML(agent.id.toLowerCase())}</div>
            </div>
            ${agent.is_master ? '<span class="agent-pill">default</span>' : ''}
        `;
        container.appendChild(row);
    });
    
    // Add New Agent button
    const addRow = document.createElement('div');
    addRow.className = `agent-row ${activeAgentId === '__NEW__' ? 'active' : ''}`;
    addRow.onclick = () => selectAgent('__NEW__');
    addRow.innerHTML = `
        <div class="agent-avatar" style="background:transparent; border: 1px dashed #4b5563; color:#ef4444">+</div>
        <div class="agent-info">
            <div class="agent-title" style="color:#ef4444">Criar Especialista</div>
            <div class="agent-sub" style="color:#7f1d1d">novo obreiro</div>
        </div>
    `;
    container.appendChild(addRow);
}

function selectAgent(agentId) {
    activeAgentId = agentId;
    renderAgentList();
    
    const placeholder = document.getElementById('agent-selection-placeholder');
    const container = document.getElementById('agent-details-container');
    
    if (!agentId) {
        placeholder.style.display = 'block';
        container.style.display = 'none';
        return;
    }
    
    placeholder.style.display = 'none';
    container.style.display = 'flex';
    
    const coreBtn = document.getElementById('btn-agent-core');
    const ctxBtn = document.getElementById('btn-agent-context');
    const cfgBtn = document.getElementById('btn-agent-config');
    
    const nameEl = document.getElementById('selected-agent-name');
    const idEl = document.getElementById('selected-agent-id');
    const avatarEl = document.getElementById('selected-agent-avatar');
    const badgeEl = document.getElementById('selected-agent-badge');
    
    if (agentId === '__NEW__') {
        nameEl.innerText = "Novo Especialista";
        idEl.innerText = "worker_agent";
        avatarEl.innerText = "+";
        badgeEl.style.display = "none";

        cfgBtn.style.display = 'block';
        switchAgentSegment('config');
        
        document.getElementById('agent-form-id').value = '';
        document.getElementById('agent-form-id').disabled = false;
        document.getElementById('agent-form-id').focus();
        document.getElementById('agent-form-name').value = '';
        document.getElementById('agent-form-description').value = '';
        document.getElementById('agent-form-provider').value = 'mistral';
        document.getElementById('agent-form-env').value = '';
        
        // Desmarcar todas as tools nativas exceto DDG_SEARCH e READ_PAGE
        document.querySelectorAll('.native-tool-check').forEach(cb => {
            cb.checked = (cb.value === 'DDG_SEARCH' || cb.value === 'READ_PAGE');
        });
        
        // Desmarcar todos os MCP servers
        document.querySelectorAll('.mcp-server-check').forEach(cb => {
            cb.checked = false;
        });
        
        document.getElementById('btn-delete-agent').style.display = 'none';
        
        // Hide Core since new agents don't have files until saved
        coreBtn.style.display = 'none';
        ctxBtn.style.display = 'none';
    } else {
        const agent = agentListCache.find(a => a.id === agentId);
        if(!agent) return;
        
        nameEl.innerText = agent.name;
        idEl.innerText = agent.id.toLowerCase();
        
        // Pick an icon/emoji
        let avatar = agent.is_master ? '🤖' : '👤';
        if (agent.name.toLowerCase().includes('don')) avatar = '🎨';
        if (agent.name.toLowerCase().includes('harry')) avatar = '📊';
        if (agent.name.toLowerCase().includes('pete')) avatar = '💻';
        if (agent.name.toLowerCase().includes('peggy')) avatar = '👱‍♀️';
        avatarEl.innerText = avatar;

        if (agent.is_master) {
            badgeEl.style.display = 'inline-block';
            badgeEl.innerText = 'default';
            cfgBtn.style.display = 'inline-block'; // Agora aparece para o mestre também
        } else {
            badgeEl.style.display = 'none';
            cfgBtn.style.display = 'inline-block';
        }

        coreBtn.style.display = 'inline-block';
        ctxBtn.style.display = 'inline-block';
        
        // Fill form
        document.getElementById('agent-form-id').value = agent.id;
        document.getElementById('agent-form-id').disabled = true;
        document.getElementById('agent-form-name').value = agent.name || '';
        document.getElementById('agent-form-description').value = agent.description || '';
        document.getElementById('agent-form-provider').value = agent.provider || 'mistral';
        
        // Preencher checkboxes de tools nativas
        const nativeTools = agent.tools_local || [];
        document.querySelectorAll('.native-tool-check').forEach(cb => {
            cb.checked = nativeTools.includes(cb.value);
        });
        
        // Preencher checkboxes de MCP servers (será feito após carregar a lista)
        setTimeout(() => {
            const mcpServers = agent.tools_mcp || [];
            document.querySelectorAll('.mcp-server-check').forEach(cb => {
                cb.checked = mcpServers.includes(cb.value);
            });
        }, 500);
        
        document.getElementById('agent-form-env').value = (agent.env_vars || []).join('\n');
        
        document.getElementById('btn-delete-agent').style.display = agent.is_master ? 'none' : 'block';
        
        if (activeAgentId !== agentId || !document.querySelector('.agent-segment.active')) {
            switchAgentSegment('core');
        }
        
        loadAgentFiles();
    }
}

async function saveAgentConfig() {
    const idField = document.getElementById('agent-form-id');
    const id = idField.value.trim();
    if(!id) return alert('Insira um ID para o sub-agente (Letras minúsculas e sublinhados, ex: criador_de_tweets).');
    
    const btn = event.target;
    const oldTxt = btn.innerText;
    btn.innerText = "Salvando...";
    btn.disabled = true;
    
    const envText = document.getElementById('agent-form-env').value;
    const envVars = {};
    envText.split('\n').forEach(line => {
        if(line.includes('=')) {
            const parts = line.split('=');
            envVars[parts[0].trim()] = parts.slice(1).join('=').trim();
        }
    });
    
    // Coletar tools nativas selecionadas
    const selectedNativeTools = Array.from(document.querySelectorAll('.native-tool-check:checked'))
        .map(cb => cb.value);
    
    // Coletar servidores MCP selecionados
    const selectedMcpServers = Array.from(document.querySelectorAll('.mcp-server-check:checked'))
        .map(cb => cb.value);
    
    const payload = {
        id: id,
        name: document.getElementById('agent-form-name').value || id,
        description: document.getElementById('agent-form-description').value,
        provider: document.getElementById('agent-form-provider').value,
        tools_local: selectedNativeTools,
        tools_mcp: selectedMcpServers,
        env_vars: envVars
    };
    
    try {
        const res = await fetch('/api/agents', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if(res.ok) {
            alert('Especialista salvo com sucesso e adicionado na sua agência MoltyClaw!');
            await loadAgentList();
            selectAgent(payload.id);
        } else {
            const err = await res.json();
            alert('Falha ao salvar agente: ' + err.error);
        }
    } catch(e) {
        alert('Erro de conexão.');
    } finally {
        btn.innerText = oldTxt;
        btn.disabled = false;
    }
}

async function deleteAgent() {
    if (!activeAgentId || activeAgentId === 'MoltyClaw' || activeAgentId === '__NEW__') return;
    
    if (!confirm(`Tem certeza que deseja excluir o agente '${activeAgentId}'? Isso apagará sua configuração, alma e memória permanentemente.`)) {
        return;
    }
    
    try {
        const res = await fetch(`/api/agents/${activeAgentId}`, {
            method: 'DELETE'
        });
        
        if (res.ok) {
            alert('Agente removido com sucesso.');
            await loadAgentList();
        } else {
            const err = await res.json();
            alert('Erro ao excluir: ' + err.error);
        }
    } catch(e) {
        alert('Erro de conexão.');
    }
}

// ─── Tools Selector Functions ───────────────────────────────────────────────

function selectAllTools(select) {
    const checkboxes = document.querySelectorAll('.native-tool-check');
    checkboxes.forEach(cb => cb.checked = select);
}

async function loadMcpToolsSelector() {
    const container = document.getElementById('mcp-tools-selector');
    if (!container) return;
    
    container.innerHTML = '<div class="mcp-loading"><i class="fa-solid fa-circle-notch fa-spin"></i> Carregando servidores MCP...</div>';
    
    try {
        const res = await fetch('/api/mcp/list');
        const data = await res.json();
        const installedMcps = data.installed || [];
        
        if (installedMcps.length === 0) {
            container.innerHTML = '<div class="mcp-loading" style="color: var(--text-muted);"><i class="fa-solid fa-info-circle"></i> Nenhum servidor MCP instalado. Vá para a aba MCP para instalar.</div>';
            return;
        }
        
        container.innerHTML = '';
        
        installedMcps.forEach(mcpId => {
            const mcpInfo = (data.mcps || []).find(m => m.id === mcpId);
            const mcpName = mcpInfo ? mcpInfo.name : mcpId;
            const mcpDesc = mcpInfo ? mcpInfo.description : 'Servidor MCP instalado';
            
            const item = document.createElement('div');
            item.className = 'mcp-server-item';
            item.innerHTML = `
                <input type="checkbox" class="mcp-server-check" value="${mcpId}" id="mcp-${mcpId}">
                <div class="mcp-server-info">
                    <div class="mcp-server-name">${mcpName}</div>
                    <div class="mcp-server-desc">${mcpDesc}</div>
                </div>
                <span class="mcp-server-badge">Instalado</span>
            `;
            container.appendChild(item);
        });
    } catch (e) {
        console.error('Erro ao carregar MCPs:', e);
        container.innerHTML = '<div class="mcp-loading" style="color: #ef4444;"><i class="fa-solid fa-exclamation-triangle"></i> Erro ao carregar servidores MCP</div>';
    }
}

// Carregar MCP tools quando a aba Agent Config for aberta
function onAgentConfigSegmentOpen() {
    loadMcpToolsSelector();
}

let currentAgentFile = 'soul';
let agentFilesContent = {
    soul: '',
    memory: '',
    identity: '',
    user: '',
    bootstrap: ''
};

async function loadAgentFiles() {
    try {
        const query = `?agent=${activeAgentId}`;
        const files = ['memory', 'soul', 'identity', 'user', 'bootstrap'];
        
        for (const f of files) {
            try {
                const res = await fetch(`/api/agent/${f}${query}`);
                const data = await res.json();
                agentFilesContent[f] = data.content || '';
            } catch (err) {
                console.warn(`Could not load ${f} for agent ${activeAgentId}`, err);
            }
        }

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
    const targetCard = document.getElementById(`card-${fileId}`);
    if (targetCard) targetCard.classList.add('active');

    if (activeEditor) {
        activeEditor.value = agentFilesContent[fileId] || '';
    }

    const titleEl = document.getElementById('current-editor-title');
    const pathEl = document.getElementById('current-editor-path');
    
    const rootPath = activeAgentId === 'MoltyClaw' ? '~/.moltyclaw/workspace/' : `~/.moltyclaw/agents/${activeAgentId}/workspace/`;

    const fileMap = {
        soul: 'SOUL.md',
        identity: 'IDENTITY.md',
        user: 'USER.md',
        bootstrap: 'BOOTSTRAP.md',
        memory: 'MEMORY.md'
    };

    const fileName = fileMap[fileId] || 'UNKNOWN.md';
    titleEl.innerText = fileName;
    pathEl.innerText = rootPath + fileName;
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
        const res = await fetch(`/api/agent/${currentAgentFile}?agent=${activeAgentId}`, {
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
        const data = await res.json(); // format { "discord": ["MoltyClaw", "goku"], ... }

        const platforms = ['whatsapp', 'discord', 'telegram', 'twitter', 'bluesky'];
        platforms.forEach(p => {
            const activeList = data[p] || [];
            const toggle = document.getElementById(`toggle-${p}`);
            const activeDiv = document.getElementById(`active-${p}`);
            
            if (toggle) toggle.checked = activeList.length > 0;
            if (activeDiv) {
                activeDiv.innerHTML = activeList.map(id => `<span class="int-agent-pill">${id}</span>`).join('');
            }
        });
    } catch (e) {
        console.error('Failed to fetch integrations', e);
    }
}

async function toggleIntegration(name) {
    const toggle = document.getElementById(`toggle-${name}`);
    const agentSelect = document.getElementById(`select-${name}`);
    const agentId = agentSelect ? agentSelect.value : 'MoltyClaw';
    const action = toggle.checked ? 'start' : 'stop';

    toggle.disabled = true; // Prevent spamming
    try {
        const res = await fetch(`/api/integrations/${action}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, agent_id: agentId })
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

// --- MCP Tab Logic ---
let mcpList = [];
let installedMcps = [];

async function loadMCPList() {
    const grid = document.getElementById('mcp-grid');
    if (grid) {
        grid.innerHTML = '<div style="grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 0; color: #64748b; font-family: sans-serif;"><i class="fa-solid fa-circle-notch fa-spin" style="font-size: 2.5rem; color: #3b82f6; margin-bottom: 20px;"></i><h3 style="color: #0f172a; margin: 0 0 10px 0;">Buscando Catálogo Local...</h3><p style="margin: 0; font-size: 14px;">Carregando a lista recomendada de servidores MCP oficiais suportados pelo MoltyClaw.</p></div>';
    }

    try {
        const res = await fetch('/api/mcp/list');
        const data = await res.json();
        mcpList = data.mcps || [];
        installedMcps = data.installed || [];
        renderMCPGrid();
    } catch (e) {
        console.error('Falha ao carregar MCPs', e);
        if (grid) {
            grid.innerHTML = '<div style="grid-column: 1 / -1; color: #ef4444; padding: 20px; text-align: center; border: 1px solid #ef4444; border-radius: 12px; background: #fef2f2;">Falha de Conexão: Não foi possível baixar o Registry.</div>';
        }
    }
}

function renderMCPGrid() {
    const grid = document.getElementById('mcp-grid');
    if (!grid) return;

    grid.innerHTML = '';

    mcpList.forEach(mcp => {
        const isInstalled = installedMcps.includes(mcp.id);
        const card = document.createElement('div');

        // Usar variáveis CSS ou classes para suportar o Dark Mode
        card.className = 'mcp-card';
        if (isInstalled) card.classList.add('installed');

        card.innerHTML = `
            <div class="mcp-card-header">
                <h3 class="mcp-card-title">
                    <i class="fa-solid fa-cube" style="color: ${isInstalled ? '#22c55e' : '#ef4444'}; margin-right: 8px;"></i>
                    ${mcp.name}
                </h3>
                ${isInstalled ? '<span class="mcp-badge-active"><i class="fa-solid fa-check" style="margin-right: 4px;"></i>Ativo</span>' : ''}
            </div>
            <p class="mcp-card-desc">${mcp.description}</p>
            <div class="mcp-card-command">
                > ${mcp.command} ${mcp.args[0] ? mcp.args[0] : ''}
            </div>
            <div class="mcp-card-footer">
                <button class="btn-primary mcp-install-btn" 
                    ${isInstalled ? 'disabled' : ''} 
                    onclick="installMCP(event, '${mcp.id}')">
                    ${isInstalled ? 'Configurado no start_moltyclaw' : '<i class="fa-solid fa-download" style="margin-right: 5px;"></i> Instalar Módulo'}
                </button>
            </div>
        `;

        grid.appendChild(card);
    });
}

async function installMCP(event, mcpId) {
    const target = mcpList.find(m => m.id === mcpId);
    if (!target) return;

    const originalBtnContent = event.currentTarget.innerHTML;
    event.currentTarget.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Clonando e Instalando... (Pode demorar)';
    event.currentTarget.disabled = true;

    try {
        const res = await fetch('/api/mcp/install', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(target)
        });

        if (res.ok) {
            alert(`O Módulo Cybernético '${target.name}' foi instalado no seu 'mcp_servers.json' e está pronto para uso!\n\nFeche o Launcher (Ctrl+C) e rode 'python start_moltyclaw.py' navamente para a plataforma despertar com os novos poderes MCP ativos na rede.`);
            loadMCPList(); // Refresh grid
        } else {
            alert('Falha ao instalar MCP');
            event.currentTarget.innerHTML = originalBtnContent;
            event.currentTarget.disabled = false;
        }
    } catch (e) {
        alert('Erro de conexão ao instalar MCP');
        event.currentTarget.innerHTML = originalBtnContent;
        event.currentTarget.disabled = false;
    }
}

// Segment switching within the Agent View
function switchAgentSegment(segment) {
    // Tabs
    document.querySelectorAll('.agent-tab').forEach(tab => tab.classList.remove('active'));
    document.getElementById(`btn-agent-${segment}`).classList.add('active');

    // Content containers
    const coreSeg = document.getElementById('agent-segment-core');
    const contextSeg = document.getElementById('agent-segment-context');
    const configSeg = document.getElementById('agent-segment-config');

    [coreSeg, contextSeg, configSeg].forEach(s => {
        if(s) s.style.display = 'none';
    });

    if (segment === 'core') {
        if(coreSeg) coreSeg.style.display = 'flex';
    } else if (segment === 'config') {
        if(configSeg) configSeg.style.display = 'flex';
        // Carregar MCP tools quando abrir a aba de configuração
        loadMcpToolsSelector();
    } else {
        if(contextSeg) contextSeg.style.display = 'flex';
    }
}

async function importContext() {
    // Reset modal to first stage
    goToStage('prompt');
    document.getElementById('context-input-text').value = '';
    document.getElementById('import-context-modal').classList.add('active');
}

function closeImportModal() {
    document.getElementById('import-context-modal').classList.remove('active');
}

function goToStage(stage) {
    // Hide all stages
    document.querySelectorAll('.modal-stage').forEach(s => s.classList.remove('active'));
    // Show target stage
    const target = document.getElementById(`stage-${stage}`);
    if (target) target.classList.add('active');

    // Update title based on stage
    const title = document.getElementById('modal-title');
    if (stage === 'prompt') title.innerText = 'Extract Context';
    if (stage === 'input') title.innerText = 'Import Knowledge';
    if (stage === 'loading') title.innerText = 'Assimilating...';
    if (stage === 'review') title.innerText = 'Review Memory';
    if (stage === 'success') title.innerText = 'Done!';
}

function copyPrompt() {
    const promptText = document.getElementById('extraction-prompt').innerText;
    navigator.clipboard.writeText(promptText).then(() => {
        alert('Prompt copiado! Cole no seu outro assistente.');
    });
}

async function processContext() {
    const contextData = document.getElementById('context-input-text').value.trim();
    if (!contextData) {
        alert('Por favor, insira o contexto extraído.');
        return;
    }

    goToStage('loading');

    try {
        const response = await fetch('/api/agent/import_context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ context: contextData })
        });

        if (response.ok) {
            const data = await response.json();
            // Show new memory for review
            document.getElementById('new-memory-preview').value = data.new_content;
            goToStage('review');
        } else {
            const err = await response.json();
            alert(`Erro na assimilação: ${err.error}`);
            goToStage('input');
        }
    } catch (e) {
        alert('Erro de rede ao processar contexto.');
        goToStage('input');
    }
}

async function fetchBindings() {
    try {
        const response = await fetch('/api/bindings');
        const bindings = await response.json();
        renderBindings(bindings);
    } catch (e) {
        console.error("Erro ao buscar bindings:", e);
    }
}

function renderBindings(bindings) {
    const list = document.getElementById('bindings-list');
    list.innerHTML = '';
    
    bindings.forEach((b, index) => {
        const tr = document.createElement('tr');
        const m = b.match || {};
        
        let context = `<strong>Canal:</strong> ${escapeHTML(m.channel || '-')}`;
        if (m.guild_id) context += `<br><strong>Guild/Chat:</strong> ${escapeHTML(m.guild_id)}`;
        if (m.peer_id) context += `<br><strong>Peer/User:</strong> ${escapeHTML(m.peer_id)}`;
        
        tr.innerHTML = `
            <td>${escapeHTML(m.channel || '-')}</td>
            <td><span class="agent-pill">${escapeHTML(b.agent_id)}</span></td>
            <td class="context-cell">${context}</td>
            <td>
                <button class="icon-btn delete" onclick="deleteBinding(${index})" title="Remover Regra">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </td>
        `;
        list.appendChild(tr);
    });
}

async function addBinding() {
    const platform = document.getElementById('route-platform').value;
    const agent = document.getElementById('route-agent').value;
    const guild = document.getElementById('route-guild').value.trim();
    const peer = document.getElementById('route-peer').value.trim();
    
    const newBinding = {
        agent_id: agent,
        match: {
            channel: platform
        }
    };
    
    if (guild) newBinding.match.guild_id = guild;
    if (peer) newBinding.match.peer_id = peer;
    
    try {
        const currentResp = await fetch('/api/bindings');
        const bindings = await currentResp.json();
        bindings.push(newBinding);
        
        await fetch('/api/bindings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bindings)
        });
        
        // Limpar campos
        document.getElementById('route-guild').value = '';
        document.getElementById('route-peer').value = '';
        
        fetchBindings();
    } catch (e) {
        alert("Erro ao adicionar binding.");
    }
}

async function deleteBinding(index) {
    if (!confirm("Remover esta regra de roteamento?")) return;
    
    try {
        const currentResp = await fetch('/api/bindings');
        let bindings = await currentResp.json();
        bindings.splice(index, 1);
        
        await fetch('/api/bindings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bindings)
        });
        
        fetchBindings();
    } catch (e) {
        alert("Erro ao remover binding.");
    }
}
