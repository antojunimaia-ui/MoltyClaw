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

        // Desloga da API local o que MoltyClaw resolveu falar
        console.log(`🤖 Resposta do MoltyClaw: ${iaReply || (mediaPath ? "Enviando arquivo de mídia..." : "Resposta vazia.")}`);

        // Devolve o texto final lá no WhatsApp
        if (mediaPath) {
            const { MessageMedia } = require('whatsapp-web.js');
            const media = MessageMedia.fromFilePath(mediaPath);
            if (iaReply && iaReply.trim() !== "") {
                msg.reply(media, undefined, { caption: iaReply });
            } else {
                msg.reply(media);
            }
        } else {
            msg.reply(iaReply || "Tive um problema processando o texto...");
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
