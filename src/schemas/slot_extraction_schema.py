# src/schemas/slot_extraction_schema.py
from pydantic import BaseModel, Field
from typing import Optional, Literal

# Slots necessários para o agendamento
class SlotExtraction(BaseModel):
    """Focado estritamente na extração de slots para agendamento."""

    # Campos que podem ser preenchidos, independente da intenção
    servico: Optional[str] = Field(
        None
        , description="Nome do serviço solicitado "
        "Deve ser o termo mais literal que o usuário usou. "
    )

    data: Optional[str] = Field(
        None,
        description="Data do agendamento"
        "(ex: 'amanhã', 'próxima terça', '20/10/2025', '20/10', 'daqui 3 dias')."
    )

    turno: Optional[Literal["manhã", "tarde", "noite"]] = Field(
        None,
        description="O turno preferido."
    )

    hora_inicio: Optional[str] = Field(
        None,
        description="O horário do agendamento (ex: '14:30', 'dez da manhã', '9h')."
    )
