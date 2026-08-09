import asyncio
import os
import json
import sys
from contextlib import AsyncExitStack
from typing import Dict, Any

from rich.console import Console
console = Console()

class MCPHub:
    def __init__(self, allowed_servers=None):
        self.sessions: Dict[str, Any] = {}
        self.exit_stack = AsyncExitStack()
        self.allowed_servers = set(allowed_servers) if allowed_servers else None  # None = todos permitidos

    async def connect_servers(self, config_path: str = None):
        if not config_path:
            config_path = os.path.join(os.path.expanduser("~"), ".moltyclaw", "mcp_servers.json")
            
        if not os.path.exists(config_path):
            console.print(f"[dim yellow]Nenhum arquivo {config_path} encontrado. Pulando inicialização de servidores MCP externos.[/dim yellow]")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            mcp_servers = config.get("mcpServers", {})
            if not mcp_servers:
                return
                
            # Importa mcp apenas se for usar, para não quebrar quem não instalou
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            
            for server_name, server_config in mcp_servers.items():
                # Verifica se este servidor é permitido para este agente
                if self.allowed_servers is not None and server_name not in self.allowed_servers:
                    console.print(f"[dim yellow]Servidor MCP '{server_name}' não permitido para este agente. Pulando...[/dim yellow]")
                    continue
                
                try:
                    console.print(f"[dim cyan]Conectando ao servidor MCP: {server_name}...[/dim cyan]")
                    
                    env = server_config.get("env", {})
                    # Mesclar ambiente atual
                    full_env = os.environ.copy()
                    for k, v in env.items():
                        full_env[k] = v
                        
                    server_params = StdioServerParameters(
                        command=server_config["command"],
                        args=server_config.get("args", []),
                        env=full_env
                    )
                    
                    stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
                    stdio, write = stdio_transport
                    session = await self.exit_stack.enter_async_context(ClientSession(stdio, write))
                    
                    await session.initialize()
                    self.sessions[server_name] = session
                    
                    console.print(f"[green]Servidor MCP '{server_name}' conectado e inicializado![/green]")
                except Exception as e:
                    console.print(f"[bold red]Erro ao inicializar servidor MCP '{server_name}': {e}[/bold red]")

        except Exception as e:
            console.print(f"[bold red]Erro ao ler {config_path}: {e}[/bold red]")

    async def get_all_tools_formatted(self) -> str:
        """Coleta as ferramentas de todos os servidores MCP e retorna uma string formatada para o prompt do LLM."""
        if not self.sessions:
            return ""
            
        tools_text = []
        for server_name, session in self.sessions.items():
            try:
                response = await session.list_tools()
                for tool in response.tools:
                    # tool.name, tool.description, tool.inputSchema
                    tools_text.append(f"- `[{{\"action\": \"MCP_TOOL\", \"server\": \"{server_name}\", \"tool\": \"{tool.name}\", \"params\": {json.dumps(tool.inputSchema)}}}]`: {tool.description}")
            except Exception as e:
                console.print(f"[dim red]Aviso: Falha ao listar tools do MCP '{server_name}': {e}[/dim red]")
        
        if tools_text:
            return "\n".join(tools_text)
        return ""

    async def call_tool(self, server_name: str, tool_name: str, arguments: dict) -> str:
        if server_name not in self.sessions:
            return f"Erro: Servidor MCP '{server_name}' não conectado."
            
        session = self.sessions[server_name]
        try:
            # Em python MCP SDK v1.x: result is CallToolResult
            result = await session.call_tool(tool_name, arguments)
            
            # format the result
            output_texts = []
            for item in result.content:
                if item.type == "text":
                    output_texts.append(item.text)
                else:
                    output_texts.append(f"<{item.type} contents omitted>")
                    
            if result.isError:
                return f"MCP Tool Retornou um ERRO:\n" + "\n".join(output_texts)
            
            return "\n".join(output_texts)
        except Exception as e:
            return f"Erro ao executar MCP tool '{tool_name}' no servidor '{server_name}': {e}"
            
    async def cleanup(self):
        """
        Fecha todas as conexões MCP de forma segura.

        O anyio/mcp tem um bug conhecido no Python 3.12+ onde o stdio_client
        usa um TaskGroup cujo cancel scope é criado em uma task e desfeito em
        outra durante o shutdown do uvicorn, causando:
          RuntimeError: Attempted to exit cancel scope in a different task
        A estratégia é:
          1. Silenciar os warnings de async_generator no processo.
          2. Rodar o aclose() numa task isolada e capturar qualquer BaseException.
        """
        # Suprime o aviso de 'error during closing of asynchronous generator'
        # que o Python emite quando o GC tenta fechar o stdio_client de forma abrupta.
        if hasattr(sys, 'set_asyncgen_hooks'):
            try:
                sys.set_asyncgen_hooks(finalizer=lambda ag: None)
            except Exception:
                pass

        async def _do_close():
            try:
                await self.exit_stack.aclose()
            except BaseException:
                # Captura RuntimeError (cancel scope mismatch), GeneratorExit,
                # e qualquer outro erro que o anyio/mcp lance durante o shutdown.
                pass

        try:
            # Cria uma task isolada para o fechamento — isso evita que o cancel
            # scope do anyio reclame de task mismatch.
            task = asyncio.ensure_future(_do_close())
            await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
        except BaseException:
            pass
