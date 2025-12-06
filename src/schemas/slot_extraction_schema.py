# src/schemas/slot_extraction_schema.py
from pydantic import BaseModel, Field
from typing import Optional, Literal

# Slots necessários para o agendamento
# A IA deve preencher estes campos se encontrar os dados na mensagem


class SlotExtraction(BaseModel):
    """Estrutura de dados para a intenção e extração de slots de agendamento."""

    # Adicionando as intenções de controle (RESET e SERVICOS)
    intent: Literal['AGENDAR', 'GENERICO', 'RESET', 'SERVICOS', 'BUSCAR_SERVICO'] = Field(
        ..., description="A intenção primária do usuário. AGENDAR, GENERICO, RESET (limpar conversa), "
        " SERVICOS (pedir lista) ou BUSCAR_SERVICO."
    )

    # Campos que podem ser preenchidos, independente da intenção
    servico_nome: Optional[str] = Field(
        None,
        description="O nome do serviço de beleza solicitado "
        "(ex: 'Corte Degrade', 'Manicure'). Deve ser o termo mais literal que o usuário usou. "
        "Preenchido para AGENDAR"
    )

    data: Optional[str] = Field(
        None,
        description="A data do agendamento, se fornecida. Formato flexível "
        "(ex: 'amanhã', 'próxima terça', '20/10/2025', '20/10'). Preencha se a intenção for AGENDAR."
    )

    turno: Optional[str] = Field(
        None,
        description="O turno preferido, se fornecido (ex: 'Manhã', 'Tarde', 'Noite'). Preencha se a intenção for AGENDAR."
    )

    hora: Optional[str] = Field(
        None,
        description="O horário do agendamento, se fornecido (ex: '14:30', 'dez da manhã', '9h')."
        "Preencha se a intenção for AGENDAR."
    )
