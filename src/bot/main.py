# src/bot/ai_agent.py

import os
import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Importações de Configurações e Utilitários
# Nota: 'settings_loader' foi mantido, mas as chaves de API estão lendo de os.getenv
from src.utils.system_message import MESSAGES
from src.utils.constants import REQUIRED_SLOTS, BUSINESS_HOURS # Importe se for necessário aqui

# Importações dos Gerenciadores de Baixo Nível
from src.bot.database_manager import DatabaseManager # Mantido
from src.bot.history_manager import HistoryManager     # NOVO
from src.bot.llm_config import LLMConfig             # NOVO
from src.bot.llm_service import LLMService           # NOVO

# Importações dos Módulos de Serviço (Lógica de Negócio)
from src.services.appointment_validator import AppointmentValidator # NOVO
from src.services.appointment_service import AppointmentService     # NOVO
from src.services.service_finder import ServiceFinder             # NOVO

# Importações dos Módulos de Fluxo e Roteamento
from src.bot.slot_filling_manager import SlotFillingManager # NOVO
from src.bot.telegram_handlers import TelegramHandlers      # Refatorado (antiga BotHandlers)

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) 

class Main:
    """Orquestrador principal do Chatbot: Inicializa e conecta os componentes."""
    def __init__(self):
        # 1. Carregar Configurações e APIs
        self.telegram_api_key = os.getenv('TELEGRAM_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not self.telegram_api_key or not self.openai_api_key:
            raise ValueError("Chaves de API (TELEGRAM ou OPENAI) não definidas.")

        # 2. Inicializar o Gerenciador de Banco de Dados
        self.db_manager = DatabaseManager()
        self.db_manager.init_db()
        
        # 3. Inicializar Componentes de LLM e Histórico
        services_list = self.db_manager.get_available_services_names() # Contexto para o LLM
        
        self.history_manager = HistoryManager(
            system_message_content=MESSAGES['RESPOSTA_SUCINTA']
        )
        self.llm_config = LLMConfig(
            openai_api_key=self.openai_api_key, 
            services_list=services_list
        )
        self.llm_service = LLMService(
            llm_config=self.llm_config, 
            history_manager=self.history_manager, 
            db_manager=self.db_manager
        )
        
        # 4. Inicializar a Lógica de Negócios (Serviços e Validações)
        self.validator = AppointmentValidator()
        self.appointment_service = AppointmentService(
            db_manager=self.db_manager,
            validator=self.validator
        )
        self.service_finder = ServiceFinder(
            db_manager=self.db_manager
        )
        
        # 5. Inicializar o Gerenciador de Fluxo (Slot Filling)
        self.slot_filling_manager = SlotFillingManager(
            db_manager=self.db_manager,
            appointment_service=self.appointment_service
        )
        
        # 6. Inicializar os Handlers do Telegram (Injeta as dependências)
        self.bot_handlers = TelegramHandlers(
            db_manager=self.db_manager,
            llm_service=self.llm_service,
            service_finder=self.service_finder,
            slot_filling_manager=self.slot_filling_manager
        )

        # 7. Inicializar o Aplicativo do Telegram
        self.app = Application.builder().token(self.telegram_api_key).build()
        self._add_handlers()

    def _add_handlers(self):
        """Configura todos os handlers do Telegram a partir do TelegramHandlers."""
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