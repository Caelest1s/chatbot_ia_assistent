# # src/bot/telegram_handlers.py
from typing import Optional, Dict, Any

from telegram import Update
from telegram.ext import ContextTypes

from src.services.data_service import DataService
from src.bot.llm_service import LLMService
from src.services.service_finder import ServiceFinder
from src.bot.slot_filling_manager import SlotFillingManager

from src.utils.system_message import MESSAGES
from src.config.logger import setup_logger
logger = setup_logger(__name__)


class TelegramHandlers:
    """Roteia as mensagens e comandos para os serviços e gerenciadores apropriados."""

    def __init__(self, 
                 data_service: DataService, 
                 llm_service: LLMService, 
                 service_finder: ServiceFinder, 
                 slot_filling_manager: SlotFillingManager):
        
        self.data_service = data_service
        self.llm_service = llm_service
        self.service_finder = service_finder
        self.slot_filling_manager = slot_filling_manager

    # ======================================================================================================
    #                                       Handlers Default
    # ======================================================================================================
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.critical(f"🚀 HANDLER START ACIONADO! Recebendo update: {update.update_id}")
        
        user_id = update.message.from_user.id
        nome = update.message.from_user.first_name
        await self.data_service.salvar_usuario(user_id, nome)
        self.llm_service.history_manager.reset_history(user_id)
        await update.message.reply_text(f'Olá, {nome}! {MESSAGES['WELCOME_MESSAGE']}')
        logger.info(f"Comando /start recebido de {update.effective_user.first_name} (ID: {update.effective_user.id})")

    async def reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        self.llm_service.history_manager.reset_history(user_id)
        # Limpa o estado da sessão também
        await self.data_service.clear_session_state(user_id)
        await update.message.reply_text('Conversação e estado de agendamento reiniciados. Pode perguntar algo novo!')

    # ======================================================================================================
    #                                       Handlers Custom
    # ======================================================================================================
    async def servicos(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.message.from_user.id
        nome = await self.data_service.get_nome_usuario(user_id) or update.message.from_user.first_name

        # Reutilizamos a lógica do ServiceFinder
        dados_servicos = await self.data_service.buscar_servicos('')

        if not dados_servicos:
            await update.message.reply_text(f'{nome}, nenhum serviço disponível.')
            return

        resposta = "Serviços disponíveis:\n" + "\n".join([
            f"- {s['nome']}: {s['descricao']} (R${s['preco']:.2f}, {s['duracao_minutos']} min)"
            for s in dados_servicos
        ])
        await update.message.reply_text(f'{nome}, {resposta}')

    async def agenda(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Inicia o processo de agendamento via comando /agenda."""
        user_id = update.message.from_user.id
        nome = await self.data_service.get_nome_usuario(user_id) or update.message.from_user.first_name

        # Limpa o estado para iniciar o Slot Filling
        await self.data_service.clear_session_state(user_id)

        # 2. Define a intenção AGENDAR
        await self.data_service.update_session_state(user_id, current_intent='AGENDAR', slot_data={})

        await update.message.reply_text(MESSAGES['SLOT_FILLING_WELCOME'].format(nome=nome))

    # ======================================================================================================
    #                                       ANSWER
    # ======================================================================================================
    async def answer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Roteia a mensagem do usuário para o gerenciador de fluxo apropriado."""

        if update.message.text is None:
            return

        user_id = update.effective_user.id
        nome = await self.data_service.get_nome_usuario(user_id) or update.effective_user.first_name

        # 1. Recuperar o estado da sessão atual
        session_state = await self.data_service.get_session_state(user_id)
        current_intent = session_state.get('current_intent')

        # ===============================================================================================
        # 2. Extrair Slots e Intenção da LLM (COM MEMÓRIA)
        # A LLMService deve retornar SlotExtraction(intent='GENERICO') no pior caso de falha de parsing.
        # ===============================================================================================
        original_question = update.message.text

        # RECUPERA OS SLOTS ATUAIS DA SESSÃO
        current_slots = session_state.get('slot_data', {})

        # CHAMA O MÉTODO CORRETO QUE RECEBE A MEMÓRIA
        dados_estruturados = await self.llm_service.extract_intent_and_data(
            text=original_question
            , current_slots=current_slots)

        # 3. Prioridade para INTENÇÕES DE INTERRUPÇÃO/COMANDO
        if dados_estruturados.intent == 'RESET':
            return await self.reset(update, context)
        
        if dados_estruturados.intent == 'SERVICOS':
            # Limpa se mudar de tópico
            await self.data_service.clear_session_state(user_id)
            return await self.servicos(update, context)

        # 🚨 OTIMIZAÇÃO CRÍTICA: Priorizar Intenção Persistente para Slot Filling
        # Se o bot está no fluxo de AGENDAR, corrigimos a intenção para AGENDAR.
        if current_intent == 'AGENDAR':
            if dados_estruturados.intent != 'AGENDAR':
                logger.info(f"Intenção corrigida: de {dados_estruturados.intent} para AGENDAR (Fluxo ativo).")
                dados_estruturados.intent = 'AGENDAR'

        # ===============================================================================================
        #                   4. Roteamento baseado na Intenção Extraída ou Corrigida
        # ===============================================================================================
        if dados_estruturados.intent == 'AGENDAR':
            return await self.slot_filling_manager.handle_slot_filling(update, context, dados_estruturados)

        elif dados_estruturados.intent == 'BUSCAR_SERVICO':
            # Limpa o estado se a intenção for alterada, para não misturar fluxos.
            if current_intent and current_intent != 'BUSCAR_SERVICO':
                await self.data_service.clear_session_state(user_id)

            return await self.service_finder.handle_buscar_servicos_estruturado(update, context, dados_estruturados)

        # 5. Resposta Padrão (GENERICO ou falha no tratamento)
        elif dados_estruturados.intent == 'GENERICO' or (dados_estruturados.intent is None):

            # Limpa o estado se sair de um fluxo estruturado.
            if current_intent and current_intent != 'GENERICO':
                await self.data_service.clear_session_state(user_id)
            return await self.llm_service.handle_generico(update, context)

        await update.message.reply_text("Desculpe, não entendi o que você quis dizer. Por favor, tente de outra forma.")
        return True
