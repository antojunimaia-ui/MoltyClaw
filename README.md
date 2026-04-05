![MoltyClaw Banner](MoltyClaw-Banner.png)

<p align="center">
  <b>MoltyClaw toma atitudes, não importa aonde você esteja.</b>
</p>

<p align="center">
  <a href="https://pypi.org/project/moltyclaw/"><img src="https://img.shields.io/pypi/v/moltyclaw?style=flat-square&color=00d7ff" alt="PyPI"></a>
  <a href="https://github.com/antojunimaia-ui/MoltyClaw"><img src="https://img.shields.io/github/stars/antojunimaia-ui/MoltyClaw?style=flat-square&color=00d7ff" alt="Stars"></a>
  <a href="https://github.com/antojunimaia-ui/MoltyClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/antojunimaia-ui/MoltyClaw?style=flat-square&color=00d7ff" alt="License"></a>
</p>

> **MoltyClaw** é um agente de IA autônomo e local, construído em Python, que opera o seu computador Windows e a Internet em tempo real com autonomia total. Ele não fica preso em uma janela de chat — ele age, pesquisa, clica, organiza arquivos, manda mensagens, controla música, delega tarefas a sub-agentes, renderiza código visualmente e responde a você por WhatsApp, Discord e Telegram simultaneamente.

---

## 📋 Índice

1. [Visão Geral e Filosofia](#visao-geral)
2. [O Loop Cognitivo — Como o Agente Pensa](#o-loop-cognitivo)
3. [Ferramentas Disponíveis — O Arsenal Completo](#ferramentas-disponiveis)
4. [Alma e Memória Persistente (A Tríade de Consciência)](#alma-e-memoria)
5. [Sistema de Skills — Módulos Inteligentes](#skills)
6. [Stealth Headless Browser & Playwright](#stealth-browser)
7. [Operant ID — Visão DOM Lógica](#operant-id)
8. [Canvas — Renderização Visual em Tempo Real](#canvas)
9. [Integração MCP — Model Context Protocol](#mcp)
10. [Integrações Sociais](#integracoes-sociais)
11. [IA de Voz — Audição e Síntese](#voz)
12. [Sistema de Sub-Agentes (Swarm)](#sub-agentes)
13. [Roteamento Dinâmico](#roteamento)
14. [Agendador (Scheduler) — Tarefas Recorrentes](#agendador)
15. [WebUI Dashboard](#webui)
16. [CLI Global — Comandos de Linha de Comando](#cli)
17. [Instalação e Configuração](#instalacao)
18. [Arquitetura de Arquivos (Padrão Workspace)](#workspace)

---

## <a id="visao-geral"></a>🧭 Visão Geral e Filosofia

O MoltyClaw nasceu de uma pergunta simples: **por que um agente de IA precisa ficar preso em uma janela de chat?**

A maioria dos assistentes de IA disponíveis no mercado são sistemas "passivos": recebem texto, retornam texto. Não conseguem abrir o navegador, não executam comandos reais no computador, não mandam mensagens autonomamente, não se lembram de você no dia seguinte.

O MoltyClaw rompe com esse paradigma. Ele é projetado como um **agente de ação**, onde a linguagem natural é apenas a superfície — a real potência está na capacidade de:

- **Atuar sobre o sistema operacional** via CMD/PowerShell com total autonomia
- **Navegar a web de forma humana** com bypass de anti-bots e fingerprint stealth
- **Renderizar código e documentos** em tempo real num painel visual interativo (Canvas)
- **Integrar-se a plataformas sociais** (WhatsApp, Discord, Telegram, Twitter/X, Bluesky)
- **Expandir seu próprio poder** conectando-se a servidores MCP externos a quente
- **Lembrar coerentemente** do usuário através de uma memória em disco de longo prazo
- **Carregar Skills modulares** que ensinam o agente workflows especializados sob demanda
- **Delegar tarefas** a sub-agentes especializados que rodam em paralelo em background
- **Trabalhar em Workspaces isolados**, garantindo que cada agente tenha sua própria pasta de arquivos e memórias sem interferência

O modelo base pode ser **Mistral AI**, **Google Gemini** ou qualquer modelo via **OpenRouter** — configurável via `.env` ou arquivo centralizado `~/.moltyclaw/moltyclaw.json`.

---

## <a id="o-loop-cognitivo"></a>🧠 O Loop Cognitivo — Como o Agente Pensa

O mecanismo central é implementado na classe `MoltyClaw` dentro de `src/moltyclaw.py`, no método `.ask()`.

### O Ciclo Pensa → Age → Observa

```
Usuário envia mensagem
        │
        ▼
  LLM recebe prompt + ferramentas + histórico + SOUL + MEMORY + Skills
        │
        ▼
  ┌────────────────────────────────┐
  │  <think> (raciocínio interno)  │  ← invisível ao usuário
  │  1. O que o usuário quer?      │
  │  2. Qual ferramenta usar?      │
  └────────────┬───────────────────┘
               │
   ┌───────────▼──────────┐
   │  Resposta Direta     │  ← Se já tem a resposta
   │  (texto ao usuário)  │
   └──────────────────────┘
               │
   ┌───────────▼──────────┐
   │  Tool Call em JSON   │  ← Se precisa agir
   │  <tool>              │
   │  {"action": "CMD",   │
   │   "param": "dir"}    │
   │  </tool>             │
   └───────────┬──────────┘
               │
         Python parseia e executa
               │
         Captura output (stdout, DOM, JSON...)
               │
         Injeta resultado no histórico como [SISTEMA]
               │
         Loop reinicia → LLM processa e decide o próximo passo
               │
         Repete até ter resposta final para o usuário
```

### Por que JSON no corpo da resposta?

O MoltyClaw não usa o sistema nativo de "function calling" das APIs. Em vez disso, o system prompt **treina o LLM a emitir blocos JSON crus** no formato `<tool>{"action": "...", "param": "..."}</tool>`. Isso garante:

1. **Compatibilidade universal**: Funciona com qualquer modelo que siga instruções.
2. **Debugging transparente**: Todo o fluxo é visível no terminal em tempo real.
3. **Controle granular**: O parser Python decide o que fazer com cada bloco.
4. **Raciocínio visível**: Blocos `<think>...</think>` são processados e descartados antes de exibir ao usuário.

---

## <a id="ferramentas-disponiveis"></a>🔧 Ferramentas Disponíveis — O Arsenal Completo

### 🌐 Navegação Web (Browser Playwright)

| Tool | Descrição |
|---|---|
| `OPEN_BROWSER` | Inicializa ou reinicia a sessão Edge/Playwright com stealth ativo |
| `GOTO` | Navega para uma URL. Aguarda `domcontentloaded` antes de retornar |
| `READ_PAGE` | Extrai o `body.innerText` da página atual (texto cru, sem HTML) |
| `INSPECT_PAGE` | Roda o script Operant ID: identifica e numera elementos interativos, desenha marcadores azuis na tela |
| `CLICK` | Clica num elemento CSS ou `[data-operant-id="X"]` |
| `TYPE` | Digita texto num input: `"seletor | texto"` |
| `PRESS_ENTER` | Pressiona Enter no foco atual |
| `PRESS_KEY` | Pressiona qualquer tecla: `Tab`, `Escape`, `ArrowDown`, etc. |
| `SCREENSHOT` | Captura a tela e salva em `~/.moltyclaw/temp/` |
| `SCROLL_DOWN` | Rola a página para baixo (útil em feeds com lazy loading) |
| `DDG_SEARCH` | Consulta a DuckDuckGo API diretamente, sem abrir o browser |

### ⚙️ Sistema Operacional

| Tool | Descrição |
|---|---|
| `CMD` | Executa qualquer comando no shell do Windows. Captura `stdout` + `stderr`. Executa no diretório workspace do agente. Bloqueado no modo público. |

### 🖼️ Canvas — Artefatos Visuais

| Tool | Descrição |
|---|---|
| `CANVAS_UPDATE` | Renderiza código ou documento num painel visual interativo da WebUI em tempo real. Formato: `"id | tipo | conteudo"`. Tipos suportados: `html`, `markdown`, `svg`, `react`, `css`, `js` |

### 📧 E-mail (Gmail via IMAP/SMTP)

| Tool | Descrição |
|---|---|
| `READ_EMAILS` | Lê os últimos N emails da caixa de entrada via IMAP |
| `SEND_EMAIL` | Envia email via SMTP: `"destinatario | assunto | corpo"` |
| `DELETE_EMAIL` | Remove email por UID no servidor IMAP |

Configuração: `GMAIL_USER` e `GMAIL_APP_PASSWORD` no `.env`.

### 🎵 Spotify

| Tool | Descrição |
|---|---|
| `SPOTIFY_PLAY` | Toca música por nome ou URI Spotify |
| `SPOTIFY_PAUSE` | Pausa a reprodução atual |
| `SPOTIFY_SEARCH` | Pesquisa músicas e retorna URIs |
| `SPOTIFY_ADD_QUEUE` | Enfileira uma faixa para reprodução futura |

### 📺 YouTube

| Tool | Descrição |
|---|---|
| `YOUTUBE_SUMMARIZE` | Baixa a transcrição de um vídeo via `youtube-transcript-api` e injeta no contexto para sumarização |

### 🔊 Síntese de Voz (Text-to-Speech)

| Tool | Descrição |
|---|---|
| `VOICE_REPLY` | Sintetiza texto em MP3 via Microsoft Edge TTS Neural (`pt-BR-AntonioNeural`). Com `"texto | ID_DESTINO"` envia ativamente ao destinatário via WhatsApp/Telegram/Discord |

### 📱 Integrações Sociais (Disparo Ativo)

| Tool | Canal |
|---|---|
| `WHATSAPP_SEND` | `"numero | texto opcional | caminho arquivo opcional"` |
| `DISCORD_SEND` | `"id_usuario | texto opcional | caminho arquivo opcional"` |
| `TELEGRAM_SEND` | `"id ou @username | texto opcional | caminho arquivo opcional"` |
| `X_POST` | Publica tweet de até 280 caracteres |
| `BLUESKY_POST` | Publica skeet de até 300 caracteres via AT Protocol |

### 📂 Workspace & Memória

| Tool | Descrição |
|---|---|
| `FILE_WRITE` | Cria ou sobrescreve um arquivo no workspace: `"caminho_relativo | conteudo"` |
| `FILE_APPEND` | Adiciona conteúdo ao final de um arquivo: `"caminho_relativo | conteudo"` |
| `FILE_READ` | Lê o conteúdo completo de um arquivo do workspace |
| `MEMORY_SEARCH` | Busca híbrida (semântica + BM25) na memória de longo prazo e diários |

### 🧩 Skills

| Tool | Descrição |
|---|---|
| `SKILL_USE` | Ativa uma skill pelo nome e carrega suas instruções detalhadas no contexto atual |

### 🤖 Sub-Agentes (Swarm)

| Tool | Descrição |
|---|---|
| `SESSION_SPAWN` | Spawna um sub-agente em background: `"id_do_agente | tarefa"` |
| `SESSION_SEND` | Injeta uma mensagem numa sessão ativa: `"id_sessao | mensagem"` |
| `SESSION_HISTORY` | Lê o histórico de pensamentos e ações de um agente ativo: `"id_sessao"` |
| `SESSION_LIST` | Lista todas as sessões ativas com status e tempo decorrido |

### 🔌 MCP (Model Context Protocol)

| Tool | Descrição |
|---|---|
| `MCP_TOOL` | Executa ferramenta de servidor MCP externo: `{"server": "nome", "tool": "ferramenta", "params": {...}}` |

---

## <a id="alma-e-memoria"></a>🪄 Alma e Memória Persistente

O MoltyClaw usa arquitetura baseada em **Workspaces** — cada agente opera dentro de uma subpasta `/workspace` com seus arquivos de identidade e memória.

### Estrutura por Agente

```
~/.moltyclaw/              ← Master (MoltyClaw)
└── workspace/
    ├── SOUL.md        # Personalidade, tom de voz e valores
    ├── IDENTITY.md    # Fatos fixos sobre quem o agente é
    ├── USER.md        # O que o agente sabe sobre você
    ├── BOOTSTRAP.md   # Instruções executadas na primeira inicialização
    └── MEMORY.md      # Memória de longo prazo (hipocampo digital)

~/.moltyclaw/agents/<id>/  ← Sub-agentes
└── workspace/
    └── (mesma estrutura acima)
```

### `SOUL.md` — A Identidade Inquebrável

Define o tom de voz, nível de formalidade, valores e restrições absolutas do agente. Injetado diretamente no system prompt a cada sessão.

### `IDENTITY.md` & `USER.md` — Contexto Estático

- `IDENTITY.md`: quem o agente *é* tecnicamente (especialidades, papel)
- `USER.md`: tudo o que o agente aprendeu sobre o usuário para personalizar respostas

### `MEMORY.md` — O Hipocampo Digital

Memória de longo prazo. O agente pode escrever nela via `FILE_APPEND` e buscá-la via `MEMORY_SEARCH`. É carregada automaticamente no início de cada conversa.

### `BOOTSTRAP.md` — O Manual de Inicialização

Se presente, o agente lê e executa suas instruções na primeira interação da sessão (útil para setup inicial de identidade ou tarefas automáticas).

### Migração Automática

O MoltyClaw detecta e migra automaticamente arquivos que estejam na raiz do agente (estrutura antiga) para dentro de `/workspace` (estrutura nova), sem intervenção manual.

---

## <a id="skills"></a>🧩 Sistema de Skills — Módulos Inteligentes

O sistema de Skills implementa **Progressive Disclosure**: ao invés de carregar instruções detalhadas de todas as skills no system prompt (caro em tokens), apenas o nome e descrição de cada skill são injetados. As instruções completas são carregadas sob demanda quando o agente invoca `SKILL_USE`.

### Estrutura de uma Skill

```
skill-name/
├── SKILL.md       ← Obrigatório: frontmatter YAML + instruções detalhadas
├── scripts/       ← Scripts auxiliares (opcional)
├── references/    ← Materiais de referência (opcional)
└── assets/        ← Outros recursos (opcional)
```

**Exemplo de `SKILL.md`:**

```markdown
---
name: git-helper
description: Auxilia com operações Git, commits semânticos e GitFlow
emoji: 🌿
requires:
  bins: [git]
---

# Git Helper

Instruções detalhadas sobre como fazer commits semânticos...
```

### Fontes de Skills (Precedência)

| Fonte | Caminho | Prioridade |
|---|---|---|
| Bundled | `~/.moltyclaw/bundled/skills/` | Menor (padrão do sistema) |
| Managed | `~/.moltyclaw/skills/` | Média (instaladas pelo usuário) |
| Workspace | `~/.moltyclaw/workspace/skills/` | Maior (projeto específico) |

Skills com o mesmo nome da fonte de maior prioridade sobrepõem as demais.

### Skills Bundled (pré-instaladas)

- 🌿 **git-helper** — Operações Git e commits semânticos
- 📁 **file-organizer** — Organização e categorização de arquivos
- 🔍 **web-search** — Estratégias avançadas de pesquisa na web
- ☁️ **weather** — Consulta de condições climáticas
- 👀 **code-reviewer** — Revisão e análise de código

### Gerenciamento via CLI

```bash
moltyclaw skill install ./minha-skill/    # Instala de pasta local
moltyclaw skill install skill.skill       # Instala de arquivo .skill (zip)
moltyclaw skill list                      # Lista skills instaladas
moltyclaw skill uninstall nome-da-skill   # Remove skill managed
```

---

## <a id="stealth-browser"></a>🥷 Stealth Headless Browser & Playwright

### O Problema

Serviços modernos (Cloudflare, Google, redes sociais) detectam scripts automatizados via:
- `navigator.webdriver = true` no JavaScript
- Ausência de plugins de browser reais
- User-Agent inconsistente com fingerprint
- Padrões de timing não-humanos

### A Solução: Edge Real + CDP + Socket Lock

O MoltyClaw usa **Microsoft Edge real** (não Chromium genérico) via Playwright com `playwright-stealth` injetado. Um navegador **Master** é inicializado na porta `9222`; todos os outros agentes se **conectam a ele via CDP** — compartilhando uma única instância:

```python
# Um único browser na porta 9222
browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
```

Um **lock via socket** na porta `9223` garante que apenas um agente inicialize o browser por vez, evitando race conditions mesmo em cenários de múltiplos agentes simultâneos. Como o lock é em nível de SO, é liberado automaticamente mesmo se o processo Python crashar.

O resultado é uma sessão que, para todos os fins dos sistemas anti-bot, parece ser uma pessoa real usando o Edge no Windows.

---

## <a id="operant-id"></a>🎯 Operant ID — Visão DOM Lógica

### O Problema

Uma página moderna tem 50.000+ linhas de HTML com CSS inline, SVGs e estruturas aninhadas. Jogar isso num LLM é caro, lento e causa alucinações.

### A Solução

Quando a IA chama `INSPECT_PAGE`, um script JavaScript é injetado via `page.evaluate()`:

1. **Remove ruído**: scripts, styles, SVGs, atributos CSS
2. **Identifica elementos interativos**: botões, links, inputs, selects, contenteditable
3. **Atribui IDs sequenciais**: `[data-operant-id="1"]`, `[data-operant-id="2"]`, ...
4. **Desenha marcadores azuis visuais** na tela para cada elemento
5. **Retorna descrição comprimida**: apenas texto + seletores

**Output típico:**

```
[data-operant-id="1"] -> <input role="text"> Username or email address
[data-operant-id="2"] -> <input role="password"> Password
[data-operant-id="3"] -> <button role="button"> Sign in
[data-operant-id="4"] -> <a role="link"> Forgot password?
```

A IA processa ~50 tokens e decide: `CLICK [data-operant-id="3"]`. Zero alucinação de HTML.

---

## <a id="canvas"></a>🖼️ Canvas — Renderização Visual em Tempo Real

A tool `CANVAS_UPDATE` permite ao agente renderizar código e documentos diretamente em um painel visual interativo na WebUI, **em tempo real** enquanto escreve.

**Uso:**
```
CANVAS_UPDATE: "meu-site | html | <!DOCTYPE html>..."
CANVAS_UPDATE: "relatorio | markdown | # Relatório..."
CANVAS_UPDATE: "diagrama | svg | <svg>..."
CANVAS_UPDATE: "componente | react | function App() {...}"
```

**Tipos suportados:** `html`, `markdown`, `svg`, `react`, `css`, `js`

Os artefatos são salvos em `~/.moltyclaw/canvas/<id>.<ext>` e o frontend é notificado via um marcador `<!-- MOLTY_CANVAS_SYNC -->` no stream SSE para sincronização silenciosa sem refresh.

---

## <a id="mcp"></a>🔌 Integração MCP — Model Context Protocol

### O que é MCP?

MCP (Model Context Protocol) é um padrão aberto que define como agentes de IA se comunicam com servidores de ferramentas externos via **Stdin/Stdout**. Um servidor MCP pode expor N ferramentas que ficam disponíveis para o agente sem modificação do código base.

### Como o MoltyClaw integra MCP

Na inicialização, o MoltyClaw lê `~/.moltyclaw/mcp_servers.json` e inicia cada servidor declarado como processo filho:

```json
{
  "mcpServers": {
    "meu_servidor_db": {
      "command": "python",
      "args": ["mcp_modules/meu_db_server/server.py"]
    },
    "filesystem": {
      "command": "node",
      "args": ["mcp_modules/mcp-filesystem/build/index.js"]
    }
  }
}
```

O `MCPHub` interno:

1. Inicia cada processo filho com suas configurações
2. Realiza o handshake MCP (`initialize` → `tools/list`)
3. **Injeta dinamicamente as ferramentas descobertas no system prompt** via placeholder `[MCP_TOOLS_INJECTED_HERE_AUTOMATICALLY]`
4. Mantém as conexões Stdio ativas durante toda a sessão

Sub-agentes têm acesso apenas aos servidores MCP listados em `config.json["tools_mcp"]`.

### Gerenciamento via CLI

```bash
moltyclaw mcp install https://github.com/exemplo/meu-mcp-server  # Clona, detecta node/python, build e registra
moltyclaw mcp list                                                 # Lista servidores registrados
moltyclaw mcp off meu_servidor_db                                  # Desativa sem remover
moltyclaw mcp on  meu_servidor_db                                  # Reativa
moltyclaw mcp uninstall meu_servidor_db                            # Remove pasta + JSON
```

---

## <a id="integracoes-sociais"></a>📱 Integrações Sociais

Cada integração roda em seu próprio processo, mas comparte o mesmo núcleo `MoltyClaw`.

### 📱 WhatsApp (Arquitetura híbrida Node.js ↔ Python)

```
Celular → WhatsApp Web (protocolo criptografado)
       → whatsapp_bridge.js  (Node.js + whatsapp-web.js)
       → whatsapp_server.py  (Python + aiohttp, porta 8081)
       → MoltyClaw.ask()     (processa, usa tools se necessário)
       → whatsapp_server.py  → bridge → resposta ao celular
```

- **Whitelist**: `WHATSAPP_ALLOWED_NUMBERS` no `.env`
- **Disparo ativo**: `WHATSAPP_SEND` para enviar a qualquer número
- **Transcrição de áudios**: PTTs OGG/MP3 são transcritos via Voxtral antes de chegar ao LLM

### 🎧 Discord (discord.py)

- Responde a menções (`@bot`) em qualquer canal e a DMs diretas
- Exibe indicador "typing..." enquanto processa
- Chunking automático de mensagens longas (limite de 2000 chars)
- **Whitelist**: `DISCORD_ALLOWED_USERS` (lista de User IDs)
- **Disparo ativo**: `DISCORD_SEND` para enviar DMs a qualquer User ID

### ✈️ Telegram (python-telegram-bot)

- Funciona em DMs e grupos (em grupos, só responde se mencionado ou respondido)
- Divisão automática de mensagens longas (limite de 4096 chars)
- **Whitelist**: `TELEGRAM_ALLOWED_USERS` (por `@username` ou ID numérico)
- **Disparo ativo**: `TELEGRAM_SEND` com suporte a texto, fotos, áudios e documentos
- **Announce de sub-agentes**: quando um sub-agente termina em background, o resultado chega automaticamente no chat que originou a tarefa

### 🐦 X / Twitter (API v2 + tweepy)

- Monitora menções e responde com tweets de até 280 caracteres
- **Disparo ativo**: `X_POST` para publicar tweets autônomos

### 🦋 Bluesky (AT Protocol + atproto)

- Autenticação via **App Password** isolado (nunca a senha principal)
- Resposta em thread respeitando `root_ref` e `parent_ref` do AT Protocol
- Limite de 300 caracteres com truncagem automática
- **Whitelist**: `BLUESKY_ALLOWED_HANDLES`
- **Disparo ativo**: `BLUESKY_POST` + `BLUESKY_GET_PROFILE`

---

## <a id="voz"></a>🎙️ IA de Voz — Audição e Síntese

### Audição — Transcrição via Voxtral (Mistral)

Arquivos de áudio enviados por qualquer canal são transcritos automaticamente:

- **Formatos**: MP3, OGG (PTTs WhatsApp/Telegram), WAV, M4A
- **Motor**: `voxtral-mini-latest` — Mistral Speech API
- O texto transcrito é injetado no contexto com nota de origem

### Síntese — Microsoft Edge TTS Neural

Quando a IA invoca `VOICE_REPLY`:

- Usa a biblioteca `edge-tts` com vozes neurais do Microsoft Edge
- Vozes disponíveis: `pt-BR-AntonioNeural`, `pt-BR-FranciscaNeural`, etc.
- O áudio MP3 é salvo em `~/.moltyclaw/temp/`
- **No WhatsApp**: enviado como nota de voz nativa
- **No Discord/Telegram**: enviado como arquivo de áudio
- **Disparo ativo**: com `"texto | ID_DESTINO"` envia para outra pessoa diretamente

---

## <a id="sub-agentes"></a>🤖 Sistema de Sub-Agentes (Swarm)

O MoltyClaw suporta **sub-agentes especializados** que operam em paralelo como um Swarm controlado.

### Arquitetura

Todos os agentes são instâncias da mesma classe `MoltyClaw`, diferenciados pela flag `is_master`:

| Aspecto | MoltyClaw (Master) | Sub-Agentes |
|---|---|---|
| Workspace | `~/.moltyclaw/workspace/` | `~/.moltyclaw/agents/<id>/workspace/` |
| Ferramentas locais | Todas | Apenas as de `config.json["tools_local"]` |
| Servidores MCP | Todos | Apenas os de `config.json["tools_mcp"]` |
| Provider/Modelo | Global via `.env` | Pode ter `.env` próprio com override |
| Pode spawnar outros | Sim | Apenas se `SESSION_SPAWN` estiver em `tools_local` |

### Configurando um Sub-Agente

```
~/.moltyclaw/agents/Pesquisador/
├── config.json     ← obrigatório
├── workspace/
│   ├── SOUL.md     ← personalidade própria (opcional)
│   └── MEMORY.md   ← memória própria (opcional)
└── .env            ← override de provider/API key (opcional)
```

**Exemplo de `config.json`:**

```json
{
  "name": "Pesquisador",
  "description": "Especialista em busca na web e síntese de informações",
  "provider": "gemini",
  "tools_local": ["DDG_SEARCH", "GOTO", "READ_PAGE", "INSPECT_PAGE", "FILE_WRITE"],
  "tools_mcp": []
}
```

### Execução Assíncrona (Background)

Quando o Master invoca `SESSION_SPAWN`, o sub-agente roda em `asyncio.create_task()` — não bloqueia o Master:

```
Usuário → "pesquise tendências de IA pra mim"
Master  → SESSION_SPAWN: "Pesquisador | Pesquise tendências de IA em 2025"
Master  → "✅ [Pesquisador] iniciado em background (run_id=a1b2c3d4)."
Master  → já responde e fica livre para outras tarefas

[...Pesquisador trabalha em paralelo...]

Pesquisador → termina → announce callback disparado
Usuário ← "✅ [Pesquisador] concluiu em 18s: {resultado}"
```

### Monitoramento em Tempo Real

```
SESSION_LIST    → lista sessões ativas com status e tempo
SESSION_HISTORY → lê o histórico de raciocínio de um agente ativo
SESSION_SEND    → injeta mensagem no contexto de um agente rodando
```

O `subagent_registry.py` rastreia todos os runs com `run_id`, status, timestamps, instância viva e resultado final.

---

## <a id="roteamento"></a>🔀 Roteamento Dinâmico

O `routing.py` decide **qual agente responde a qual pessoa/grupo** em cada canal, usando `~/.moltyclaw/bindings.json`:

```
Mensagem chega (Telegram, Discord, etc.)
      │
      ▼
routing.resolve_agent(channel, peer_id, guild_id)
      │
      ├─ Match por peer_id específico  → Agente A (prioridade máxima)
      ├─ Match por guild/servidor       → Agente B
      ├─ Match por canal genérico       → Agente C
      └─ Fallback                       → MoltyClaw (Master)
```

Os bindings são gerenciados pela aba **Integrations** da WebUI. Isso permite, por exemplo, que um grupo específico do Telegram seja atendido por um sub-agente especializado, enquanto DMs continuam indo ao Master.

---

## <a id="agendador"></a>⏲️ Agendador (Scheduler) — Tarefas Recorrentes

O motor de agendamento permite ao agente executar tarefas proativamente:

- **Jobs persistentes**: salvos em `~/.moltyclaw/jobs.json`, sobrevivem a reinicializações
- **Payload dinâmico**: cada job envia um prompt ao agente (ex: "Verifique o clima e me avise se vai chover")
- **Inteligência de ocupação**: se `agent.is_busy == True`, o scheduler aguarda a próxima janela livre
- **Intervalo mínimo**: checagem a cada 30 segundos; intervalo de job configurável em minutos

---

## <a id="webui"></a>🖥️ WebUI Dashboard

Dashboard web completo construído com **Flask** (backend SSE) + HTML/CSS/JS vanilla (frontend).

### Como Iniciar

```bash
moltyclaw web           # Modo local: http://127.0.0.1:5000
moltyclaw web --share   # Modo rede: http://0.0.0.0:5000 (exibe IP local automaticamente)
```

### Abas da Interface

| Aba | Função |
|---|---|
| **💬 Chat** | Interface de conversa com streaming de tokens em tempo real via SSE. Suporta Markdown, imagens, áudio e Canvas visual |
| **🔗 Integrations** | Toggles para ligar/desligar bots (WhatsApp, Discord, Telegram, etc.) por agente. Gerenciamento de Bindings |
| **🧠 Agent** | Editor live de `SOUL.md`, `MEMORY.md`, `USER.md` e `IDENTITY.md` por agente. Criação e exclusão de sub-agentes |
| **⏲️ Scheduler** | Painel de controle do motor de agendamento: adicionar, remover e ativar/desativar jobs |
| **🔌 MCP** | Catálogo e instalador de servidores Model Context Protocol |

### Streaming de Respostas (SSE)

```
Frontend POST /api/chat (JSON ou FormData com arquivo opcional)
         │
         ▼
Backend cria asyncio task na thread do agente
         │
         ▼
stream_callback → Queue thread-safe → Generator Flask
         │
         ▼
data: {"type": "token", "content": "..."}   ← tokens individuais
data: {"type": "tool", "content": "..."}    ← notificações de tool use
data: {"type": "done"}                      ← fim da resposta
```

### Upload de Arquivos

Arquivos enviados via WebUI são salvos em `~/.moltyclaw/temp/`. Áudios (MP3, OGG, WAV, M4A) são transcritos automaticamente via Voxtral antes de chegar ao agente.

### Assimilação de Contexto

Ferramenta que usa IA para fundir memórias de outros chats ou documentos diretamente no `MEMORY.md` sem criar duplicatas — via `POST /api/agent/import_context`.

---

## <a id="cli"></a>💻 CLI Global

Após instalação, o comando `moltyclaw` fica disponível globalmente.

```bash
# Iniciar o menu interativo (shell)
moltyclaw

# Setup Inicial
moltyclaw onboard          # Wizard: configura provider, modelo, API key e identidade

# WebUI
moltyclaw web              # WebUI em 127.0.0.1:5000
moltyclaw web --share      # WebUI aberta na rede em 0.0.0.0:5000

# Bots
moltyclaw start discord    # Inicia bot Discord em background
moltyclaw start telegram   # Inicia bot Telegram
moltyclaw start whatsapp   # Inicia WhatsApp (mostra QR Code para escanear)
moltyclaw start twitter    # Inicia bot Twitter/X
moltyclaw start bluesky    # Inicia bot Bluesky
moltyclaw start all        # Inicia todos simultaneamente

# Skills
moltyclaw skill install ./minha-skill/   # Instala skill de pasta local
moltyclaw skill install skill.skill      # Instala skill de arquivo .skill (zip)
moltyclaw skill list                     # Lista skills instaladas
moltyclaw skill uninstall nome           # Remove skill managed

# MCP
moltyclaw mcp install https://github.com/user/repo   # Instala MCP do GitHub
moltyclaw mcp list                                    # Lista servidores registrados
moltyclaw mcp off  nome_do_servidor                   # Desativa sem remover
moltyclaw mcp on   nome_do_servidor                   # Reativa
moltyclaw mcp uninstall nome_do_servidor              # Remove completamente

# Utilidades de IA
moltyclaw organize "C:\Users\Cliente\Downloads"
# → Escaneia a pasta, chama a IA, usa CMD (mkdir + move) para organizar por tipo

moltyclaw research "O que mudou do React 18 pro 19?"
# → Abre browser, pesquisa, lê artigos, exibe resumo técnico no terminal

# Configurações
moltyclaw config set MISTRAL_API_KEY sk-xxxx    # Grava variável no .env
moltyclaw config get MISTRAL_API_KEY             # Lê variável do .env
moltyclaw --config                               # Abre .env no editor

# Manutenção
moltyclaw update        # Verifica e aplica atualizações
moltyclaw reset memory  # Limpa o MEMORY.md
moltyclaw doctor        # Diagnóstico: Python, Node, .env, dependências
moltyclaw --help        # Lista todos os comandos
```

---

## <a id="instalacao"></a>🛠️ Instalação e Configuração

### Requisitos

| Componente | Versão Mínima |
|---|---|
| Python | 3.10+ |
| Microsoft Edge | Qualquer versão recente |
| Node.js | 18+ (apenas para WhatsApp) |

### Instalação via PyPI (Recomendado)

```bash
pip install moltyclaw
playwright install msedge
moltyclaw onboard
```

O wizard de onboarding:
1. Exibe aviso de segurança (o agente tem controle total sobre o sistema)
2. Pergunta o provider (Gemini, Mistral ou OpenRouter)
3. Solicita API Key e busca os modelos disponíveis em tempo real
4. Configura o `.env` e cria os arquivos de identidade (`SOUL.md`, `MEMORY.md`)

### Instalação Manual (Desenvolvimento)

```bash
git clone https://github.com/antojunimaia-ui/MoltyClaw.git
cd MoltyClaw
pip install -e .
playwright install msedge
moltyclaw onboard

# Somente para WhatsApp:
npm install
```

### Configuração

**`~/.moltyclaw/moltyclaw.json`** (suporta comentários e variáveis de ambiente):

```json
{
  "providers": {
    "gemini": {
      "api_key": "${GEMINI_API_KEY}",
      "model": "gemini-2.0-flash"
    },
    "mistral": {
      "api_key": "${MISTRAL_API_KEY}",
      "model": "mistral-medium"
    },
    "openrouter": {
      "api_key": "${OPENROUTER_API_KEY}",
      "model": "google/gemini-2.5-flash"
    }
  }
}
```

**`~/.moltyclaw/.env`** (referência completa):

```env
# ─── PROVIDER PRINCIPAL ──────────────────────────────────────────────────────
MOLTY_PROVIDER=mistral             # mistral | gemini | openrouter

MISTRAL_API_KEY=sua_chave_aqui
MISTRAL_MODEL=mistral-medium

GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-2.0-flash

OPENROUTER_API_KEY=sua_chave_aqui
OPENROUTER_MODEL=google/gemini-2.5-flash

# ─── INTEGRAÇÕES SOCIAIS ─────────────────────────────────────────────────────
DISCORD_BOT_TOKEN=seu_token_discord
DISCORD_ALLOWED_USERS=123456789,987654321

TELEGRAM_BOT_TOKEN=seu_token_telegram
TELEGRAM_ALLOWED_USERS=@seunome,123456789

WHATSAPP_ALLOWED_NUMBERS=5511999999999,5511888888888

TWITTER_API_KEY=chave
TWITTER_API_SECRET=segredo
TWITTER_ACCESS_TOKEN=token
TWITTER_ACCESS_TOKEN_SECRET=token_segredo
TWITTER_BEARER_TOKEN=bearer

BLUESKY_HANDLE=seunome.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
BLUESKY_ALLOWED_HANDLES=               # vazio = aceita todos

# ─── E-MAIL ──────────────────────────────────────────────────────────────────
GMAIL_USER=seuemail@gmail.com
GMAIL_APP_PASSWORD=sua_app_password_gmail

# ─── SPOTIFY ─────────────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID=seu_client_id
SPOTIFY_CLIENT_SECRET=seu_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# ─── MODO DE OPERAÇÃO ────────────────────────────────────────────────────────
MOLTY_MODE=private     # private (padrão) | public (desabilita CMD)
MOLTY_WEBUI_SHARE=0    # 1 = abre na rede (0.0.0.0:5000)
```

---

## <a id="workspace"></a>📁 Arquitetura de Arquivos

### Repositório (código-fonte)

```
MoltyClaw/
├── src/
│   ├── moltyclaw.py           # Classe principal — loop cognitivo e tool-use
│   ├── system_prompt.py       # Construção modular do System Prompt
│   ├── skills.py              # Sistema de Skills (Progressive Disclosure)
│   ├── config_loader.py       # Carrega moltyclaw.json e .env
│   ├── routing.py             # Roteamento canal → agente via bindings.json
│   ├── scheduler.py           # Motor de agendamento de jobs
│   ├── subagent_registry.py   # Rastreamento de runs de sub-agentes
│   ├── heartbeat.py           # Tarefas proativas periódicas
│   ├── initializer.py         # Setup de diretórios na inicialização
│   ├── memory_rag.py          # Busca híbrida BM25 + semântica na memória
│   ├── integrations/
│   │   ├── discord_bot.py
│   │   ├── telegram_bot.py
│   │   ├── whatsapp_server.py
│   │   ├── whatsapp_bridge.js
│   │   ├── twitter_bot.py
│   │   ├── bluesky_bot.py
│   │   └── mcp_hub.py
│   └── webui/
│       ├── app.py             # Flask backend + endpoints REST + SSE
│       ├── templates/
│       │   └── index.html
│       └── static/
│           ├── style.css
│           └── script.js
├── start_moltyclaw.py         # Entrypoint CLI global
├── requirements.txt
├── pyproject.toml
└── package.json               # Dependências Node.js (WhatsApp)
```

### Diretório de Dados (`~/.moltyclaw/`)

```
~/.moltyclaw/
├── .env                       # Variáveis de ambiente e chaves
├── moltyclaw.json             # Configuração central (providers, channels, etc.)
├── jobs.json                  # Jobs do Scheduler (persistidos)
├── workspace/                 # Workspace do Master
│   ├── SOUL.md
│   ├── IDENTITY.md
│   ├── USER.md
│   ├── BOOTSTRAP.md
│   └── MEMORY.md
├── memory/                    # Diários diários (YYYY-MM-DD.md)
├── agents/                    # Sub-agentes
│   └── <agent_id>/
│       ├── config.json
│       ├── .env               # Override de provider (opcional)
│       └── workspace/
│           └── (mesma estrutura do Master)
├── bundled/
│   └── skills/                # Skills pré-instaladas do sistema
├── skills/                    # Skills managed (instaladas pelo usuário)
├── mcp_modules/               # Código-fonte dos servidores MCP instalados
├── mcp_servers.json           # Configuração dos servidores MCP ativos
├── canvas/                    # Artefatos gerados pelo CANVAS_UPDATE
├── browser_profile/           # Perfil persistente do Edge/Playwright
├── temp/                      # Arquivos temporários (screenshots, áudios)
└── logs/                      # Logs das integrações
```

---

<p align="center">
  Feito com ☕ e autonomia — <a href="https://github.com/antojunimaia-ui/MoltyClaw">github.com/antojunimaia-ui/MoltyClaw</a>
</p>
