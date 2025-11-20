# src/utils/json_utils.py

from datetime import date, datetime, time
from typing import Union

def _default_json_serializer(obj: any) -> any:
    """
    Função auxiliar para serializar objetos não JSON (como date, datetime, time).
    Retorna a representação em string ISO 8601 ou levanta TypeError.
    """
    if isinstance(obj, date):
        # Converte date para string ISO 8601 (YYYY-MM-DD)
        return obj.strftime('%Y-%m-%d')  # ← sempre YYYY-MM-DD
    if isinstance(obj, datetime):
        # Converte time para string HH:MM
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(obj, time):
        return obj.strftime('%H:%M')
    
    # Se não for um tipo especial que estamos tratando, levanta TypeError para o JSON padrão lidar
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

def prepare_data_for_json(data: Union[dict, list, any]) -> Union[dict, list, any]:
    """
    Percorre recursivamente uma estrutura de dados e converte objetos
    datetime.date, datetime.datetime e datetime.time em strings para serialização JSON.
    """
    
    if isinstance(data, dict):
        # Percorre o dicionário e aplica a conversão recursivamente
        return {k: prepare_data_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        # Percorre a lista e aplica a conversão recursivamente
        return [prepare_data_for_json(item) for item in data]
    else:
        # Tenta serializar o objeto diretamente (útil para date, datetime, time)
        try:
            return _default_json_serializer(data)
        except TypeError:
            # Se não for um tipo especial (é str, int, float, bool, None), retorna o valor
            return data