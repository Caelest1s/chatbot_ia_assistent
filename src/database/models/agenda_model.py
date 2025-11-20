# src/database/models/agenda_model.py
from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import (BigInteger, Time, Date, DateTime, ForeignKey, 
    CheckConstraint, UniqueConstraint, String)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, time, date
from ...database.session import Base

if TYPE_CHECKING:
    from .user_model import Usuario
    from .servico_model import Servico

class Agenda(Base):
    __tablename__ = 'agenda'

    agenda_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('usuarios.user_id', ondelete='CASCADE'))
    servico_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('servicos.servico_id', ondelete='RESTRICT'))

    hora_inicio: Mapped[time] = mapped_column(Time, nullable=False)
    hora_fim: Mapped[time] = mapped_column(Time, nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default='agendado')
        
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    # Campo para rastrear a última modificação
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    __tableargs__ = (
        CheckConstraint(
            "status IN ('agendado', 'cancelado', 'concluido')"
            , name='check_agenda_status'),

        CheckConstraint('hora_inicio < hora_fim', name='chk_horas_validas'),

        # Garante que um slot de serviço (ex: médico) só tenha um agendamento
        UniqueConstraint('servico_id', 'data', 'hora_inicio', name='uc_servico_slot'),
        # Garante que um usuário só tenha um agendamento por slot
        UniqueConstraint('user_id', 'data', name='uc_usuario_slot_per_day'),
    )

    # Relacionamentos
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="agendamentos")
    servico: Mapped["Servico"] = relationship("Servico", back_populates="agendamentos")

    def __repr__(self):
        return f"<Agenda(id={self.agenda_id}, user={self.user_id}, data={self.data} {self.hora_inicio})>"
    