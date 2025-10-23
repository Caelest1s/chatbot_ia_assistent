# src/bot/ai_agent.py

import os
from src.config import settings_loader # Mantenha a importação da sua config
from src.utils import MESSAGES # Mantenha a importação de mensagens
import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from src.bot.database_manager import DatabaseManager # Importação da sua classe de BD
from src.bot.ai_assistant import AIAssistant
from src.bot.bot_services import BotServices
from src.bot.bot_handlers import BotHandlers

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) 

class AIAgent:
    """Orquestrador principal do Chatbot: Inicializa e conecta os componentes."""
    def __init__(self):
        # 1. Carregar Configurações
        self.telegram_api_key = os.getenv('TELEGRAM_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not self.telegram_api_key or not self.openai_api_key:
            raise ValueError("Chaves de API (TELEGRAM ou OPENAI) não definidas.")

        # 2. Inicializar Gerenciadores de Dados e Serviços
        self.db_manager = DatabaseManager()
        self.db_manager.init_db()
        
        # 3. Inicializar a Lógica da IA
        self.ai_assistant = AIAssistant(
            openai_api_key=self.openai_api_key, 
            messages=MESSAGES, 
            db_manager=self.db_manager
        )
        
        # 4. Inicializar a Lógica de Negócios
        self.bot_services = BotServices(db_manager=self.db_manager)
        
        # 5. Inicializar os Handlers do Telegram (Injeta as dependências)
        self.bot_handlers = BotHandlers(
            db_manager=self.db_manager,
            ai_assistant=self.ai_assistant,
            bot_services=self.bot_services,
            messages=MESSAGES
        )

        # 6. Inicializar o Aplicativo do Telegram
        self.app = Application.builder().token(self.telegram_api_key).build()
        self._add_handlers()

    def _add_handlers(self):
        """Configura todos os handlers do Telegram a partir do BotHandlers."""
        # Handlers de Comando Padrão
        self.app.add_handler(CommandHandler('start', self.bot_handlers.start))
        self.app.add_handler(CommandHandler('reset', self.bot_handlers.reset))
        
        # Handlers de Comando Custom
        self.app.add_handler(CommandHandler('servicos', self.bot_handlers.servicos))
        self.app.add_handler(CommandHandler('agenda', self.bot_handlers.agenda))
        
        # Handler de Mensagem Principal (Roteamento)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_handlers.answer))

    def run(self):
        """Inicia o bot do Telegram."""
        logger.info("Iniciando o bot do Telegram...")
        self.app.run_polling()

if __name__ == '__main__':
    try:
        bot = AIAgent()
        bot.run()
    except Exception as e:
        logger.error(f"Erro de configuração ou execução: {e}")