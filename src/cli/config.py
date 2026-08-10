"""
MoltyClaw CLI — Config (set/get .env)
"""
import os
import sys
from . import console, MOLTY_DIR


def cli_config():
    if len(sys.argv) >= 4 and sys.argv[2].lower() == "set":
        from . import config_set
        config_set(sys.argv[3], sys.argv[4])
        sys.exit(0)
    elif len(sys.argv) >= 4 and sys.argv[2].lower() == "get":
        from . import config_get
        config_get(sys.argv[3])
        sys.exit(0)
    else:
        console.print("[bold red]Uso: moltyclaw config set <CHAVE> <VALOR> ou moltyclaw config get <CHAVE>[/bold red]")
        sys.exit(1)
