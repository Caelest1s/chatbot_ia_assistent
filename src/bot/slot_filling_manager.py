# src/bot/slot_filling_manager.py
from telegram import Update
from telegram.ext import ContextTypes

from typing import Optional
from datetime import date, datetime

from src.services.data_service import DataService
from src.services.appointment_service import AppointmentService
from src.schemas.slot_extraction_schema import SlotExtraction

from src.utils.json_utils import prepare_data_for_json

from src.utils.system_message import MESSAGES
from src.utils.constants import REQUIRED_SLOTS

from src.config.logger import setup_logger
logger = setup_logger(__name__)

class SlotFillingManager:
    """[ASYNC] Gerencia o diálogo multi-turno para preencher os slots de agendamento (AGENDAR)"""

    def __init__(
            self,
            data_service: DataService,
            appointment_service: AppointmentService):

        self.data_service = data_service
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
            servicos_nomes = await self.data_service.get_available_services_names()

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
            servico_info = await self.data_service.get_service_details_by_name(servico_nome)

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
                self.data_service.update_slot_data(
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
            servico_info = await self.data_service.get_service_details_by_name(servico_nome)
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
                self.data_service.update_slot_data(
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

    async def handle_slot_filling(self, update: Update, context: ContextTypes.DEFAULT_TYPE, new_slots: SlotExtraction):
        """Gerencia o fluxo principal do Slot Filling, incluindo a resolução de ambiguidades."""

        user_id = update.effective_user.id
        nome = await self.data_service.get_nome_usuario(user_id) or update.effective_user.first_name

        session_state = await self.data_service.get_session_state(user_id)
        current_slots: dict[str, any] = session_state.get('slot_data', {})
        updated_slots = current_slots.copy()

        # 1. Mesclar slots extraídos
        for slot_name in REQUIRED_SLOTS:
            slot_key = 'hora' if slot_name == 'hora_inicio' else slot_name

            new_value = getattr(new_slots, slot_key, None)
            if new_value is not None:
                updated_slots[slot_name] = new_value.strip() if isinstance(new_value, str) else new_value

        # =========================================================
        # 1.5. 📅 TRATAMENTO DE DATA (NORMALIZAÇÃO E VALIDAÇÃO BÁSICA)
        # =========================================================
        data_input = updated_slots.get('data')

        date_obj: Optional[date] = None
        if isinstance(data_input, str):
            data_str = data_input.strip()

            # 1. Tenta o formato ISO (YYYY-MM-DD)
            if len(data_str) == 10 and data_str.count('-') == 2:
                try:
                    date_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
                except ValueError:
                    pass

            # 2. Se não for ISO, tenta os formatos DD/MM/YYYY ou DD-MM-YYYY (input do usuário/LLM)
            if date_obj is None:
                # O validador agora retorna (sucesso, msg_erro, data_string_DD/MM/YYYY)
                is_valid, msg_erro, data_str_dd_mm_yyyy = self.appointment_service.validator.normalize_date_format(data_str)

                if is_valid and isinstance(data_str_dd_mm_yyyy, str):
                    try:
                        # Se for válido, converte a string normalizada de volta para objeto date
                        date_obj = datetime.strptime(data_str_dd_mm_yyyy, '%d/%m/%Y').date()
                    except ValueError:
                        # Erro interno de conversão - deve ser tratado como falha
                        is_valid = False
                        msg_erro = "Erro interno no formato de data. Tente novamente."
                
                if not is_valid:
                    # Falha de validação de formato
                    await update.message.reply_text(msg_erro.format(nome=nome))
                    updated_slots.pop('data', None)
                    serializable_slots = prepare_data_for_json(updated_slots)
                    await self.data_service.update_session_state(user_id, current_intent='AGENDAR'
                                                                 , slot_data=serializable_slots)
                    return True
        
        # O Caso em que data_input é um objeto date (para re-execução) foi removido pois 
        # agora gravamos sempre como string ISO no final do bloco.
        
        # SE CHEGOU AQUI: temos um date_obj válido → gravamos SEMPRE como string ISO
        if date_obj is not None:
            updated_slots['data'] = date_obj.strftime('%Y-%m-%d') # SEMPRE string ISO no dict

        # 2. TRATAMENTO E VALIDAÇÃO DE SERVIÇO
        servico_nome_atual = updated_slots.get('servico_nome')
        session_ambiguity: Optional[dict[str, any]] = updated_slots.get(
            'ambiguous_service_options')

        # 2.0. AJUSTE CRÍTICO: FORÇAR RESET DE AMBIGUIDADE PENDENTE
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

            resolved_servicos = await self.data_service.buscar_servicos(term_to_search)

            # Tenta buscar apenas pelo termo curto como fallback (ex: 'feminino' sozinho)
            if not resolved_servicos:
                resolved_servicos = await self.data_service.buscar_servicos(servico_nome_atual)

            if len(resolved_servicos) == 1:
                # Ambiguidade RESOLVIDA!
                updated_slots['servico_nome'] = resolved_servicos[0]['nome']
                updated_slots.pop('ambiguous_service_options', None)
            else:
                # Ambiguidade NÃO resolvida
                await update.message.reply_text(
                    f"Ainda não consegui entender qual serviço você deseja. "
                    "Por favor, diga o nome **exato** do serviço que você viu na lista."
                )
                serializable_slots = prepare_data_for_json(updated_slots)
                await self.data_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=serializable_slots)
                return True

        # 2.2. Validar o Serviço (Detecção inicial, só executa se o serviço ainda não foi resolvido)
        if servico_nome_atual and 'ambiguous_service_options' not in updated_slots:

            servicos_encontrados = await self.data_service.buscar_servicos(servico_nome_atual)
            if len(servicos_encontrados) == 0:
                # Serviço não encontrado.
                nomes_servicos = await self.data_service.get_available_services_names()

                sugestao = ""
                if nomes_servicos:
                    if len(nomes_servicos) <= 4:
                        sugestao = "\n\n👉 Nossos serviços principais são: " + \
                            ", ".join(nomes_servicos[:4]) + "."
                    else:
                        sugestao = "\n\n👉 Você pode usar o comando /servicos para ver a lista completa."

                resposta_erro = MESSAGES['VALIDATION_SERVICE_NOT_FOUND'].format(
                    nome=nome, servico=servico_nome_atual)

                resposta_completa = f"{resposta_erro}.{sugestao}"
                await update.message.reply_text(resposta_completa)

                updated_slots.pop('servico_nome', None)
                await self.data_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=updated_slots)
                return True

            elif len(servicos_encontrados) > 1:
                # Ambiguidade DETECTADA! (Primeira vez que o termo gera múltiplos resultados)

                # 1. Salva o contexto de ambiguidade na sessão (ISSO JÁ OCORREU E ESTÁ NO SEU LOG)
                updated_slots['ambiguous_service_options'] = {
                    'original_term': servico_nome_atual,
                    'options': [s['servico_id'] for s in servicos_encontrados if s.get('servico_id') is not None]
                }

                # 2. MONTAGEM DA MENSAGEM:
                opcoes = "\n".join(
                    [f"- {s.get('nome', 'Serviço sem nome')} (R${s.get('preco', 0.0):.2f})" for s in servicos_encontrados])
                await update.message.reply_text(f"Encontrei mais de uma opção para '{servico_nome_atual}':\n{opcoes}\nQual deles você gostaria de agendar?")

                # 3. Persiste o estado e interrompe
                serializable_slots = prepare_data_for_json(updated_slots)
                await self.data_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=serializable_slots)
                return True

            elif len(servicos_encontrados) == 1:
                # Serviço único:
                updated_slots['servico_id'] = servicos_encontrados[0]['servico_id']
                updated_slots['servico_nome'] = servicos_encontrados[0]['nome']
                updated_slots.pop('ambiguous_service_options', None)

        # 3. Verificar slots faltantes
        # Garante que o serviço ambíguo não é considerado um slot faltante para forçar a pergunta
        missing_slots = [
            slot for slot in REQUIRED_SLOTS
            if slot not in updated_slots or updated_slots[slot] is None or updated_slots[slot] == ''
        ]

        # A ambiguidade resolvida deve ser suficiente, mas se o ID não foi resolvido, precisamos do nome/ID
        if 'servico_nome' in missing_slots and 'servico_id' not in updated_slots:
            # O slot principal é 'servico_id'. Se ele estiver faltando, pedimos o nome.
            # Garante que pedimos o nome
            missing_slots[missing_slots.index('servico_nome')] = 'servico_nome'

        if not missing_slots:
            # 4. Todos os slots preenchidos: Finalizar Agendamento
            # Os slots agora incluem o servico_id

            # Passa a data e hora normalizadas para o AppointmentService.process_appointment
            # O AppointmentService deve converter o objeto date/datetime para string antes de chamar o Repository.
            is_successful, response_msg = await self.appointment_service.process_appointment(
                user_id=user_id,
                slot_data=updated_slots
            )

            await update.message.reply_text(response_msg)

            if is_successful:
                # O AppointmentService já gerencia o commit; limpamos a sessão.
                # Assumindo que você tem um método clear_session_state
                await self.data_service.clear_session_state(user_id)
            else:
                # Se falhar, limpamos slots problemáticos ou mantemos o estado
                serializable_slots = prepare_data_for_json(updated_slots)
                await self.data_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=serializable_slots)
            return True

        else:
            # 5. Slots Faltando: Solicitar o Próximo
            # Persiste o estado atual dos slots
            serializable_slots = prepare_data_for_json(updated_slots)
            await self.data_service.update_session_state(user_id, current_intent='AGENDAR', slot_data=serializable_slots)
            await self._ask_for_next_slot(update, context, nome, updated_slots, missing_slots)
            return True
