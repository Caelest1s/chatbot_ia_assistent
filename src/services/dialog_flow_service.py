# src/services/dialog_flow_service.py
import logging
from typing import Optional, TYPE_CHECKING

from src.services.slot_processor_service import SlotProcessorService
from src.schemas.slot_extraction_schema import SlotExtraction
from src.bot.slot_filling_manager import SlotFillingManager

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
    """Orquestra o fluxo de conversação, extração de slots via LLM e a atualização do estado da sessão e persistência das msgs."""
    def __init__(self
                 , llm_service: 'LLMService'
                 , persistence_service: 'PersistenceService'
                 , slot_processor_service: SlotProcessorService
                 , slot_filling_manager: SlotFillingManager):
        if not llm_service:
            raise ValueError("LLMService deve ser fornecido")
        
        self._llm_service = llm_service
        self._persistence_service = persistence_service
        self._slot_processor_service = slot_processor_service
        self._slot_filling_manager = slot_filling_manager
        logger.info("DialogFlowService inicializado com sucesso.")

    # =========================================================
    # FLUXO PRINCIPAL: PROCESSAMENTO DA RESPOSTA LLM 
    # =========================================================
    async def process_llm_response(self, user_id: int, user_message: str) -> dict:
        """
        Orquestra o ciclo completo de uma mensagem:
        1. Salva pergunta -> 2. Interpreta IA -> 3. Processa/Merge Slots -> 4. Salva Resposta/Estado.
        """

        # 1. PERSISTÊNCIA DA ENTRADA ---
        # Salvamos no BD e no HistoryManager (Memória RAM do LLM)
        await self._persistence_service.salvar_mensagem(user_id, user_message, origem='user')
        self._llm_service.history_manager.add_message(user_id, user_message, is_user=True)

        # Recupera o estado atual da sessão para MERGE
        session_state = await self._persistence_service.get_session_state(user_id)
        existing_slots = session_state.get('slot_data', {}) or {}

        current_intent = session_state.get('current_intent') # Pode ser None ou 'AGENDAR'

        # =========================================================
        # DECISÃO: Usar missing_slot apenas se já estamos em agendamento
        # =========================================================
        if current_intent == 'AGENDAR':
            # Identifica o próximo slot faltante
            missing_slot = await self._slot_filling_manager.get_next_missing_slot(user_id)
            if missing_slot == "NENHUM":
                missing_slot = None # Evita string "NENHUM" vazando
        else:
            missing_slot = None # Força uso do prompt genérico

        # 2. Chama a LLM para extração de slots
        llm_result = await self._llm_service.process_user_input(
            user_id=user_id
            , text=user_message
            , missing_slot=missing_slot
        )

        # 3. Tratamento do resultado e MERGE (CASO AGENDAMENTO)
        if isinstance(llm_result, SlotExtraction):
            # Enriquecimento (Datas, IDs, etc)
            # Pós-processamento e Resolução (Datas, IDs de serviço, etc)
            new_slots = await self._slot_processor_service.process_slots(llm_result)

            # LÓGICA DE MERGE: Mantém o que já existia e atualiza com o novo. Isso evita que informar a "hora" apague o "serviço" já salvo.
            updated_slots = {**existing_slots, **new_slots}

            new_intent = 'AGENDAR'
            # Persiste o novo estado (Intenção + Slots Mesclados)
            await self._persistence_service.update_session_state(
                user_id
                , current_intent=new_intent
                , slot_data=updated_slots
            )

            logger.info(f"Agendamento em progresso para {user_id}. Slots preenchidos: {list(updated_slots.keys())}")
            return updated_slots
        
        # 4. TRATAMENTO (CASO CONVERSA GERAL)
        elif isinstance(llm_result, str):
            # Salva a resposta do bot no BD e no HistoryManager
            await self._persistence_service.salvar_mensagem(user_id, llm_result, origem='bot')
            self._llm_service.history_manager.add_message(user_id, llm_result, is_user=False)

            # Se não for agendamento, podemos manter a intenção anterior ou resetar
            # optamos por manter para não quebrar fluxos em andamento
            return llm_result
        
        return "Desculpe, não consegui entender. Podemos recomeçar?"

    # =========================================================
    # FUNÇÕES DE SLOT (DIÁLOGO)
    # =========================================================
    async def update_slot_data(self, user_id: int, slot_key: str, slot_value: any):
        """Busca o estado atual, aplica a modificação (mesclagem) e persiste."""

        # 1. Recupera o estado atual para saber qual mesclagem aplicar
        current_state = await self._persistence_service.get_session_state(user_id)
        slot_data: dict = current_state.get('slot_data', {}) or {}

        # 2. Aplica a modificação específica no dicionário (Lógica do Diálogo)
        if slot_value is None:
            slot_data.pop(slot_key, None) # Remove a chave se o valor == None
        else:
            slot_data[slot_key] = slot_value # Atualiza a chave

        # 3. Persiste o dicionário mesclado no DB (delegando ao PersistenceService)
        await self._persistence_service.update_session_state(
            user_id=user_id,
            current_intent=current_state.get('current_intent'),
            slot_data=slot_data
        )
