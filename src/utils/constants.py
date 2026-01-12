# src/utils/constants.py
from datetime import time

# Regras de Negócio
# Mapeamento do dia da semana (weekday) para a chave do dicionário
WEEKDAY_MAP = {
    0: "segunda",
    1: "terca",
    2: "quarta",
    3: "quinta",
    4: "sexta",
    5: "sabado",
    6: "domingo"
}

# Horário de Funcionamento
BUSINESS_HOURS = {
    # 0 = Segunda-feira, 6 = Domingo
    "segunda": {"start": time(9, 0), "end": time(22, 0)},  # 09:00 às 22:00
    "terca": {"start": time(9, 0), "end": time(22, 0)},
    "quarta": {"start": time(9, 0), "end": time(22, 0)},
    "quinta": {"start": time(9, 0), "end": time(22, 0)},
    "sexta": {"start": time(9, 0), "end": time(22, 0)},
    "sabado": {"start": time(9, 0), "end": time(16, 0)},  # Sábado mais curto
    "domingo": None  # Fechado
}

# Slots obrigatórios para o Agendamento
REQUIRED_SLOTS = ["servico_id", "data", "turno", "hora_inicio"]

SHIFT_TIMES = {
    "Manhã": {"inicio": "08:00", "fim": "12:00"}, "Tarde": {"inicio": "12:00", "fim": "18:00"}, "Noite": {"inicio": "18:00", "fim": "22:00"},
}

BUSINESS_DOMAIN = "Barbearia"
BUSINESS_NAME = "Wesley Barbearia"