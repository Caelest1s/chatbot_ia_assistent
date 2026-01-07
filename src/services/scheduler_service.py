# src/services/scheduler_service.py

from datetime import datetime, timedelta, time, date
from typing import Optional, Union
import logging
from src.utils.constants import SHIFT_TIMES, BUSINESS_HOURS, WEEKDAY_MAP

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, agenda_repo):
        self.agenda_repo = agenda_repo

    def _get_operation_limits(self, data: date, shift_name: Optional[str]) -> Optional[dict]:
        """Lógica de regra de negócio: Define os limites de operação (horário de abertura/fechamento)."""

        weekday_idx = data.weekday() # 0 = Segunda, 6 = Domingo
        day_name = WEEKDAY_MAP[weekday_idx]
        business_rule = BUSINESS_HOURS.get(day_name)

        if not business_rule:
            logger.info(f"Estabelecimento fechado em: {day_name}")
            return None
        
        inicio_operacao = business_rule['start']
        fim_operacao = business_rule['end']

        if shift_name and shift_name in SHIFT_TIMES:
            shift = SHIFT_TIMES[shift_name]
            inicio_operacao = datetime.strptime(shift['inicio'], '%H:%M').time()
            fim_operacao = datetime.strptime(shift['fim'], '%H:%M').time()
    
        return {"start": inicio_operacao, "end": fim_operacao}
    
    async def calculate_available_blocks(self
                                         , data: Union[str, date]
                                         , duracao_minutos: int
                                         , shift_name: Optional[str] = None) -> list[str]:
        """Calcula os blocos de tempo disponíveis para agendamento."""
        # 1. Normalização da data e verificação de regras de negócio (BUSINESS_HOURS)

        if isinstance(data, str):
            data_obj = datetime.strptime(data, '%Y-%m-%d').date()
            data_str = data
        else:
            data_obj = data
            data_str = data.strftime('%Y-%m-%d')

        limits = self._get_operation_limits(data_obj, shift_name)
        if not limits:
            return []
        
        inicio_operacao = limits['start']
        fim_operacao = limits['end']

        # 2. Obter agendamentos ocupados (CHAMA O REPOSITÓRIO)
        agendamentos_ocupados = await self.agenda_repo.verificar_disponibilidade(data_str)
        horarios_livres: list[str] = []

        # Usar uma data dummy para facilitar calculo de tempo
        dummy_date = datetime(2000, 1, 1).date()
        current_dt = datetime.combine(dummy_date, inicio_operacao)
        fim_operacao_dt = datetime.combine(dummy_date, fim_operacao)

        # 3. Iterar de 30 em 30 minutos (ou a cada 15 minuto se quiser ser granular)
        intervalo_step = timedelta(minutes=30)
        duracao_delta = timedelta(minutes=duracao_minutos)

        # Loop de verificação
        while current_dt + duracao_delta <= fim_operacao_dt:
            hora_inicio_bloco = current_dt.time()
            hora_fim_bloco = (current_dt + duracao_delta).time()

            is_available = True

            # Checa se o bloco de tempo colide com algum agendamento ocupado
            for inicio_agendado, fim_agendado in agendamentos_ocupados:
                if (hora_inicio_bloco < fim_agendado and hora_fim_bloco > inicio_agendado):
                    is_available = False
                    break

            if is_available:
                horarios_livres.append(hora_inicio_bloco.strftime('%H:%M'))

            current_dt += intervalo_step
        return horarios_livres
    
    async def is_slot_available(self, data: str, hora_inicio: str, servico_minutos: int) -> tuple[bool, str]:
        # Verifica se um slot específico está disponível para agendamento.
        # 1. Validação de Formato e Tempo Passado
        try:
            data_dt = datetime.strptime(data, '%Y-%m-%d').date()
            hora_inicio_dt = datetime.strptime(hora_inicio, '%H:%M')
            hora_inicio_time = hora_inicio_dt.time()
        except ValueError:
            return False, "Formato de data ou hora inválido."
        
        agora = datetime.now()
        data_hora_pedido = datetime.combine(data_dt, hora_inicio_time)

        if data_hora_pedido < agora:
            return False, "Não é possível agendar para horários passados."
        
        # 2. Validação de Horário Comercial (Business Hours)
        limits = self._get_operation_limits(data_dt, None) # Checagem geral de horário comercial
        if not limits:
            return False, f"Estabelecimento fechado no dia {WEEKDAY_MAP.get(data_dt.weekday())}"
        
        # Lógica de Horário de Início/Fim (Opcional, mas útil)
        hora_fim_dt = hora_inicio_dt + timedelta(minutes=servico_minutos)
        hora_fim_time = hora_fim_dt.time()

        # O slot completo deve estar dentro dos limites de operação
        if hora_inicio_time < limits['start'] or hora_fim_time > limits['end']:
            return False, "O horário de agendamento está fora do horário comercial permitido."
        
        # 3. Verificação de Conflitos no DB (CHAMA O REPOSITÓRIO)
        agendamentos_ocupados = await self.agenda_repo.verificar_disponibilidade(data)

        for inicio_agendado, fim_agendado in agendamentos_ocupados:
            if (hora_inicio_time < fim_agendado and hora_fim_time > inicio_agendado):
                return False, "Horário indisponível. Conflito com agendamento existente."
            
        return True, "Horário disponível para agendamento."
    