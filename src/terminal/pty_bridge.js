const os = require('os');
const pty = require('node-pty');
const WebSocket = require('ws');

// Escolha do shell baseado no Windows ou Linux
const shell = os.platform() === 'win32' ? 'powershell.exe' : 'bash';

// Cria o processo do terminal persistente
const ptyProcess = pty.spawn(shell, [], {
    name: 'xterm-color',
    cols: 100,
    rows: 30,
    cwd: process.cwd(),
    env: process.env
});

// Configura o servidor WebSocket na porta 9001
const wss = new WebSocket.Server({ port: 9001 });

// Buffer para enviar os logs iniciais se o cliente se desconectar e voltar
let outputBuffer = "";
const MAX_BUFFER = 10000;

ptyProcess.onData((data) => {
    outputBuffer += data;
    if (outputBuffer.length > MAX_BUFFER) {
        outputBuffer = outputBuffer.slice(outputBuffer.length - MAX_BUFFER);
    }
    
    // Envia o output para todos os clientes conectados (geralmente só um: o MoltyClaw)
    wss.clients.forEach(client => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify({ type: 'output', data: data }));
        }
    });
});

wss.on('connection', (ws) => {
    console.log('[PTY Bridge] Cliente conectado (MoltyClaw)');
    
    // Envia o estado atual do terminal pro cliente carregar o contexto
    ws.send(JSON.stringify({ type: 'init', data: outputBuffer }));
    
    ws.on('message', (message) => {
        try {
            const payload = JSON.parse(message);
            if (payload.type === 'input') {
                // Escreve diretamente no terminal persistente
                ptyProcess.write(payload.data);
            } else if (payload.type === 'resize') {
                ptyProcess.resize(payload.cols, payload.rows);
            }
        } catch (err) {
            console.error('[PTY Bridge] Erro ao processar mensagem do cliente:', err.message);
        }
    });

    ws.on('close', () => {
        console.log('[PTY Bridge] Cliente desconectado.');
    });
});

console.log(`📡 Terminal PTY Bridge ativo em ${shell} na porta 9001!`);
console.log(`🚀 O MoltyClaw agora tem uma sessão persistente.`);
