import os
from src.bot.ai_agent import AIAgent
import logging
from src.config import settings_loader

if __name__ == '__main__':
    try:
        bot = AIAgent()
        bot.run()
    except Exception as e:
        logging.error(f"Erro de configuração: {e}")