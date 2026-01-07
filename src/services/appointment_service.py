# src/services/appointment_service.py
from typing import Optional, Tuple
import logging

from telegram import Update
from telegram.ext import ContextTypes

from src.services.persistence_service import PersistenceService
from src.schemas.slot_extraction_schema import SlotExtraction
from src.services.appointment_validator import AppointmentValidator

from src.utils.system_message import MESSAGES
from src.utils.constants import SHIFT_TIMES

logger = logging.getLogger(__name__)

class AppointmentService:
    """Lógica de negócio para a criação e consulta de disponibilidade de agendamentos."""

    def __init__(self, persistence_service: PersistenceService, validator: AppointmentValidator):
        self.persistence_service = persistence_service
        self.validator = validator

    async def process_appointment(self, user_id: int, slot_data: dict) -> Tuple[bool, str]:
        """Tenta inserir o agendamento no banco após todas as validações de slots."""
        # 1. Validação de Regras de Negócio (Horário comercial, passado, etc.)
        is_valid, validation_msg, normalized_slots = await self.validate_slots(slot_data)

        if not is_valid:
            return False, validation_msg

        # 2. Extração de slots normalizados
        try:
            # 2. Recupera detalhes técnicos do serviço para o cálculo da hora_fim no DB
            servico_id = normalized_slots.get('servico_id')
            servico = await self.persistence_service.get_service_details_by_id(servico_id)

            # Safety check (redundante, mas bom)
            if not servico:
                return False, "O serviço selecionado não foi encontrado no catálogo."
            
            # 3. Inserção final via PersistenceService
            # O banco agora recebe ID, Data e Hora já normalizados
            success, response_msg = await self.persistence_service.inserir_agendamento(
                user_id=user_id
                , servico_id=servico_id
                , servico_nome=servico.get('nome')
                , servico_minutos=servico.get('duracao_minutos')
                , data=normalized_slots.get('data')
                , hora_inicio=normalized_slots.get('hora_inicio')
            )
            return success, response_msg

        except Exception as e:
            logger.error(f"Erro ao processar agendamento final: {e}")
            return False, "Desculpe, ocorreu um erro técnico ao finalizar seu agendamento."
        
    # =========================================================
    # FUNÇÃO DE VALIDAÇÃO DE SLOTS (Completa)
    # =========================================================
    async def validate_slots(self, slot_data: dict) -> Tuple[bool, str, Optional[dict]]:
        """Valida se os dados processados respeitam as regras de tempo (ex: não agendar no passado)."""
        data_str = slot_data.get('data')
        hora_str = slot_data.get('hora_inicio')

        # 1. Validação de Regras de Negócio (Data/Hora - Síncrona)
        if data_str and hora_str:
            is_valid, msg, data_hora_obj = self.validator.validate_date_time_rules(data_str, hora_str)
            if not is_valid:
                return False, msg, None

            # Garante formato string limpo para o DB
            # Normalização: Converte a data e hora para o formato YYYY-MM-DD e HH:MM para o DB
            slot_data['data'] = data_hora_obj.strftime('%Y-%m-%d')
            slot_data['hora_inicio'] = data_hora_obj.strftime('%H:%M')
            
            return True, "", slot_data
        
        return False, "Dados de data ou hora incompletos.", None
        
    async def get_available_shifts(self, data: str, duracao_minutos: int) -> list[str]:
        """Consulta turnos disponíveis (Manhã, Tarde, Noite)."""
        disponiveis = []

        for shift_name in SHIFT_TIMES.keys():
            # Chamada ao método de cálculo do repositório, filtrando pelo turno
            horarios_livres = await self.persistence_service.get_available_blocks_for_shift(
                data=data,
                duracao_minutos=duracao_minutos,
                shift_name=shift_name
            )

            if horarios_livres:
                disponiveis.append(shift_name)

        return disponiveis

    async def get_available_times_by_shift(self, data: str, turno: str, duracao_minutos: int) -> list[str]:
        """Retorna todos os horários HH:MM livres dentro de um turno específico."""
        horarios = await self.persistence_service.get_available_blocks_for_shift(
            data=data,
            duracao_minutos=duracao_minutos,
            shift_name=turno
        )
        return horarios # O método já retorna a lista de strings 'HH:MM'
