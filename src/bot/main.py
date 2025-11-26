# # src/bot/main.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Importações dos Módulos de Fluxo e Roteamento
from src.bot.telegram_handlers import TelegramHandlers

from src.platform.telegram.handlers.start_handlers import start_command
from src.platform.telegram.handlers.contact_handler import receive_contact_info

import logging
logger = logging.getLogger(__name__)

class Main:
    """
    Orquestrador principal do Chatbot. 
    Apenas configura e executa o bot do Telegram com dependências injetadas.
    """

    # O __init__ agora recebe as dependências já construídas do Factory
    def __init__(self,  telegram_app: Application, bot_handlers: TelegramHandlers):
        # 1. Inicializar os Handlers (Recebidos como DI)
        self.bot_handlers = bot_handlers

        # 2. Inicializar o Aplicativo do Telegram
        self.app = telegram_app # <-- AGORA RECEBE A INSTÂNCIA PRONTA DO FACTORY
        self._add_handlers()

    def _add_handlers(self):
        """Configura todos os handlers do Telegram a partir do TelegramHandlers"""

        # 1. 📞 Handler de Coleta de Contato (DEVE VIR PRIMEIRO)
        # Filtra MENSAGENS que contêm um OBJETO de contato (filters.CONTACT).
        self.app.add_handler(MessageHandler(filters.CONTACT, receive_contact_info))

        # 2. 🚀 Handler de Comando START (MODULARIZADO)
        # Substituímos self.bot_handlers.start pelo módulo importado `start_command`.
        self.app.add_handler(CommandHandler('start', start_command))

        # 3. Handlers de Comando Padrão (Mantidos na classe central)
        self.app.add_handler(CommandHandler('reset', self.bot_handlers.reset))

        # Handlers de Comando Custom
        self.app.add_handler(CommandHandler('servicos', self.bot_handlers.servicos))
        self.app.add_handler(CommandHandler('agenda', self.bot_handlers.agenda))

        # Handler de Mensagem Principal (Roteamento)
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_handlers.answer))

    # 🚨 Retorna a instância configurada do Application
    def get_telegram_app(self) -> Application:
        """Retorna a instância do Application Builder configurada com os handlers."""
        return self.app
    
    def run(self):
        """Método para iniciar o polling do bot."""
        logger.info("Iniciando o bot...")
        self.app.run_polling()