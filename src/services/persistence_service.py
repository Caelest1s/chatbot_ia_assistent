# src/services/persistence_service.py
import logging
from src.config.logger import setup_logger
from typing import Optional
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from src.database.repositories import UserRepository, AgendaRepository, SessionRepository, MensagemRepository, ServicoRepository
from src.services.scheduler_service import SchedulerService
from src.utils import MESSAGES

# Configuração do logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = setup_logger(__name__)

class PersistenceService:
    """Coordenador de Repositórios de Dados e Orquestrador do Processamento LLM/Slots."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        """Recebe o criador de sessões assíncronas."""
        self._session_maker = session_maker
        logger.info("Database (Coordenador Assíncrono) inicializado com sucesso.")
        self.resposta_sucinta = MESSAGES.get('RESPOSTA_SUCINTA' + MESSAGES['WELCOME_MESSAGE'])

    def _get_session(self) -> AsyncSession:
        """Retorna uma nova sessão assíncrona"""
        return self._session_maker()

    def _get_repos(self, session: AsyncSession) -> dict:
        """Centraliza a criação de todos os repositórios para a sessão atual."""
        return {
            "user_repo": UserRepository(session, self.resposta_sucinta)
            , "agenda_repo": AgendaRepository(session)
            , "session_repo": SessionRepository(session)
            , "mensagem_repo": MensagemRepository(session, self.resposta_sucinta)
            , "servico_repo": ServicoRepository(session)
        }
    
    def _get_scheduler_service(self, session: AsyncSession):
        """Retorna o SchedulerService para a sessão atual (Leitura de Agendamentos/Disponibilidade)."""
        agenda_repo = self._get_repos(session)['agenda_repo']
        return SchedulerService(agenda_repo=agenda_repo)
    
    # =========================================================
    # FUNÇÕES DE USUÁRIO (PROXY para UserRepository)
    # =========================================================
    async def salvar_usuario(self, user_id: int, nome: str, telefone: Optional[str] = None):
        """Salva ou atualiza usuaário e comita em uma transação."""
        async with self._get_session() as session:
            async with session.begin():
                try:
                    await self._get_repos(session)["user_repo"].salvar_usuario(user_id, nome, telefone)
                    logger.info(f"Usuário {user_id} salvo/atualizado com sucesso (Telefone: {telefone}).")
                except Exception as e:
                    logger.error(f"Erro transacional ao salvar usuário: {e}")
                    raise

    async def get_telefone_usuario(self, user_id: int) -> Optional[str]:
        """Recupera o número de telefone do usuário pelo ID."""
        async with self._get_session() as session:
            return await self._get_repos(session)["user_repo"].get_telefone_by_user_id(user_id)

    async def get_nome_usuario(self, user_id: int) -> Optional[str]:
        """Recupera nome de usuário."""
        async with self._get_session() as session:
            return await self._get_repos(session)["user_repo"].get_nome_usuario(user_id)

    # =========================================================
    # FUNÇÕES DE HISTÓRICO (PROXY para MensagemRepository)
    # =========================================================
    async def get_historico_llm(self, user_id: int) -> list:
        """Recupera o histórico de conversas formatado (com System Prompt) para o LLM."""
        async with self._get_session() as session:
            return await self._get_repos(session)["mensagem_repo"].get_historico_llm(user_id)

    async def salvar_mensagem(self, user_id: int, mensagem: str, origem: str):
        """Salva uma mensagem (usuário ou bot) no histórico.
        Args:
            origem: 'user' ou 'bot'.
        """
        async with self._get_session() as session:
            async with session.begin():
                try:
                    await self._get_repos(session)["mensagem_repo"].salvar_mensagem(user_id, mensagem, origem)
                    logger.info(f"Mensagem de '{origem}' para usuário {user_id} salva e comitada.")
                except Exception as e:
                    logger.error(f"Erro transacional ao salvar mensagem: {e}")
                    raise

    async def clear_historico(self, user_id: int):
        """Limpa o histórico de mensagens persistente no DB para um usuário."""
        async with self._get_session() as session:
            async with session.begin():
                try:
                    await self._get_repos(session)["mensagem_repo"].clear_historico(user_id)
                    logger.info(f"Histórico de mensagens do usuário {user_id} limpo e comitado.")
                except Exception as e:
                    logger.error(f"Erro transacional ao limpar histórico: {e}")
                    raise

    # =========================================================
    # FUNÇÕES DE SESSÃO (PROXY para SessionRepository)
    # =========================================================
    async def get_session_state(self, user_id: int) -> dict:
        async with self._get_session() as session:
            return await self._get_repos(session)["session_repo"].get_session_state(user_id)

    async def update_session_state(self, user_id: int, current_intent: Optional[str] = None, slot_data: Optional[dict] = None):
        """Atualiza o estado da sessão e comita em uma transação."""
        if slot_data is None and current_intent is None:
            return

        async with self._get_session() as session:
            async with session.begin():
                try:
                    await self._get_repos(session)["session_repo"].update_session_state(user_id, current_intent, slot_data)
                    logger.info(f"Estado da sessão do usuário {user_id} atualizado com sucesso.")
                except Exception as e:
                    logger.error(f"Erro transacional ao atualizar sessão: {e}")
                    raise

    async def clear_session_state(self, user_id: int):
        """Limpa o estado da sessão (UserSession) do usuário. Remove o estado do diálogo."""

        async with self._get_session() as session:
            async with session.begin():
                try:
                    await self._get_repos(session)["session_repo"].delete_session_by_id(user_id)
                    logger.info(f"Estado da sessão do usuário {user_id} limpo com sucesso.")
                except Exception as e:
                    logger.error(f"Erro transacional ao limpar sessão: {e}")
                    raise

    async def get_current_slots(self, user_id: int) -> dict:
        """Apenas retorna o dicionário de slots atual do banco."""
        state = await self.get_session_state(user_id)
        return state.get('slot_data', {}) or {}

    # =========================================================
    # FUNÇÕES DE SERVIÇOS (PROXY para ServicoRepository)
    # =========================================================
    async def buscar_servicos(self, termo: str) -> list:
        async with self._get_session() as session:
            return await self._get_repos(session)["servico_repo"].buscar_servicos(termo)

    async def get_available_services_names(self) -> list[str]:
        async with self._get_session() as session:
            return await self._get_repos(session)["servico_repo"].get_available_services_names()
        
    async def get_service_details_by_id(self, servico_id: int) -> Optional[dict]:
        """Busca ID, nome e duração de um serviço ativo pelo seu ID."""
        async with self._get_session() as session:
            servico_repo = self._get_repos(session)["servico_repo"]
            servico = await servico_repo.get_by_id(servico_id)

            if servico:
                return {
                    "servico_id": servico.servico_id,
                    "nome": servico.nome,
                    "duracao_minutos": servico.duracao_minutos,
                }
            return None
        
    async def get_service_details_by_name(self, servico_nome: str) -> Optional[dict]:
        """[ASYNC] Busca o ID, nome e duração de um serviço ativo pelo nome."""
        async with self._get_session() as session:
            servico = await self._get_repos(session)["servico_repo"].get_by_name(servico_nome)

            if servico:
                return {
                    "servico_id": servico.servico_id,
                    "nome": servico.nome,
                    "duracao_minutos": servico.duracao_minutos,
                }
            return None
        
    # =========================================================
    # FUNÇÕES DE AGENDAMENTO (PROXY para AgendaRepository)
    # =========================================================
    async def verificar_disponibilidade(self, data: str) -> list:
        async with self._get_session() as session:
            return await self._get_repos(session)["agenda_repo"].verificar_disponibilidade(data)
        
    """Validação de disponibilidade (SchedulerService) e Persistência transacional"""
    async def inserir_agendamento(self
                                  , user_id: int
                                  , servico_id: int
                                  , servico_nome: str
                                  , servico_minutos: int
                                  , data: str
                                  , hora_inicio: str) -> tuple[bool, str]:
        """Orquestra a validação final e a inserção física no banco."""
        
        async with self._get_session() as session:
            # 1. Validação de Disponibilidade via Scheduler
            scheduler = self._get_scheduler_service(session)

            # VALIDAÇÃO DE DISPONIBILIDADE (Regra de Negócio)
            is_available, validation_msg = await scheduler.is_slot_available(
                data=data
                , hora_inicio=hora_inicio
                , servico_minutos=servico_minutos
            )

            if not is_available:
                # Retorna a mensagem de erro (ex: horário passado, conflito, fora do horário comercial)
                return False, validation_msg
            
        # 2. Preparação dos dados para o AgendaRepository
        try:
            # Converte os strings para objetos date/time que o AgendaRepository espera
            data_dt = datetime.strptime(data, '%Y-%m-%d').date()
            hora_inicio_dt = datetime.strptime(hora_inicio, '%H:%M')
            hora_fim_time = (hora_inicio_dt + timedelta(minutes=servico_minutos)).time()
            hora_inicio_time = hora_inicio_dt.time()
            # O SchedulerService já fez este cálculo, mas repetimos para persistência
        except ValueError:
            return False, "Erro no formato de data/hora enviado ao banco."
        
        # 3. Transação de Escrita
        async with session.begin():
            try:
                agenda_repo = self._get_repos(session)['agenda_repo']
                # 1. Executa a lógica que manipula a sessão (INSERT/UPDATE)
                agenda_obj, final_servico_nome, msg = await agenda_repo.inserir_agendamento(
                    user_id=user_id 
                    , servico_id=servico_id 
                    , servico_nome=servico_nome 
                    , data_dt=data_dt
                    , hora_inicio_time=hora_inicio_time
                    , hora_fim_time=hora_fim_time)

                if agenda_obj:
                    return True, (f"Agendamento confirmado! {final_servico_nome} no dia "
                                     f"{data_dt.strftime('%d/%m')} às {hora_inicio_time.strftime('%H:%M')}.")

                return False, msg  # Erro de validação/conflito
            except Exception as e:
                logger.error(f"Falha ao comitar agendamento: {e}")
                raise

    async def get_available_blocks_for_shift(self, data: str, duracao_minutos: int, shift_name: Optional[str] = None) -> list[str]:
        """Retorna os horários HH:MM livres."""
        async with self._get_session() as session:
            scheduler = self._get_scheduler_service(session)
            # 3. Chama o método de cálculo no repositório (o Objeto Real)
            return await scheduler.calculate_available_blocks(
                data=data,
                duracao_minutos=duracao_minutos,
                shift_name=shift_name
            )
        
    # =========================================================
    # FUNÇÕES DE AGENDAMENTO (PROXY para AgendaRepository)
    # =========================================================
    async def reset_all_user_data(self, user_id: int):
        """Limpa histórico e estado da sessão (slots) de uma vez."""
        async with self._get_session() as session:
            async with session.begin():
                await self._get_repos(session)["mensagem_repo"].clear_historico(user_id)
                await self._get_repos(session)["session_repo"].delete_session_by_id(user_id)
                logger.info(f"Dados totais do usuário {user_id} resetados.")
        
