from datetime import time

# Regras de Negócio do Salão

BUSINESS_HOURS = {
    # 0 = Segunda-feira, 6 = Domingo
    "segunda": {"start": time(9,0), "end": time(18, 0)}, # 09:00 às 18:00
    "terca": {"start": time(9,0), "end": time(20, 0)}, 
    "quarta": {"start": time(9,0), "end": time(20, 0)}, 
    "quinta": {"start": time(9,0), "end": time(20, 0)}, 
    "sexta": {"start": time(9,0), "end": time(20, 0)}, 
    "sabado": {"start": time(9,0), "end": time(17, 0)}, # Sábado mais curto
    "domingo": None # Fechado
}

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