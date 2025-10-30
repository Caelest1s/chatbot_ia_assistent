import logging
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langchain_community.chat_message_histories import ChatMessageHistory
from datetime import datetime

logger = logging.getLogger(__name__)

class HistoryManager:
    """Gerencia o histórico de conversas em memória, aplicando janela deslizante."""
    def __init__(self, system_message_content: str, max_length: int = 10):
        # Dicionário para armazenar o histórico em memória: {user_id: ChatMessageHistory}
        self.historico_por_usuario = {}
        self.system_message = SystemMessage(content=system_message_content)
        self.max_historico_length = max_length

    def _get_or_create_history(self, user_id: int) -> ChatMessageHistory:
        """Recupera ou inicializa o histórico de mensagens para o usuário."""
        if user_id not in self.historico_por_usuario:
            self.historico_por_usuario[user_id] = ChatMessageHistory()
            self.historico_por_usuario[user_id].add_message(self.system_message)
        return self.historico_por_usuario[user_id]
    
    def reset_history(self, user_id: int):
        """Reinicia o histórico de conversação do usuário."""
        self.historico_por_usuario[user_id] = ChatMessageHistory()
        self.historico_por_usuario[user_id].add_message(self.system_message)

    def add_message(self, user_id: int, message: str, is_user: bool = True):
        """Adiciona uma mensagem (usuário ou IA) ao histórico e aplica a janela deslizante."""
        historico = self._get_or_create_history(user_id)

        metadata = {"timestamp": datetime.now().isoformat()}

        if is_user:
            historico.add_message(HumanMessage(content=message, metadata=metadata))
        else:
            historico.add_message(AIMessage(content=message, metadata=metadata))

        # Limita o histórico com janela deslizante (mantendo a SystemMessage na 1ª posição)
        if len(historico.messages) > self.max_historico_length:
            historico.messages = [historico.messages[0]] + historico.messages[- (self.max_historico_length -1):]

    def get_prompt(self, user_id: int):
        """Retorna o prompt completo (incluindo histórico) para a LLM."""
        return self._get_or_create_history(user_id).messages