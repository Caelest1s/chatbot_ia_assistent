# import logging
from typing import TYPE_CHECKING
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.history_manager import HistoryManager
from src.bot.database_manager import DatabaseManager
from src.schemas.slot_extraction_schema import SlotExtraction
from src.bot.llm_config import LLMConfig
from src.utils.system_message import MESSAGES
from src.utils.logger import setup_logger

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage # Apenas para typing

logger = setup_logger(__name__)

class LLMService: # Antiga ai_assistance.py
    """Gerencia a interação direta com a LLM (Extração e Resposta Genérica)."""
    def __init__(self, llm_config: LLMConfig, history_manager: HistoryManager, db_manager: DatabaseManager):
        self.llm = llm_config.llm
        self.extraction_prompt = llm_config.extraction_prompt
        self.output_parser = llm_config.output_parser
        self.history_manager = history_manager
        self.db_manager = db_manager
        self.search_prompt = llm_config.search_prompt # Mantido se for útil

    def extract_intent_and_data(self, text: str) -> SlotExtraction:
        """Chama a LLM para extrair a intenção e dados estruturados."""
        try:
            prompt_extraction: list['BaseMessage'] = self.extraction_prompt.format_messages(texto_usuario=text)
            extraction_response = self.llm.invoke(prompt_extraction)
            logger.info(f"Resposta bruta da extração: '{extraction_response.content}'")

            dados_estruturados: SlotExtraction = self.output_parser.parse(extraction_response.content)
            logger.info(f"Dados extraídos (JSON/Pydantic): {dados_estruturados.model_dump()}")
            return dados_estruturados
        except Exception as e:
            logger.error(f"Erro ao extrair JSON ou parsear: {e}. Retornando SlotExtraction GENERICO.")
            # Se a extração falhar (como intent=null), retorna GENERICO,
            # e os slots ficam nulos (data=null, hora=null), permitindo que o SlotFiller continue.
            return SlotExtraction(intent='GENERICO')
        
    async def handle_generico(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Chama a LLM para perguntas genéricas com histórico."""
        user_id = update.effective_user.id
        question = update.message.text
        try:
            # 1. Adiciona a pergunta do usuário ao histórico
            self.history_manager.add_message(user_id, question, is_user=True)
            self.db_manager.salvar_mensagem_usuario(user_id, question)

            # 2. Obtém o prompt completo (com histórico e SystemMessage)
            prompt = self.history_manager.get_prompt(user_id)
            logger.info(f"Prompt enviado ao LLM (Genérico) para user_id {user_id}")

            # 3. Invoca a LLM
            response = self.llm.invoke(prompt)
            resposta = response.content.strip()

            # 4. Adiciona a resposta da IA ao histórico
            self.history_manager.add_message(user_id, resposta, is_user=False)
            await update.message.reply_text(resposta)
            return resposta
        
        except Exception as e:
            logger.error(f"Erro ao chamar a API da Inteligência Artificial em handle_generico: {e}")
            nome = self.db_manager.get_nome_usuario(user_id) or update.effective_user.first_name
            await update.message.reply_text(MESSAGES['GENERAL_ERROR'].format(nome=nome))
            return False