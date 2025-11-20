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

# Variável global para manter a referência do bot configurado
TELEGRAM_APP: Application = None

# --- Lifespan: Gerencia startup e shutdown do bot ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # === STARTUP ===
    logger.info("Serviço iniciado: Carregando dependências e configurando Bot...")

    # 1. Cria a instância do Main e injeta dependências (ASSÍNCRONO)
    main_instance = await create_main_bot()

    # 2. Obtém a instância do Application configurada
    global TELEGRAM_APP
    TELEGRAM_APP = main_instance.get_telegram_app()

    logger.info("Iniciando bot com polling async (FastAPI Lifespan)...")

    # 3. Inicializa e Inicia o Polling
    await TELEGRAM_APP.initialize()
    await TELEGRAM_APP.start()

    # IMPORTANTE: Usamos o método do updater para rodar o polling dentro do loop do FastAPI
    # Isso é a forma estável de rodar o polling assíncrono (como você descobriu no teste).
    await TELEGRAM_APP.updater.start_polling(
        drop_pending_updates=True
    )

    logger.info("Bot e API FastAPI iniciados com sucesso!")

    try:
        yield # ← Aqui o FastAPI fica "vivo" e gerencia o loop
    finally:
        # === SHUTDOWN ===
        logger.info("Parando o bot e limpando recursos...")
        if TELEGRAM_APP.updater and TELEGRAM_APP.updater.running:
            await TELEGRAM_APP.updater.stop()
        await TELEGRAM_APP.stop()
        await TELEGRAM_APP.shutdown()
        logger.info("Shutdown completo.")

# --- FastAPI com lifespan ---
app = FastAPI(
    title="Chatbot IA Assistente",
    lifespan=lifespan
)

# --- Endpoint de Saúde ---
@app.get("/")
async def root():
    return {"status": "OK", "service": "Telegram Bot + FastAPI", "health": TELEGRAM_APP.running}

# O bot agora está totalmente isolado no Lifespan.
# Você pode adicionar rotas da API aqui (ex: para dashboard) sem interromper o bot.