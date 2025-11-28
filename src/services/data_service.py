# src/services/data_service.py
import logging
from src.config.logger import setup_logger
import json

from typing import Optional

# Importações do SQLAlchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

# Importações dos módulos
from src.database.repositories import UserRepository, AgendaRepository, SessionRepository, MensagemRepository
from src.utils import MESSAGES

# Configuração do logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = setup_logger(__name__)


class DataService:
    """
    Coordenador de Repositórios de Dados.
    Responsável por gerenciar o acesso aos diferentes repositórios de dados 
    e o ciclo de vida da sessão assíncrona (AsyncSession).
    """

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        """
        Recebe o criador de sessões assíncronas como dependência.
        """
        self._session_maker = session_maker
        logger.info(
            "Database (Coordenador Assíncrono) inicializado com sucesso.")

        self.resposta_sucinta = MESSAGES.get(
            'RESPOSTA_SUCINTA', "Olá! Como posso ajudar você hoje?")

    def _get_session(self) -> AsyncSession:
        """
        Retorna uma nova sessão assíncrona (objeto que implementa o 
        Asynchronous Context Manager, a ser usado com 'async with').
        """
        # Apenas chame a factory de sessão. Isso retorna o AsyncSession
        # que será gerenciado pelo 'async with' em cada método.
        return self._session_maker()

    def _get_repos(self, session: AsyncSession) -> dict:
        """Centraliza a criação de todos os repositórios para a sessão atual."""
        return {
            "user_repo": UserRepository(session, self.resposta_sucinta)
            , "agenda_repo": AgendaRepository(session)
            , "session_repo": SessionRepository(session)
            ,"mensagem_repo": MensagemRepository(session, self.resposta_sucinta)
        }

    # =========================================================
    # FUNÇÕES DE USUÁRIO (PROXY para UserRepository)
    # =========================================================
    async def salvar_usuario(self, user_id: int, nome: str, telefone: Optional[str] = None):
        """
        Salva ou atualiza usuaário e comita em uma transação.
        Args:
            user_id: ID do usuário.
            nome: Nome do usuário.
            telefone: Opcional, número de telefone como string.
        """
        # Usa o context manager assíncrono para gerenciar a sessão e a transação
        async with self._get_session() as session:
            async with session.begin():
                try:
                    repositories = self._get_repos(session)

                    # Se o repositório fizer a lógica de INSERT/UPDATE
                    await repositories["user_repo"].salvar_usuario(user_id, nome, telefone)

                    logger.info(
                        f"Usuário {user_id} salvo/atualizado com sucesso (Telefone: {telefone}).")
                except Exception as e:
                    # Não precisa de commit ou rollback manual aqui
                    logger.error(f"Erro transacional ao salvar usuário: {e}")
                    # Re-lança a exceção para que o bloco session.begin() faça o ROLLBACK.
                    raise

    # ✅ NOVO MÉTODO: BUSCAR TELEFONE
    async def get_telefone_usuario(self, user_id: int) -> Optional[str]:
        """
        Recupera o número de telefone do usuário pelo ID. Usado para checagem de onboarding.
        """
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            # Você precisa implementar get_telefone_by_user_id no UserRepository
            return await repositories["user_repo"].get_telefone_by_user_id(user_id)

    async def get_nome_usuario(self, user_id: int) -> Optional[str]:
        """Recupera nome de usuário (leitura não precisa de commit)."""
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            return await repositories["user_repo"].get_nome_usuario(user_id)

    # =========================================================
    # FUNÇÕES DE HISTÓRICO (PROXY para MensagemRepository)
    # =========================================================
    async def get_historico_llm(self, user_id: int) -> list:
        """Recupera o histórico de conversas formatado (com System Prompt) para o LLM."""
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            return await repositories["mensagem_repo"].get_historico_llm(user_id)

    async def salvar_mensagem(self, user_id: int, mensagem: str, origem: str):
        """
        Salva uma mensagem (usuário ou bot) no histórico e comita em uma transação.
        
        Args:
            user_id: ID do usuário (do Telegram/plataforma).
            mensagem: Conteúdo da mensagem.
            origem: 'user' ou 'bot'.
        """
        async with self._get_session() as session:
            async with session.begin():
                try:
                    repositories = self._get_repos(session)

                    await repositories["mensagem_repo"].salvar_mensagem(user_id, mensagem, origem)

                    logger.info(f"Mensagem de '{origem}' para usuário {user_id} salva e comitada.")
                except Exception as e:
                    logger.error(f"Erro transacional ao salvar mensagem: {e}")
                    # Re-lança a exceção para que o bloco session.begin() faça o ROLLBACK.
                    raise

    async def clear_historico(self, user_id: int):
        """
        Limpa o histórico de mensagens persistente no DB para um usuário.
        """
        async with self._get_session() as session:
            async with session.begin():
                try:
                    repositories = self._get_repos(session)
                    # Chama o método de remoção no repositório
                    await repositories["mensagem_repo"].clear_historico(user_id)
                    logger.info(f"Histórico de mensagens do usuário {user_id} limpo e comitado.")
                except Exception as e:
                    logger.error(f"Erro transacional ao limpar histórico: {e}")
                    raise

    # =========================================================
    # FUNÇÕES DE SESSÃO (PROXY para SessionRepository)
    # =========================================================
    async def get_session_state(self, user_id: int) -> dict:
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            return await repositories["session_repo"].get_session_state(user_id)

    async def update_session_state(self, user_id: int, current_intent: Optional[str] = None, slot_data: Optional[dict] = None):
        """Atualiza o estado da sessão e comita em uma transação."""
        if slot_data is None and current_intent is None:
            return

        async with self._get_session() as session:
            async with session.begin():
                try:
                    repositories = self._get_repos(session)
                    await repositories["session_repo"].update_session_state(user_id, current_intent, slot_data)

                    logger.info(
                        f"Estado da sessão do usuário {user_id} atualizado com sucesso.")
                except Exception as e:
                    logger.error(f"Erro transacional ao atualizar sessão: {e}")
                    # Re-lança a exceção para que o bloco session.begin() faça o ROLLBACK.
                    raise

    async def clear_session_state(self, user_id: int):
        """
        Limpa o estado da sessão (UserSession) do usuário e comita em uma transação.
        Equivalente a remover o estado do diálogo.
        """

        async with self._get_session() as session:
            async with session.begin():
                try:
                    repositories = self._get_repos(session)
                    await repositories["session_repo"].delete_by_id(user_id)

                    logger.info(
                        f"Estado da sessão do usuário {user_id} limpo com sucesso.")
                except Exception as e:
                    logger.error(f"Erro transacional ao limpar sessão: {e}")
                    raise

    # =========================================================
    # FUNÇÕES DE AGENDAMENTO E SERVIÇO (PROXY para AgendaRepository)
    # =========================================================
    async def buscar_servicos(self, termo: str) -> list:
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            return await repositories["agenda_repo"].buscar_servicos(termo)

    async def get_available_services_names(self) -> list[str]:
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            return await repositories["agenda_repo"].get_available_services_names()

    async def verificar_disponibilidade(self, data: str) -> list:
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            return await repositories["agenda_repo"].verificar_disponibilidade(data)

    async def inserir_agendamento(self, user_id: int, servico_id: int, data: str, hora_inicio: str) -> tuple[bool, str]:
        """Insere um agendamento e comita em uma transação. Retorna ID do agendamento ou erro."""
        async with self._get_session() as session:
            async with session.begin():
                try:
                    agenda_repo = AgendaRepository(session)

                    # O repositório deve ser assíncrono
                    # 1. Executa a lógica que manipula a sessão (INSERT/UPDATE)
                    agenda_obj, servico_nome, msg = await agenda_repo.inserir_agendamento(user_id, servico_id, data, hora_inicio)

                    if agenda_obj:
                        # 2. Se for um sucesso de banco de dados:
                        # O COMMIT será executado AUTOMATICAMENTE na saída do 'async with session.begin():'

                        # Lógica de resposta (mantida, mas garantindo que o objeto é assíncrono)
                        agenda_id = agenda_obj.agenda_id
                        hora_fim_str = agenda_obj.hora_fim.strftime('%H:%M')
                        final_servico_nome = servico_nome if servico_nome else "Serviço"

                        response_msg = (
                            f"Agendamento #{agenda_id} confirmado para o serviço '{final_servico_nome}' "
                            f"na data {data} das {agenda_obj.hora_inicio.strftime('%H:%M')} às {hora_fim_str}."
                        )

                        logger.info(response_msg)
                        return True, response_msg

                    return False, msg  # Erro de validação/conflito

                except Exception as e:
                    logger.error(
                        f"Erro transacional ao inserir agendamento. Erro ao agendar: {e}. ")
                    # O rollback é tratado pelo Context Manager se o commit falhar
                    # Re-lança a exceção para que o bloco session.begin() faça o ROLLBACK.
                    raise

    async def get_available_blocks_for_shift(self, data: str, duracao_minutos: int, shift_name: Optional[str] = None) -> list[str]:
        """
        [PROXY] Chama o método de cálculo de blocos livres no AgendaRepository (calculate_available_blocks),
        garantindo a gestão da sessão.
        """
        # 1. Abre a sessão assíncrona
        async with self._get_session() as session:
            # 2. Obtém os repositórios para esta sessão
            repositories = self._get_repos(session)
            agenda_repo = repositories["agenda_repo"]

            # 3. Chama o método de cálculo no repositório (o Objeto Real)
            return await agenda_repo.calculate_available_blocks(
                data=data,
                duracao_minutos=duracao_minutos,
                shift_name=shift_name
            )

    async def get_service_details_by_name(self, servico_nome: str) -> Optional[dict]:
        """
        [ASYNC] Busca o ID, nome e duração de um serviço ativo pelo seu nome.
        Depende de um novo método em AgendaRepository.
        """
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            # Chama o novo método no AgendaRepository
            servico = await repositories["agenda_repo"].get_servico_by_name(servico_nome)

            if servico:
                return {
                    "servico_id": servico.servico_id,
                    "nome": servico.nome,
                    "duracao_minutos": servico.duracao_minutos,
                }
            return None

    async def update_slot_data(self, user_id: int, slot_key: str, slot_value: any):
        """
        [ASYNC] Atualiza ou remove (se slot_value for None) um slot 
        específico na sessão do usuário. Comita em uma transação.
        """
        async with self._get_session() as session:
            async with session.begin():
                try:
                    session_repo = self._get_repos(session)['session_repo']

                    user_session = await session_repo.get_by_id(user_id)

                    if user_session and user_session.slot_data:
                        # slot_data é string JSON no modelo, precisa de (de)serialização
                        slot_data: dict = json.loads(user_session.slot_data)

                        if slot_value is None:
                            slot_data.pop(slot_key, None)
                        else:
                            slot_data[slot_key] = slot_value

                        # Atualiza o objeto do modelo
                        await session_repo.update_session_state(
                            user_id=user_id,
                            current_intent=user_session.current_intent,
                            slot_data=slot_data
                        )

                        logger.debug(
                            f"Slot '{slot_key}' atualizado/removido para o usuário {user_id}")
                    else:
                        logger.warning(
                            f"Sessão de usuário {user_id} não encontrada para atualizar slot.")

                except Exception as e:
                    logger.error(
                        f"Erro transacional ao atualizar slot {slot_key}: {e}")
                    raise
