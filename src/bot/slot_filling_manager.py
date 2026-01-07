# src/bot/slot_filling_manager.py
from telegram import Update
from telegram.ext import ContextTypes

from src.services.appointment_service import AppointmentService
from src.services.persistence_service import PersistenceService

from src.utils.helpers import SafeDict
from src.utils.system_message import MESSAGES
from src.utils.constants import REQUIRED_SLOTS

from src.config.logger import setup_logger
logger = setup_logger(__name__)

class SlotFillingManager:
    """[ASYNC] Gerencia o diálogo multi-turno para preencher os slots de agendamento (AGENDAR)"""

    def __init__(self, persistence_service: PersistenceService, appointment_service: AppointmentService):

        self.persistence_service = persistence_service
        self.appointment_service = appointment_service

    async def _ask_for_next_slot(self, update: Update, nome: str, updated_slots: dict, missing_slots: list):
        """Pergunta o próximo slot baseado nas chaves do Schema e DB."""
        if not missing_slots:
            return
        
        next_slot = missing_slots[0]
        response = None

        # PREPARAÇÃO DO CONTEXTO SEGURO 
        ctx = SafeDict(nome=nome) # Criamos o SafeDict injetando o nome e os slots já preenchidos
        ctx.update(updated_slots) # Agora ctx tem: nome, servico, data, turno, etc. (o que estiver disponível)

        # Se falta servico_id, perguntamos pelo 'servico' (nome)
        if next_slot == 'servico_id':
            servicos = await self.persistence_service.get_available_services_names()

            if not servicos:
                await update.message.reply_text("Ops, Não encontrei serviços disponíveis no momento. Tente novamente mais tarde.")
                return
            
            lista_servicos = "\n".join([f"  - {s}" for s in servicos])
            # Use uma mensagem mais descritiva com a lista
            response = MESSAGES['SLOT_FILLING_ASK_SERVICE'].format_map(ctx)
            response += f"\n\n**Serviços Disponíveis:**\n{lista_servicos}"
            
            # if lista_servicos: Poderei remover essa verificação depois
            #     response += f"\n\n**Opções:**\n{lista_servicos}"
            
        elif next_slot == 'data':
            response = MESSAGES['SLOT_FILLING_ASK_DATE'].format_map(ctx)

        elif next_slot == 'turno':
            # Proteção: Se por algum motivo o servico_id sumiu, volta um passo
            sid = updated_slots.get('servico_id')
            if not sid:
                missing_slots.insert(0, 'servico_id')
                return await self._ask_for_next_slot(update, nome, updated_slots, missing_slots)
            
            # Usa servico_id e data para validar turnos reais
            servico_info = await self.persistence_service.get_service_details_by_id(updated_slots['servico_id'])
            duracao = servico_info['duracao_minutos']
            turnos = await self.appointment_service.get_available_shifts(data=updated_slots['data'], duracao_minutos=duracao)

            if not turnos:
                # Se não houver turnos livres, informar e pedir uma nova data
                response = MESSAGES['SLOT_FILLING_NO_AVAILABILITY'].format_map(ctx)
                updated_slots.pop('data', None) # Limpa data para o bot pedir outra
                await self.persistence_service.update_session_state(
                    update.effective_user.id
                    , slot_data=updated_slots
                )
            else:
                ctx['lista_turnos'] = ", ".join([f"**{t}**" for t in turnos])
                response = MESSAGES['SLOT_FILLING_ASK_SHIFT'].format_map(ctx)

        elif next_slot == 'hora_inicio':
            servico_info = await self.persistence_service.get_service_details_by_id(updated_slots['servico_id'])
            duracao = servico_info['duracao_minutos']

            # 2. Obter horários disponíveis para o turno
            horarios_livres = await self.appointment_service.get_available_times_by_shift(
                data=updated_slots['data'],
                turno=updated_slots['turno'],
                duracao_minutos=duracao
            )

            if not horarios_livres:
                # Deve ser raro, mas é uma segurança
                response = MESSAGES['SLOT_FILLING_SHIFT_FULL'].format_map(ctx)
                updated_slots.pop('turno', None)
                await self.persistence_service.update_session_state(update.effective_user.id, slot_data=updated_slots)
            else:
                    # 3. Montar a lista (apresentar apenas os 8 primeiros para não poluir)
                ctx['horarios'] = ", ".join(horarios_livres[:8])
                response = MESSAGES['SLOT_FILLING_ASK_SPECIFIC_TIME'].format_map(ctx)
        
        if response:
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            logger.warning(f"Nenhuma resposta gerada para o slot: {next_slot}")

    async def handle_slot_filling(self, update: Update, context: ContextTypes.DEFAULT_TYPE, slots_from_db: dict = None):
        user_id = update.effective_user.id
        nome = await self.persistence_service.get_nome_usuario(user_id) or update.effective_user.first_name

        if slots_from_db is not None:
            updated_slots = slots_from_db
        else:
            # 1. Obtém o estado ATUAL da sessão
            session_state = await self.persistence_service.get_session_state(user_id)
            updated_slots = session_state.get('slot_data', {}) if session_state else {}

        # Validação: REQUIRED_SLOTS = ["servico_id", "data", "turno", "hora_inicio"]
        missing_slots = [s for s in REQUIRED_SLOTS if not updated_slots.get(s)]

        if not missing_slots:
            # 4. Todos os slots preenchidos: Finalizar Agendamento
            sucess, msg = await self.appointment_service.process_appointment(user_id=user_id,slot_data=updated_slots)
            await update.message.reply_text(msg)

            if sucess:
                await self.persistence_service.clear_session_state(user_id)
            return True

        # Slots Faltando: Solicitar o Próximo
        await self._ask_for_next_slot(update, nome, updated_slots, missing_slots)
        return True
    
    async def get_next_missing_slot(self, user_id: int) -> str:
        """Analisa o estado e pergunta pelo próximo slot na fila de prioridade."""
        session_state = await self.persistence_service.get_session_state(user_id)
        updated_slots = session_state.get('slot_data', {})

        for slot in REQUIRED_SLOTS:
            if not updated_slots.get(slot):
                return slot
        return "NENHUM"
