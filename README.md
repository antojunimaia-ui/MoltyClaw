# 🤖 MoltyClaw — O Agente Autônomo Definitivo

```text
███╗   ███╗ ██████╗ ██╗  ████████╗██╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗
████╗ ████║██╔═══██╗██║  ╚══██╔══╝╚██╗ ██╔╝██╔════╝██║     ██╔══██╗██║    ██║
██╔████╔██║██║   ██║██║     ██║    ╚████╔╝ ██║     ██║     ███████║██║ █╗ ██║
██║╚██╔╝██║██║   ██║██║     ██║     ╚██╔╝  ██║     ██║     ██╔══██║██║███╗██║
██║ ╚═╝ ██║╚██████╔╝███████╗██║      ██║   ╚██████╗███████╗██║  ██║╚███╔███╔╝
╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝      ╚═╝    ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
```

> **MoltyClaw** é um agente de IA autônomo e local, construído em Python, que opera o seu computador Windows e a Internet em tempo real com autonomia total. Ele não fica preso em uma janela de chat — ele age, pesquisa, clica, organiza arquivos, manda mensagens, controla música, e responde a você por WhatsApp, Discord e Telegram simultaneamente.

---

## 📋 Índice

1. [Visão Geral e Filosofia](#-visão-geral-e-filosofia)
2. [O Loop Cognitivo — Como o Agente Pensa](#-o-loop-cognitivo--como-o-agente-pensa)
3. [Ferramentas Disponíveis (O Arsenal Completo)](#-ferramentas-disponíveis-o-arsenal-completo)
4. [Alma e Memória Persistente](#-alma-e-memória-persistente)
5. [Stealth Headless Browser & Playwright](#-stealth-headless-browser--playwright)
6. [Operant ID — Visão DOM Lógica](#-operant-id--visão-dom-lógica)
7. [Integração MCP (Model Context Protocol)](#-integração-mcp-model-context-protocol)
8. [Integrações Sociais](#-integrações-sociais)
9. [IA de Voz — Audição e Síntese](#-ia-de-voz--audição-e-síntese)
10. [WebUI Dashboard](#-webui-dashboard)
11. [CLI Global (Comandos de Linha de Comando)](#-cli-global-comandos-de-linha-de-comando)
12. [Instalação e Configuração](#-instalação-e-configuração)
13. [Arquitetura de Arquivos](#-arquitetura-de-arquivos)

---

## 🧭 Visão Geral e Filosofia

O MoltyClaw nasceu de uma pergunta simples: **por que um agente de IA precisa ficar preso em uma janela de chat?**

A maioria dos assistentes de IA disponíveis no mercado são sistemas "passivos": recebem texto, retornam texto. Não conseguem abrir o navegador, não executam comandos reais no computador, não mandam mensagens autonomamente, não se lembram de você no dia seguinte.

O MoltyClaw rompe com esse paradigma. Ele é projetado como um **agente de ação**, onde a linguagem natural é apenas a superfície — a real potência está na capacidade de:

- **Atuar sobre o sistema operacional** via CMD/PowerShell com total autonomia
- **Navegar a web de forma humana** com bypass de anti-bots e fingerprint stealth
- **Integrar-se a plataformas sociais** (WhatsApp, Discord, Telegram, Twitter/X) como se fosse uma pessoa real
- **Expandir seu próprio poder** conectando-se a servidores MCP externos a quente
- **Lembrar coerentemente** do usuário através de uma memória em disco de longo prazo

O modelo base é o **Mistral AI** (`mistral-large-latest` / `devstral-small`), com suporte opcional a **OpenRouter** para usar outros LLMs como Gemini, GPT-4o ou Llama.

---

## 🧠 O Loop Cognitivo — Como o Agente Pensa

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
    │   "command": "dir"} │
    └──────────┬──────────┘
               │
        Python parseia a tool call
               │
        Executa a ação no SO / Browser / API
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

O MoltyClaw não usa o sistema nativo de "function calling" da OpenAI/Mistral para as suas ferramentas locais. Em vez disso, o sistema de prompt **treina o LLM a emitir blocos JSON crus** no corpo da resposta em formato `<action>{"action": "...", ...}</action>`. Isso garece:

1. **Compatibilidade universal**: Funciona com qualquer modelo que saiba seguir instruções (não depende de APIs específicas de cada provider para tool-use).
2. **Debugging transparente**: Todo o fluxo de decisões é visível no terminal em tempo real.
3. **Controle granular**: O parser Python decide o que fazer com cada bloco, com fallback para erros de parsing.

---

## 🔧 Ferramentas Disponíveis — O Arsenal Completo

Cada ferramenta abaixo é uma ação que a IA pode invocar autonomamente. O LLM aprende quais existem através do System Prompt.

### 🌐 Navegação Web

| Tool | Descrição Técnica |
|---|---|
| `OPEN_BROWSER` | Inicializa a sessão Playwright MsEdge em modo headless com injeção stealth |
| `GOTO` | Navega para uma URL. Aguarda `networkidle` antes de retornar |
| `READ_PAGE` | Extrai todo o texto visível da página atual via JavaScript DOM traversal |
| `INSPECT_PAGE` | Roda o script de Operant ID (veja seção dedicada) e retorna o mapa lógico de elementos clicáveis |
| `CLICK` | Clica num elemento pelo seu Operant ID. Usa `.locator()` do Playwright para clique real de mouse |
| `TYPE` | Digita texto em campo de input identificado por Operant ID, simulando teclas reais |
| `PRESS_ENTER` | Pressiona Enter no contexto atual (util para formulários de busca) |
| `SCREENSHOT` | Captura tela e salva em `/temp/`, retorna o path para o LLM anexar na resposta |
| `SCROLL_DOWN` | Rola a página pra baixo, útil em feeds ou listas longas com lazy loading |
| `DDG_SEARCH` | Bypass direto: consulta a DuckDuckGo Search API sem precisar do browser, retorna lista de resultados |

### ⚙️ Sistema Operacional (CMD)

| Tool | Descrição Técnica |
|---|---|
| `CMD` | Executa qualquer comando Windows no shell. Captura `stdout` + `stderr`. Timeout configurável. |

O MoltyClaw pode executar sequências de comandos encadeados com `&&`, criar pastas, mover arquivos, verificar variáveis de sistema, rodar outros scripts Python, etc. **O agente usa sua inteligência para decidir quando usar CMD vs Browser.**

### 📧 E-mail (Gmail via IMAP/SMTP)

| Tool | Descrição |
|---|---|
| `READ_EMAILS` | Conecta via IMAP, lê os últimos N emails da caixa de entrada |
| `SEND_EMAIL` | Compõe e envia email via SMTP com suporte a múltiplos destinatários |
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
| `VOICE_REPLY` | Sintetiza texto em áudio MP3 via Microsoft Edge TTS neural (`edge-tts`) e salva em temp |

### 📱 Integrações Sociais (Disparo Ativo)

| Tool | Canal |
|---|---|
| `WHATSAPP_SEND` | Envia mensagem para número específico via bridge Node.js |
| `DISCORD_SEND` | Envia DM para User ID via API Discord |
| `TELEGRAM_SEND` | Envia mensagem para `@username` ou chat ID via Telegram Bot API |
| `X_POST` | Publica um tweet/post via Twitter API v2 com `tweepy` |

### 🧠 Memória

| Tool | Descrição |
|---|---|
| `MEMORY_WRITE` | Sobrescreve ou acrescenta conteúdo no `MEMORY.md` — chamado proativamente pelo LLM quando aprende algo novo sobre o usuário |

### 🔌 MCP (Model Context Protocol)

| Tool | Descrição |
|---|---|
| `MCP_TOOL` | Executa qualquer ferramenta exposta por um servidor MCP conectado via Stdio. O payload inclui o nome do servidor, nome da ferramenta e seus argumentos |

---

## 🪄 Alma e Memória Persistente

O MoltyClaw possui dois arquivos em disco que definem sua identidade e continuidade cognitiva:

### `SOUL.md` — A Identidade Inquebrável

É injetado diretamente no **System Prompt** principal de toda sessão, independente do canal (WebUI, Discord, WhatsApp...). Define:

- Quem o agente é e como ele se comporta
- Tom de voz, nível de formalidade, sarcasmo, etc.
- Restrições absolutas que ele nunca pode violar
- Informações fixas sobre o ambiente operativo (ex: nome do usuário, localidade, configurações especiais)

Pode ser editado diretamente via WebUI na aba **Agent** sem reiniciar o sistema.

### `MEMORY.md` — O Hipocampo Digital

Funciona como a memória de longo prazo. A cada interação relevante, o LLM pode decidir autonomamente invocar a tool `MEMORY_WRITE` para registrar fatos novos descobertos durante a conversa:

```markdown
- Usuário prefere respostas curtas e diretas
- Pasta principal de projetos: D:/Dev/
- Usuário usa Neovim como editor principal
- Mencionou que trabalha às noites
```

Essa memória é carregada junto com o SOUL.md em cada nova sessão, garantindo que a IA "lembre" de você mesmo após reinicializações. Pode ser resetada com `moltyclaw reset memory`.

---

## 🥷 Stealth Headless Browser & Playwright

### O Problema: Detecção de Bots

Serviços modernos como Cloudflare, Google, Ticketmaster e redes sociais detectam scripts automatizados através de:

- Propriedades JavaScript como `navigator.webdriver = true`
- Ausência de plugins de browser reais
- User-Agent inconsistente com o fingerprint
- Padrões de timing não-humanos

### A Solução: Playwright MsEdge + Stealth

O MoltyClaw inicializa o browser via Playwright usando o motor **Microsoft Edge real** (não Chromium genérico), com o pacote `playwright-stealth` injetado:

```python
# Pseudocódigo do que acontece internamente
browser = await playwright.chromium.launch(
    channel="msedge",          # Motor Edge real instalado no sistema
    headless=True,             # Invisível para o usuário
    args=["--disable-blink-features=AutomationControlled"]
)
context = await browser.new_context(
    user_agent="Mozilla/5.0 ...",   # UA realista de laptop Windows
    viewport={"width": 1366, "height": 768},
    locale="pt-BR"
)
await stealth_async(page)  # Injeta patches V8 anti-detecção
```

O resultado é uma sessão de browser que, para todos os efeitos dos sistemas anti-bot, parece ser uma pessoa real usando o Edge no Windows.

---

## 🎯 Operant ID — Visão DOM Lógica

### O Problema: LLMs não entendem HTML cru

Uma página moderna tem facilmente 50.000+ linhas de HTML com CSS inline, classes Tailwind, SVGs, scripts, atributos de acessibilidade e estruturas profundamente aninhadas. Jogar isso diretamente em um LLM é caro, lento, e leva a alucinações (o modelo "vê" elementos que não existem ou falha ao tentar clicar).

### A Solução: Mapeamento Lógico por Operant ID

Quando a IA chama `INSPECT_PAGE`, um script JavaScript é executado diretamente na página via `page.evaluate()`. Ele:

1. **Remove ruído**: `<script>`, `<style>`, `<svg>`, atributos CSS, classes internas
2. **Identifica elementos interativos**: botões, links, inputs, selects
3. **Atribui um ID sequencial único a cada um**: `[ID: 1]`, `[ID: 2]`, etc.
4. **Retorna uma descrição comprimida**: apenas texto visível + IDs

**Output típico do INSPECT_PAGE:**

```
Página: "GitHub - Login"
[ID: 1] Campo de texto: "Username or email address"
[ID: 2] Campo de senha: "Password"
[ID: 3] Botão: "Sign in"
[ID: 4] Link: "Forgot password?"
[ID: 5] Link: "Create an account"
```

A IA processa esses ~50 tokens e decide: `CLICK {"id": 3}`.

O Python mapeia o ID de volta para o seletor DOM original e o Playwright executa um clique real de mouse nas coordenadas corretas. **Zero alucinação de HTML**.

---

## 🔌 Integração MCP — Model Context Protocol

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

A IA então usa essas ferramentas exatamente como as nativas, via `MCP_TOOL {"server": "meu_servidor_db", "tool": "query", "args": {"query": "SELECT * FROM users"}}`.

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

O comando `mcp install` é inteligente: detecta automaticamente se o repositório é Node.js (`package.json`) ou Python (`requirements.txt` / `pyproject.toml`), instala as dependências com `npm install` ou `pip install`, compila TypeScript se necessário (`npm run build`), e registra o ponto de entrada correto no `mcp_servers.json`.

### MCP Recomendados (via WebUI)

A aba **Model Context Protocol** da WebUI lista um catálogo curado de servidores MCP oficiais prontos para instalar com um clique:

| Servidor | Repositório |
|---|---|
| Magic MCP | `github.com/21st-dev/magic-mcp` |
| Boost MCP | `github.com/boost-community/boost-mcp` |
| Canva MCP | `canva.dev/docs/apps/mcp-server/` |
| Cloudflare MCP | `github.com/cloudflare/mcp-server-cloudflare` |

---

## 📱 Integrações Sociais

As integrações do MoltyClaw são **módulos desacoplados** — cada um roda em sua própria thread/processo, mas todos compartilham o mesmo núcleo `MoltyClaw` e, portanto, as mesmas ferramentas, SOUL e MEMORY.

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
      │
      ▼
Celular do usuário recebe resposta
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

- Funciona em DMs e grupos. Em grupos, **só responde se mencionado** ou respondido diretamente.
- Divide mensagens longas automaticamente respeitando o limite de 4096 caracteres.
- **Whitelist**: `TELEGRAM_ALLOWED_USERS` — por `@username` ou user ID numérico.
- **Disparo ativo**: `TELEGRAM_SEND` para enviar mensagens a qualquer usuário ou grupo.

### 🐦 X / Twitter (API v2)

**Implementado em `src/integrations/twitter_bot.py` usando `tweepy`.**

- Monitora menções e responde com tweets de máximo 280 caracteres.
- Pesquisa a internet antes de responder caso necessário.
- **Disparo ativo**: `X_POST` para publicar tweets autônomos sem abrir o navegador.

### 🦋 Bluesky (AT Protocol)

**Implementado em `src/integrations/bluesky_bot.py` usando `atproto`.**

O Bluesky opera sobre o **AT Protocol**, um padrão aberto e descentralizado. A autenticação é feita com um **App Password** isolado (criado em `bsky.app → Settings → App Passwords`), nunca com a senha principal da conta.

**Fluxo de notificações:**

```
Bot faz polling de /app.bsky.notification.listNotifications
  ↓ Filtra reason == "mention" | "reply"
  ↓ Ignora autor == próprio DID (anti-loop)
  ↓ Verifica whitelist BLUESKY_ALLOWED_HANDLES
  ↓ Chama MoltyClaw.ask(texto)
  ↓ Posta resposta via client.send_post() com ReplyRef (root + parent)
```

- **Respostas em thread**: o bot respeita a estrutura de thread do AT Protocol mantendo `root_ref` e `parent_ref` corretos — respostas aparecem agrupadas no mesmo fio de conversa.
- **Limite de 300 caracteres** com truncagem automática.
- **Whitelist**: `BLUESKY_ALLOWED_HANDLES` — handlers separados por vírgula (ex: `amigo.bsky.social`). Vazio = aceita todos.
- **Tool ativa**: `BLUESKY_POST` para o agente publicar skeets autônomos quando a integração está ligada.
- **Polling**: 15 segundos por padrão, respeitando os limites de rate da API pública do Bluesky.

**Variáveis de ambiente:**

| Variável | Descrição |
|---|---|
| `BLUESKY_HANDLE` | Handle da conta (ex: `seunome.bsky.social`) |
| `BLUESKY_APP_PASSWORD` | App Password gerado em `bsky.app → Settings → App Passwords` |
| `BLUESKY_ALLOWED_HANDLES` | Handles autorizados a interagir, separados por vírgula. Vazio = todos |

---

## 🎙️ IA de Voz — Audição e Síntese

### Audição — Transcrição via Voxtral (Mistral)

Arquivos de áudio enviados via WebUI, WhatsApp ou Discord são automaticamente transcritos antes de chegar ao LLM:

- **Formatos suportados**: MP3, OGG (PTTs do WhatsApp), WAV, M4A
- **Motor**: `mistral-audio` (`voxtral-mini-2409`) — Mistral's speech API
- O áudio transcrito é injetado no contexto como texto normal com a nota `(Áudio transcrito)`
- Resultado: você pode mandar áudio, o bot entende como se fosse texto

### Síntese — Microsoft Edge TTS Neural

Quando a IA invoca `VOICE_REPLY`:

- O texto é processado pela biblioteca `edge-tts` que usa as vozes neurais do Microsoft Edge
- Vozes naturais disponíveis: `pt-BR-FranciscaNeural`, `pt-BR-AntonioNeural`, etc.
- O arquivo de áudio MP3 é salvo em `/temp/` e o path é retornado
- No WhatsApp, é enviado como nota de voz nativa (balão de áudio)
- No Discord e Telegram, é enviado como arquivo de áudio

---

## 🖥️ WebUI Dashboard

O MoltyClaw possui um painel web completo construído com **Flask** (backend) + HTML/CSS/JS vanilla (frontend).

### Como Iniciar

```bash
# Modo local (apenas seu PC)
moltyclaw web

# Modo compartilhado (rede local / Tailscale / celular)
moltyclaw web --share
```

No modo `--share`, o Flask levanta em `0.0.0.0:5000` ao invés de `127.0.0.1:5000`. O terminal exibe o IP local real detectado automaticamente:

```
🌐 Acesse pelo celular usando: http://192.168.1.6:5000
```

Qualquer dispositivo na mesma rede (ou na sua Tailnet, se usar Tailscale) pode acessar o painel completo.

### Abas da Interface

| Aba | Função |
|---|---|
| **💬 Chat** | Interface principal de conversa com streaming de tokens em tempo real via Server-Sent Events (SSE). Suporta markdown, blocos de código, imagens e players de áudio inline |
| **🔗 Integrations** | Toggles para ligar/desligar os bots (WhatsApp, Discord, Telegram, Twitter) sem reiniciar o sistema. Os status são lidos em tempo real |
| **🧠 Agent** | Editor ao vivo de `SOUL.md` e `MEMORY.md`. Salva diretamente em disco sem restart |
| **🔌 Model Context Protocol** | Catálogo curado de servidores MCP para instalação com 1 clique. Ao clicar "Instalar", chama internamente `moltyclaw mcp install <url>` |

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

## 💻 CLI Global — Comandos de Linha de Comando

Após selecionar a opção **"Configurar 'moltyclaw' Global"** no Launcher (opção 3), o executável é adicionado ao PATH do Windows. A partir daí, use de qualquer pasta, a qualquer hora.

### Referência Completa de Comandos

```bash
# Iniciar o menu interativo
moltyclaw

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
moltyclaw update       # git pull + pip install -r requirements.txt
moltyclaw reset memory # Limpa o MEMORY.md completamente
moltyclaw doctor       # Diagnóstico: checa Python, Node, .env, dependências
moltyclaw --help       # Lista todos os comandos disponíveis
```

---

## 🛠️ Instalação e Configuração

### Requisitos

| Componente | Versão Mínima |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ (apenas para WhatsApp) |
| Microsoft Edge | Qualquer versão recente (para Playwright) |

### Passo a Passo

**1. Clone o repositório:**

```bash
git clone https://github.com/antojunimaia-ui/MoltyClaw.git
cd MoltyClaw
```

**2. Configure o `.env`:**

```env
# ─── IA PRINCIPAL ───────────────────────────────────────
MISTRAL_API_KEY=sua_chave_mistral_aqui
# Alternativa (escolha no menu):
OPENROUTER_API_KEY=sua_chave_openrouter_aqui
OPENROUTER_MODEL=google/gemini-2.5-flash

# ─── INTEGRAÇÕES SOCIAIS ────────────────────────────────
DISCORD_TOKEN=seu_token_discord_aqui
TELEGRAM_TOKEN=seu_token_telegram_aqui

# ─── E-MAIL ─────────────────────────────────────────────
GMAIL_USER=seu_email@gmail.com
GMAIL_APP_PASSWORD=sua_senha_de_app_google  # Não é sua senha normal!

# ─── SPOTIFY ────────────────────────────────────────────
SPOTIFY_CLIENT_ID=seu_client_id
SPOTIFY_CLIENT_SECRET=seu_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8080

# ─── TWITTER/X ──────────────────────────────────────────
TWITTER_BEARER_TOKEN=seu_bearer_token
TWITTER_API_KEY=sua_api_key
TWITTER_API_SECRET=sua_api_secret
TWITTER_ACCESS_TOKEN=seu_access_token
TWITTER_ACCESS_TOKEN_SECRET=seu_access_token_secret

# ─── SEGURANÇA / WHITELISTS ─────────────────────────────
WHATSAPP_ALLOWED_NUMBERS=5511999999999,5511888888888
DISCORD_ALLOWED_USERS=123456789012345678
TELEGRAM_ALLOWED_USERS=seu_usuario,12345678
```

**3. Instale as dependências Python:**

```bash
pip install -r requirements.txt
playwright install msedge
```

**4. (Opcional) WhatsApp — dependências Node.js:**

```bash
npm install whatsapp-web.js qrcode-terminal axios dotenv
```

**5. Inicie:**

```bash
python start_moltyclaw.py
```

---

## 📁 Arquitetura de Arquivos

```
moltyclaw/
│
├── start_moltyclaw.py         # Ponto de entrada. CLI, Menu interativo,
│                              # Orquestrador multithread, Parser de argumentos
│
├── src/
│   ├── moltyclaw.py           # O Kernel do Agente. Classe MoltyClaw com:
│   │                          # - Método .ask() com loop Plano→Ação→Observação
│   │                          # - Parser de tool calls JSON
│   │                          # - Client Mistral/OpenRouter com streaming
│   │                          # - Motor Playwright (Stealth + Operant ID)
│   │                          # - MCPHub (gestão de conexões Stdio com MCP servers)
│   │                          # - Handlers de cada ferramenta (CMD, email, Spotify, etc.)
│   │
│   ├── webui/
│   │   ├── app.py             # Backend Flask. Rotas REST + SSE streaming.
│   │   │                      # Roda o agente numa thread assíncrona dedicada.
│   │   ├── static/
│   │   │   ├── script.js      # Frontend JS. Tab switching, SSE consumer,
│   │   │   │                  # Markdown renderer (marked.js + DOMPurify),
│   │   │   │                  # Audio player inline, MCP grid installer
│   │   │   └── style.css      # UI premium do dashboard
│   │   └── templates/
│   │       └── index.html     # HTML base do dashboard
│   │
│   └── integrations/
│       ├── whatsapp_server.py # Servidor AIOHTTP da integração WhatsApp (Python-side)
│       ├── whatsapp_bridge.js # Bridge Node.js que conecta ao WhatsApp Web via QR
│       ├── discord_bot.py     # Bot Discord com discord.py
│       ├── telegram_bot.py    # Bot Telegram com python-telegram-bot
│       └── twitter_bot.py     # Bot Twitter/X com tweepy (API v2)
│
├── SOUL.md                    # Identidade, personalidade e regras invioláveis do agente
├── MEMORY.md                  # Hipocampo de longo prazo. Atualizado autonomamente pelo agente
├── mcp_servers.json           # Configuração dos servidores MCP ativos (gerado automaticamente)
├── mcp_servers.example.json   # Template de referência para configurar MCPs manualmente
├── requirements.txt           # Dependências Python
└── .env                       # Variáveis de ambiente (NÃO versionar!)
```

---

> **⚠️ Aviso de Segurança:** O MoltyClaw opera com as mesmas permissões do usuário Windows que iniciou o processo. O agente tem acesso ao CMD, ao sistema de arquivos e à internet. Configure as whitelists corretamente e não compartilhe o modo `--share` em redes públicas sem autenticação adicional. Revise o `SOUL.md` para impor restrições de comportamento conforme necessário.
