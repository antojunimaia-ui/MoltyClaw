![MoltyClaw Banner](MoltyClaw-Banner.png)

<p align="center">
  **MoltyClaw toma atitudes, não importa aonde você esteja.**
</p>

<p align="center">
  <a href="https://pypi.org/project/moltyclaw/"><img src="https://img.shields.io/pypi/v/moltyclaw?style=flat-square&color=00d7ff" alt="PyPI"></a>
  <a href="https://github.com/antojunimaia-ui/MoltyClaw"><img src="https://img.shields.io/github/stars/antojunimaia-ui/MoltyClaw?style=flat-square&color=00d7ff" alt="Stars"></a>
  <a href="https://github.com/antojunimaia-ui/MoltyClaw/blob/main/LICENSE"><img src="https://img.shields.io/github/license/antojunimaia-ui/MoltyClaw?style=flat-square&color=00d7ff" alt="License"></a>
</p>

> **MoltyClaw** é um agente de IA autônomo e local, construído em Python, que opera o seu computador Windows e a Internet em tempo real com autonomia total. Ele não fica preso em uma janela de chat — ele age, pesquisa, clica, organiza arquivos, manda mensagens, controla música, delega tarefas a sub-agentes e responde a você por WhatsApp, Discord e Telegram simultaneamente.

---

## 📋 Índice

1. [Visão Geral e Filosofia](#visao-geral)
2. [O Loop Cognitivo — Como o Agente Pensa](#o-loop-cognitivo)
3. [Ferramentas Disponíveis — O Arsenal Completo](#ferramentas-disponiveis)
4. [Alma e Memória Persistente (A Tríade de Consciência)](#alma-e-memoria)
5. [Stealth Headless Browser & Playwright](#stealth-browser)
6. [Operant ID — Visão DOM Lógica](#operant-id)
7. [Integração MCP — Model Context Protocol](#mcp)
8. [Integrações Sociais](#integracoes-sociais)
9. [IA de Voz — Audição e Síntese](#voz)
10. [Sistema de Sub-Agentes (Swarm)](#sub-agentes)
11. [Agendador (Scheduler) — Tarefas Recorrentes](#agendador)
12. [WebUI Dashboard](#webui)
13. [CLI Global — Comandos de Linha de Comando](#cli)
14. [Instalação e Configuração](#instalacao)
15. [Arquitetura de Arquivos (Padrão Workspace)](#workspace)

---

## <a id="visao-geral"></a>🧭 Visão Geral e Filosofia

O MoltyClaw nasceu de uma pergunta simples: **por que um agente de IA precisa ficar preso em uma janela de chat?**

A maioria dos assistentes de IA disponíveis no mercado são sistemas "passivos": recebem texto, retornam texto. Não conseguem abrir o navegador, não executam comandos reais no computador, não mandam mensagens autonomamente, não se lembram de você no dia seguinte.

O MoltyClaw rompe com esse paradigma. Ele é projetado como um **agente de ação**, onde a linguagem natural é apenas a superfície — a real potência está na capacidade de:

- **Atuar sobre o sistema operacional** via CMD/PowerShell com total autonomia
- **Navegar a web de forma humana** com bypass de anti-bots e fingerprint stealth
- **Integrar-se a plataformas sociais** (WhatsApp, Discord, Telegram, Twitter/X, Bluesky) como se fosse uma pessoa real
- **Expandir seu próprio poder** conectando-se a servidores MCP externos a quente
- **Lembrar coerentemente** do usuário através de uma memória em disco de longo prazo
- **Delegar tarefas** a sub-agentes especializados que rodam em paralelo em background
- **Trabalhar em Workspaces isolados**, garantindo que cada agente tenha sua própria pasta de arquivos e memórias sem interferência.

O modelo base pode ser **Mistral AI**, **Google Gemini** ou qualquer modelo via **OpenRouter** — configurável por variável de ambiente ou via arquivo centralizado `moltyclaw.json`.

---

## <a id="o-loop-cognitivo"></a>🧠 O Loop Cognitivo — Como o Agente Pensa

O mecanismo central do MoltyClaw é implementado na classe `MoltyClaw` dentro de `src/moltyclaw.py`, especificamente no método `.ask()`.

### O Ciclo Plano → Ação → Observação

Diferente de simples chatbots que apenas retornam texto, o MoltyClaw implementa um loop recursivo de tool-use:

```
Usuário envia mensagem
        │
        ▼
  LLM recebe o prompt + ferramentas disponíveis + histórico + SOUL + MEMORY
        │
        ▼
  ┌─────────────────────────────────┐
  │  LLM decide se precisa de info  │
  │  externa ou pode responder direto│
  └────────────┬────────────────────┘
               │
    ┌──────────▼──────────┐
    │  Resposta Direta    │     ←── Se já tem tudo que precisa
    │  (texto ao usuário) │
    └─────────────────────┘
               │
    ┌──────────▼──────────┐
    │  Tool Call em JSON  │     ←── Se precisa agir antes de responder
    │  {"action": "CMD",  │
    │   "param": "dir"}   │
    └──────────┬──────────┘
               │
        Python parseia a tool call
               │
        Executa a ação no SO / Browser / API / Sub-Agente
               │
        Captura o output raw (stdout, HTML, JSON...)
               │
        Injeta o resultado de volta no histórico como "System Observation"
               │
        Loop reinicia → LLM processa o novo contexto
               │
        Repete até ter a resposta final
```

### Por que JSON como protocolo de Tool Calls?

O MoltyClaw não usa o sistema nativo de "function calling" da OpenAI/Mistral para as suas ferramentas locais. Em vez disso, o sistema de prompt **treina o LLM a emitir blocos JSON crus** no corpo da resposta em formato `<tool>{"action": "...", ...}</tool>`. Isso garante:

1. **Compatibilidade universal**: Funciona com qualquer modelo que saiba seguir instruções (não depende de APIs específicas de cada provider para tool-use).
2. **Debugging transparente**: Todo o fluxo de decisões é visível no terminal em tempo real.
3. **Controle granular**: O parser Python decide o que fazer com cada bloco, com fallback para erros de parsing.

---

## <a id="ferramentas-disponiveis"></a>🔧 Ferramentas Disponíveis — O Arsenal Completo

Cada ferramenta abaixo é uma ação que a IA pode invocar autonomamente. O LLM aprende quais existem através do System Prompt.

### 🌐 Navegação Web

| Tool | Descrição Técnica |
|---|---|
| `OPEN_BROWSER` | Inicializa a sessão Playwright MsEdge em modo headless com injeção stealth |
| `GOTO` | Navega para uma URL. Aguarda `domcontentloaded` antes de retornar |
| `READ_PAGE` | Extrai todo o texto visível da página atual via JavaScript DOM traversal |
| `INSPECT_PAGE` | Roda o script de Operant ID (veja seção dedicada) e retorna o mapa lógico de elementos clicáveis |
| `CLICK` | Clica num elemento pelo seu Operant ID. Usa `.locator()` do Playwright para clique real de mouse |
| `TYPE` | Digita texto em campo de input identificado por Operant ID, simulando teclas reais |
| `PRESS_ENTER` | Pressiona Enter no contexto atual (útil para formulários de busca) |
| `PRESS_KEY` | Pressiona qualquer tecla especial: `Tab`, `Escape`, `ArrowDown`, etc. |
| `SCREENSHOT` | Captura tela e salva em `/temp/`, retorna o path para o LLM anexar na resposta |
| `SCROLL_DOWN` | Rola a página pra baixo, útil em feeds ou listas longas com lazy loading |
| `DDG_SEARCH` | Bypass direto: consulta a DuckDuckGo Search API sem precisar do browser, retorna lista de resultados |

### ⚙️ Sistema Operacional (CMD)

| Tool | Descrição Técnica |
|---|---|
| `CMD` | Executa qualquer comando Windows no shell. Captura `stdout` + `stderr`. Bloqueado em modo público. |

O MoltyClaw pode executar sequências de comandos encadeados com `&&`, criar pastas, mover arquivos, verificar variáveis de sistema, rodar outros scripts Python, etc. **O agente usa sua inteligência para decidir quando usar CMD vs Browser.**

### 📧 E-mail (Gmail via IMAP/SMTP)

| Tool | Descrição |
|---|---|
| `READ_EMAILS` | Conecta via IMAP, lê os últimos N emails da caixa de entrada |
| `SEND_EMAIL` | Compõe e envia email via SMTP: `destinatario | assunto | corpo` |
| `DELETE_EMAIL` | Marca email para deleção por UID no servidor IMAP |

Configuração via `.env`: `GMAIL_USER` e `GMAIL_APP_PASSWORD`.

### 🎵 Spotify

| Tool | Descrição |
|---|---|
| `SPOTIFY_PLAY` | Toca música por URI ou nome usando `spotipy` |
| `SPOTIFY_PAUSE` | Pausa a reprodução atual |
| `SPOTIFY_SEARCH` | Pesquisa músicas, artistas ou álbuns e retorna URIs |
| `SPOTIFY_ADD_QUEUE` | Enfileira faixas para reprodução futura |

### 📺 YouTube

| Tool | Descrição |
|---|---|
| `YOUTUBE_SUMMARIZE` | Pega a URL do YouTube, baixa a transcrição via `youtube-transcript-api` e injeta no contexto do LLM para ele sumarizar |

### 🔊 Síntese de Voz

| Tool | Descrição |
|---|---|
| `VOICE_REPLY` | Sintetiza texto em áudio MP3 via Microsoft Edge TTS neural (`edge-tts`) e salva em temp. Pode enviar ativamente a um destino com `texto | ID_DO_DESTINO`. |

### 📱 Integrações Sociais (Disparo Ativo)

| Tool | Canal |
|---|---|
| `WHATSAPP_SEND` | Envia mensagem para número específico via bridge Node.js |
| `DISCORD_SEND` | Envia DM para User ID via API Discord |
| `TELEGRAM_SEND` | Envia mensagem para `@username` ou chat ID via Telegram Bot API |
| `X_POST` | Publica um tweet/post via Twitter API v2 com `tweepy` |
| `BLUESKY_POST` | Publica um skeet via AT Protocol |
| `BLUESKY_GET_PROFILE` | Busca informações de perfil de um handle Bluesky |

### 🧠 Memória

| Tool | Descrição |
|---|---|
| `MEMORY_SAVE_LONG_TERM` | Acrescenta um fato permanente ao `MEMORY.md` — o LLM invoca isso quando aprende algo relevante sobre o usuário |
| `MEMORY_SAVE_DAILY` | Acrescenta uma nota com timestamp ao diário do dia (`memory/YYYY-MM-DD.md`) |
| `MEMORY_SEARCH` | Busca por texto nas memórias (arquivo longo prazo + diários) |
| `MEMORY_GET` | Lê conteúdo completo de um arquivo de memória específico |
| `SOUL_UPDATE` | Reescreve o `SOUL.md` do agente com novo conteúdo |

### 🔌 MCP (Model Context Protocol)

| Tool | Descrição |
|---|---|
| `MCP_TOOL` | Executa qualquer ferramenta exposta por um servidor MCP conectado via Stdio. O payload inclui o nome do servidor, nome da ferramenta e seus argumentos |

### 🤖 Sub-Agentes

| Tool | Descrição |
|---|---|
| `CALL_AGENT` | Delega uma tarefa a um sub-agente especializado que roda em background. Formato: `id_do_agente \| tarefa detalhada`. O Master responde imediatamente; o resultado chega ao canal quando pronto. |

---

### <a id="alma-e-memoria"></a>🪄 Alma e Memória Persistente (A Tríade de Consciência)

O MoltyClaw agora utiliza uma arquitetura baseada em **Workspaces**. Cada agente (Master ou Sub-Agente) opera dentro de uma subpasta `/workspace` onde residem seus arquivos de identidade e memória.

#### 📁 A Estrutura de Arquivos por Agente

```
~/.moltyclaw/ (ou ~/.moltyclaw/agents/<id>/)
└── workspace/
    ├── SOUL.md        # Personalidade e comportamento
    ├── IDENTITY.md    # Fatos fixos sobre quem o agente é
    ├── USER.md        # O que o agente sabe sobre você (preferências, etc)
    ├── BOOTSTRAP.md   # Instruções de inicialização rápida
    └── MEMORY.md      # Memória de longo prazo (hipocampo)
```

### `SOUL.md` — A Identidade Inquebrável

Define o tom de voz, nível de formalidade e restrições absolutas. É injetado diretamente no System Prompt.

### `IDENTITY.md` & `USER.md` — O Contexto Estático

Enquanto o SOUL define *como* o agente fala, o `IDENTITY.md` define *quem* ele é tecnicamente (ex: "Especialista em Python") e o `USER.md` armazena tudo o que ele aprendeu sobre você para personalizar a experiência.

### `MEMORY.md` — O Hipocampo Digital

Funciona como a memória de longo prazo. A cada interação relevante, o LLM pode decidir autonomamente invocar a tool `MEMORY_SAVE_LONG_TERM` para registrar fatos novos.

### `BOOTSTRAP.md` — O Manual de Instruções

Se este arquivo estiver presente, o agente o lê na primeira interação para configurar sua identidade inicial ou realizar uma tarefa de "setup" imediata.

---

## <a id="stealth-browser"></a>🥷 Stealth Headless Browser & Playwright

### O Problema: Detecção de Bots

Serviços modernos como Cloudflare, Google, Ticketmaster e redes sociais detectam scripts automatizados através de:

- Propriedades JavaScript como `navigator.webdriver = true`
- Ausência de plugins de browser reais
- User-Agent inconsistente com o fingerprint
- Padrões de timing não-humanos

### A Solução: Playwright MsEdge + Navegador Compartilhado via CDP

O MoltyClaw inicializa o browser via Playwright usando o motor **Microsoft Edge real** (não Chromium genérico), com o pacote `playwright-stealth` injetado. Além disso, usa um **modo CDP (Chrome DevTools Protocol)** para compartilhar uma única instância de navegador entre todos os agentes/integrações:

```python
# Um único navegador Master na porta 9222
# Todos os agentes se conectam a ele via CDP
browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
```

Um mecanismo de **lock via socket** (porta 9223) garante que apenas um agente inicialize o browser ao mesmo tempo, evitando race conditions.

O resultado é uma sessão de browser que, para todos os efeitos dos sistemas anti-bot, parece ser uma pessoa real usando o Edge no Windows.

---

## <a id="operant-id"></a>🎯 Operant ID — Visão DOM Lógica

### O Problema: LLMs não entendem HTML cru

Uma página moderna tem facilmente 50.000+ linhas de HTML com CSS inline, classes Tailwind, SVGs, scripts, atributos de acessibilidade e estruturas profundamente aninhadas. Jogar isso diretamente em um LLM é caro, lento, e leva a alucinações (o modelo "vê" elementos que não existem ou falha ao tentar clicar).

### A Solução: Mapeamento Lógico por Operant ID

Quando a IA chama `INSPECT_PAGE`, um script JavaScript é executado diretamente na página via `page.evaluate()`. Ele:

1. **Remove ruído**: `<script>`, `<style>`, `<svg>`, atributos CSS, classes internas
2. **Identifica elementos interativos**: botões, links, inputs, selects
3. **Atribui um ID sequencial único a cada um**: `[data-operant-id="1"]`, `[data-operant-id="2"]`, etc.
4. **Desenha marcadores azuis visuais** na tela para cada elemento
5. **Retorna uma descrição comprimida**: apenas texto visível + seletores

**Output típico do INSPECT_PAGE:**

```
[data-operant-id="1"] -> <input role="text"> Username or email address
[data-operant-id="2"] -> <input role="password"> Password
[data-operant-id="3"] -> <button role="button"> Sign in
[data-operant-id="4"] -> <a role="link"> Forgot password?
```

A IA processa esses ~50 tokens e decide: `CLICK {"action": "CLICK", "param": "[data-operant-id=\"3\"]"}`.

O Python mapeia o seletor de volta para o elemento DOM e o Playwright executa um clique real de mouse nas coordenadas corretas. **Zero alucinação de HTML**.

---

## <a id="mcp"></a>🔌 Integração MCP — Model Context Protocol

### O que é MCP?

MCP (Model Context Protocol) é um padrão aberto que define como agentes de IA se comunicam com servidores de ferramentas externos via **Stdin/Stdout**. Um servidor MCP pode expor N ferramentas (ex: consultar banco de dados, manipular arquivos, chamar APIs proprietárias) que ficam disponíveis para o agente sem modificação do código base.

### Como o MoltyClaw integra MCP

Na inicialização, o MoltyClaw lê o arquivo `mcp_servers.json` e, para cada servidor declarado, inicia o processo filho via `subprocess` + Stdin/Stdout pipe:

```json
{
  "mcpServers": {
    "meu_servidor_db": {
      "command": "python",
      "args": ["mcp_modules/meu_db_server/server.py", "--db", "dados.sqlite"]
    },
    "filesystem_manager": {
      "command": "node",
      "args": ["mcp_modules/mcp-filesystem/build/index.js"]
    }
  }
}
```

O `MCPHub` interno:

1. Inicia cada processo filho com suas configurações
2. Realiza o handshake MCP (`initialize` → `tools/list`)
3. **Injeta dinamicamente as ferramentas descobertas no System Prompt do LLM**
4. Mantém as conexões Stdio ativas durante toda a sessão

A IA então usa essas ferramentas exatamente como as nativas, via `MCP_TOOL {"server": "meu_servidor_db", "tool": "query", "params": {"query": "SELECT * FROM users"}}`.

Sub-agentes têm acesso apenas aos servidores MCP permitidos em seu `config.json` (`tools_mcp`).

### Gerenciamento via CLI

```bash
# Instalar um MCP direto do GitHub (clona, detecta node/python, faz build, registra)
moltyclaw mcp install https://github.com/exemplo/meu-mcp-server

# Listar todos os servidores MCP registrados
moltyclaw mcp list

# Desativar um servidor sem desinstalar
moltyclaw mcp off meu_servidor_db

# Reativar
moltyclaw mcp on meu_servidor_db

# Desinstalar completamente (remove pasta + JSON)
moltyclaw mcp uninstall meu_servidor_db
```

---

## <a id="integracoes-sociais"></a>📱 Integrações Sociais

As integrações do MoltyClaw são **módulos desacoplados** — cada um roda em sua própria thread/processo, mas todos compartilham o mesmo núcleo `MoltyClaw` e, portanto, as mesmas ferramentas, SOUL e MEMORY.

### Roteamento Dinâmico (`routing.py`)

O sistema de roteamento decide **qual agente responde a qual pessoa/grupo** em cada canal, usando um arquivo `~/.moltyclaw/bindings.json`:

```
Mensagem chega (Telegram, Discord, etc.)
      │
      ▼
routing.resolve_agent(channel, peer_id, guild_id)
      │
      ├─ Match por peer_id específico  → Agente A
      ├─ Match por guild/servidor       → Agente B
      ├─ Match por canal genérico       → Agente C
      └─ Fallback                       → MoltyClaw (Master)
```

Isso permite, por exemplo, que um grupo específico do Telegram seja atendido por um sub-agente especializado, enquanto DMs continuam indo ao Master.

### 📱 WhatsApp (QR Code Criptografado)

**Arquitetura bidirecional híbrida Node.js ↔ Python:**

```
Celular do usuário
      │ (mensagem)
      ▼
WhatsApp Web (protocolo criptografado)
      │
      ▼
whatsapp_bridge.js  ←── Node.js + whatsapp-web.js
      │  (HTTP POST para /message na porta local)
      ▼
whatsapp_server.py  ←── Python + aiohttp
      │
      ▼
moltyclaw.py (MoltyClaw.ask())
      │ (usa Browser, CMD, Spotify, etc. conforme necessário)
      ▼
whatsapp_server.py (resposta pronta)
      │
      ▼
whatsapp_bridge.js (envia resposta ao número)
```

**Recursos:**

- **Whitelist de segurança**: `WHATSAPP_ALLOWED_NUMBERS` no `.env`. Apenas números autorizados recebem resposta.
- **Disparo ativo**: A IA pode enviar mensagens proativamente a qualquer número usando `WHATSAPP_SEND`.
- **Suporte a áudios**: Voice notes OGG/MP3 são transcritos pelo Voxtral (Mistral API) e convertidos em texto antes de chegar ao LLM.

### 🎧 Discord (Bot API Oficial)

**Implementado em `src/integrations/discord_bot.py` usando `discord.py`.**

- O bot escuta por menções diretas (`@MoltyClaw`) em qualquer canal visível, e também por DMs.
- Exibe **"typing..."** em DMs enquanto o agente processa, criando experiência humana.
- Suporte a **respostas longas** com chunking automático de 2000 caracteres (limite do Discord).
- **Whitelist**: `DISCORD_ALLOWED_USERS` — lista de User IDs que podem interagir com o bot.
- **Disparo ativo**: Via `DISCORD_SEND`, o agente envia DMs autônomas para qualquer User ID.

### ✈️ Telegram (python-telegram-bot)

**Implementado em `src/integrations/telegram_bot.py`.**

- Funciona em DMs e grupos. Em grupos, **só responde se mencionado** (`@nome_do_bot`) ou respondido diretamente.
- Divide mensagens longas automaticamente respeitando o limite de 4096 caracteres.
- **Whitelist**: `TELEGRAM_ALLOWED_USERS` — por `@username` ou user ID numérico.
- **Disparo ativo**: `TELEGRAM_SEND` para enviar mensagens a qualquer usuário ou grupo.
- **Announce de sub-agentes**: quando um sub-agente delgado termina em background, o resultado chega automaticamente no chat que originou a conversa.

### 🐦 X / Twitter (API v2)

**Implementado em `src/integrations/twitter_bot.py` usando `tweepy`.**

- Monitora menções e responde com tweets de máximo 280 caracteres.
- Pesquisa a internet antes de responder caso necessário.
- **Disparo ativo**: `X_POST` para publicar tweets autônomos sem abrir o navegador.

### 🦋 Bluesky (AT Protocol)

**Implementado em `src/integrations/bluesky_bot.py` usando `atproto`.**

O Bluesky opera sobre o **AT Protocol**, um padrão aberto e descentralizado. A autenticação é feita com um **App Password** isolado (criado em `bsky.app → Settings → App Passwords`), nunca com a senha principal da conta.

- **Respostas em thread**: o bot respeita a estrutura de thread do AT Protocol mantendo `root_ref` e `parent_ref` corretos.
- **Limite de 300 caracteres** com truncagem automática.
- **Whitelist**: `BLUESKY_ALLOWED_HANDLES`. Vazio = aceita todos.
- **Tool ativa**: `BLUESKY_POST` para o agente publicar skeets autônomos.

| Variável | Descrição |
|---|---|
| `BLUESKY_HANDLE` | Handle da conta (ex: `seunome.bsky.social`) |
| `BLUESKY_APP_PASSWORD` | App Password gerado em `bsky.app → Settings → App Passwords` |
| `BLUESKY_ALLOWED_HANDLES` | Handles autorizados a interagir, separados por vírgula. Vazio = todos |

---

## <a id="voz"></a>🎙️ IA de Voz — Audição e Síntese

### Audição — Transcrição via Voxtral (Mistral)

Arquivos de áudio enviados via WebUI, WhatsApp, Discord ou Telegram são automaticamente transcritos antes de chegar ao LLM:

- **Formatos suportados**: MP3, OGG (PTTs do WhatsApp/Telegram), WAV, M4A
- **Motor**: `voxtral-mini-latest` — Mistral's speech API
- O áudio transcrito é injetado no contexto como texto normal com a nota `(Áudio Transcrito do Usuário)`

### Síntese — Microsoft Edge TTS Neural

Quando a IA invoca `VOICE_REPLY`:

- O texto é processado pela biblioteca `edge-tts` que usa as vozes neurais do Microsoft Edge
- Vozes naturais disponíveis: `pt-BR-FranciscaNeural`, `pt-BR-AntonioNeural`, etc.
- O arquivo de áudio MP3 é salvo em `~/.moltyclaw/temp/` e o path é retornado
- No WhatsApp, é enviado como nota de voz nativa (balão de áudio)
- No Discord e Telegram, é enviado como arquivo de áudio

---

## <a id="sub-agentes"></a>🤖 Sistema de Sub-Agentes (Swarm)

O MoltyClaw suporta um sistema de **sub-agentes especializados** que operam em paralelo como um Swarm controlado.

### Arquitetura

Todos os agentes são instâncias da mesma classe `MoltyClaw`, diferenciados pela flag `is_master`:

| Aspecto | MoltyClaw (Master) | Sub-Agentes |
|---|---|---|
| Workspace | `~/.moltyclaw/` | `~/.moltyclaw/agents/<id>/` |
| Ferramentas | Todas | Apenas as de `config.json["tools_local"]` |
| Servidores MCP | Todos | Apenas os de `config.json["tools_mcp"]` |
| Memória | `~/.moltyclaw/MEMORY.md` | `~/.moltyclaw/agents/<id>/MEMORY.md` |
| SOUL | `~/.moltyclaw/SOUL.md` | `~/.moltyclaw/agents/<id>/SOUL.md` |
| Modelo/Provider | Global via `.env` | Pode ter `.env` próprio com override |

### Criando um Sub-Agente

Crie a pasta e o `config.json`:

```
~/.moltyclaw/
└── agents/
    └── Pesquisador/
        ├── config.json
        ├── SOUL.md       ← personalidade própria (opcional)
        └── MEMORY.md     ← memória própria (optional)
```

**Exemplo de `config.json`:**

```json
{
  "name": "Pesquisador",
  "description": "Especialista em busca na web e síntese de informações",
  "provider": "gemini",
  "tools_local": ["DDG_SEARCH", "GOTO", "READ_PAGE", "INSPECT_PAGE"],
  "tools_mcp": []
}
```

### Execução Assíncrona (Background)

Quando o Master invoca `CALL_AGENT`, o sub-agente roda em um **`asyncio.create_task()`** — não bloqueia o Master:

```
Usuário → "pesquise tendências de IA pra mim"
Master  → CALL_AGENT: "Pesquisador | Pesquise tendências de IA em 2025"
Master  → "✅ Pesquisador iniciado em background (run=a1b2c3d4). Resultado chegará em breve."
Master  → já responde o usuário e fica livre para outras tarefas

[...Pesquisador trabalha em paralelo...]

Pesquisador → termina → announce callback disparado
Usuário ← "✅ [Pesquisador] concluiu em 18s: {resultado da pesquisa}"
```

O **`subagent_registry.py`** rastreia todos os runs ativos com `run_id`, status, timestamps e resultado.

### Roteamento de Canal para Sub-Agentes

Via `bindings.json`, diferentes usuários/grupos podem ser atendidos por sub-agentes diferentes automaticamente, sem intervenção manual. Veja a seção [Roteamento Dinâmico](#roteamento-dinâmico-routingpy).

---

## <a id="agendador"></a>⏲️ Agendador (Scheduler) — Tarefas Recorrentes

O MoltyClaw possui um motor de agendamento que permite à IA executar tarefas de forma proativa sem intervenção humana.

- **Jobs persistentes**: Salvos em `jobs.json`, eles sobrevivem a reinicializações.
- **Payload Dinâmico**: O agendador envia um prompt para o agente (ex: "Verifique o clima agora e me avise se vai chover") a cada intervalo de minutos.
- **Inteligência de Ocupação**: Se o agente estiver ocupado processando uma mensagem do usuário, o agendador aguarda a próxima janela de tempo livre para não interromper o fluxo atual.

---

## <a id="webui"></a>🖥️ WebUI Dashboard

O MoltyClaw possui um painel web completo construído com **Flask** (backend) + HTML/CSS/JS vanilla (frontend).

### Novidades da V26+

- **🌗 Dark Mode**: Interface otimizada para ambientes escuros por padrão.
- **🧠 Assimilação de Contexto**: Ferramenta que usa IA para fundir memórias de outros chats ou documentos diretamente no seu `MEMORY.md` sem criar duplicatas.
- **📅 Gestão de Jobs**: Interface visual para adicionar, remover e monitorar tarefas agendadas.

### Como Iniciar

```bash
# Modo local (apenas seu PC)
moltyclaw web

# Modo compartilhado (rede local / Tailscale / celular)
moltyclaw web --share
```

No modo `--share`, o Flask levanta em `0.0.0.0:5000` ao invés de `127.0.0.1:5000`. O terminal exibe o IP local real detectado automaticamente.

### Abas da Interface

| Aba | Função |
|---|---|
| **💬 Chat** | Interface principal de conversa com streaming de tokens em tempo real via Server-Sent Events (SSE). Suporta markdown, imagens e áudio |
| **🔗 Integrations** | Toggles para ligar/desligar bots sociais (WhatsApp, Discord, etc) em background |
| **🧠 Agent** | Editor live de `SOUL`, `MEMORY`, `USER` e `IDENTITY`. |
| **⏲️ Scheduler** | Painel de controle do motor de agendamento. |
| **🔌 MCP** | Catálogo e instalador de servidores Model Context Protocol. |

### Streaming de Respostas

A comunicação entre o frontend e o backend usa **Server-Sent Events (SSE)**:

```
Frontend envia POST /api/chat (FormData com texto + arquivo opcional)
         │
         ▼
Backend inicia asyncio task em thread dedicada
         │
         ▼
Tokens chegam pelo stream_callback → Queue thread-safe
         │
         ▼
Generator Flask lê da Queue e emite: data: {"type": "token", "content": "..."}
         │
         ▼
Frontend acumula tokens e renderiza Markdown incrementalmente
```

---

## <a id="cli"></a>💻 CLI Global — Comandos de Linha de Comando

Após instalar via `pip install moltyclaw` ou selecionar **"Configurar 'moltyclaw' Global"** no Launcher, o comando `moltyclaw` fica disponível globalmente no terminal.

### Referência Completa de Comandos

```bash
# Iniciar o menu interativo
moltyclaw

# Setup Inicial (Wizard guiado com aviso de segurança)
moltyclaw onboard          # Configura provedor, modelo, API key e identidade

# WebUI
moltyclaw web              # WebUI local em 127.0.0.1:5000
moltyclaw web --share      # WebUI aberta na rede local/Tailscale em 0.0.0.0:5000

# Bots (start/stop)
moltyclaw start discord    # Inicia apenas o bot Discord em background
moltyclaw start telegram   # Inicia apenas o bot Telegram
moltyclaw start whatsapp   # Inicia WhatsApp (abre QR Code para escanear)
moltyclaw start twitter    # Inicia o bot do Twitter/X
moltyclaw start all        # Inicia todos os bots simultaneamente

# Organização de Arquivos com IA
moltyclaw organize "C:\Users\Cliente\Downloads"
# → Escaneia a pasta, chama a IA, e usa CMD (mkdir + move) para
#   organizar os arquivos por tipo (Documentos, Imagens, Vídeos, etc.)

# Pesquisa Web com IA
moltyclaw research "O que mudou do React 18 pro 19?"
# → Abre browser headless, pesquisa no DuckDuckGo, lê os artigos,
#   e exibe um resumo técnico direto no terminal

# Gerenciamento de MCP
moltyclaw mcp list                                   # Lista servidores registrados
moltyclaw mcp install https://github.com/user/repo  # Instala MCP do GitHub
moltyclaw mcp uninstall nome_do_servidor             # Remove servidor e arquivos
moltyclaw mcp on  nome_do_servidor                   # Reativa servidor desativado
moltyclaw mcp off nome_do_servidor                   # Desativa sem remover

# Configurações
moltyclaw config set MISTRAL_API_KEY sk-xxxx        # Grava variável no .env
moltyclaw config get MISTRAL_API_KEY                 # Lê variável do .env
moltyclaw --config                                   # Abre .env no Bloco de Notas

# Manutenção
moltyclaw update       # Verifica releases no GitHub, exibe changelog e atualiza
moltyclaw reset memory # Limpa o MEMORY.md completamente
moltyclaw doctor       # Diagnóstico: checa Python, Node, .env, dependências
moltyclaw --help       # Lista todos os comandos disponíveis
```

---

## <a id="instalacao"></a>🛠️ Instalação e Configuração

### Requisitos

| Componente | Versão Mínima |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ (apenas para WhatsApp) |
| Microsoft Edge | Qualquer versão recente (para Playwright) |

### Instalação via PyPI (Recomendado)

```bash
pip install moltyclaw
playwright install msedge
moltyclaw onboard
```

O comando `moltyclaw onboard` inicia um **Wizard de Configuração Guiado** que:

1. Exibe um aviso de segurança (o agente tem controle total sobre o sistema)
2. Pergunta qual provedor de IA usar (Gemini, Mistral ou OpenRouter)
3. Solicita a API Key e faz **fetch em tempo real** dos modelos disponíveis
4. Configura automaticamente o `.env` e cria os arquivos de identidade (`SOUL.md`, `MEMORY.md`)

### Instalação Manual (Desenvolvimento)

**1. Clone o repositório:**

```bash
git clone https://github.com/antojunimaia-ui/MoltyClaw.git
cd MoltyClaw
```

**2. Instale em modo desenvolvimento:**

```bash
pip install -e .
playwright install msedge
```

**3. Execute o Onboarding:**

```bash
moltyclaw onboard
```

**4. Instale as dependências Node.js (apenas para WhatsApp):**

```bash
npm install
```

**5. Inicie o MoltyClaw:**

```bash
moltyclaw
```

### Configuração Manual (Avançado)

Você pode usar variáveis de ambiente no `.env` ou o arquivo centralizado `~/.moltyclaw/moltyclaw.json`:

**Opção A: `moltyclaw.json` (JSON5 com comentários e variáveis de ambiente)**

```json
{
  "providers": {
    "gemini": {
      "api_key": "${GEMINI_API_KEY}",
      "model": "gemini-2.0-flash"
    }
  }
}
```

**Opção B: Tradicional `.env`:**

```env
# ─── IA PRINCIPAL (escolha um provider) ─────────────────────────────────────
MOLTY_PROVIDER=mistral             # mistral | gemini | openrouter

# Mistral
MISTRAL_API_KEY=sua_chave_mistral_aqui
MISTRAL_MODEL=mistral-medium       # ou mistral-large-latest, devstral-small...

# Gemini
GEMINI_API_KEY=sua_chave_gemini_aqui
GEMINI_MODEL=gemini-2.0-flash

# OpenRouter (acessa qualquer modelo via API unificada)
OPENROUTER_API_KEY=sua_chave_openrouter_aqui
OPENROUTER_MODEL=google/gemini-2.5-flash

# ─── INTEGRAÇÕES SOCIAIS ─────────────────────────────────────────────────────
DISCORD_BOT_TOKEN=seu_token_discord
DISCORD_ALLOWED_USERS=123456789,987654321

TELEGRAM_BOT_TOKEN=seu_token_telegram
TELEGRAM_ALLOWED_USERS=@seunome,123456789

WHATSAPP_ALLOWED_NUMBERS=5511999999999,5511888888888

X_API_KEY=sua_api_key_twitter
X_API_SECRET=seu_api_secret_twitter
X_ACCESS_TOKEN=seu_access_token
X_ACCESS_SECRET=seu_access_secret

BLUESKY_HANDLE=seunome.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
BLUESKY_ALLOWED_HANDLES=

# ─── E-MAIL ──────────────────────────────────────────────────────────────────
GMAIL_USER=seuemail@gmail.com
GMAIL_APP_PASSWORD=sua_app_password_gmail

# ─── SPOTIFY ─────────────────────────────────────────────────────────────────
SPOTIFY_CLIENT_ID=seu_client_id
SPOTIFY_CLIENT_SECRET=seu_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

---

## <a id="workspace"></a>📁 Arquitetura de Arquivos (Padrão Workspace)

### Repositório (código-fonte)

```
MoltyClaw/
├── src/
│   ├── moltyclaw.py           # Classe principal — loop cognitivo e tool-use
│   ├── system_prompt.py       # Construção dinâmica do System Prompt
│   ├── config_loader.py       # Carrega moltyclaw.json e .env
│   ├── routing.py             # Roteamento canal → agente
│   ├── scheduler.py           # Motor de agendamento de jobs
│   ├── subagent_registry.py   # Rastreamento de runs de sub-agentes
│   ├── heartbeat.py           # Tarefas proativas periódicas
│   ├── integrations/
│   │   ├── mcp_hub.py         # Gerenciador de servidores MCP (Stdio)
│   │   ├── discord_bot.py     # Bot Discord com discord.py
│   │   ├── telegram_bot.py    # Bot Telegram com python-telegram-bot
│   │   ├── whatsapp_server.py # Servidor Python que recebe mensagens do bridge
│   │   ├── whatsapp_bridge.js # Bridge Node.js + whatsapp-web.js
│   │   ├── twitter_bot.py     # Bot Twitter/X com tweepy (API v2)
│   │   └── bluesky_bot.py     # Bot Bluesky com atproto
│   └── webui/
│       ├── app.py             # Servidor Flask + endpoints SSE
│       ├── templates/
│       │   └── index.html     # Interface principal
│       └── static/
│           ├── script.js      # Lógica frontend (chat, SSE, abas)
│           └── style.css      # Estilos dark mode
│
├── mcp_servers.json           # Configuração dos servidores MCP ativos
├── mcp_servers.example.json   # Template de referência para MCPs
├── start_moltyclaw.py         # Ponto de entrada / launcher interativo
├── pyproject.toml             # Manifesto PyPI (pip install moltyclaw)
├── VERSION                    # Versão atual (usada pelo updater e PyPI)
├── requirements.txt           # Dependências Python
└── .env                       # Variáveis de ambiente (NÃO versionar!)
```

### Dados em runtime (fora do repositório)

```
~/.moltyclaw/
├── SOUL.md                    # Identidade e personalidade do Master
├── MEMORY.md                  # Memória de longo prazo do Master
├── bindings.json              # Regras de roteamento canal → agente
├── moltyclaw.json             # Configuração centralizada (opcional)
├── browser_profile/           # Perfil persistente do Edge (cookies, logins)
├── temp/                      # Screenshots e áudios temporários
├── memory/                    # Diários diários (YYYY-MM-DD.md)
└── agents/
    └── <NomeAgente>/
        ├── config.json        # provider, tools_local, tools_mcp, description
        ├── SOUL.md            # Alma própria do sub-agente
        ├── MEMORY.md          # Memória própria do sub-agente
        └── .env               # Chaves de API próprias (opcional, override do global)
```

---

> ⚠️ **Aviso de Segurança:** O MoltyClaw opera com as mesmas permissões do usuário Windows que iniciou o processo. O agente tem acesso ao CMD, ao sistema de arquivos e à internet. Configure as whitelists corretamente e não compartilhe o modo `--share` em redes públicas sem autenticação adicional. Revise o `SOUL.md` para impor restrições de comportamento conforme necessário.
