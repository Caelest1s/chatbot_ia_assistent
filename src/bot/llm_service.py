# src/bot/llm_service.ppy

from typing import TYPE_CHECKING, Union

from src.bot.history_manager import HistoryManager
from src.schemas.slot_extraction_schema import SlotExtraction
from src.bot.llm_config import LLMConfig
from src.config.logger import setup_logger

from src.utils.constants import BUSINESS_DOMAIN, BUSINESS_NAME, REQUIRED_SLOTS

if TYPE_CHECKING:
    from src.services.persistence_service import PersistenceService

logger = setup_logger(__name__)

class LLMService: 
    """Interface entre o sistema de chat e a inteligência artificial (LangChain)."""

    def __init__(self, llm_config: LLMConfig, history_manager: HistoryManager, persistence_service: 'PersistenceService'):
        self.llm_config = llm_config
        self.history_manager = history_manager
        self.data_service = persistence_service

    async def process_user_input(self, user_id: int, text: str) -> Union[SlotExtraction, str]:
        """Entrada única para qualquer mensagem do usuário. Orquestrador decide se extrai slots ou se responde uma dúvida."""
        try:

            # 1. Obtém o Orquestrador (Cérebro)
            orchestrator = self.llm_config.create_bot_orchestrator(
                reset_fn=self.data_service.clear_session_state
                , user_id=user_id
            )

            # === CÁLCULO SEGURO DO MISSING_SLOT ===
            session_state = await self.data_service.get_session_state(user_id)

            # Só entra no modo focado se:
            # 1. Existe estado de sessão
            # 2. A intenção atual é explicitamente 'AGENDAR'
            # 3. Há slots faltando
            if session_state and session_state.get('current_intent') == 'AGENDAR' and 'slot_data' in session_state:
                slot_data = session_state.get('slot_data', {})
                missing_slots = [s for s in REQUIRED_SLOTS if not slot_data.get(s)]
                next_missing_slot = missing_slots[0] if missing_slots else "NENHUM"
                logger.debug(f"Modo FOCO ativado - próximo slot: {next_missing_slot}")
            else:
                next_missing_slot = "NENHUM"
                logger.debug("Modo GERAL ativado - sem agendamento em andamento")

            # 2. Invoca a inteligência, o orquestrador decide se chama a Chain de Extração, Tool ou Conversa Geral
            response = await orchestrator.ainvoke({
                "texto_usuario": text
                , "tipo_negocio": BUSINESS_DOMAIN
                , "nome_negocio": BUSINESS_NAME
                , "missing_slot": next_missing_slot
            })

            # Se a resposta for uma mensagem do LangChain (AIMessage, HumanMessage, etc)
            if hasattr(response, 'content') and not isinstance(response, str):
                response = response.content
            # Se a resposta for um dicionário (comum no LangChain Orquestrador)
            if isinstance(response, dict):
                # Tenta pegar o conteúdo da resposta, se não existir, pega o objeto todo
                response = response.get('output') or response.get('answer') or str(response)
            
            # 3. Se a resposta for uma string (Conversa Geral)
            # Caso A: Conversa Geral
            if isinstance(response, str):
                if not response.strip():
                    return "Desculpe, não consegui formular uma resposta."
                return response
            
            # 5. Se for um objeto SlotExtraction (Agendamento)
            # Caso B: Objeto de Extração
            if isinstance(response, SlotExtraction):
                logger.info(f"Slots detectados para {user_id}: {response.model_dump()}")
                return response
            
            # Fallback de segurança
            logger.warning(f"Resposta inesperada. Tipo: {type(response)} Valor {response}")
            return "Desculpe, tive um problema ao interpretar a resposta."
        
        except Exception as e:
            logger.error(f"Erro no processamento do Orquestrador para {user_id}: {e}", exc_info=True)
            return "Tive um problema técnico. Podemos tentar novamente em um instante?"
        
    # Caso você ainda precise de uma extração pura (sem passar pelo orquestrador completo)
    async def extract_only(self, user_id: int, text: str) -> SlotExtraction:
        """Uso específico para quando você tem certeza que quer apenas extrair dados."""
        filler = self.llm_config.get_filler_chain_for_user(user_id) # Se criar este helper na llm_config
        return await filler.ainvoke({"texto_usuario": text})
