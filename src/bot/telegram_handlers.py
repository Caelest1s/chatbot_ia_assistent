# # src/bot/telegram_handlers.py
from telegram import Update
from telegram.ext import ContextTypes, JobQueue

from src.services.persistence_service import PersistenceService
from src.services.dialog_flow_service import DialogFlowService
from src.bot.llm_service import LLMService
from src.services.service_finder import ServiceFinder
from src.bot.slot_filling_manager import SlotFillingManager

from src.utils.system_message import MESSAGES
from src.config.logger import setup_logger
logger = setup_logger(__name__)

# Constante de Timeout
TIMEOUT_MINUTES = 10
TIMEOUT_SECONDS = TIMEOUT_MINUTES * 60 # 600 segundos (10 minutes)

class TelegramHandlers:
    """Roteia as mensagens e comandos para os serviços e gerenciadores apropriados."""

    TIMEOUT_SECONDS = TIMEOUT_SECONDS
    TIMEOUT_MINUTES = TIMEOUT_MINUTES

    def __init__(self, 
                 persistence_service: PersistenceService, 
                 llm_service: LLMService, 
                 service_finder: ServiceFinder, 
                 slot_filling_manager: SlotFillingManager, 
                 dialog_flow_service: DialogFlowService):
        
        self.persistence_service = persistence_service
        self.llm_service = llm_service
        self.service_finder = service_finder
        self.slot_filling_manager = slot_filling_manager
        self.dialog_flow_service = dialog_flow_service

    async def _ensure_user_registered(self, user_id: int, nome: str):
        """
        Garanta que o usuário existe no DB antes de qualquer operação de persistência.
        Não limpa histórico/sessão, apenas cria ou atualiza o registro.
        """
        # O salvar_usuario no DataService/UserRepository fará a checagem se o registro
        # existe e o criará/atualizará se necessário, com commit.
        await self.persistence_service.salvar_usuario(user_id=user_id, nome=nome, telefone=None)
        logger.debug(f"Registro de usuário {user_id} garantido (criado ou atualizado).")
    
    async def _get_user_name(self, user_id: int, update: Update) -> str:
        """Helper para obter o nome do usuário do DB ou do Telegram (fallback)."""
        # Prioriza o nome salvo no DB para consistência
        nome = await self.persistence_service.get_nome_usuario(user_id)
        if nome:
            return nome
        
        # Fallback para o nome do Telegram (deve ser atualizado pelo start/contact handler)
        return update.effective_user.first_name
    
    # ======================================================================================================
    #                                       Timer / Job Manager
    # ======================================================================================================
    def _remove_inactivity_timer(self, user_id: int, job_queue: JobQueue) -> bool:
        """Remove o job de timeout existente para o usuário, se houver."""
        job_name = f'timeout_{user_id}'
        current_jobs = job_queue.get_jobs_by_name(job_name)

        if current_jobs:
            current_jobs[0].schedule_removal()
            logger.debug(f"Job de timeout antigo ({job_name}) removido.")
            return True
        return False

    def _set_inactivity_timer(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """
        Agenda o job de limpeza da sessão, substituindo um job anterior.
        Deve ser chamado no final de cada handler de interação.
        """
        job_name = f'timeout_{user_id}'

        # 1. Remove o job antigo (se existir)
        self._remove_inactivity_timer(user_id, context.application.job_queue)

        # 2. Agenda o novo Job
        context.application.job_queue.run_once(
            self.session_timeout_job
            , self.TIMEOUT_SECONDS
            , chat_id=user_id
            , name=job_name
        )
        logger.debug(f"Novo job de timeout ({job_name}) agendado para {self.TIMEOUT_MINUTES} minutos.")
        # A função do Job não precisa ser um método da instância (pode ser static ou externa), 
        # mas mantê-la aqui como um método da classe facilita o acesso às dependências.

    async def session_timeout_job(self, context: ContextTypes.DEFAULT_TYPE):
        """Função chamada pelo Job para limpar o contexto da sessão após o timeout."""

        user_id = context.job.chat_id

        # 1. Limpa o histórico da LLM (em memória)
        self.llm_service.history_manager.reset_history(user_id)

        # 2. Limpa o estado da sessão (DB)
        await self.persistence_service.clear_session_state(user_id)

        # 3. Limpa o histórico persistente (mensagens salvas no DB)
        await self.persistence_service.clear_historico(user_id)

        # 4. Limpa o user_data (se você usa para armazenar estado temporário)
        if user_id in context.application.user_data:
            context.application.user_data[user_id].clear()

        # 5. Notificar o usuário que a sessão expirou
        await context.bot.send_message(
            user_id
            , f"⚠️ Sua sessão expirou por inatividade ({self.TIMEOUT_MINUTES} minutos). Por favor, comece uma nova conversa."
        )

        logger.info(f"Sessão do usuário {user_id} limpa devido a timeout de inatividade.")

    # ======================================================================================================
    #                                       Handlers Default
    # ======================================================================================================
    # Note: O /start e /reset já fazem uma limpeza completa e podem remover o timer
    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Reinicia a conversação e o estado de agendamento."""
        user_id = update.effective_user.id

        self.llm_service.history_manager.reset_history(user_id)
        # Limpa o estado da sessão também
        await self.persistence_service.clear_session_state(user_id)
        await self.persistence_service.clear_historico(user_id)

        # Remove o timer existente ao resetar
        self._remove_inactivity_timer(user_id, context.application.job_queue)

        await update.message.reply_text('Conversação e estado de agendamento reiniciados. Pode perguntar algo novo!')
        # Não agenda novo timer aqui, pois a interação acabou.

    # ======================================================================================================
    #                                       Handlers Custom
    # ======================================================================================================
    async def servicos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Exibe a lista de serviços disponíveis."""
        user_id = update.effective_user.id
        nome = await self._get_user_name(user_id, update) # <-- USANDO HELPER

        dados_servicos = await self.persistence_service.buscar_servicos('')

        if not dados_servicos:
            await update.message.reply_text(f'{nome}, nenhum serviço disponível.')
            return

        # Formatação otimizada
        resposta = "Serviços disponíveis:\n" + "\n".join([
            f"- {s['nome']}: {s['descricao']} (R${s['preco']:.2f}, {s['duracao_minutos']} min)"
            for s in dados_servicos
        ])
        await update.message.reply_text(f'{nome}, {resposta}')

    async def agenda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia o processo de agendamento via comando /agenda."""
        user_id = update.message.from_user.id
        nome = await self._get_user_name(user_id, update)

        # Limpa o estado para iniciar o Slot Filling
        await self.persistence_service.clear_session_state(user_id)

        # 2. Define a intenção AGENDAR
        await self.persistence_service.update_session_state(user_id, current_intent='AGENDAR', slot_data={})

        await update.message.reply_text(MESSAGES['SLOT_FILLING_WELCOME'].format(nome=nome))

        # Reagenda o timer para o usuário ter 10 minutos para iniciar o agendamento
        self._set_inactivity_timer(user_id, context)

    # ======================================================================================================
    #                                       ANSWER
    # ======================================================================================================
    async def answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Roteia a mensagem do usuário para o gerenciador de fluxo apropriado."""

        if update.message.text is None:
            return

        user_id = update.effective_user.id
        original_question = update.message.text
        nome = update.effective_user.first_name

        await self._ensure_user_registered(user_id, nome)

        # Variável de controle para saber se a mensagem foi tratada por algum fluxo
        handled_message = False

        # 1. 🚨 ORQUESTRAÇÃO DE LLM E PROCESSAMENTO DE SLOTS
        processed_slots = await self.dialog_flow_service.process_llm_response(
            user_id=user_id
            , user_message=original_question
        )

        # 2. RECUPERA O ESTADO ATUALIZADO DA SESSÃO
        session_state = await self.persistence_service.get_session_state(user_id)
        current_intent = session_state.get('current_intent')

        # 3. Prioridade para INTENÇÕES DE INTERRUPÇÃO/COMANDO (Lidas diretamente do DB)
        if current_intent == 'RESET':
            return await self.reset(update, context)
        
        if current_intent == 'SERVICOS':
            return await self.servicos(update, context)

        # 🚨 4. Roteamento baseado na Intenção Salva
        if current_intent == 'AGENDAR':
            await self.slot_filling_manager.handle_slot_filling(update, context)
            handled_message = True

        elif current_intent == 'BUSCAR_SERVICO':
            # 💡 Fluxo para Busca de Serviço: Precisa de um objeto estruturado para o ServiceFinder.

            # Classe Dummy para compatibilidade com o ServiceFinder
            class DummyStructuredData:
                def __init__(self, intent, slots):
                    self.intent = intent
                    # O service_finder antigo provavelmente espera a busca no campo data_extracao
                    self.data_extracao = slots 

            # Cria o objeto de compatibilidade
            dummy_data = DummyStructuredData(current_intent, processed_slots)

            # Executa a busca
            await self.service_finder.handle_buscar_servicos_estruturado(update, context, dummy_data)
            
            # 🚨 IMPORTANTE: Limpa a sessão após a busca para não contaminar a próxima conversa
            await self.persistence_service.clear_session_state(user_id) 

            handled_message = True

        # ===============================================================================================
        #                   5. Roteamento baseado na Intenção Extraída ou Corrigida
        # ===============================================================================================

        # 6. Resposta Padrão (GENERICO ou falha no tratamento)
        elif current_intent == 'GENERICO' or (current_intent is None):
            await self.llm_service.handle_generico(update, context)
            handled_message = True

        # ===============================================================================================
        #                               6. Timer e Fallback Final
        # ===============================================================================================
        if handled_message:
            # SUCESSO: Rearranja o Timer de Inatividade após uma interação bem-sucedida
            self._set_inactivity_timer(user_id, context)
        else:
            # FALLBACK: Se handled_message ainda for False, a mensagem não foi reconhecida por nenhum fluxo.
            await update.message.reply_text("Desculpe, não entendi o que você quis dizer. Por favor, tente de outra forma.")
            # O timer de inatividade pode ser setado aqui também, pois é uma resposta final do bot.
            self._set_inactivity_timer(user_id, context)
        
        return True
    