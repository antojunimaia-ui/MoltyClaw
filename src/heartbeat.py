import asyncio
import os
import json
import time
from datetime import datetime
import threading
from typing import TYPE_CHECKING
from config_loader import get_config

if TYPE_CHECKING:
    from moltyclaw import MoltyClaw

class HeartbeatManager:
    def __init__(self, agent: "MoltyClaw"):
        self.agent = agent
        self.config = get_config()
        self.enabled = self.config.get("heartbeat", {}).get("enabled", True)
        self.interval = self._parse_interval(self.config.get("heartbeat", {}).get("every", "15m"))
        self.active_hours = self.config.get("heartbeat", {}).get("active_hours", {"start": "08:00", "end": "22:00"})
        self.silence_token = self.config.get("heartbeat", {}).get("token_silence", "HEARTBEAT_OK")
        self.is_running = False
        self._loop_task = None

    def _parse_interval(self, every_str):
        if every_str.endswith("m"):
            return int(every_str[:-1]) * 60
        if every_str.endswith("h"):
            return int(every_str[:-1]) * 3600
        return 900 # default 15m

    def is_within_active_hours(self):
        now = datetime.now().time()
        start = datetime.strptime(self.active_hours["start"], "%H:%M").time()
        end = datetime.strptime(self.active_hours["end"], "%H:%M").time()
        
        if start <= end:
            return start <= now <= end
        else: # Over midnight
            return now >= start or now <= end

    async def run(self):
        if not self.enabled:
            return
        
        self.is_running = True
        while self.is_running:
            try:
                # Espera o intervalo
                await asyncio.sleep(self.interval)
                
                if not self.is_within_active_hours():
                    continue

                if self.agent.is_busy: # Precisaremos adicionar essa flag no moltyclaw.py
                    continue

                # Prompt de Heartbeat
                prompt = (
                    "PROMPT DE HEARTBEAT: Verifique suas memórias e o estado do sistema. "
                    "Há algo que exija sua atenção ou proatividade agora? "
                    "Se não houver nada urgente para relatar ao usuário, responda EXATAMENTE com 'HEARTBEAT_OK'. "
                    "Caso contrário, execute as ferramentas necessárias ou responda o que for importante. "
                    "Não mencione que isso é um heartbeat para o usuário."
                )

                # Executa o ask silenciosamente
                response = await self.agent.ask(prompt, silent=True)

                if self.silence_token in response:
                    continue
                
                # Se a resposta não for o token de silêncio, envia para os canais ativos
                # Isso seria implementado integrando com os bots no start_moltyclaw.py
                print(f"[HEARTBEAT] Agente tem algo a dizer: {response[:100]}...")
                
            except Exception as e:
                print(f"[HEARTBEAT ERROR] {e}")

    def stop(self):
        self.is_running = False
