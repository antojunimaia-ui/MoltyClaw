"""
MoltyClaw — Environment Manager
Gerencia leitura e escrita segura do arquivo .env
"""
import os
import re
from typing import Dict, Optional, List
from initializer import MOLTY_DIR


class EnvManager:
    """Gerenciador de variáveis de ambiente no .env"""
    
    def __init__(self, env_path: Optional[str] = None):
        self.env_path = env_path or os.path.join(MOLTY_DIR, ".env")
        
    def read_all(self) -> Dict[str, str]:
        """Lê todas as variáveis do .env"""
        if not os.path.exists(self.env_path):
            return {}
            
        env_vars = {}
        try:
            with open(self.env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Ignora comentários e linhas vazias
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=VALUE
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        except Exception as e:
            print(f"Erro ao ler .env: {e}")
            
        return env_vars
    
    def read(self, key: str) -> Optional[str]:
        """Lê uma variável específica"""
        env_vars = self.read_all()
        return env_vars.get(key)
    
    def write(self, key: str, value: str) -> bool:
        """Escreve ou atualiza uma variável no .env"""
        try:
            # Lê o arquivo atual
            lines = []
            if os.path.exists(self.env_path):
                with open(self.env_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            
            # Procura se a chave já existe
            found = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    existing_key = stripped.split('=', 1)[0].strip()
                    if existing_key == key:
                        lines[i] = f"{key}={value}\n"
                        found = True
                        break
            
            # Se não encontrou, adiciona no final
            if not found:
                lines.append(f"{key}={value}\n")
            
            # Salva o arquivo
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
            return True
        except Exception as e:
            print(f"Erro ao escrever no .env: {e}")
            return False
    
    def write_multiple(self, vars_dict: Dict[str, str]) -> bool:
        """Escreve múltiplas variáveis de uma vez"""
        try:
            for key, value in vars_dict.items():
                if not self.write(key, value):
                    return False
            return True
        except Exception as e:
            print(f"Erro ao escrever múltiplas variáveis: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Remove uma variável do .env"""
        try:
            if not os.path.exists(self.env_path):
                return True
                
            lines = []
            with open(self.env_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Filtra a linha com a chave
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    existing_key = stripped.split('=', 1)[0].strip()
                    if existing_key == key:
                        continue  # Pula essa linha
                new_lines.append(line)
            
            # Salva o arquivo
            with open(self.env_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
                
            return True
        except Exception as e:
            print(f"Erro ao deletar variável: {e}")
            return False
    
    def get_integration_config(self, platform: str) -> Dict[str, any]:
        """Retorna configuração de uma integração específica"""
        env_vars = self.read_all()
        
        config = {
            "configured": False,
            "fields": {}
        }
        
        # Mapeia campos por plataforma
        field_map = {
            "discord": ["DISCORD_TOKEN", "DISCORD_ALLOWED_USERS"],
            "telegram": ["TELEGRAM_TOKEN", "TELEGRAM_ALLOWED_USERS"],
            "whatsapp": ["WHATSAPP_ALLOWED_NUMBERS"],
            "twitter": ["TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET", "TWITTER_BEARER_TOKEN"],
            "bluesky": ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD", "BLUESKY_ALLOWED_HANDLES"]
        }
        
        if platform not in field_map:
            return config
        
        # Verifica se está configurado
        required_fields = field_map[platform]
        for field in required_fields:
            value = env_vars.get(field, "")
            
            # Sempre adiciona o campo, mesmo que vazio
            if value:
                config["configured"] = True
                # Mascara tokens/senhas (mostra apenas primeiros e últimos caracteres)
                if "TOKEN" in field or "SECRET" in field or "PASSWORD" in field:
                    if len(value) > 10:
                        config["fields"][field] = f"{value[:4]}...{value[-4:]}"
                    else:
                        config["fields"][field] = "***"
                else:
                    config["fields"][field] = value
            else:
                # Campo vazio - retorna string vazia
                config["fields"][field] = ""
        
        return config
    
    def save_integration_config(self, platform: str, fields: Dict[str, str]) -> bool:
        """Salva configuração de uma integração"""
        try:
            for key, value in fields.items():
                if not value or not value.strip():
                    continue

                clean_value = value.strip()

                # Ignora valores mascarados (ex: "MTIz...xyz") — não sobrescreve com lixo
                if '...' in clean_value and len(clean_value) < 20:
                    continue

                self.write(key, clean_value)

            return True
        except Exception as e:
            print(f"Erro ao salvar configuração de {platform}: {e}")
            return False
