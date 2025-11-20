# src/database/repositories/user_repo.py
import json
# import logging
from src.config.logger import setup_logger
from datetime import datetime
from typing import Optional, List, Dict, Any

# Importações Assíncronas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

# Importações da Base e dos Modelos
from src.database.repositories.base_repo import BaseRepository # Repositório Genérico
from src.database.models.user_model import Usuario
from src.database.models.historico_model import Historico

logger = setup_logger(__name__)

class UserRepository(BaseRepository[Usuario]):
    """
    Repositório para operações de persistência assíncronas relacionadas aos Usuários.
    Herdando de BaseRepository, ele já herda __init__ e métodos básicos.
    """

    # Adicionamos a AsyncSession no construtor
    def __init__(self, session: AsyncSession, default_msg: str):
        # Inicializa o BaseRepository com a AsyncSession e o modelo Usuario
        super().__init__(session, Usuario)
        self.resposta_sucinta = default_msg

        # O self.session agora é a AsyncSession ativa
        
    async def salvar_usuario(self, user_id: int, nome: str) -> Usuario:
        """
        Salva ou Atualiza usuário de forma assíncrona.
        Retorna o objeto Usuario (existente ou novo).
        """
        usuario = await self.session.get(Usuario, user_id)

        if usuario:
            """Atualiza"""
            if usuario.nome != nome:
                usuario.nome = nome
                logger.info(f"Usuário {user_id} atualizado: {nome}")
        else:
            """Cria novo"""
            novo_usuario = Usuario(user_id=user_id, nome=nome)
            self.session.add(novo_usuario)
            # O commit é responsabilidade do DataService/UoW
            logger.info(f"Novo usuário {user_id} criado: {nome}")
        
        return usuario

    async def get_nome_usuario(self, user_id: int) -> Optional[str]:
        """Recupera o nome do usuário pelo ID de forma assíncrona."""
        stmt = select(Usuario.nome).where(Usuario.user_id == user_id)
        return await self.session.scalar(stmt)
