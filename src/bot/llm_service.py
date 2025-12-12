# src/bot/llm_service.ppy

from typing import TYPE_CHECKING
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.history_manager import HistoryManager
from src.schemas.slot_extraction_schema import SlotExtraction
from src.bot.llm_config import LLMConfig
from src.utils.system_message import MESSAGES
from src.config.logger import setup_logger

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage  # Apenas para typing
    from src.services.persistence_service import PersistenceService

logger = setup_logger(__name__)


class LLMService:  # Antiga ai_assistance.py
    """Gerencia a interação direta com a LLM (Extração e Resposta Genérica)."""

    def __init__(self, llm_config: LLMConfig, history_manager: HistoryManager, persistence_service: 'PersistenceService'):
        self.llm_config = llm_config
        self.extraction_prompt = llm_config.extraction_prompt
        self.output_parser = llm_config.output_parser
        self.history_manager = history_manager
        self.data_service = persistence_service
        self.search_prompt = llm_config.search_prompt  # Mantido se for útil

    async def extract_intent_and_data(self, text: str, current_slots: dict | None = None) -> SlotExtraction:
        """
        Extrai intenção e slots com MEMÓRIA dos slots já preenchidos.
        current_slots = dicionário da sessão.
        """
        try:
            # 1. Obter a Chain/Runnable de Extração, injetando a memória (current_slots)
            # O LLMConfig.get_extraction_chain já cuida da serialização JSON e do prompt.
            extraction_chain = self.llm_config.get_extraction_chain(current_slots or {})

            # 2. Invocar a Chain com o texto atual do usuário
            # A chave de entrada aqui é a que foi definida na chain formatada (texto_usuario)
            dados_estruturados = await extraction_chain.ainvoke({"texto_usuario": text})
            logger.info(f"Dados extraídos (Pydantic): {dados_estruturados.model_dump()}")

            # O resultado da chain já é o objeto SlotExtraction parseado
            return dados_estruturados
        except Exception as e:
            logger.error(f"Erro ao extrair slots: {e}", exc_info=True)
            # Se a extração falhar (como intent=null), retorna GENERICO,
            # e os slots ficam nulos (data=null, hora=null), permitindo que o SlotFiller continue.
            # Retorna GENERICO para que o bot possa tratar o erro ou pedir reformulação
            return SlotExtraction(intent="GENERICO")

    async def handle_generico(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Chama a LLM para perguntas genéricas com histórico."""
        user_id = update.effective_user.id
        question = update.message.text
        resposta_do_bot = False

        # Define o nome de fallback caso a busca no DB falhe
        nome = update._effective_user.first_name

        try:
            # 1. Adiciona a pergunta do usuário ao histórico (in-memory)
            self.history_manager.add_message(user_id, question, is_user=True)

            # **Salva a mensagem do usuário no DB ANTES da chamada do LLM.**
            # Se a LLM falhar, a mensagem do usuário já está registrada.
            # Usa o novo método com a origem 'user'.
            await self.data_service.salvar_mensagem(user_id, question, origem='user')

            # 2. Obtém o prompt completo (com histórico e SystemMessage)
            prompt = self.history_manager.get_prompt(user_id)
            logger.info(f"Prompt enviado ao LLM (Genérico) para user_id {user_id}")

            # 3. Invoca a LLM
            response = self.llm_config.llm.invoke(prompt)
            resposta = response.content.strip()
            resposta_do_bot = resposta # Guarda a resposta para salvar

            # 4. Adiciona a resposta da IA ao histórico
            self.history_manager.add_message(user_id, resposta, is_user=False)
            # **Salva a resposta do bot no DB.**
            await self.data_service.salvar_mensagem(user_id, resposta, origem='bot')

            await update.message.reply_text(resposta)
            return True # Retorna True para indicar sucesso/tratamento ANTES resposta

        except Exception as e:
            logger.error(f"Erro na API da IA em handle_generico para user_id {user_id}: {e}", exc_info=True)
            
            db_nome = await self.data_service.get_nome_usuario(user_id)
            if db_nome:
                nome = db_nome

            # Se a resposta do bot foi gerada, mas o salvamento falhou, 
            # o bot ainda deve tentar enviar a mensagem de erro (ou a resposta se o erro foi no salvamento do bot).
            await update.message.reply_text(MESSAGES['GENERAL_ERROR'].format(nome=nome))
            return False
