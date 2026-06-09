# analise o projeto

Exported: 5/29/2026, 9:11:33 PM

---

**User:**

analise o projeto

---

**Assistant:**

### Sub-Agent: Context Gatherer

**Explanation:** Delegando a análise completa do projeto para o context-gatherer, que vai explorar a estrutura e arquivos relevantes de forma eficiente.

**Prompt:**

Analise o projeto localizado em c:\Users\Cliente\OpenPy. Explore a estrutura de pastas e arquivos principais (ignorando .wwebjs_auth, .git e node_modules), leia os arquivos de configuração (package.json, README, etc.), os arquivos de código fonte principais, e qualquer documentação relevante. Forneça um resumo completo do que o projeto faz, sua arquitetura, tecnologias usadas, e estrutura geral.

**Response:**

## MoltyClaw — Resumo Completo do Projeto

### O que é

**MoltyClaw** (versão `v2026.5.4-1`) é um **agente de IA autônomo local**, desenvolvido em Python, que opera o computador Windows e a internet em tempo real. Diferente de chatbots convencionais, ele age: executa comandos no sistema, navega na web, envia mensagens, controla música, agenda tarefas e delega trabalho a sub-agentes — tudo de forma autônoma.

O projeto é publicado no PyPI como pacote `moltyclaw` e está disponível em `github.com/antojunimaia-ui/MoltyClaw`.

---

### Arquitetura Geral

O projeto é **híbrido Python + Node.js**:

- **Python** é o núcleo: toda a lógica de IA, integrações sociais, WebUI e orquestração
- **Node.js** é usado exclusivamente para a ponte com WhatsApp (`whatsapp-web.js`) e para o terminal persistente (`node-pty`)

```
start_moltyclaw.py          ← Entrypoint CLI global
src/
├── moltyclaw.py            ← Classe principal: loop cognitivo, tool execution, LLM calls
├── system_prompt.py        ← Builder modular do system prompt
├── routing.py              ← Roteamento de mensagens → agente correto
├── skills.py               ← Sistema de Skills (Progressive Disclosure)
├── scheduler.py            ← Agendador de tarefas recorrentes
├── heartbeat.py            ← Monitor de saúde em background
├── memory_rag.py           ← Busca híbrida semântica + BM25 na memória
├── subagent_registry.py    ← Rastreamento de sub-agentes ativos
├── config_loader.py        ← Leitura do moltyclaw.json
├── initializer.py          ← Setup inicial do diretório ~/.moltyclaw
├── onboarding.py           ← Wizard de configuração inicial
├── integrations/
│   ├── whatsapp_bridge.js  ← Bridge Node.js (whatsapp-web.js)
│   ├── whatsapp_server.py  ← Servidor aiohttp (porta 8080) que recebe do bridge
│   ├── discord_bot.py      ← Bot Discord (discord.py)
│   ├── telegram_bot.py     ← Bot Telegram (python-telegram-bot)
│   ├── twitter_bot.py      ← Bot Twitter/X (tweepy)
│   ├── bluesky_bot.py      ← Bot Bluesky (atproto)
│   └── mcp_hub.py          ← Gerenciador de servidores MCP externos
├── terminal/
│   └── pty_bridge.js       ← Terminal persistente via node-pty (WebSocket porta 9001)
└── webui/
    ├── app.py              ← Flask app com SSE streaming
    ├── env_manager.py      ← Gerenciador de variáveis de ambiente
    ├── gateway.py          ← Gateway de roteamento da WebUI
    ├── templates/index.html
    └── static/ (script.js, style.css)
```

---

### Loop Cognitivo (Como o Agente Pensa)

O método central é `MoltyClaw.ask()` em `src/moltyclaw.py`. O ciclo é:

1. Usuário envia mensagem
2. LLM recebe: system prompt + histórico + SOUL + MEMORY + Skills + ferramentas MCP
3. LLM raciocina em `<think>...</think>` (invisível ao usuário)
4. LLM emite resposta direta **ou** um bloco `<tool>{"action": "...", "param": "..."}</tool>`
5. Python parseia e executa a ferramenta
6. Output é injetado no histórico como `[SISTEMA]`
7. Loop reinicia até ter resposta final

**Importante**: o projeto **não usa function calling nativo das APIs**. O LLM é treinado via system prompt a emitir JSON cru em tags `<tool>`, garantindo compatibilidade com qualquer modelo.

---

### Tecnologias Usadas

**Python (backend principal)**
- `mistralai`, `google-generativeai`, `openai` (OpenRouter), `ollama` — providers de LLM
- `playwright` + `playwright-stealth` — browser automation com anti-bot stealth
- `flask` — WebUI com SSE streaming
- `aiohttp` — servidor async para WhatsApp bridge
- `discord.py` — bot Discord
- `python-telegram-bot` — bot Telegram
- `tweepy` — bot Twitter/X
- `atproto` — bot Bluesky
- `edge-tts` — síntese de voz (Microsoft Edge Neural TTS)
- `spotipy` — controle do Spotify
- `imap_tools` — leitura de e-mails via IMAP
- `mcp` — Model Context Protocol (ferramentas externas)
- `rich` — UI de terminal colorida
- `questionary` — menus interativos no CLI

**Node.js (bridge)**
- `whatsapp-web.js` — automação do WhatsApp Web
- `node-pty` — terminal persistente (PTY)
- `ws` — WebSocket server para o PTY bridge
- `axios`, `dotenv`, `qrcode-terminal`

---

### Providers de LLM Suportados

| Provider | Modelos |
|---|---|
| Mistral AI | mistral-small/medium/large, pixtral |
| Google Gemini | gemini-1.5-flash/pro, gemini-2.0-flash |
| OpenRouter | Qualquer modelo (Llama, Claude, etc.) |
| Koda Cloud | gemini-2.5-flash, mistral-large, codestral |
| Ollama | Modelos locais (llama3, mistral, phi3...) |

O sistema tem **auto-discovery**: se a chave do provider configurado não existir, tenta automaticamente outro provider disponível.

---

### Ferramentas Disponíveis para o Agente

- **Browser**: `OPEN_BROWSER`, `GOTO`, `READ_PAGE`, `INSPECT_PAGE`, `CLICK`, `TYPE`, `SCREENSHOT`, `SCROLL_DOWN`, `DDG_SEARCH`
- **Sistema**: `CMD` (PowerShell/CMD do Windows, bloqueado em modo público)
- **Canvas**: `CANVAS_UPDATE` (renderiza HTML, Markdown, SVG, React na WebUI)
- **E-mail**: `READ_EMAILS`, `SEND_EMAIL`, `DELETE_EMAIL`
- **Spotify**: `SPOTIFY_PLAY`, `SPOTIFY_PAUSE`, `SPOTIFY_SEARCH`, `SPOTIFY_ADD_QUEUE`
- **YouTube**: `YOUTUBE_SUMMARIZE`
- **Voz**: `VOICE_REPLY` (TTS via Edge Neural)
- **Mensagens**: `WHATSAPP_SEND`, `DISCORD_SEND`, `TELEGRAM_SEND`, `X_POST`, `BLUESKY_POST`
- **Arquivos**: `FILE_WRITE`, `FILE_APPEND`, `FILE_READ`
- **Memória**: `MEMORY_SEARCH` (busca híbrida semântica + BM25)
- **Skills**: `SKILL_USE`
- **Sub-agentes**: `SESSION_SPAWN`, `SESSION_SEND`, `SESSION_HISTORY`, `SESSION_LIST`
- **MCP**: `MCP_TOOL` (ferramentas de servidores externos)

---

### Sistema de Identidade e Memória

Cada agente opera em um **Workspace** isolado em `~/.moltyclaw/`:

```
~/.moltyclaw/workspace/
├── SOUL.md       ← Personalidade e valores (injetado no system prompt)
├── IDENTITY.md   ← Fatos técnicos sobre o agente
├── USER.md       ← O que o agente sabe sobre o usuário
├── BOOTSTRAP.md  ← Instruções executadas na primeira inicialização
└── MEMORY.md     ← Memória de longo prazo (hipocampo digital)
```

Sub-agentes ficam em `~/.moltyclaw/agents/<id>/workspace/` com a mesma estrutura.

---

### Sistema de Sub-Agentes (Swarm)

Todos os agentes são instâncias da mesma classe `MoltyClaw`. O Master pode spawnar sub-agentes via `SESSION_SPAWN`, que rodam em `asyncio.create_task()` (não bloqueiam o Master). Sub-agentes têm ferramentas restritas definidas em `config.json`. O `subagent_registry.py` rastreia todos os runs com `run_id`, status e timestamps.

---

### WebUI

Dashboard Flask com SSE streaming em `http://127.0.0.1:5000`:
- **Chat** — conversa com streaming de tokens em tempo real
- **Integrations** — liga/desliga bots por agente, gerencia bindings de roteamento
- **Agent** — editor live de SOUL/MEMORY/USER/IDENTITY por agente
- **Scheduler** — painel de tarefas recorrentes
- **MCP** — catálogo e instalador de servidores MCP

---

### CLI Global

Após `pip install moltyclaw`, o comando `moltyclaw` fica disponível globalmente com subcomandos para: `web`, `start discord/telegram/whatsapp/all`, `skill install/list/uninstall`, `mcp install/list/on/off/uninstall`, `config set/get`, `provider`, `model`, `doctor`, `update`, `reset memory`, `onboard`.

---

### Contexto do Projeto

- **Autor**: Júnior (`antojunimaia-ui` no GitHub)
- **Versão atual**: `v2026.5.4-1`
- **Licença**: MIT
- **Distribuição**: PyPI (`pip install moltyclaw`) + GitHub
- **Arquivo aberto**: `Release v26.0.0.md` (ainda vazio — release em preparação)
- **Pasta `temp/`**: contém arquivos de áudio MP3 e screenshots gerados pelo agente em uso real, indicando que o projeto está **em uso ativo**


Let me explore the project structure directly, ignoring the irrelevant folders.

Aqui está a análise completa do projeto:

---

## MoltyClaw

**MoltyClaw** é um agente de IA autônomo local para Windows, desenvolvido por Júnior (`antojunimaia-ui`). A versão atual é `v2026.5.4-1` (Release v26.0.0 em preparação). Está publicado no PyPI como `pip install moltyclaw`.

---

### O que faz

Diferente de chatbots comuns, o MoltyClaw **age**: executa comandos no sistema, navega na web com bypass de anti-bots, envia mensagens em múltiplas plataformas, controla música, agenda tarefas recorrentes e delega trabalho a sub-agentes — tudo de forma autônoma a partir de linguagem natural.

---

### Arquitetura

O projeto é **híbrido Python + Node.js**:

- **Python** é o núcleo — toda a lógica de IA, integrações, WebUI e orquestração
- **Node.js** é usado apenas para a ponte com WhatsApp (`whatsapp-web.js`) e terminal persistente (`node-pty`)

O loop cognitivo central (`MoltyClaw.ask()`) funciona assim:
1. LLM recebe system prompt + histórico + SOUL + MEMORY + Skills
2. Raciocina em `<think>...</think>` (invisível ao usuário)
3. Emite resposta direta **ou** um bloco `<tool>{"action": "...", "param": "..."}</tool>`
4. Python parseia, executa a ferramenta, injeta o resultado no histórico
5. Repete até ter resposta final

Não usa function calling nativo das APIs — o LLM é instruído via system prompt a emitir JSON cru em tags `<tool>`, garantindo compatibilidade universal.

---

### Tecnologias principais

| Camada | Tecnologias |
|---|---|
| LLM providers | Mistral AI, Google Gemini, OpenRouter, Ollama |
| Browser automation | Playwright + playwright-stealth (Edge real, porta CDP 9222) |
| WebUI | Flask + SSE streaming |
| Integrações sociais | discord.py, python-telegram-bot, tweepy, atproto |
| Voz | edge-tts (Microsoft Neural TTS), Voxtral (transcrição) |
| Música | spotipy (Spotify) |
| E-mail | imap_tools |
| Ferramentas externas | MCP (Model Context Protocol) |
| Terminal | node-pty via WebSocket |
| UI de terminal | rich, questionary |

---

### Funcionalidades-chave

- **Operant ID** — injeta script JS na página para numerar elementos interativos, reduzindo o contexto de 50k linhas de HTML para ~50 tokens
- **Canvas** — renderiza HTML, Markdown, SVG, React na WebUI em tempo real
- **Sistema de Skills** — Progressive Disclosure: só nome/descrição no prompt, corpo carregado sob demanda via `SKILL_USE`
- **Sub-agentes (Swarm)** — instâncias paralelas da mesma classe `MoltyClaw`, com ferramentas restritas e workspace isolado
- **Roteamento dinâmico** — `routing.py` decide qual agente responde a qual pessoa/grupo por canal
- **Memória persistente** — `SOUL.md`, `MEMORY.md`, `USER.md`, `IDENTITY.md` por agente; busca híbrida BM25 + semântica
- **Scheduler** — jobs persistidos em `jobs.json`, sobrevivem a reinicializações

---

### Estado atual

A pasta `.wwebjs_auth` com sessão ativa e arquivos de áudio/screenshots em `temp/` indicam que o projeto está **em uso real**. O arquivo `Release v26.0.0.md` está aberto mas ainda vazio, sugerindo que uma nova release está sendo preparada.

---

**User:**

eu quero fazer uma coisa, eu quero que o agente principal  tenha acesso a todas as plataformas, não quero que sejam agentes separados, por exemplo, o agente da webui vai ser o mesmo do telegram ou discord, e se eu pedir por exemplo pela weui que o agente envie uma mensagem pra alguem na dm do discord, ele vai enviar

---

**User:**

continue

---

**Assistant:**

Deixa eu entender o estado atual antes de implementar.

Agora vou ver como as tools `DISCORD_SEND`, `TELEGRAM_SEND` e `WHATSAPP_SEND` estão implementadas no `moltyclaw.py`:

Agora tenho o quadro completo. Vou analisar o problema:

**Situação atual:**
- `discord_bot.py` ainda cria instâncias próprias de `MoltyClaw` (via `routing.py` + `agent_instances`) em vez de usar o `AgentHub`
- `telegram_bot.py` idem — tem seu próprio `agent_instances` e não usa o `AgentHub`
- `whatsapp_server.py` idem — cria um `MoltyClaw` próprio
- Só a WebUI e o Discord bot já usam o `AgentHub` (o Discord foi migrado, o Telegram não)

**O que precisa mudar:**
1. `telegram_bot.py` → migrar para `AgentHub` (igual ao Discord)
2. `whatsapp_server.py` → migrar para `AgentHub`
3. As tools `DISCORD_SEND`, `TELEGRAM_SEND`, `WHATSAPP_SEND` já funcionam via API direta — isso está correto e não precisa mudar

Vamos fazer as migrações:

Agora preciso garantir que o `AgentHub` também exponha o `transcribe_audio_sync` de forma assíncrona para o Telegram (que roda no loop do próprio bot). Vou verificar se o `ask` do hub já passa o `reply_callback` corretamente, e também checar se o `start_integration` no `app.py` ainda passa `--agent` para o Telegram (o que não faz mais sentido):

O `start_integration` ainda passa `--agent` e `--name` para os scripts Python. Como o Telegram e WhatsApp agora usam o `AgentHub` e não aceitam mais esses argumentos, preciso ajustar o `app.py` para não passar esses args para eles (ou simplesmente ignorar no script). A forma mais limpa é remover o `argparse` do Telegram (já feito) e ajustar o `app.py` para não passar `--agent` para integrações que usam o hub:

Agora preciso garantir que o `AgentHub.ask()` suporte o `reply_callback` para que sub-agentes possam anunciar resultados de volta ao canal correto. Vou verificar se isso já existe:

O `reply_callback` já está no `AgentHub.ask()`. Agora vou verificar se o `ask_sync` também o suporta (para o caso do WhatsApp que é síncrono):

O `whatsapp_server.py` agora usa `hub.ask()` de forma assíncrona (é um servidor aiohttp), então está correto. Mas o `whatsapp_server.py` roda em seu próprio processo separado — ele vai criar um `AgentHub` próprio, não compartilhado com a WebUI. Isso é um problema arquitetural: processos separados não compartilham memória.

Vou verificar como o `start_integration` inicia o WhatsApp:

Confirmado: Discord, Telegram, WhatsApp e outros são iniciados como **processos separados** via `subprocess.Popen`. Isso significa que cada processo tem seu próprio `AgentHub` e sua própria instância do `MoltyClaw` — eles não compartilham estado.

A solução correta para ter **um único agente** é fazer todos os bots rodarem **dentro do mesmo processo** que a WebUI, não como subprocessos separados. Vou refatorar o `start_integration` para iniciar os bots como tasks assíncronas dentro do loop do `AgentHub`, em vez de subprocessos:

Agora vou criar um `IntegrationManager` no `AgentHub` que roda os bots como tasks dentro do mesmo processo/loop, e refatorar o `start_integration` do `app.py` para usá-lo:

Agora vou adicionar o `IntegrationManager` ao final do `AgentHub`, antes do fechamento da classe:

Agora vou atualizar o `app.py` para usar o `hub.start_integration()` e `hub.stop_integration()` em vez do `subprocess.Popen` direto, e também atualizar o endpoint de status das integrações:

Agora preciso ajustar o `toggle_integration` no `app.py` para não passar `agent_id` (já que agora é sempre o agente único):

Agora vou verificar se há algum problema de diagnóstico nos arquivos modificados:

Tudo limpo. Vou fazer uma verificação final para garantir que o `start_moltyclaw.py` (CLI) também está alinhado com a nova arquitetura quando inicia os bots via linha de comando:

O CLI (`start_moltyclaw.py`) ainda inicia os bots como subprocessos separados. Preciso atualizar as funções `run_discord`, `run_telegram` e `run_whatsapp` para usar o `AgentHub` em vez de subprocessos:

Tudo limpo. Aqui está um resumo do que foi feito:

---

### O que mudou

**Problema raiz:** Discord, Telegram e WhatsApp eram iniciados como subprocessos separados, cada um criando sua própria instância do `MoltyClaw`. Isso significa que cada canal tinha seu próprio histórico, memória e estado — eram agentes diferentes.

**Solução:** Todos os canais agora rodam dentro do mesmo processo, compartilhando o `AgentHub` (e portanto a mesma instância do `MoltyClaw`).

---

**`src/integrations/telegram_bot.py`** — Reescrito para usar `get_hub()` igual ao Discord. Removido o sistema de `agent_instances` e `routing.py`. Agora é um bot simples que passa mensagens para o hub compartilhado.

**`src/integrations/whatsapp_server.py`** — Reescrito para usar `get_hub()`. Removida a criação própria de `MoltyClaw`. O servidor aiohttp agora é apenas um receptor que repassa para o hub.

**`src/agent_hub.py`** — Adicionado o `IntegrationManager`: métodos `start_integration()`, `stop_integration()` e `get_active_integrations()`. Discord e Telegram rodam como `asyncio.Task` dentro do loop do hub. WhatsApp roda o servidor aiohttp como task interna (o bridge Node.js ainda é subprocesso separado, pois é Node). Twitter e Bluesky continuam como subprocesso (sem runner nativo ainda).

**`src/webui/app.py`** — `start_integration()` e `stop_integration()` agora delegam para `hub.start_integration()`. O endpoint `/api/integrations` usa `hub.get_active_integrations()`.

**`start_moltyclaw.py`** — `run_discord()`, `run_telegram()` e `run_whatsapp()` agora chamam `hub.start_integration()` em vez de subprocessos.

---

**Resultado prático:** Se você pedir pela WebUI "manda uma mensagem pro fulano no Discord", o agente usa `DISCORD_SEND` com o token que já está no `.env` — e funciona, porque é o mesmo agente que recebe mensagens do Discord, Telegram e WhatsApp.

---

**User:**

Na integração de WhatssApp, o MoltyClaw poderia saber quais são os meus contatos, e poder ver a mensagem de cada um

---

**Assistant:**

Deixa eu ver como o bridge do WhatsApp está implementado hoje:

Agora vejo o quadro completo. O bridge Node.js já tem acesso ao cliente `whatsapp-web.js` que expõe tudo — contatos, chats, histórico. Só precisa adicionar endpoints para isso e as tools correspondentes no Python.

Vou implementar:
1. **Bridge**: novos endpoints `/get_contacts`, `/get_chats`, `/get_chat_messages`
2. **Python**: tools `WHATSAPP_GET_CONTACTS`, `WHATSAPP_GET_CHATS`, `WHATSAPP_GET_MESSAGES`
3. **moltyclaw.py**: registrar as tools na lista e no executor

Agora vou adicionar as três tools no `moltyclaw.py`. Primeiro localizo onde ficam as outras tools do WhatsApp:

Agora tenho tudo que preciso. Vou adicionar o método `execute_whatsapp_read` no `moltyclaw.py` e registrar as três novas tools:

Agora adiciono o despacho das novas tools no loop principal do `ask()`:

O replace acima não mudou nada porque os textos eram iguais. Preciso adicionar o bloco das novas tools logo após o bloco existente:

Agora registro as três tools na lista `_build_tools_list`:

Agora verifica diagnósticos:

Tudo limpo. Vou fazer uma verificação rápida para confirmar que as três tools aparecem corretamente no código:

Tudo registrado nos três lugares certos: método, despacho no loop e lista de tools. Aqui está o resumo do que foi feito:

---

### O que mudou

**`whatsapp_bridge.js`** — Adicionados 3 novos endpoints no servidor HTTP da porta 8081:

- `GET /get_contacts` — busca todos os contatos salvos na agenda via `client.getContacts()`, filtrando grupos e retornando nome, número e ID
- `GET /get_chats` — busca as 50 conversas mais recentes via `client.getChats()`, com contagem de não lidas e prévia da última mensagem
- `POST /get_chat_messages` — recebe `{ chat_id, limit }` e busca as últimas N mensagens via `chat.fetchMessages()`, com direção (enviado/recebido), timestamp e tipo

**`moltyclaw.py`** — Adicionados:

- Método `execute_whatsapp_read()` que chama os novos endpoints do bridge via `aiohttp`
- Despacho das 3 novas actions no loop principal do `ask()`
- 3 novas tools registradas no `_build_tools_list` (visíveis no system prompt)

---

### Como usar

O agente agora pode fazer coisas como:

> "Quais são meus contatos no WhatsApp?"
→ usa `WHATSAPP_GET_CONTACTS`

> "Tem alguma mensagem não lida no zap?"
→ usa `WHATSAPP_GET_CHATS` e filtra `unreadCount > 0`

> "Me mostra a conversa com o João"
→ usa `WHATSAPP_GET_CONTACTS` para achar o ID, depois `WHATSAPP_GET_MESSAGES` com o ID

> "Responde pro Pedro que vou chegar às 18h"
→ usa `WHATSAPP_GET_CONTACTS` para achar o número, depois `WHATSAPP_SEND`

O bridge precisa estar conectado (QR Code escaneado) para as tools funcionarem. Se não estiver, o agente recebe uma mensagem de erro clara explicando isso.

---

**User:**

o MoltyClaw, a WebUI dele, é identica com a de outro agente em que ele foi inspirado, e eu quero mudar completamente, assim, tire a side, agora, a visualização de cada sidebar vai ser do lado direito, como um painel bem grande, e em cima desse painel vai estar as abas em forma de pilulas, sem categoria, a abna padrão selecionada vai ser a de arquivos, o chat chat, vai estar do lado direito desse painel

---

**Assistant:**

Deixa eu ver o estado atual da WebUI antes de redesenhar:

Tenho o suficiente para entender a estrutura completa. Vou redesenhar do zero — novo layout, novo CSS, mantendo todo o JS funcional.

O novo layout:
- **Esquerda**: chat (flex: 1)
- **Direita**: painel grande com abas em pílulas no topo, aba padrão = Arquivos (agent files)
- Sem sidebar lateral
- Navbar no topo com brand + status + tema

Agora tenho tudo. Vou reescrever o HTML e CSS completamente com o novo layout, mantendo todo o JS intacto.

Agora o CSS novo — do zero, limpo:

---
