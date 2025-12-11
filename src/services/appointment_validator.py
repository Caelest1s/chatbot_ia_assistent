# src/services/appointment_validator.py
from datetime import datetime, time, date
import logging

from typing import Tuple, Optional

from src.utils.constants import BUSINESS_HOURS, WEEKDAY_MAP
from src.utils.system_message import MESSAGES

logger = logging.getLogger(__name__)

class AppointmentValidator:
    """Validações de regras de negócio para agendamentos."""

    # =========================================================
    # MÉTODOS DE NORMALIZAÇÃO
    # =========================================================
    def normalize_date_format(self, data_str: str) -> Tuple[bool, str, Optional[str]]:
        """
        Tenta converter a data de 'DD/MM/YYYY' para o formato DB 'YYYY-MM-DD'.
        Retorna (sucesso, mensagem de erro, data normalizada ou None).
        """
        if not data_str:
            return False, "Data não fornecida.", None

        # Tenta o formato ISO, pois é o formato que o LLM DEVE retornar
        try:
            date_obj = datetime.strptime(data_str, '%Y-%m-%d').date()
            # Se for ISO, retorna a string padronizada DD/MM/AAAA para o slot manager
            return True, "", date_obj.strftime('%d/%m/%Y')
        except ValueError:
            pass # Não era ISO, tenta o formato do usuário

        # Tenta formatos comuns do usuário (DD/MM/YYYY, DD-MM-YYYY)
        for fmt in ('%d/%m/%Y', '%d-%m-%Y'):
            try:
                date_obj = datetime.strptime(data_str, fmt).date()
                # Retorna a string padronizada DD/MM/AAAA
                return True, "", date_obj.strftime('%d/%m/%Y')
            except ValueError:
                continue

        # Mensagem de erro padrão
        msg = MESSAGES['VALIDATION_FORMAT_ERROR_DATE'].format(nome="usuário")
        return False, msg, None

    def _combine_date_time(self, date_obj: date, hora_str: str) -> tuple[datetime, str] | tuple[None, str]:
        """[INTERNO] Combina um objeto date com uma string de hora em um objeto datetime."""
        try:
            # 1. Limpa a string de hora
            hora_limpa = hora_str.replace(
                'h', ':00').replace('H', ':00').strip()

            # Garante que a hora tem minutos, adicionando ':00' se necessário
            if ':' not in hora_limpa:
                hora_limpa += ':00'

            # 2. Converte a string de hora para um objeto time
            time_obj = datetime.strptime(hora_limpa, '%H:%M').time()

            # 3. Combina o objeto date e o objeto time em um datetime
            data_hora_agendamento = datetime.combine(date_obj, time_obj)

            return data_hora_agendamento, ""
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
                nome="usuário",
                dia=dia_semana_chave.capitalize(),
                inicio=hora_inicio.strftime("%H:%M"),
                fim=hora_fim.strftime("%H:%M")
            )
        return ""

    # =========================================================
    # ORQUESTRAÇÃO DE REGRAS
    # =========================================================
    def validate_date_time_rules(self, data_str: str, hora_str: str) -> Tuple[bool, str, Optional[datetime]]:
        """
        Orquestra todas as validações de data e hora.
        Retorna (sucesso, mensagem, objeto datetime).
        """
        # 1. Normalização de Data (Saída: string DD/MM/YYYY)
        sucesso_data, msg_erro, data_str_normalized = self.normalize_date_format(data_str)
        if not sucesso_data:
            return False, msg_erro, None
        
        # Converter a string normalizada para objeto date para _combine_date_time
        try:
            # Converte a string DD/MM/YYYY para um objeto date
            date_obj = datetime.strptime(data_str_normalized, '%d/%m/%Y').date()
        except ValueError:
            return False, "Erro interno de conversão de data.", None
        
        # 2. Combinação e Validação de Formato da Hora
        data_hora_obj, msg_erro = self._combine_date_time(
            date_obj, hora_str)
        if data_hora_obj is None:
            return False, msg_erro, None

        # 3. Validação de Tempo Passado
        msg_erro = self.validate_past_time(data_hora_obj)
        if msg_erro:
            return False, msg_erro, None

        # 4. Validação de Horário de Funcionamento
        msg_erro = self.validate_business_hours(data_hora_obj)
        if msg_erro:
            return False, msg_erro, None

        return True, "", data_hora_obj
