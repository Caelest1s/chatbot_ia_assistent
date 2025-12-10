# src/database/repositories/mensagem_repo.py
from src.config.logger import setup_logger
from typing import Optional

from sqlalchemy import select, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.mensagem_model import Mensagem
from src.database.models.user_model import Usuario

logger = setup_logger(__name__)

# Definimos o formato padrão que o LLM espera
DEFAULT_USER_ROLE = "user"
DEFAULT_BOT_ROLE = "bot"
DEFAULT_SYSTEM_ROLE = "system" 

class MensagemRepository:
    """
    Repositório para operações assíncronas de persistência e recuperação de Mensagens
    usando o padrão RELACIONAL (uma linha por mensagem).
    """
    def __init__(self, session: AsyncSession, default_system_msg: str):
        self.session = session
        self.default_system_msg = default_system_msg # Mensagem de sistema para o LLM


    async def get_usuario_pk(self, telegram_user_id: int) -> Optional[int]:
        """
        Busca a Chave Primária (PK) interna do usuário (`Usuario.id`) 
        dado o ID externo (`user_id_telegram`).
        """
        stmt = select(Usuario.id).where(Usuario.user_id == telegram_user_id)
        return await self.session.scalar(stmt)
    

    async def salvar_mensagem(self, telegram_user_id: int, conteudo: str, origem: str) -> None:
        """
        Salva uma ÚNICA mensagem no banco de dados, indicando a origem.
        
        NOTA: Para garantir integridade, primeiro buscamos a PK interna.
        """

        if origem not in [DEFAULT_USER_ROLE, DEFAULT_BOT_ROLE]:
            logger.warning(f"Origem inválida '{origem}' para salvar mensagem. Ignorando.")
            return
        
        # 1. Busca a Chave Primária (PK) interna do usuário
        usuario_pk = await self.get_usuario_pk(telegram_user_id)

        if usuario_pk is None:
            logger.error(f"Não foi possível salvar mensagem. Usuário com ID {telegram_user_id} não encontrado.")
            # **Este raise é o que garante o ROLLBACK e a notificação de erro no LLMService**
            raise ValueError(f"Usuário não registrado (ID {telegram_user_id}).")
        
        # 2. Cria e adiciona a nova mensagem
        nova_mensagem = Mensagem(usuario_id=usuario_pk, conteudo=conteudo, origem=origem)
        self.session.add(nova_mensagem)
        logger.info(f"Mensagem de '{origem}' para usuário {usuario_pk} preparada para commit.")


    async def get_historico_llm(self, telegram_user_id: int, limit: int = 20) -> list[dict[str, str]]:
        """
        Recupera o histórico de conversas do usuário, formatado para o LLM (chat history).
        Retorna as últimas 'limit' mensagens, na ordem correta (antiga -> nova).
        """
        # 1. Mensagem Padrão do Sistema (System Prompt)
        historico_formatado = [{
            "role": DEFAULT_SYSTEM_ROLE,
            "content": self.default_system_msg
        }]

        # 2. Busca a Chave Primária (PK) interna do usuário
        usuario_pk = await self.get_usuario_pk(telegram_user_id)

        if usuario_pk is None:
            logger.warning(f"Usuário {telegram_user_id} não encontrado ao buscar histórico. Retornando system prompt.")
            return historico_formatado
        
        # 3. Busca as N últimas mensagens (usuário e bot)
        stmt = (
            select(Mensagem.conteudo, Mensagem.origem)
            .where(Mensagem.usuario_id == usuario_pk)
            .order_by(desc(Mensagem.created_at))
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        mensagens_db = result.all()

        # 4. Mapeia para o formato LLM e INVERTE para ordem cronológica (mais antigo -> mais recente)
        mensagens_llm = [{
            "role": msg.origem,
            "content": msg.conteudo
        }for msg in reversed(mensagens_db)]

        # Retorna o System Prompt + as mensagens da conversa
        return historico_formatado + mensagens_llm
    
    async def clear_historico(self, telegram_user_id: int) -> None:
        """
        Remove todas as mensagens persistentes do usuário.
        """
        usuario_pk = await self.get_usuario_pk(telegram_user_id)

        if usuario_pk is None:
            logger.warning(f"Tentativa de limpar histórico para usuário não existente (ID {telegram_user_id}).")
            return

        # 1. Deleta todas as mensagens associadas à PK (FK)
        stmt = delete(Mensagem).where(Mensagem.usuario_id == usuario_pk)
        
        # 2. Executa o delete assíncrono
        result = await self.session.execute(stmt)
        logger.info(f"Deletadas {result.rowcount} mensagens para o usuário PK {usuario_pk}.")
        
        # O commit é feito pela camada de Serviço (DataService)
    