from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal

# 1. Defina as Intenções Possíveis
class Intencao(BaseModel):
    """Modelo para determinar a intenção principal do usuário."""

    # Intenções são limitadas a um conjunto predefinido (enum)
    intent: Literal['AGENDAR', 'BUSCAR_SERVICO', 'GENERICO'] = Field(
        ..., description="A intenção primária do usuário. Escolha a mais relevante."
    )

    # Campos que podem ser preenchidos, independente da intenção
    servico_nome: Optional[str] = Field(
        None, description="O nome do serviço ou termo principal de busca (ex: corte, manicure, preço de luzes)."
    )
    data: Optional[str] = Field(
        None, description="Data no formato DD/MM/AAAA (ex: 29:10:2025). Preencha se a intenção for AGENDAR."
    )
    hora: Optional[str] = Field(
        None, description="Hoora no formato HH:MM (ex: 15:30). Preencha se a intenção for AGENDAR"
    )