# src/database/repositories/session_repo.py
from src.config.logger import setup_logger
from typing import Optional, Dict, Any

# Importações Assíncronas
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession # A chave para o modo assíncrono

# Importações da Base e dos Modelos
from src.database.repositories.base_repo import BaseRepository
from src.database.models.session_model import UserSession

logger = setup_logger(__name__)


class SessionRepository(BaseRepository[UserSession]):
    """
    Repositório para operações de persistência assíncronas relacionadas ao estado da sessão (UserSession).
    """
    def __init__ (self, session: AsyncSession):
        # Inicializa o BaseRepository com o modelo principal
        super().__init__(session, UserSession)
        # O self.session agora é a AsyncSession ativa

    async def get_session_state(self, user_id: int) -> Dict[str, Any]:
        """Recupera o estado atual da sessão (intenção e slots preenchidos) de forma assíncrona."""

        # 1. Busca o objeto UserSession pela Chave Primária (user_id)
        session_state_obj: Optional[UserSession] = await self.session.get(UserSession, user_id)

        if session_state_obj:
            return {
                "user_id": user_id,
                "current_intent": session_state_obj.current_intent,
                "slot_data": session_state_obj.slot_data  # JSONB retorna como dict
            }
        
        # Retorna o estado padrão se não houver sessão ativa
        return {"user_id": user_id, "current_intent": None, "slot_data": {}}

    async def update_session_state(self,
                             user_id: int,
                             current_intent: Optional[str] = None,
                             slot_data: Optional[Dict] = None):
        """Atualiza o estado da sessão (INSERT/UPDATE) de forma assíncrona."""

        if slot_data is None and current_intent is None:
            return  

        # 1. Busca o objeto existente (Assíncrono)
        session_obj: Optional[UserSession] = await self.session.get(UserSession, user_id)

        if session_obj:
            # UPDATE (Atualiza no Objeto)
            # Garantimos que estamos trabalhando com uma cópia do dict
            new_slot_data = session_obj.slot_data.copy() if session_obj.slot_data else {}

            # Mescla os slots
            if slot_data:
                for key, value in slot_data.items():
                    if value is not None:
                        new_slot_data[key] = value

            if current_intent is not None:
                session_obj.current_intent = current_intent

            session_obj.slot_data = new_slot_data

            # O SQLAlchemy monitora as mudanças no objeto e as enviará no commit

        else:
            # INSERT (Cria o Objeto)
            new_slot_data = {}
            if slot_data:
                for key, value in slot_data.items():
                    if value is not None:
                        new_slot_data[key] = value

            session_obj = UserSession(
                user_id=user_id,
                current_intent=current_intent,
                slot_data=new_slot_data
            )
            self.session.add(session_obj)

        logger.info(f"Estado da sessão {user_id} preparado para commit.")
        return session_obj

    async def delete_session_by_id(self, user_id: int):
        """Deleta o estado da sessão de um usuário (exclusão por PK)."""
        session_obj = await self.session.get(UserSession, user_id)
        if session_obj:
            await self.session.delete(session_obj)
            # O commit será feito pelo DataService
