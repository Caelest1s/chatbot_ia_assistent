# src/database/models/session_model.py
from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from ...database.session import Base  # Importa Base do diretório pai (database)

if TYPE_CHECKING:
    from .user_model import Usuario

class UserSession(Base):
    __tablename__ = 'user_sessions'

    user_id: Mapped[int] = mapped_column(BigInteger, 
        ForeignKey('usuarios.user_id', ondelete='CASCADE'), primary_key=True)
    current_intent: Mapped[str] = mapped_column(String(50), nullable=True)
    slot_data: Mapped[dict] = mapped_column(JSONB, default={})
    session_start: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relacionamento
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="session")

    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, intent='{self.current_intent}')>"