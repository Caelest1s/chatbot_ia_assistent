# src/bot/slot_filling_manager.py
from telegram import Update
from telegram.ext import ContextTypes

from typing import Optional
from datetime import date, datetime

from src.services.persistence_service import PersistenceService
from src.services.appointment_service import AppointmentService

from src.utils.json_utils import prepare_data_for_json

from src.utils.system_message import MESSAGES
from src.utils.constants import REQUIRED_SLOTS

from src.config.logger import setup_logger
logger = setup_logger(__name__)

class SlotFillingManager:
    """[ASYNC] Gerencia o diálogo multi-turno para preencher os slots de agendamento (AGENDAR)"""

    def __init__(
            self,
            persistence_service: PersistenceService,
            appointment_service: AppointmentService):

        self.persistence_service = persistence_service
        self.appointment_service = appointment_service

    async def _ask_for_next_slot(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            nome: str,
            updated_slots: dict[str, any],
            missing_slots: list[str]):
        """Envia a mensagem ao usuário pedindo o próximo slot em falta."""

        next_slot = missing_slots[0]

        if next_slot == 'servico_nome':
            # 1. Busca a lista de serviços disponíveis
            servicos_nomes = await self.persistence_service.get_available_services_names()

            if servicos_nomes:
                lista_servicos = "\n".join(
                    [f"  - {s}" for s in servicos_nomes])
                # Use uma mensagem mais descritiva com a lista
                response = (
                    MESSAGES['SLOT_FILLING_ASK_SERVICE'].format(nome=nome) +
                    f"\n\n**Estes são nossos serviços disponíveis:**\n{lista_servicos}" +
                    "\n\nPor favor, digite o nome do serviço que deseja agendar."
                )
            else:
                # Mensagem de fallback se não houver serviços ativos
                response = MESSAGES['SLOT_FILLING_ASK_SERVICE'].format(
                    nome=nome)

        elif next_slot == 'data':
            response = MESSAGES['SLOT_FILLING_ASK_DATE'].format(
                nome=nome, servico=updated_slots.get('servico_nome', 'o serviço'))

        elif next_slot == 'turno':
            # 1. Obter duração do serviço
            servico_nome = updated_slots['servico_nome']
            servico_info = await self.persistence_service.get_service_details_by_name(servico_nome)

            if not servico_info:
                response = MESSAGES['ERROR_SERVICE_NOT_FOUND'].format(
                    nome=nome)
                return await update.message.reply_text(response)

            duracao = servico_info['duracao_minutos']
            data_agendamento = updated_slots['data']

            # 2. Obter turnos disponíveis
            turnos_disponiveis = await self.appointment_service.get_available_shifts(
                data=data_agendamento,
                duracao_minutos=duracao
            )

            if not turnos_disponiveis:
                # Se não houver turnos livres, informar e pedir uma nova data
                response = MESSAGES['SLOT_FILLING_NO_AVAILABILITY'].format(
                    nome=nome, servico=servico_nome, data=data_agendamento
                )

                # Força o bot a pedir a data novamente, limpando o slot 'data'
                self.persistence_service.update_slot_data(
                    update.effective_user.id, 'data', None)
                await update.message.reply_text(response)
                return  # Interrompe o fluxo e pede a data novamente

            else:
                lista_turnos = ", ".join(
                    [f"**{t}**" for t in turnos_disponiveis])
                response = MESSAGES['SLOT_FILLING_ASK_SHIFT'].format(
                    nome=nome, data=data_agendamento, lista_turnos=lista_turnos
                )

        elif next_slot == 'hora_inicio':
            turno_selecionado = updated_slots.get('turno')
            data_agendamento = updated_slots.get('data')
            servico_nome = updated_slots['servico_nome']

            # 1. Reobter duração
            servico_info = await self.persistence_service.get_service_details_by_name(servico_nome)
            duracao = servico_info['duracao_minutos']

            # 2. Obter horários disponíveis para o turno
            horarios_livres = await self.appointment_service.get_available_times_by_shift(
                data=data_agendamento,
                turno=turno_selecionado,
                duracao_minutos=duracao
            )

            if not horarios_livres:
                # Deve ser raro, mas é uma segurança
                response = MESSAGES['SLOT_FILLING_SHIFT_FULL'].format(
                    nome=nome, turno=turno_selecionado
                )

                # Força a pedir o turno novamente
                self.persistence_service.update_slot_data(
                    update.effective_user.id, ' turno', None)
                await update.message.reply_text(response)
                return

            # 3. Montar a lista (apresentar apenas os 8 primeiros para não poluir)
            horarios_display = horarios_livres[:8]
            lista_horarios = ", ".join(horarios_display)

            response = MESSAGES['SLOT_FILLING_ASK_SPECIFIC_TIME'].format(
                nome=nome, data=data_agendamento, turno=turno_selecionado, horarios=lista_horarios
            )

        else:
            response = MESSAGES['SLOT_FILLING_GENERAL_PROMPT'].format(
                nome=nome)

        await update.message.reply_text(response)

    async def handle_slot_filling(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gerencia o fluxo principal do Slot Filling, incluindo a resolução de ambiguidades."""

        user_id = update.effective_user.id
        nome = await self.persistence_service.get_nome_usuario(user_id) or update.effective_user.first_name

        # 1. Obtém o estado ATUALIZADO (que já contém os slots limpos e enriquecidos pelo DataService)
        session_state = await self.persistence_service.get_session_state(user_id)
        current_slots: dict[str, any] = session_state.get('slot_data', {})
        updated_slots = current_slots.copy()

        if 'hora' in updated_slots:
            # Renomeia 'hora' para 'hora_inicio' para consistência
            # Usa .pop() para mover o valor e remover a chave antiga, evitando duplicidade
            updated_slots['hora_inicio'] = updated_slots.pop('hora')
            logger.debug(f"Slot 'hora' renomeado para 'hora_inicio' para validação final.")

        # 2. TRATAMENTO E VALIDAÇÃO DE SERVIÇO
        servico_nome_atual = updated_slots.get('servico_nome')
        session_ambiguity: Optional[dict[str, any]] = updated_slots.get(
            'ambiguous_service_options')

        # FORÇAR RESET DE AMBIGUIDADE PENDENTE
        # Se um NOVO servico_nome foi extraído (e não é uma resposta a uma pergunta),
        # limpamos qualquer estado de ambiguidade persistente.
        is_new_service_term = servico_nome_atual and (
            'servico_nome' != current_slots.get('servico_nome'))

        if is_new_service_term and session_ambiguity:
            logger.warning(
                "Novo termo de serviço fornecido. Resetando ambiguidade pendente.")
            updated_slots.pop('ambiguous_service_options', None)
            session_ambiguity = None  # Atualiza a variável local para o próximo passo

        # 2.1. Tentar Resolver Ambiguidade (Fluxo de Resposta à Pergunta)
        if servico_nome_atual and session_ambiguity:
            # Usa o termo original + o termo da resposta (ex: "corte de cabelo feminino")
            original_term = session_ambiguity.get('original_term', '')
            term_to_search = f"{original_term} {servico_nome_atual}"

            resolved_servicos = await self.persistence_service.buscar_servicos(term_to_search)

            # Tenta buscar apenas pelo termo curto como fallback (ex: 'feminino' sozinho)
            if not resolved_servicos:
                resolved_servicos = await self.persistence_service.buscar_servicos(servico_nome_atual)

            if len(resolved_servicos) == 1:
                # Ambiguidade RESOLVIDA!
                updated_slots['servico_nome'] = resolved_servicos[0]['nome']
                updated_slots['servico_id'] = resolved_servicos[0]['servico_id']
                updated_slots.pop('ambiguous_service_options', None)
            else:
                # Ambiguidade NÃO resolvida
                await update.message.reply_text(
                    f"Ainda não consegui entender qual serviço você deseja. "
                    "Por favor, diga o nome **exato** do serviço que você viu na lista."
                )
                serializable_slots = prepare_data_for_json(updated_slots)
                await self.persistence_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=serializable_slots)
                return True

        # 3. Verificar slots faltantes
        # Garante que o serviço ambíguo não é considerado um slot faltante para forçar a pergunta
        missing_slots = [
            slot for slot in REQUIRED_SLOTS
            if slot not in updated_slots or updated_slots[slot] is None or updated_slots[slot] == ''
        ]

        # Garantir que se 'servico_id' falta, pedimos 'servico_nome'
        if 'servico_id' not in updated_slots and 'servico_nome' in REQUIRED_SLOTS:
            # Se o ID não está, e o nome é requerido, pedimos o nome.
            if 'servico_nome' not in missing_slots:
                missing_slots.append('servico_nome') # Garante que 'servico_nome' é o que será solicitado
                missing_slots = [s for s in missing_slots if s != 'servico_id']

        if not missing_slots:
            # 4. Todos os slots preenchidos: Finalizar Agendamento
            is_successful, response_msg = await self.appointment_service.process_appointment(
                user_id=user_id,
                slot_data=updated_slots
            )

            await update.message.reply_text(response_msg)

            if is_successful:
                await self.persistence_service.clear_session_state(user_id)
            else:
                # Se falhar, limpamos slots problemáticos ou mantemos o estado
                serializable_slots = prepare_data_for_json(updated_slots)
                await self.persistence_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=serializable_slots)
            return True

        else:
            # 5. Slots Faltando: Solicitar o Próximo
            serializable_slots = prepare_data_for_json(updated_slots)
            await self.persistence_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=serializable_slots)
            await self._ask_for_next_slot(update, context, nome, updated_slots, missing_slots)
            return True
