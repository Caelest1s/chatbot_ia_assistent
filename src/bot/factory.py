# # src/bot/factory.py
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from src.database.base import init_db
from src.database.session import engine, AsyncSessionLocal
from src.bot.main import Main
from src.utils.system_message import MESSAGES

# Importações dos Módulos de Serviço (A Main depende deles)
from src.services.data_service import DataService
from src.bot.history_manager import HistoryManager
from src.bot.llm_config import LLMConfig
from src.bot.llm_service import LLMService
from src.services.appointment_validator import AppointmentValidator
from src.services.appointment_service import AppointmentService
from src.services.service_finder import ServiceFinder
from src.bot.slot_filling_manager import SlotFillingManager
from src.bot.telegram_handlers import TelegramHandlers

from src.config.logger import setup_logger
logger = setup_logger(__name__)

async def create_main_bot() -> Main:
    """
    Função Factory Assíncrona para inicializar todas as dependências 
    e criar a instância da classe Main.
    """

    # --- 1. Inicialização da Infraestrutura ---
   
    # Executa o init_db (criação de tabelas) antes de tudo
    logger.info("Iniciando sincronização de tabelas (init_db)...")
    await init_db(engine)
    logger.info("Sincronização de tabelas concluída.")

    # --- 2. Preparação das Dependências de API ---
    telegram_api_key = os.getenv('TELEGRAM_API_KEY')
    openai_api_key = os.getenv('OPENAI_API_KEY')

    if not telegram_api_key or not openai_api_key:
        raise ValueError("Chaves de API (TELEGRAM ou OPENAI) não definidas.")
    
    # --- 3. Inicialização de Serviços e Componentes Assíncronos ---

    # 3.1. Serviços Base
    data_service = DataService(session_maker=AsyncSessionLocal)
    services_list = await data_service.get_available_services_names()

    # 3.2 Componentes LLM e Histórico
    history_manager = HistoryManager(
        system_message_content=MESSAGES['RESPOSTA_SUCINTA']
    )
    llm_config = LLMConfig(
        openai_api_key=openai_api_key,
        services_list=services_list
    )
    llm_service = LLMService(
        llm_config=llm_config,
        history_manager=history_manager,
        data_service=data_service
    )

    # 3.3 Lógica de Negócios
    validator = AppointmentValidator()
    appointment_service = AppointmentService(
        data_service=data_service,
        validator=validator
    )
    service_finder = ServiceFinder(
        data_service=data_service
    )

    # 3.4 Gerenciador de Fluxo
    slot_filling_manager = SlotFillingManager(
        data_service=data_service,
        appointment_service=appointment_service
    )

    # 3.5 Handlers do Telegram (Instância de classe com métodos roteados)
    bot_handlers = TelegramHandlers(
        data_service=data_service,
        llm_service=llm_service,
        service_finder=service_finder,
        slot_filling_manager=slot_filling_manager
    )

    # --- 4. Criação e Retorno da Instância Main ---

    # A Main agora recebe apenas as dependências já construídas
    main_instance = Main(
        telegram_api_key=telegram_api_key,
        bot_handlers=bot_handlers
    )

    # O start_command e contact_handler precisam desses serviços no `bot_data`.
    telegram_app = main_instance.get_telegram_app()

    # Injeta DataService e LLMService, que são usados no start_command
    telegram_app.bot_data['data_service'] = data_service
    telegram_app.bot_data['llm_service'] = llm_service

    # O contact_handler (receive_contact_info) também precisa de data_service
    # (data_service já está injetado acima, mas vale o lembrete)

    logger.info("Dependências injetadas no Application.bot_data.")

    return main_instance