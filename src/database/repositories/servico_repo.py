# src/database/repositories/servico_repo.py
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.repositories.base_repo import BaseRepository
from src.database.models.servico_model import Servico

class ServicoRepository(BaseRepository[Servico]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Servico)

    async def get_by_id(self, servico_id: int) -> Optional[Servico]:
        return await self.session.get(Servico, servico_id)
    
    async def get_by_name(self, nome: str) -> Optional[Servico]:
        stmt = select(Servico).where(
            Servico.ativo.is_(True), 
            func.lower(Servico.nome) == func.lower(nome)
        )
        return (await self.session.scalars(stmt)).one_or_none()
    
    async def get_available_services_names(self) -> list[str]:
        """Lista serviços disponíveis."""
        stmt = select(Servico.nome).where(
            Servico.ativo.is_(True)).order_by(Servico.nome)
        
        return (await self.session.scalars(stmt)).all()
    
    async def buscar_servicos(self, termo: str) -> list[dict]:
        search_term = f'%{termo}%'

        # Otimização: Selecionar apenas colunas necessárias
        stmt = select(Servico).where(
            Servico.ativo.is_(True),
            (func.lower(Servico.nome).like(func.lower(search_term))) 
            | (func.lower(Servico.descricao).like(func.lower(search_term))) 
        )
        resultados = (await self.session.scalars(stmt)).all()

        return [
            {
                "servico_id": servico.servico_id,
                "nome": servico.nome,
                "descricao": servico.descricao,
                "preco": float(servico.preco),
                "duracao_minutos": servico.duracao_minutos,
            }
            for servico in resultados
        ]