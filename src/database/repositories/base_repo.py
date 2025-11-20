# src/database/repositories/base_repo.py

from typing import TypeVar, Generic
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from src.database.base import Base # Importa a Base que definimos

# Define um tipo genérico para os modelos (User, Agenda, etc.)
ModelType = TypeVar("ModelType", bound=Base) 

class BaseRepository(Generic[ModelType]):
    """Repositório base genérico para operações CRUD assíncronas"""
    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model

        # NOVO: Cache da coluna PK
        # self.model.__mapper__.primary_key[0] retorna o objeto Column (ex: UserSession.user_id)
        # Isso permite construir consultas WHERE dinamicamente.
        self._pk_column = self.model.__mapper__.primary_key[0]

    async def get_by_id(self, item_id: int) -> ModelType | None:
        """Obtém um item pelo ID."""
        stmt = select(self.model).where(self._pk_column == item_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def add(self, item: ModelType) -> ModelType:
        """Adiciona um novo item ao banco de dados."""
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item
    
    async def delete_by_id(self, item_id: int) -> bool:
        """Deleta um item pelo ID."""
        stmt = delete(self.model).where(self._pk_column == item_id)
        result = await self.session.execute(stmt)

        # NOTA: O DataService é quem deveria fazer o commit. Se este Repositório
        # for usado DENTRO de uma transação maior (como no DataService), remover o commit
        # daqui é mais seguro. Mas, se ele é usado standalone, o commit é necessário.
        # Vou manter o commit aqui, mas é um ponto de atenção.
        await self.session.commit()
        return result.rowcount > 0

    async def get_all(self) -> list[ModelType]:
        """Obtém todos os itens."""
        stmt = select(self.model)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    # O método update é geralmente implementado de forma específica no repositório filho.