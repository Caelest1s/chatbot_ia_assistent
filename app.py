# app.py
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI
from telegram.ext import Application

from src.bot.factory import create_main_bot
from src.config.logger import setup_logger

# --- Setup e Logs ---
load_dotenv('./config/.env')
logger = setup_logger(__name__)

# --- Lifespan: Gerencia startup e shutdown do bot ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === STARTUP ===
    logger.info("Serviço iniciado: Carregando dependências e configurando Bot...")

    # 1. Cria a instância do Main e injeta dependências (ASSÍNCRONO)
    main_instance = await create_main_bot()

    # 2. Obtém a instância do Application configurada
    telegram_app: Application = main_instance.get_telegram_app()
    app.state.telegram_app = telegram_app
    logger.info("Iniciando bot com polling async (FastAPI Lifespan)...")

    # 3. Inicializa e Inicia o Polling
    bot_app: Application = app.state.telegram_app
    await bot_app.initialize()
    await bot_app.start()

    # IMPORTANTE: Usamos o método do updater para rodar o polling dentro do loop do FastAPI
    # Isso é a forma estável de rodar o polling assíncrono (como você descobriu no teste).
    await bot_app.updater.start_polling(
        drop_pending_updates=True
    )

    logger.info("Bot e API FastAPI iniciados com sucesso!")

    try:
        yield # ← Aqui o FastAPI fica "vivo" e gerencia o loop
    finally:
        # === SHUTDOWN ===
        logger.info("Parando o bot e limpando recursos...")

        bot_app_to_stop: Application | None = getattr(app.state, 'telegram_app', None)

        if bot_app_to_stop:
            # O autocompletar funciona melhor com a variável local bot_app_to_stop
            # Verifica e para o updater
            if bot_app.updater and bot_app.updater.running:
                await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
        logger.info("Shutdown completo.")

# --- FastAPI com lifespan ---
app = FastAPI(
    title="Chatbot IA Assistente",
    lifespan=lifespan
)

# --- Endpoint de Saúde ---
@app.get("/")
async def root():
    # 1. Acessa o objeto Application do estado. Ele será do tipo Application ou None.
    # O getattr evita AttributeError se o 'telegram_app' não existir no estado.
    bot_app: Application | None = getattr(app.state, 'telegram_app', None)

    # 2. Verifica o status 'running' do objeto Application
    # Não há needade de 'app_running.running', apenas 'bot_app.running'
    status = bot_app.running if bot_app else False

    return {"status": "OK", "service": "Telegram Bot + FastAPI", "health": status}

# O bot agora está totalmente isolado no Lifespan.
# Você pode adicionar rotas da API aqui (ex: para dashboard) sem interromper o bot.