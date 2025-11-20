# src/database/repositories/historico_repo.py
import json
from src.config.logger import setup_logger
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.historico_model import Historico

logger = setup_logger(__name__)

# Definimos o formato padrão que o LLM espera
DEFAULT_SYSTEM_ROLE = "system" 
DEFAULT_USER_ROLE = "user"

class HistoricoRepository:
    """
    Repositório para operações de persistência assíncronas relacionadas ao Histórico de Conversas.
    Não herda de BaseRepository pois a manipulação é específica (JSON).
    """
    def __init__(self, session: AsyncSession, default_msg: str):
        self.session = session
        self.resposta_sucinta = default_msg

    async def get_historico(self, user_id: int) -> list[dict[str, str]]:
        """
        Recupera o histórico de conversas do usuário. 
        Retorna a lista decodificada ou o histórico padrão.
        """
        default_history = [{
            "role": DEFAULT_SYSTEM_ROLE,
            "content": self.resposta_sucinta
        }]

        # Busca a coluna 'conversas' do Historico
        stmt = select(Historico.conversas).where(Historico.user_id == user_id)
        conversas_json = await self.session.scalar(stmt)

        if conversas_json:
            try:
                # Retorna o histórico decodificado, filtrando o campo 'timestamp'
                historico_completo: List[Dict[str, Any]] = json.loads(conversas_json)
                
                # Mapeia para o formato esperado pelo LLM (apenas role e content)
                return [{
                    "role": msg["role"],
                    "content": msg["content"]
                } for msg in historico_completo if "role" in msg and "content" in msg]

            except json.JSONDecodeError:
                logger.error(
                    f"Erro ao decodificar histórico JSON para o user_id {user_id}")
                return default_history
            
        return default_history

    async def salvar_mensagem_usuario(self, user_id: int, mensagem: str):
        """Salva a mensagem do usuário no histórico, atualizando o JSON existente (assíncrono)."""
        historico = await self.session.get(Historico, user_id)

        # Estrutura completa (inclui timestamp para fins de debug/tracking)
        mensagens_completas: list[dict[str, any]] = []

        if historico and historico.conversas:
            try:
                mensagens_completas = json.loads(historico.conversas)
            except json.JSONDecodeError:
                logger.warning(f"Histórico inválido encontrado para {user_id}. Reiniciando histórico.")

        mensagens_completas.append({
            "role": DEFAULT_USER_ROLE,
            "content": mensagem,
            "timestamp": datetime.now().isoformat()
        })

        # Converte para JSON
        conversas_json = json.dumps(mensagens_completas)

        # Atualiza ou Cria (Upsert)
        if historico:
            historico.conversas = conversas_json
            historico.created_at = datetime.now() # Atualiza o timestamp de modificação
        else:
            historico = Historico(
                user_id=user_id, conversas=conversas_json, created_at=datetime.now())
            self.session.add(historico)

        logger.info(f"Mensagem do usuário {user_id} preparada para commit.")
