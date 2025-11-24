# src/database/repositories/user_repo.py
import json
# import logging
from src.config.logger import setup_logger
from typing import Optional

# Importações Assíncronas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importações da Base e dos Modelos
from src.database.repositories.base_repo import BaseRepository # Repositório Genérico
from src.database.models.user_model import Usuario
from src.database.models.mensagem_model import Mensagem

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

    async def salvar_usuario(self, user_id: int, nome: str, telefone: Optional[str]) -> Usuario:
        """
        Salva ou Atualiza usuário de forma assíncrona, buscando pelo user_id do Telegram.
        Retorna o objeto Usuario (existente ou novo).
        """

        # 💥 CORREÇÃO PRINCIPAL: Busca o usuário pela coluna user_id do Telegram
        stmt = select(Usuario).where(Usuario.user_id == user_id)
        result = await self.session.execute(stmt)
        usuario = result.scalar_one_or_none() # Retorna a instância do Usuario ou None

        updates = {} # Dicionário para rastrear o que foi atualizado

        if usuario:
            """Atualiza"""
            is_updated = False

            if usuario.nome != nome:
                usuario.nome = nome
                updates['nome'] = nome

                is_updated = True
                logger.info(f"Usuário {user_id} atualizado: {nome}")

            if usuario.telefone != telefone:
                usuario.telefone = telefone
                updates['telefone'] = telefone
                is_updated = True

            if is_updated:
                self.session.add(usuario) # Marca para o commit
                log_msg = ", ".join([f"{k}='{v}'" for k, v in updates.items()])
                logger.info(f"Usuário {user_id} atualizado: {log_msg}")
                
        else:
            """Cria novo"""
            novo_usuario = Usuario(user_id=user_id, nome=nome, telefone=telefone)
            self.session.add(novo_usuario)
            # O commit é responsabilidade do DataService/UoW
            logger.info(f"Novo usuário {user_id} criado: Nome='{nome}', Telefone='{telefone}'")
            usuario = novo_usuario
        
        return usuario
    
    async def get_nome_usuario(self, user_id: int) -> Optional[str]:
        """Recupera o nome do usuário pelo ID de forma assíncrona."""
        stmt = select(Usuario.nome).where(Usuario.user_id == user_id)
        return await self.session.scalar(stmt)
    
    async def get_telefone_by_user_id(self, user_id: int) -> Optional[str]:
        """Busca o número de telefone de um usuário pelo seu user_id."""
        stmt = select(Usuario.telefone).where(Usuario.user_id == user_id)
        # Retorna a string do telefone ou None
        return await self.session.scalar(stmt)
    