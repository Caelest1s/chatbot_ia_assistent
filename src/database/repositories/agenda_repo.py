# src/database/repositores/agenda_repo.py
import json
from src.config.logger import setup_logger
from datetime import datetime, time, date
from typing import Optional

# Importações Assíncronas
from sqlalchemy import select, func, text, and_
from sqlalchemy.ext.asyncio import AsyncSession 

# Importações da Base e dos Modelos (Ajuste conforme a sua estrutura)
from src.database.repositories.base_repo import BaseRepository
from src.database.models.agenda_model import Agenda

logger = setup_logger(__name__)

class AgendaRepository(BaseRepository[Agenda]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Agenda)
        # O self.session agora é a AsyncSession ativa

    async def verificar_disponibilidade(self, data: str) -> list[tuple[time, time]]:
        """Busca no DB todos os horários agendados e concluídos para uma data específica."""
        try:
            data_obj = datetime.strptime(data, '%Y-%m-%d').date()
        except ValueError as e:
            logger.info(f"Data inválida em verificar_disponibilidade: {data}. Erro: {e}.")
            return []

        stmt = select(Agenda.hora_inicio, Agenda.hora_fim).where(
                Agenda.data == data_obj,
                Agenda.status.in_(['agendado', 'concluido'])
            ).order_by(Agenda.hora_inicio)

        # Assume-se que a verificação é para qualquer profissional, já que não temos o campo
        return (await self.session.execute(stmt)).all()

    async def inserir_agendamento(self,
                                  user_id: int,
                                  servico_id: int,
                                  servico_nome: str,
                                  data_dt: date,
                                  hora_inicio_time: time, 
                                  hora_fim_time: time) -> tuple[Optional[Agenda], Optional[str], str]:
        """Insere um novo agendamento"""
        novo_agendamento = Agenda(
            user_id=user_id
            , servico_id=servico_id
            , data=data_dt
            , hora_inicio=hora_inicio_time
            , hora_fim=hora_fim_time
            , status='agendado'
            , created_at=datetime.now()
        )

        self.session.add(novo_agendamento)
        await self.session.flush()
        await self.session.refresh(novo_agendamento)

        return novo_agendamento, servico_nome, "Agendamento pronto para ser confirmado." 
