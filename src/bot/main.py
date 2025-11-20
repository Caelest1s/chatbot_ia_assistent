# # src/bot/main.py
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Importações dos Módulos de Fluxo e Roteamento
from src.bot.telegram_handlers import TelegramHandlers

import logging
logger = logging.getLogger(__name__)

class Main:
    """
    Orquestrador principal do Chatbot. 
    Apenas configura e executa o bot do Telegram com dependências injetadas.
    """

    # O __init__ agora recebe as dependências já construídas do Factory
    def __init__(self,  telegram_api_key: str, bot_handlers: TelegramHandlers):
        # 1. Inicializar os Handlers (Recebidos como DI)
        self.bot_handlers = bot_handlers

        # 2. Inicializar o Aplicativo do Telegram
        self.app = Application.builder().token(telegram_api_key).build()
        self._add_handlers()

    def _add_handlers(self):
        """Configura todos os handlers do Telegram a partir do TelegramHandlers"""
        # Handlers de Comando Padrão
        self.app.add_handler(CommandHandler('start', self.bot_handlers.start))
        self.app.add_handler(CommandHandler('reset', self.bot_handlers.reset))

        # Handlers de Comando Custom
        self.app.add_handler(CommandHandler(
            'servicos', self.bot_handlers.servicos))
        self.app.add_handler(CommandHandler(
            'agenda', self.bot_handlers.agenda))

        # Handler de Mensagem Principal (Roteamento)
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.bot_handlers.answer))

    # 🚨 Retorna a instância configurada do Application
    def get_telegram_app(self) -> Application:
        """Retorna a instância do Application Builder configurada com os handlers."""
        return self.app