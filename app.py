import os
from src.bot.main import Main
import logging
from src.config import settings_loader
from src.utils.logger import setup_logger
logger = setup_logger(__name__)

if __name__ == '__main__':
    try:
        logger.info("Serviço iniciado!")
        bot = Main()
        bot.run()
    except Exception as e:
        logging.error(f"Erro de configuração: {e}")