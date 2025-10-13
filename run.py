from dotenv import load_dotenv
import os
from src.bot.main import TelegramBot
import logging

load_dotenv(os.path.join(os.path.dirname(__file__), 'config/.env'))

if __name__ == '__main__':
    try:
        bot = TelegramBot()
        bot.run()
    except Exception as e:
        logging.error(f"Erro de configuração: {e}")