# src/services/data_service.py
import logging
from src.config.logger import setup_logger
import json

from typing import Optional, TYPE_CHECKING
from datetime import date

# Importações do SQLAlchemy
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

# Importações dos módulos
from src.database.repositories import UserRepository, AgendaRepository, SessionRepository, MensagemRepository
from src.utils import MESSAGES

# Importar dependências de serviço
from src.services.slot_processor_service import SlotProcessorService

# Use TYPE_CHECKING para evitar erro de importação circular no runtime
if TYPE_CHECKING:
    from src.bot.llm_service import LLMService

# Configuração do logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = setup_logger(__name__)


class DataService:
    """Coordenador de Repositórios de Dados e Orquestrador do Processamento LLM/Slots."""

    def __init__(self, session_maker: async_sessionmaker[AsyncSession], llm_service: Optional['LLMService'] = None):
        """Recebe o criador de sessões assíncronas e o LLMService como dependências."""
        self._session_maker = session_maker
        self._llm_service: Optional[LLMService] = llm_service
        logger.info("Database (Coordenador Assíncrono) inicializado com sucesso.")

        self.resposta_sucinta = MESSAGES.get('RESPOSTA_SUCINTA', "Olá! Como posso ajudar você hoje?")

    def _get_session(self) -> AsyncSession:
        """Retorna uma nova sessão assíncrona"""
        # chama a factory de sessão. Isso retorna o AsyncSession
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
    # FLUXO PRINCIPAL: PROCESSAMENTO DA RESPOSTA LLM (NOVO)
    # =========================================================
    async def process_llm_response(self, user_id: int, user_message: str) -> dict:
        """
        Orquestra o ciclo de extração de slots:
        1. Recupera o estado da sessão.
        2. Chama a LLM para extração de slots.
        3. Pós-processa os slots (Resolução/Enriquecimento).
        4. Salva o novo estado da sessão no banco de dados.

        Retorna os slots processados (dicionário).
        """
        # A sessão é aberta para as leituras iniciais (estado)
        async with self._get_session() as session:
            repositories = self._get_repos(session)
            session_repo = repositories['session_repo']

            # 1. Recupera o estado atual da sessão
            session_state = await session_repo.get_session_state(user_id)
            current_slots = session_state.get('slot_data', {})
            current_intent = session_state.get('current_intent', 'GENERICO')

            if self._llm_service is None:
                raise RuntimeError("LLMService não foi injetado no DataService. O ciclo de dependência falhou.")

        # 2. Chama a LLM para extração de slots
        llm_extracted_pydantic = await self._llm_service.extract_intent_and_data(
            user_message, current_slots
        )

        # 3. Pós-processamento e Resolução de Slots
        slot_processor = SlotProcessorService(data_service=self)

        # Executa a transformação e enriquecimento dos slots
        processed_slots: dict = await slot_processor.process_slots(llm_extracted_pydantic)

        # A intenção primária vem do LLM
        new_intent = llm_extracted_pydantic.intent or current_intent

        # 4. Salva o Novo Estado da Sessão (transacional)
        # O update_session_state já abre uma nova sessão e transação para salvar.
        await self.update_session_state(
            user_id=user_id
            , current_intent=new_intent
            , slot_data=processed_slots
        )

        return processed_slots

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

    # BUSCAR TELEFONE
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

        # 1. Busca o estado atual para mesclagem no DataService (ou dependa do Repositório)
        # O SessionRepository.update_session_state já lida com a mesclagem de dicionários,
        # mas precisamos garantir que estamos enviando o dicionário de mesclagem correto.

        async with self._get_session() as session:
            repositories = self._get_repos(session)
            session_repo = repositories['session_repo']

            # 1. Recupera o estado atual para saber qual mesclagem aplicar
            current_state = await session_repo.get_session_state(user_id)
            slot_data: dict = current_state.get('slot_data', {})

            # 2. Aplica a modificação específica no dicionário
            if slot_value is None:
                slot_data.pop(slot_key, None) # Remove a chave se o valor for None
                logger.debug(f"Slot '{slot_key}' removido para o usuário {user_id}")
            else:
                slot_data[slot_key] = slot_value # Atualiza a chave
                logger.debug(f"Slot '{slot_key}' atualizado para o usuário {user_id}")

            # 3. Usa o método transacional de atualização do DataService
            # Chamar o update_session_state aqui é mais limpo, mas ele precisa ser transacional.
            
            # Como este método já é transacional, vamos chamar o repositório diretamente:
            async with session.begin():
                try:
                    # Atualiza o objeto do modelo
                    await session_repo.update_session_state(
                        user_id=user_id,
                        # Mantém a intenção atual
                        current_intent=current_state.get('current_intent'),
                        # Passa o dicionário mesclado
                        slot_data=slot_data
                    )
                    logger.info(f"Slot '{slot_key}' persistido com sucesso para o usuário {user_id}.")

                except Exception as e:
                    logger.error(f"Erro transacional ao atualizar slot {slot_key}: {e}")
                    raise
