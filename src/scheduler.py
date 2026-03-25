import asyncio
import json
import os
import time
from datetime import datetime
from uuid import uuid4

class SchedulerManager:
    def __init__(self, agent):
        self.agent = agent
        self.jobs_file = os.path.join(os.path.expanduser("~"), ".moltyclaw", "jobs.json")
        self.jobs = self.load_jobs()
        self.is_running = False
        self._loop_task = None

    def load_jobs(self):
        if not os.path.exists(self.jobs_file):
            return []
        try:
            with open(self.jobs_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []

    def save_jobs(self):
        try:
            with open(self.jobs_file, "w", encoding="utf-8") as f:
                json.dump(self.jobs, f, indent=4)
        except Exception as e:
            print(f"[Scheduler] Error saving jobs: {e}")

    def add_job(self, name, description, interval_min, payload, enabled=True):
        job = {
            "id": str(uuid4())[:8],
            "name": name,
            "description": description,
            "interval": int(interval_min) * 60,
            "payload": payload,
            "enabled": enabled,
            "last_run": 0,
            "created_at": datetime.now().isoformat()
        }
        self.jobs.append(job)
        self.save_jobs()
        return job

    def remove_job(self, job_id):
        self.jobs = [j for j in self.jobs if j["id"] != job_id]
        self.save_jobs()

    def toggle_job(self, job_id, enabled):
        for j in self.jobs:
            if j["id"] == job_id:
                j["enabled"] = enabled
        self.save_jobs()

    async def run(self):
        self.is_running = True
        print("[Scheduler] Motor de Agendamento iniciado.")
        while self.is_running:
            try:
                now = time.time()
                for job in self.jobs:
                    if not job.get("enabled", True):
                        continue
                    
                    last_run = job.get("last_run", 0)
                    interval = job.get("interval", 900)
                    
                    if now - last_run >= interval:
                        # Verifica se o agente está ocupado
                        if hasattr(self.agent, "is_busy") and self.agent.is_busy:
                            continue
                            
                        print(f"[Scheduler] Executando Job: {job['name']}")
                        job["last_run"] = now
                        self.save_jobs()
                        
                        # Executa em background
                        asyncio.create_task(self.agent.ask(job["payload"], silent=True))
                        
                await asyncio.sleep(30) # Check a cada 30 segundos
            except Exception as e:
                print(f"[Scheduler Error] {e}")
                await asyncio.sleep(10)

    def stop(self):
        self.is_running = False
