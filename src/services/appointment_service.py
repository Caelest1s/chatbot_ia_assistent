# src/services/appointment_service.py
from typing import Optional, Dict, Tuple, List, Any
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.services.data_service import DataService
from src.schemas.slot_extraction_schema import SlotExtraction
from src.services.appointment_validator import AppointmentValidator

from src.utils.system_message import MESSAGES
from src.utils.constants import SHIFT_TIMES

logger = logging.getLogger(__name__)


class AppointmentService:
    """Lógica de negócio para a criação de agendamentos."""

    def __init__(self, data_service: DataService, validator: AppointmentValidator):
        """Valida se todos os slots necessários estão preenchidos e formatados."""
        # Esta função é presumida como síncrona, pois não acessa o DB.
        # Sua implementação real deve estar em src/services/appointment_validator.py
        self.data_service = data_service
        self.validator = validator

    async def handle_agendamento_estruturado(
            self
            , update: Update
            , context: ContextTypes.DEFAULT_TYPE
            , dados: SlotExtraction) -> tuple[bool, str]:
        """
        Processa a intenção AGENDAR com dados extraídos.
        Retorna (True, 'Mensagem de sucesso/erro tratada') ou (False, 'Erro interno não tratado').
        """
        user_id = update.effective_user.id
        nome = self.data_service.get_nome_usuario(
            user_id) or update.effective_user.first_name

        servico_nome = dados.servico_nome.strip()
        data_str = dados.data
        hora_str = dados.hora

        # 1. VALIDAÇÃO DE SERVIÇO (Garante que é unívoco)
        servicos_encontrados = self.data_service.buscar_servicos(servico_nome)
        if len(servicos_encontrados) != 1:
            # O SlotFillingManager deveria prevenir isso, mas é uma segurança.
            await update.message.reply_text(MESSAGES['VALIDATION_SERVICE_NOT_FOUND'].format(nome=nome, servico=servico_nome))
            return True, f"Serviço ambíguo ou não encontrado: {servico_nome}"

        servico = servicos_encontrados[0]
        servico_id = servico['servico_id']

        servico_minutos = servico['duracao_minutos']

        # 2. VALIDAÇÕES DE DATA E HORA
        data_hora_agendamento, erro_msg = self.validator.validate_date_time_format(
            data_str, hora_str)
        if erro_msg:
            await update.message.reply_text(erro_msg.format(nome=nome))
            return True, erro_msg

        erro_msg = self.validator.validate_past_time(data_hora_agendamento)
        if erro_msg:
            await update.message.reply_text(erro_msg.format(nome=nome))
            return True, erro_msg

        erro_msg = self.validator.validate_business_hours(
            data_hora_agendamento)
        if erro_msg:
            await update.message.reply_text(erro_msg.format(nome=nome))
            return True, erro_msg

        try:
            # 3. CHAMADA FINAL DE AGENDAMENTO
            data_dt = data_hora_agendamento.strftime('%Y-%m-%d')
            hora_dt = data_hora_agendamento.strftime('%H:%M')

            sucesso, mensagem = await self.data_service.inserir_agendamento(
                user_id, servico_id, servico_nome, servico_minutos, data_dt, hora_dt)

            # A mensagem de sucesso ou falha (ex: horário indisponível) vem do DBManager
            await update.message.reply_text(f'{nome}, {mensagem}')

            if sucesso:
                await self.data_service.clear_session_state(user_id)

            return True, mensagem

        except Exception as e:
            logger.error(f"Erro ao agendar com dados estruturados: {e}")
            await update.message.reply_text(MESSAGES['ERROR_INTERNAL'].format(nome=nome))
            return False, f"Erro interno: {e}"

    # =========================================================
    # FUNÇÃO DE VALIDAÇÃO DE SLOTS (Completa)
    # =========================================================
    async def validate_slots(self, slot_data: Dict) -> Tuple[bool, str, Optional[Dict]]:
        """
        [ASYNC] Valida todos os slots necessários (serviço, data, hora).
        Retorna (sucesso, mensagem, slots normalizados).
        """
        data_str = slot_data.get('data')
        hora_str = slot_data.get('hora_inicio')
        servico_id = slot_data.get('servico_id')

        # 1. Validação de Regras de Negócio (Data/Hora - Síncrona)
        if data_str and hora_str:
            is_valid, msg, data_hora_obj = self.validator.validate_date_time_rules(
                data_str, hora_str)
            if not is_valid:
                return False, msg, None

            # Normalização: Converte a data e hora para o formato YYYY-MM-DD e HH:MM para o DB
            slot_data['data'] = data_hora_obj.strftime('%Y-%m-%d')
            slot_data['hora_inicio'] = data_hora_obj.strftime('%H:%M')

        elif data_str or hora_str:
            # Se um foi fornecido e o outro não, é inválido
            return False, "Por favor, forneça a data E a hora para agendamento.", None

        # 2. Validação de Serviço (Assíncrona: Checa se o ID existe)
        if servico_id:
            # Assumimos que o DataService tem um método para checar se o ID existe (Ex: get_service_by_id)
            # Como não temos esse método no DataService, vamos simular a busca:

            # Chama o método de busca de serviços (retorna uma lista de dicts)
            servicos_ativos = await self.data_service.get_available_services_names()

            # Se o servico_id for o NOME, precisamos converter para ID
            if isinstance(servico_id, str):
                # O ideal é usar o LLM para resolver o ID, mas aqui, vamos verificar
                return False, "Erro de processamento: O ID do serviço deve ser um número.", None

            # A checagem final de existência do serviço é feita dentro do inserir_agendamento
            # Aqui, apenas verificamos se é um número.

            # Para manter a arquitetura limpa: A checagem de conflito/existência
            # de Serviço é delegada à transação final (inserir_agendamento).
            pass

        # 3. Se todos os slots básicos estão formatados e as regras de tempo atendidas
        return True, "", slot_data

    async def process_appointment(self, user_id: int, slot_data: dict) -> Tuple[bool, str]:
        """[ASYNC] Tenta processar e inserir um agendamento."""
        is_valid, validation_msg, normalized_slots = await self.validate_slots(slot_data)

        if not is_valid:
            return False, validation_msg

        # 2. Extração de slots normalizados
        try:
            # Agora os slots estão no formato esperado pelo DB
            servico_id = normalized_slots.get('servico_id')
            data = normalized_slots.get('data')
            hora_inicio = normalized_slots.get('hora_inicio')

            # Safety check (redundante, mas bom)
            if not servico_id or not data or not hora_inicio:
                return False, "Erro interno: Slots essenciais faltando após normalização."

        except Exception as e:
            logger.error(f"Erro ao extrair slots normalizados: {e}")
            return False, "Erro ao formatar os dados do agendamento."
        
        servico = await self.data_service.get_service_details_by_id(servico_id)
        if not servico:
            logger.error(f"Serviço ID {servico_id} não encontrado para agendamento.")
            return False, "O serviço selecionado não está disponível ou não encontrado."
        
        servico_nome = servico.get('nome')
        servico_minutos = servico.get('duracao_minutos')

        # 3. Inserção do Agendamento (Transação final e checagem de conflito DB)
        success, response_msg = await self.data_service.inserir_agendamento(
            user_id=user_id,
            servico_id=servico_id,
            servico_nome=servico_nome,
            servico_minutos=servico_minutos,
            data=data,
            hora_inicio=hora_inicio
        )

        if success:
            logger.info(
                f"Agendamento do usuário {user_id} concluído com sucesso.")
            return True, response_msg
        else:
            logger.warning(
                f"Agendamento do usuário {user_id} falhou: {response_msg}")
            return False, response_msg

    async def get_available_shifts(self, data: str, duracao_minutos: int) -> list[str]:
        """
        Retorna a lista de turnos (Manhã, Tarde, Noite) que têm pelo menos
        UM horário livre para a duração do serviço na data fornecida.
        """
        disponiveis: list[str] = []

        for shift_name in SHIFT_TIMES.keys():
            # Chamada ao método de cálculo do repositório, filtrando pelo turno
            horarios_livres = await self.data_service.get_available_blocks_for_shift(
                data=data,
                duracao_minutos=duracao_minutos,
                shift_name=shift_name
            )

            if horarios_livres:
                disponiveis.append(shift_name)

        return disponiveis

    async def get_available_times_by_shift(self, data: str, turno: str, duracao_minutos: int) -> list[str]:
        """
        Retorna todos os horários HH:MM livres dentro de um turno específico.
        """
        horarios = await self.data_service.get_available_blocks_for_shift(
            data=data,
            duracao_minutos=duracao_minutos,
            shift_name=turno
        )
        # O método já retorna a lista de strings 'HH:MM'
        return horarios
