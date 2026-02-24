const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
require('dotenv').config();

// Inicializa o cliente WhatsApp com salvamento de sessão
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true, // Roda sem mostrar outro Chrome na sua tela, invisível!
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            '--disable-dev-shm-usage',
            '--disable-software-rasterizer'
        ]
    }
});

client.on('qr', (qr) => {
    // Escaneie este QR code com seu WhatsApp (Aparelhos Conectados)
    console.log('\n===========================================');
    console.log('[!] ESCANEIE O QR CODE COM O SEU WHATSAPP [!]');
    console.log('===========================================\n');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('✅ Cliente do WhatsApp conectado com Sucesso!');
    console.log('🚀 MOLTYCLAW agora está ouvindo suas mensagens no zap!');
});

// Evento quando alguém te manda uma mensagem ou vice-versa
client.on('message', async msg => {
    // Opcional: Só responder se a mensagem começar com "MoltyClaw," ou ".mt"
    // Aqui decidi responder qualquer mensagem direta se não for do próprio bot
    // Vamos garantir que não respondemos em grupos por enquanto, só conversas isoladas

    if (msg.from.includes("@g.us")) {
        // Ignora grupos
        return;
    }

    const permittedNumbers = process.env.WHATSAPP_ALLOWED_NUMBERS;
    if (permittedNumbers && permittedNumbers.trim() !== '') {
        const allowedList = permittedNumbers.split(',').map(n => n.trim() + '@c.us');
        if (!allowedList.includes(msg.from)) {
            console.log(`[Segurança] Ignorando contato não autorizado: ${msg.from}`);
            return;
        }
    }

    // Mostra o texto quem enviou
    const contact = await msg.getContact();
    console.log(`\n💬 Nova msg do WhatsApp de [${contact.pushname || msg.from}]: ${msg.body}`);

    try {
        // Sinaliza ao contato que a IA está "digitando..."
        const chat = await msg.getChat();
        await chat.sendStateTyping();

        // Envia requisição para a nossa API do MoltyClaw (moltyclaw_server.py)
        const response = await axios.post('http://localhost:8080/whatsapp', {
            sender: contact.pushname || msg.from,
            message: msg.body
        });

        const iaReply = response.data.reply;
        const mediaPath = response.data.media;
        const audioReplyPath = response.data.audio_reply;

        // Desloga da API local o que MoltyClaw resolveu falar
        console.log(`🤖 Resposta do MoltyClaw: ${iaReply || (mediaPath ? "Enviando arquivo de mídia..." : (audioReplyPath ? "Enviando audio..." : "Resposta vazia."))}`);

        // Devolve o texto final lá no WhatsApp
        if (mediaPath) {
            const { MessageMedia } = require('whatsapp-web.js');
            const media = MessageMedia.fromFilePath(mediaPath);
            if (iaReply && iaReply.trim() !== "") {
                await msg.reply(media, undefined, { caption: iaReply });
            } else {
                await msg.reply(media);
            }
        } else if (iaReply && iaReply.trim() !== "") {
            await msg.reply(iaReply);
        }

        if (audioReplyPath) {
            const { MessageMedia } = require('whatsapp-web.js');
            const media = MessageMedia.fromFilePath(audioReplyPath);
            await msg.reply(media, undefined, { sendAudioAsVoice: true });
        }
        await chat.clearState();

    } catch (error) {
        console.error("❌ Ocorreu um erro ao comunicar com a API do MoltyClaw:", error.message);
        msg.reply("Desculpe, o MoltyClaw offline ou em erro crítico. Certifique-se de que o servidor está rodando!");
    }
});

// Dispara conexão (abre o Chromium em background)
console.log("Iniciando WPPConnect...");
client.initialize();

// Sub-servidor local para disparos ativos vindo do Python
const http = require('http');
const bridgeServer = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/send_whatsapp') {
        let body = '';
        req.on('data', chunk => { body += chunk.toString(); });
        req.on('end', async () => {
            try {
                const { to, message, mediaPath } = JSON.parse(body);
                // "to" vira formato obrigatório e aceitável do node
                if (mediaPath) {
                    const { MessageMedia } = require('whatsapp-web.js');
                    const media = MessageMedia.fromFilePath(mediaPath);
                    const isAudio = mediaPath.endsWith('.mp3') || mediaPath.endsWith('.ogg');
                    const options = {};
                    if (isAudio) options.sendAudioAsVoice = true;
                    if (message && message.trim() !== "") options.caption = message;

                    if (Object.keys(options).length > 0) {
                        await client.sendMessage(to, media, options);
                    } else {
                        await client.sendMessage(to, media);
                    }
                } else if (message && message.trim() !== "") {
                    await client.sendMessage(to, message);
                }

                console.log(`[API Bridge] Mensagem Ativa disparada para: ${to}`);
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ status: 'success' }));
            } catch (error) {
                console.error("[API Bridge] Falha ao enviar msg ativamente:", error.message);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ status: 'error', reason: error.message }));
            }
        });
    } else {
        res.writeHead(404);
        res.end();
    }
});

bridgeServer.listen(8081, () => {
    console.log('📡 WhatsApp Bridge REST API ouvindo na porta 8081 para disparos ativos!');
});
