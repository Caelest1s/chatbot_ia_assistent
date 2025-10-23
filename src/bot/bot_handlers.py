# src/bot/bot_handlers.py

import logging
from telegram import Update
from telegram.ext import CallbackContext

from src.bot.database_manager import DatabaseManager
from src.bot.ai_assistant import AIAssistant
from src.bot.bot_services import BotServices
from src.schemas.intencao_schema import Intencao
from src.utils import MESSAGES
from datetime import datetime

logger = logging.getLogger(__name__)

class BotHandlers:
    """Implementa todos os handlers de comandos e mensagens do Telegram."""
    def __init__(self, db_manager: DatabaseManager, ai_assistant: AIAssistant, bot_services: BotServices, messages: dict):
        self.db_manager = db_manager
        self.ai_assistant = ai_assistant
        self.bot_services = bot_services
        self.welcome_message = messages['WELCOME_MESSAGE']

    # ================================== Handler Command Default ==================================
    async def start(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = update.message.from_user.first_name
        self.db_manager.salvar_usuario(user_id, nome)
        self.ai_assistant.reset_history(user_id) # Inicializa/reseta o histórico
        await update.message.reply_text(f'Olá, {nome}! {self.welcome_message}')

    async def reset(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        self.ai_assistant.reset_history(user_id)
        await update.message.reply_text('Conversação reiniciada. Pode perguntar algo novo!')

    # ================================== Handlers Command Custom ==================================
    async def agenda(self, update: Update, context: CallbackContext):
        # Este handler cuida do comando /agenda <serviço> <data> <hora>
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        args = context.args

        if len(args) < 3:
            await update.message.reply_text(
                f'{nome}, use o formato: /agenda <serviço> <data: DD/MM/AAAA> <hora: HH:MM>\n'
                f'Exemplo: /agenda corte degradê 20/10/2025 09:00'
            )
            return

        # Simula a Intencao para reusar a lógica do serviço
        servico_nome = ' '.join(args[:-2]).strip()
        dados = Intencao(
            intent='AGENDAR',
            servico_nome=servico_nome,
            data=args[-2], # Passa a data e hora bruta
            hora=args[-1]
        )
        
        # Chama a lógica de serviço para processar o agendamento
        await self.bot_services.handle_agendamento_estruturado(update, dados)

    async def servicos(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        servicos = self.db_manager.buscar_servicos('')
        if not servicos:
            await update.message.reply_text(f'{nome}, nenhum serviço disponível.')
            return
        resposta = "Serviços disponíveis:\n" + "\n".join([
            f"- {s['nome']}: {s['descricao']} (R${s['preco']:.2f}, {s['duracao_minutos']} min)"
            for s in servicos
        ])
        await update.message.reply_text(f'{nome}, {resposta}')

    # ===================================== ANSWER (Principal) =====================================
    async def answer(self, update: Update, context: CallbackContext):
        """Handler principal: Roteamento de mensagens baseada em Intenção."""
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        original_question = update.message.text
        logger.info(f"Mensagem recebida de {nome} (user_id: {user_id}): {original_question}")

        # 1. Extração/Roteamento de Intenção com a IA
        dados_estruturados = self.ai_assistant.extract_intent_and_data(original_question)

        # 2. Roteamento baseado na Intenção
        is_handled = False
        if dados_estruturados.intent == 'AGENDAR':
            # Chama o serviço de agendamento com dados estruturados
            is_handled = await self.bot_services.handle_agendamento_estruturado(update, dados_estruturados)
            
        elif dados_estruturados.intent == 'BUSCAR_SERVICO':
            # Chama o serviço de busca com dados estruturados
            is_handled = await self.bot_services.handle_buscar_servicos_estruturado(update, dados_estruturados)
        
        # 3. Resposta padrão (Intenção GENERICO ou falha no tratamento)
        if not is_handled or dados_estruturados.intent == 'GENERICO':
            # Usa o termo corrigido/extraído pela IA para a pergunta genérica
            question_to_gpt = dados_estruturados.servico_nome or original_question

            # Chama a LLM genérica
            resposta = self.ai_assistant.ask_gpt(question_to_gpt, user_id)
            await update.message.reply_text(f'{nome}, a IA respondeu: {resposta}')