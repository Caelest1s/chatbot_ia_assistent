# src/utils/date_parser.py

import logging
from datetime import date, timedelta, datetime
from typing import Optional
import re
import dateparser

logger = logging.getLogger(__name__)

# Mapeamento de dias da semana em português (sem acentos para matching mais flexível)
DIAS_SEMANA = {
    'segunda': 0, 'segunda-feira': 0,
    'terca': 1, 'terça': 1, 'terça-feira': 1,
    'quarta': 2, 'quarta-feira': 2,
    'quinta': 3, 'quinta-feira': 3,
    'sexta': 4, 'sexta-feira': 4,
    'sabado': 5, 'sábado': 5,
    'domingo': 6
}

def parse_relative_date(date_string: str, today: Optional[date] = None) -> Optional[str]:
    if not date_string:
        return None

    if today is None:
        today = date.today()
    else: 
        if hasattr(today, 'date'):  # se for datetime
            today = today.date() # garante que seja date puro

    original = date_string.strip()
    text = original.lower()

    # 1. Já está em ISO? Retorna direto
    if re.match(r'^\d{4}-\d{2}-\d{2}$', original):
        return original

    # 2. Padroniza "próximo(a)" / "prox"
    text = re.sub(r'\bpr[óo]xim[ao]s?\b', 'próximo', text, flags=re.IGNORECASE)

    logger.debug(f"String original: '{original}' → normalizada: '{text}'")

    # FALLBACK MANUAL 1: "próximo [dia da semana]"
    match = re.search(r'\b(?:próximo|este|esta|está|esse|essa)?\s+([a-záéíóúçãõâêîôûäëïöüàèìòù\-]+)', text)
    if match:
        dia_str = match.group(1).replace('-feira', '').strip()
        # Remove "-feira" e normaliza acentos básicos
        dia_str = dia_str.replace('á', 'a').replace('é', 'e').replace('í', 'i') \
                        .replace('ó', 'o').replace('ú', 'u').replace('ç', 'c')
        if dia_str in DIAS_SEMANA:
            alvo = DIAS_SEMANA[dia_str]
            atual = today.weekday()

            dias_adiante = alvo - atual

            # Se for o mesmo dia ou muito próximo, pula para a próxima semana
            if dias_adiante <= 0:
                dias_adiante += 7

            data_resolvida = today + timedelta(days=dias_adiante)
            if hasattr(data_resolvida, 'date'):  # se for datetime
                data_resolvida = data_resolvida.date()
            resultado = data_resolvida.isoformat()  # agora sempre "YYYY-MM-DD"

            logger.debug(f"FALLBACK MANUAL (próximo dia) ativado: '{original}' → {resultado}")
            return resultado

    # 4. FALLBACK MANUAL 2: "daqui a X dias" ou "em X dias"
    daqui_match = re.search(r'\b(?:daqui\s+a|daqui|em)\s+(\d+)\s+dias?\b', text)
    if daqui_match:
        dias = int(daqui_match.group(1))
        resultado = (today + timedelta(days=dias)).isoformat()
        logger.debug(f"FALLBACK MANUAL (daqui a dias) ativado: '{original}' → {resultado}")
        return resultado
    
    # FALLBACK MANUAL 3: para datas DD/MM ou D/M sem ano (padrão brasileiro)
    simple_date_match = re.match(r'^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$', original)
    if simple_date_match:
        day_str, month_str = simple_date_match.groups()
        day = int(day_str)
        month = int(month_str)
        if 1 <= day <= 31 and 1 <= month <= 12:
            year = today.year
            try:
                candidate = date(year, month, day)
                if candidate < today:
                    candidate = date(year + 1, month, day)
                resultado = candidate.isoformat()
                logger.debug(f"FALLBACK MANUAL (DD/MM simples) ativado: '{original}' → {resultado}")
                return resultado
            except ValueError:
                pass  # Dia inválido, deixa pro dateparser tentar

    # 5. Se não for "próximo X", tenta o dateparser em português (ótimo para tudo mais)
    settings = {
        'PREFER_DATES_FROM': 'future',
        'DATE_ORDER': 'DMY',
        'RELATIVE_BASE': datetime.combine(today, datetime.min.time()),
        'STRICT_PARSING': False,
        'PREFER_DAY_OF_MONTH': 'first',  # Crucial para ambiguidades como 10/12
    }

    parsed = dateparser.parse(original, languages=['pt'], settings=settings)
    if parsed:
        resultado = parsed.date().isoformat()
        logger.debug(f"dateparser resolveu: '{original}' → {resultado}")
        return resultado

    logger.warning(f"Não foi possível resolver a string de data: '{original}'")
    return None