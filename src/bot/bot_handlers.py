# src/bot/bot_handlers.py

import logging
from telegram import Update
from telegram.ext import CallbackContext
from telegram.ext import ContextTypes

from src.bot.database_manager import DatabaseManager
from src.bot.ai_assistant import AIAssistant
from src.bot.bot_services import BotServices
from src.schemas.slot_extraction_schema import SlotExtraction
from src.utils import MESSAGES
from datetime import datetime

logger = logging.getLogger(__name__)
REQUIRED_SLOTS = ["servico_nome", "data", "hora"]

class BotHandlers:
    """Implementa todos os handlers de comandos e mensagens do Telegram."""
    def __init__(self, db_manager: DatabaseManager, ai_assistant: AIAssistant, bot_services: BotServices, messages: dict):
        self.db_manager = db_manager
        self.ai_assistant = ai_assistant
        self.bot_services = bot_services
        self.messages = messages # Pega todo o meu dictionary MESSAGES

    # ================================== Handler Command Default ==================================
    async def start(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = update.message.from_user.first_name
        self.db_manager.salvar_usuario(user_id, nome)
        self.ai_assistant.reset_history(user_id) # Inicializa/reseta o histórico
        await update.message.reply_text(f'Olá, {nome}! {self.messages['WELCOME_MESSAGE']}')

    async def reset(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        self.ai_assistant.reset_history(user_id)
        await update.message.reply_text('Conversação reiniciada. Pode perguntar algo novo!')

    # ================================== Handlers Command Custom ==================================
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

    async def agenda(self, update: Update, context: CallbackContext):
        """Inicia o processo de agendamento via comando /agenda ou reusado em Slot Filling."""
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        args = context.args

        if context.args:
            # Lógica antiga de agendamento rápido (1 turno)
            servico_nome = ' '.join(context.args[:-2]).strip()
            dados = SlotExtraction(intent='AGENDAR', servico_nome=servico_nome, data=context.args[-2], hora=context.args[-1])
            return await self.bot_services.handle_agendamento_estruturado(update, context, dados)
            
        # Se for comando /agenda sem args, inicia o Slot Filling (Multi-turno)
        self.db_manager.clear_session_state(user_id)
        self.db_manager.update_session_state(user_id, current_intent='AGENDAR', slot_data={})
        await update.message.reply_text(MESSAGES['SLOT_FILLING_WELCOME'].format(nome=nome))

    # ===================================== ANSWER (Principal) =====================================
    async def answer(self, update: Update, context: CallbackContext):
        """Handler principal: Roteamento de mensagens baseada em Intenção e Estado."""
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        original_question = update.message.text
        logger.info(f"Mensagem recebida de {nome} (user_id: {user_id}): {original_question}")

        # 1. Recuperar o estado da sessão (IMPORTANTE para Slot Filling)
        session_state = self.db_manager.get_session_state(user_id)
        current_intent = session_state.get('current_intent')
        logger.info(f"User {user_id} - Estado atual: {current_intent}. Input: {original_question}")

        # 2. Extração/Roteamento de Intenção com a IA
        dados_estruturados: SlotExtraction = self.ai_assistant.extract_intent_and_data(original_question)
        
        # Prioridade para INTENÇÕES DE INTERRUPÇÃO/MUDANÇA
        if dados_estruturados.intent in ['RESET', 'SERVICOS']:
            self.db_manager.clear_session_state(user_id) # Limpa o estado se mudar o tópico
            if dados_estruturados.intent == 'RESET':
                return await self.reset(update, context)
            if dados_estruturados.intent == 'SERVICOS':
                return await self.servicos(update, context)
                
        # 3. Tratamento do Fluxo de Agendamento (Slot Filling)
        if dados_estruturados.intent == 'AGENDAR' or current_intent == 'AGENDAR':
            # Se a IA detectar 'AGENDAR' ou se o usuário JÁ ESTIVER no fluxo
            return await self._handle_slot_filling(update, context, dados_estruturados)
            
        # 4. Tratamento de Outras Intenções (GENERICO, BUSCAR_SERVICO)
        is_handled = False
        if dados_estruturados.intent == 'BUSCAR_SERVICO':
            is_handled = await self.bot_services.handle_buscar_servicos_estruturado(update, context, dados_estruturados)
        
        # 5. Resposta Padrão (GENERICO ou falha no tratamento)
        if not is_handled or dados_estruturados.intent == 'GENERICO':
            # Limpa o estado se a intenção for genérica, prevenindo diálogos abandonados
            if current_intent:
                self.db_manager.clear_session_state(user_id)
                
            question_to_gpt = dados_estruturados.servico_nome or original_question
            resposta = self.ai_assistant.ask_gpt(question_to_gpt, user_id)
            await update.message.reply_text(f'{nome}, a IA respondeu: {resposta}')
    
    async def _handle_slot_filling(self, update: Update, context: CallbackContext, new_slots: SlotExtraction):
        """Gerencia o diálogo multi-turno para preencher os slots de agendamento."""
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        
        # 1. Recuperar e Mesclar o Estado Atual
        session_state = self.db_manager.get_session_state(user_id)
        current_slots = session_state.get('slot_data', {})
        
        # Mesclar os slots extraídos da nova mensagem sobre os slots atuais
        updated_slots = current_slots.copy()
        
        # Mesclar novos slots sobre os atuais
        for slot_name in REQUIRED_SLOTS:
            # 'new_slots' é o objeto SlotExtraction que vem da IA
            new_value = getattr(new_slots, slot_name, None)

            # ATENÇÃO: Se new_value for string (válido), atualiza o slot
            # Se new_value for None, o slot atual (em updated_slots) NÃO é alterado.
            if new_value:
                # O valor é extraído e atualizado
                updated_slots[slot_name] = new_value.strip()

        # =================================================================
        # 2. VALIDAÇÃO DE SERVIÇO (Ambiguidade) - Ponto de Interrupção
        # =================================================================
        servico_nome_atual = updated_slots.get('servico_nome')

        if servico_nome_atual:
            servicos_encontrados = self.db_manager.buscar_servicos(servico_nome_atual)

            if len(servicos_encontrados) == 0:
                # Serviço não encontrado: feedback e remove o slot para pedir novamente.
                del updated_slots['servico_nome']
                await update.message.reply_text(MESSAGES['VALIDATION_SERVICE_NOT_FOUND'].format(nome=nome, servico=servico_nome_atual))
                # Prossegue para o ponto 3.

            elif len(servicos_encontrados) > 1:
                # Múltiplos serviços: INTERROMPE o fluxo e pede esclarecimento.
                # Remove o slot, forçando o sistema a pedir o serviço novamente no próximo passo.
                del updated_slots['servico_nome']

                # Persiste o estado atual sem o slot ambíguo
                self.db_manager.update_session_state(
                    user_id=user_id,
                    current_intent='AGENDAR',
                    slot_data=updated_slots
                )

                # Envia a mensagem de ambiguidade (opções)
                opcoes = "\n".join([f"- {s['nome']} (R${s['preco']:.2f})" for s in servicos_encontrados])
                await update.message.reply_text(f"Encontrei mais de uma opção para '{servico_nome_atual}':\n{opcoes}\nQual deles você gostaria de agendar?")
                return True # Tratado, aguarda nova resposta (não prossegue para a busca de data/hora).
            
            elif len(servicos_encontrados) == 1:
                # Serviço único: Garante que o nome exato do serviço é usado para o agendamento final
                updated_slots['servico_nome'] = servicos_encontrados[0]['nome']
                # Prossegue normalmente

        # 3. Persistir o Novo Estado (Intenção AGENDAR e slots mesclados)
        self.db_manager.update_session_state(
            user_id=user_id,
            current_intent='AGENDAR',
            slot_data=updated_slots
        )
        
        # 4. Verificar quais slots ainda faltam
        missing_slots = [slot for slot in REQUIRED_SLOTS if slot not in updated_slots]
        
        
        if not missing_slots:
            # 5. Todos os slots preenchidos: Concluir o Agendamento
            
            # 1. Cria o objeto SlotExtraction (lembrando de adicionar a Intent corrigida)
            updated_slots['intent'] = session_state.get('current_intent', 'AGENDAR')
            dados_completos = SlotExtraction(**updated_slots)

            # 2. Roteia para o serviço de agendamento
            # Aqui está o ponto crucial: qual serviço é chamado?
            if dados_completos.intent == 'AGENDAR':
                is_successful = await self.bot_services.handle_agendamento_estruturado(update, context, dados_completos)
            
            elif dados_completos.intent == 'BUSCAR_SERVICO':
                is_successful = await self.bot_services.handle_buscar_servicos_estruturado(update, context, dados_completos)
            else:
                is_successful = False # Ou trata como erro

            # SlotExtraction (herda de pydantic.BaseModel) que requer o campo intent
            # is_successful = await self.bot_services.handle_agendamento_estruturado(update, SlotExtraction(**updated_slots))
            
            if is_successful:
                # O serviço de agendamento deve enviar a mensagem de sucesso
                # Se quiser que o Handler envie:
                await context.bot.send_message(chat_id=user_id, text=self.messages['AGENDAMENTO_SUCESSO']) # O próprio serviço deve enviar a mensagem
                self.db_manager.clear_session_state(user_id) # Limpa o estado APENAS no sucesso final.
                return
            
            # Se is_successful for False: Erro técnico grave. O BotService já enviou a mensagem de erro.
            # A sessão deve ser limpa para evitar loops:
            self.db_manager.clear_session_state(user_id)
            return
        else:
            # 6. Slots Faltando: Solicitar o Próximo Slot
            # O código para pedir data e hora (o mesmo que você já tem)
            next_slot = missing_slots[0]

            # Lógica para gerar a próxima pergunta...
            # (Seu código original que pede data/hora)

            # Lógica para gerar a próxima pergunta
            if next_slot == 'servico_nome':
                response = MESSAGES['SLOT_FILLING_ASK_SERVICE'].format(nome=nome)
            elif next_slot == 'data':
                response = MESSAGES['SLOT_FILLING_ASK_DATE'].format(nome=nome, servico=updated_slots.get('servico_nome', 'o serviço'))
            elif next_slot == 'hora':
                response = MESSAGES['SLOT_FILLING_ASK_TIME'].format(nome=nome, data=updated_slots.get('data', 'a data'))
            else:
                 response = MESSAGES['SLOT_FILLING_GENERAL_PROMPT'].format(nome=nome)

            await update.message.reply_text(response)
            
        return True # Indica que a mensagem foi tratada pelo Slot Filling