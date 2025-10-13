import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env localizado na pasta config (caminho absoluto)
ENV_PATH = os.path.join(os.path.dirname(__file__), '../../config/.env')
load_dotenv(dotenv_path=os.path.abspath(ENV_PATH))

# Carregar o .env
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH)
    print(f"Arquivo .env carregado de: {ENV_PATH}")
else:
    print(f"Arquivo .env não encontrado verifique o caminho em settings_loader")