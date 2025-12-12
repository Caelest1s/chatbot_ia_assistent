# src/services/dialog_flow_service.py
import logging
from typing import Optional, TYPE_CHECKING

from src.services.slot_processor_service import SlotProcessorService

# Use TYPE_CHECKING para evitar erro de importação circular no runtime
if TYPE_CHECKING:
    from src.bot.llm_service import LLMService
    from src.services.persistence_service import PersistenceService

try:
    from src.config.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

class DialogFlowService:
    """Orquestra o fluxo de conversação, extração de slots via LLM e a atualização do estado da sessão."""
    def __init__(self
                 , llm_service: 'LLMService'
                 , persistence_service: 'PersistenceService'
                 , slot_processor: SlotProcessorService):
        if not llm_service:
            raise ValueError("LLMService deve ser fornecido")
        
        self._llm_service = llm_service
        self._persistence_service = persistence_service
        self._slot_processor = slot_processor
        logger.info("DialogFlowService inicializado com sucesso.")

    # =========================================================
    # FLUXO PRINCIPAL: PROCESSAMENTO DA RESPOSTA LLM 
    # =========================================================
    async def process_llm_response(self, user_id: int, user_message: str) -> dict:
        """Orquestra o ciclo de extração e resolução de slots: Retorna os slots processados (dicionário)."""

        # 1. Recupera o estado atual da sessão
        session_state = await self._persistence_service.get_session_state(user_id)
        current_slots = session_state.get('slot_data', {})
        current_intent = session_state.get('current_intent', 'GENERICO')

        # 2. Chama a LLM para extração de slots
        llm_extracted_pydantic = await self._llm_service.extract_intent_and_data(
            user_message, current_slots
        )

        # 3. Pós-processamento e Resolução/Enriquecimento de Slots
        processed_slots: dict = await self._slot_processor.process_slots(llm_extracted_pydantic)

        # A intenção primária vem do LLM
        new_intent = llm_extracted_pydantic.intent or current_intent

        # 4. Salva o Novo Estado da Sessão (transacional) no banco de dados.
        await self._persistence_service.update_session_state(
            user_id=user_id
            , current_intent=new_intent
            , slot_data=processed_slots
        )

        return processed_slots
    
    # =========================================================
    # FUNÇÕES DE SLOT (DIÁLOGO)
    # =========================================================
    async def update_slot_data(self, user_id: int, slot_key: str, slot_value: any):
        """
        Busca o estado atual, aplica a modificação (mesclagem) e persiste.
        Toda a persistência é delegada ao PersistenceService.
        """

        # 1. Busca o estado atual para mesclagem no DataService (ou dependa do Repositório)
        # O SessionRepository.update_session_state já lida com a mesclagem de dicionários,
        # mas precisamos garantir que estamos enviando o dicionário de mesclagem correto.

        # 1. Recupera o estado atual para saber qual mesclagem aplicar
        current_state = await self._persistence_service.get_session_state(user_id)
        slot_data: dict = current_state.get('slot_data', {})

        # 2. Aplica a modificação específica no dicionário (Lógica do Diálogo)
        if slot_value is None:
            slot_data.pop(slot_key, None) # Remove a chave se o valor for None
            logger.debug(f"Slot '{slot_key}' removido para o usuário {user_id}")
        else:
            slot_data[slot_key] = slot_value # Atualiza a chave
            logger.debug(f"Slot '{slot_key}' atualizado para o usuário {user_id}")

        # 3. Persiste o dicionário mesclado no DB (delegando ao PersistenceService)
        await self._persistence_service.update_session_state(
            user_id=user_id,
            # Mantém a intenção atual
            current_intent=current_state.get('current_intent'),
            # Passa o dicionário mesclado
            slot_data=slot_data
        )
