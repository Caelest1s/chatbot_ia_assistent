# chatbot_ia_assistent
Sistema de IA responsável por administrar, gerenciar atendimentos e solicitações e conduzir o usuário, de maneira simples e direta, para o agendamento do serviço ideal.


## About pyproject.toml
Na raiz do projeto execute: 
    pip install -e .
        ou 
    pip install -e .[test]

[project.optional-dependencies]:
A seção test inclui pytest e pytest-asyncio como dependências opcionais para testes podem ser instaladas com "pip install .[test]"
pip install .[test].

[tool.setuptools]:
Define os pacotes src.bot e src.utils, mapeando-os para os diretórios src/bot/ e src/utils/ .
Isto permite que imports absolutos como from src.bot.main import TelegramBot funcionem após a instalação do projeto.

para reverter pip install, pyproject.toml:
    pip unistall nome-do-projeto