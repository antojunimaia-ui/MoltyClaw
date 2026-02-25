import os
import sys
import asyncio
import threading
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # Silenciar spams do flask no console

# Adiciona o diretório base para ler os imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.moltyclaw import MoltyClaw
from rich.console import Console

console = Console()
app = Flask(__name__, template_folder="templates", static_folder="static")
load_dotenv()

agent = None
loop = None
ready = False

def run_agent_loop():
    global agent, loop, ready
    
    # Prepara o Event Loop do Asyncio para a Thread 
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    agent = MoltyClaw(name="MoltyClaw (WebUI Gateway)")
    
    # Inicia o Browser do Playwright escondido
    loop.run_until_complete(agent.init_browser())
    
    ready = True
    console.print("\n[bold green]✅ WebUI Health OK -> Porta 5000 Aberta![/bold green]")
    loop.run_forever()

# Inicia o Loop do MoltyClaw silenciosamente debaixo dos panos numa thread dedicada
threading.Thread(target=run_agent_loop, daemon=True).start()


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({"ready": ready})

@app.route("/api/chat", methods=["POST"])
def chat():
    if not ready:
         return jsonify({"error": "Gateway MoltyClaw está ligando o Browser... Aguarde 5 segundos."}), 503
         
    data = request.json
    user_msg = data.get("message", "")
    if not user_msg:
        return jsonify({"error": "Mensagem vazia."}), 400
        
    try:
        # Envia a thread local HTTP para a main thread assincrona do robô de forma limpa (Threadsafe)
        future = asyncio.run_coroutine_threadsafe(agent.ask(user_msg, silent=False), loop)
        reply = future.result(timeout=600)  # Tolerância de 10 min de timeout
        return jsonify({"reply": reply})
    except Exception as e:
        console.print(f"[bold red]Erro processando requisição API: {e}[/bold red]")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    console.print("[intense_cyan]🚀 Acordando MoltyClaw WebUI... Acesse: http://127.0.0.1:5000[/intense_cyan]")
    # Roda o dev test na porta 5000 acessível local
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
