# src/schemas/router_schema.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional

class RouterClassification(BaseModel):
    """Esquema para classificar a intenção da mensagem do usuário e decidir qual chain deve ser utilizada."""

    # Define as categorias de intenção que o LLM pode classificar
    intent: Literal[
        'AGENDAR',              # Fluxo de preenchimento de slots
        'GENERICO',             # Consultas gerais
        'RESET',                # Limpar memória
        'SERVICOS',              # Listar serviços disponíveis
        'BUSCAR_SERVICO',       # Trigger direto para Tool-Calling (preços, disponibilidade)
    ] = Field(
        description=("A intenção primária da mensagem do usuário" 
            "deve ser estritamente um dos valores literais definidos."
            "Retorne apenas o valor literal, sem texto adicional, "
            "sem explicações, sem traduções e sem criar novos valores."
        )
    )

    # Opcional: Um breve resumo do que o usuário está pedindo, útil para debug e tracing.
    # <<<<<<<<<<===============!!!!!!!!!!!! Retirar SUMMARY para produção !!!!!!!!!!!!!===================>>>>>>
    summary: Optional[str] = Field(
        default=None,
        description="Um breve resumo (1-5 palavras) do pedido do usuário."
    )

    model_config = ConfigDict(
        extra="forbid"  # Proíbe campos adicionais não definidos no modelo
        , frozen=True)  # Torna o objeto imutável para garantir integridade