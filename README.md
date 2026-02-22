# 🤖 MoltyClaw - O Agente Autônomo Definitivo

```text
███╗   ███╗ ██████╗ ██╗  ████████╗██╗   ██╗ ██████╗██╗      █████╗ ██╗    ██╗
████╗ ████║██╔═══██╗██║  ╚══██╔══╝╚██╗ ██╔╝██╔════╝██║     ██╔══██╗██║    ██║
██╔████╔██║██║   ██║██║     ██║    ╚████╔╝ ██║     ██║     ███████║██║ █╗ ██║
██║╚██╔╝██║██║   ██║██║     ██║     ╚██╔╝  ██║     ██║     ██╔══██║██║███╗██║
██║ ╚═╝ ██║╚██████╔╝███████╗██║      ██║   ╚██████╗███████╗██║  ██║╚███╔███╔╝
╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝      ╚═╝    ╚═════╝╚══════╝╚═╝  ╚═╝ ╚══╝╚══╝
```

Bem-vindo ao repositório do **MoltyClaw**, um agente autônomo superpoderoso que utiliza a IA **Mistral** não apenas para conversar, mas para **agir**. O MoltyClaw foi projetado como uma ponte entre a inteligência abstrata e o mundo real, operando o seu sistema Windows e a Internet com total autonomia.

---

## ✨ O que o MoltyClaw consegue fazer?

O MoltyClaw não é um chatbot comum. Ele entende o seu pedido, elabora um plano, executa uma ou mais ferramentas e só depois volta para te dar a resposta.

### 🌐 Automação Web Completa (Playwright)

O MoltyClaw possui um navegador persistente embutido. Quando você pede algo sobre a internet:

- **`GOTO`**: Ele abre links e lê páginas reais (evitando alucinações de dados).
- **`READ_PAGE`**: Ele faz a raspagem de texto da página aberta para entender o conteúdo.
- **`CLICK` e `TYPE`**: O MoltyClaw pode **clicar** fisicamente em botões e **preencher** formulários autonomamente!

### ⚙️ Execução de Terminal

- O MoltyClaw foi programado para poder emitir comandos reais para o prompt ou shell local (`cmd`). Ele pode listar diretórios, criar arquivos, e ler saídas vitais do sistema do computador em que ele está hospedado.

### � Gerenciamento de E-mail (Gmail Autônomo)

- O MoltyClaw recebeu a permissão e o protocolo IMAP/SMTP embutidos no seu núcleo! Você pode pedir no chat: *"Leia meus últimos 3 emails"*, *"Exclua aquele email de spam"* ou *"Mande um email profissional pro meu chefe confirmando a entrega das planilhas"*. As ações `READ_EMAILS`, `SEND_EMAIL` e `DELETE_EMAIL` trabalham lendo os tokens diretamente no arquivo `.env`.

### 🎵 Integração Spotify API (Music Control)

- Acoplado com a API do Spotify via `spotipy`, o agente pode atuar como um DJ. Peça *"Toque aquela do Daft Punk"*, *"Pause a música"* ou *"Pesquise músicas do the weeknd e crie uma fila"*. Usa as ferramentas `SPOTIFY_PLAY`, `SPOTIFY_PAUSE`, `SPOTIFY_SEARCH` e `SPOTIFY_ADD_QUEUE`. Requer Autenticação no `.env`.

### 📺 Devorador de YouTube (Transcrição Oculta)

- Sem precisar gastar horas da sua vida, envie um link do YouTube e diga: *"Molty, faça um resumo desse vídeo longo"*. Ele usa o motor de `youtube-transcript-api` e a ferramenta `YOUTUBE_SUMMARIZE` para puxar silenciosamente a legenda inteira dos servidores do Google, compreendendo todo o conhecimento do vídeo para te devolver as respostas no chat em formato de resumo!

### �🔗 Múltiplas Integrações Sociais

Ficar preso a um console preto de terminal é coisa do passado! Nossa visão é criar uma inteligência artificial acessível e onipresente em suas redes sociais primárias. As integrações do Agente foram acopladas à sua lógica nativa: não importa de onde a mensagem vem, ele consome o mesmo poder das ações locais de "Browser" ou "Terminal".

Atualmente possuímos três braços totalmente integrados e funcionais que podem atuar em tempo real com você ou sua comunidade de amigos:

1. 📱 **WhatsApp (Sessão Criptografada via QR Code)**:
   - **Como funciona:** Um sub-servidor Headless intercepta mensagens via Node.js e orquestra a comunicação bidirecional de mensagens no WhatsApp com a Python Engine.
   - **O que ele faz:** O MoltyClaw intercepta mensagens do seu WhatsApp conectadas e fornece respostas imediatas com base no modelo do Mistral aliado a acesso web orgânico direto da palma da sua mão.
   - **Segurança Nativa (Whitelist):** Conta com suporte à `WHATSAPP_ALLOWED_NUMBERS` no `.env`. Você escolhe se a IA vai falar com todos do seu contato, ou apenas com os números previamente autorizados por você.

2. 🎧 **Discord (Bot App Protocol)**:
   - **Como funciona:** Um robô construído na API oficial de bibliotecas do Discord usando Python que opera conectado sob intenções restritas de ler canais e atuar como um membro da sua comunidade.
   - **O que ele faz:** Foi programado para não atrapalhar servidores (ignorando discussões alheias). Ele só acorda, pensa, e envia respostas caso alguém **o mencione** (`@MoltyClaw ...`) em canais públicos ou envie uma **Mensagem Direta (*DM*)**. Enquanto pesquisa a resposta das ferramentas na infraestrutura do Windows, ele exibe elegantemente a barra "*digitando...*" na tela das DMs do app para imersão extrema de chat.

3. ✈️ **Telegram (Python-Telegram-Bot)**:
   - **Como funciona:** O MoltyClaw se conecta ao protocolo super rápido do Telegram utilizando o token fornecido via BotFather.
   - **O que ele faz:** Ele funciona perfeitamente em DM respondendo às suas pesquisas interativas e também se sai perfeitamente em Grupos (onde só atuará de forma independente caso seja explicitamente respondido ou mencionado, não interrompendo conversas paralelas). Manda a mensagem em pedaços contínuos se o resultado do MoltyClaw passar do limite de texto da plataforma.

---

## 🚀 Como Rodar

Este projeto se divide em uma base principal em Python e uma ponte em Node.js (exclusivo para WhatsApp).

### 📋 Requisitos Iniciais

1. Python 3.10+
2. Node.js 18+
3. Criação de chaves de API:
   - Cadastre e gere sua chave em [console.mistral.ai](https://console.mistral.ai).
   - *Opcional*: Se for usar o Bot do Discord, crie o aplicativo no [Discord Developer Portal](https://discord.com/developers/applications).
   - *Opcional*: Se for usar o Telegram, crie um Bot gerando o token com o **@BotFather** no Telegram.

### 🛠️ Instalação

1. Clone ou baixe este repositório.
2. Crie ou configure o seu arquivo `.env` na raiz da pasta:

   ```env
   MISTRAL_API_KEY=sua_chave_mistral_aqui
   DISCORD_TOKEN=seu_token_discord_aqui_opcional
   TELEGRAM_TOKEN=seu_token_telegram_aqui_opcional
   GMAIL_USER=seu_email@gmail.com
   GMAIL_APP_PASSWORD=sua_senha_segura_de_aplicativo_google
   SPOTIFY_CLIENT_ID=seu_client_id_aqui
   SPOTIFY_CLIENT_SECRET=seu_client_secret_aqui
   SPOTIFY_REDIRECT_URI=http://localhost:8080
   WHATSAPP_ALLOWED_NUMBERS=5511999999999,5511888888888
   ```

3. Instale as dependências essenciais do mundo Python:

   ```bash
   pip install -r requirements.txt
   playwright install chrome
   ```

4. Se quiser usar o módulo do WhatsApp, instale as dependências do protocolo (Node.js):

   ```bash
   npm install whatsapp-web.js qrcode-terminal axios dotenv
   ```

### 🎮 O Launcher Interativo

Não sabe qual serviço rodar? Esqueça inicializações longas e abra nosso **Launcher** direto do seu terminal:

```bash
python start_moltyclaw.py
```

O MoltyClaw te apresentará um menu lindo (com poder da interface *Rich*) para você escolher qual braço da IA quer conectar naquele exato momento: WhatsApp, Discord, Telegram ou iniciar TODOS DE UMA VEZ!

---

## 🧠 Arquitetura Interna

Para desenvolvedores curiosos, eis a estrutura do MoltyClaw:

- `start_moltyclaw.py` -> Gerenciador multithread de subprocessos.
- `src/moltyclaw.py` -> A essência do agente! Contém o Prompt de Sistema com regras de Bloqueio JSON (`<tool>`), loop de interações com as *tools* da máquina física e do Chromium.
- `src/integrations/whatsapp_server.py` -> API Rest construída em `aiohttp` carregando o corpo digital do MoltyClaw.
- `src/integrations/whatsapp_bridge.js` -> Capturador headless silencioso do protocolo Web do WhatsApp que repassa o recado aos ouvidos do Python.
- `src/integrations/discord_bot.py` -> Robô clássico conectado via biblioteca `discord.py` utilizando *Intents*.
- `src/integrations/telegram_bot.py` -> Módulo assíncrono conectado usando `python-telegram-bot`, pronto para Groups e Private Chats.

---
**Nota**: O Agente opera com total liberdade dentro das permissões lógicas do usuário que inicia o script. Tenha cautela caso deixe o seu computador ligado sozinho enquanto pede para o MoltyClaw apagar arquivos do seu disco pelo zap! 😉
