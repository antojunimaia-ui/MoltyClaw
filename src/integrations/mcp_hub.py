import asyncio
import os
import json
from contextlib import AsyncExitStack
from typing import Dict, Any

from rich.console import Console
console = Console()

class MCPHub:
    def __init__(self):
        self.sessions: Dict[str, Any] = {}
        self.exit_stack = AsyncExitStack()

    async def connect_servers(self, config_path: str = "mcp_servers.json"):
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
        try:
            await self.exit_stack.aclose()
        except:
            pass
