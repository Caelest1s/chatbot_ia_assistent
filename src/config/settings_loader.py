from dotenv import load_dotenv
from pathlib import Path
import os

def load_settings():
    # Caminho absoluto até o diretório base do projeto, do arquivo .env

    base_dir = Path(__file__).resolve().parent.parent.parent  # volta 2 níveis até chatbot_ia_assistent/
    env_path = base_dir / "config" / ".env"

    # Carrega variáveis de ambiente
    load_dotenv(dotenv_path=env_path, override=True)

    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
        print(f"Arquivo .env carregado de: {env_path}")
    else:
        print(f"Arquivo .env não encontrado verifique o caminho em settings_loader")

# Carregar automaticamente quando importar o pacote config
load_settings()