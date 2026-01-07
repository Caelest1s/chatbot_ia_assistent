# src/tools/available_tools.py
from langchain_core.tools import tool

@tool
def consultar_preco_servico(nome_servico: str) -> str:
    """
    Consulta o preço de um serviço específico do salão. 
    Use esta ferramenta sempre que o cliente perguntar 'Quanto custa...' ou 'Qual o valor de...'.
    """
    # Aqui futuramente você fará um SELECT no banco de dados
    tabela_precos = {
        "corte masculino": "R$ 50,00",
        "corte feminino": "R$ 80,00",
        "manicure": "R$ 35,00",
        "pedicure": "R$ 40,00"
    }

    preço = tabela_precos.get(nome_servico.lower(), "sob consulta")
    return f"O valor do serviço {nome_servico} é {preço}."

@tool
def verificar_disponibilidade_geral() -> str:
    """
    Verifica se o salão possui horários disponíveis hoje.
    """
    return "Temos horários disponíveis para hoje no período da tarde. Qual serviço você deseja?"

# Lista que o llm_config.py irá importar
ALL_TOOLS = [consultar_preco_servico, verificar_disponibilidade_geral]