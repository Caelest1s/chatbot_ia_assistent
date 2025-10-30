from datetime import datetime, time
import logging
from src.utils.constants import BUSINESS_HOURS, WEEKDAY_MAP
from src.utils.system_message import MESSAGES

logger = logging.getLogger(__name__)

class AppointmentValidator:
    """Validações de regras de negócio para agendamentos."""

    def validate_date_time_format(self, data_str: str, hora_str: str) -> tuple[datetime, str] | tuple[None, str]:
        """Tenta converter a data e hora para datetime."""
        try: 
            hora_limpa = hora_str.replace('h', ':00').replace('H', ':00').strip()
            # Garante que a hora tem minutos, adicionando ':00' se necessário
            if ':' not in hora_limpa:
                 hora_limpa += ':00'
            data_hora_agendamento = datetime.strptime(f"{data_str} {hora_limpa}", '%d/%m/%Y %H:%M')
            return data_hora_agendamento, None
        except ValueError:
            return None, MESSAGES['VALIDATION_FORMAT_ERROR'].format(nome="usuário")
        
    def validate_past_time(self, data_hora: datetime) -> str:
        """Verifica se o agendamento está no passado."""
        if data_hora < datetime.now():
            return MESSAGES['VALIDATION_PAST_DATE']
        return ""
    
    def validate_business_hours(self, data_hora: datetime) -> str:
        """Verifica se o agendamento está dentro do horário de funcionamento."""
        dia_semana_num = data_hora.weekday()
        dia_semana_chave = WEEKDAY_MAP.get(dia_semana_num)
        horario_dia = BUSINESS_HOURS.get(dia_semana_chave)

        if horario_dia is None:
            return f'O salão está fechado na(o) {dia_semana_chave.capitalize()}. Por favor, escolha outro dia.'
        
        hora_agendada = data_hora.time()
        hora_inicio = horario_dia["start"]
        hora_fim = horario_dia["end"]

        if not (hora_inicio <= hora_agendada < hora_fim):
            return MESSAGES['VALIDATION_OUTSIDE_HOURS'].format(
                nome = "usuário",
                dia = dia_semana_chave.capitalize(),
                inicio = hora_inicio.strftime("%H:%M"),
                fim = hora_fim.strftime("%H:%M")
            )
        return ""