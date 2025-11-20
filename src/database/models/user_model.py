# src/database/models/user_model.py
from __future__ import annotations  # 1. Para avaliação futura dos type hints
from typing import TYPE_CHECKING    # 2. Para importação exclusiva do type checker

from sqlalchemy import BigInteger, String, DateTime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime
from ...database.session import Base # Importa Base do diretório pai (database)

# 3. Importação condicional APENAS para o Pylance/Type Checker
if TYPE_CHECKING:
    from .historico_model import Historico
    from .session_model import UserSession
    from .agenda_model import Agenda

class Usuario(Base):
    __tablename__ = 'usuarios'

    # user_id como chave primária única.
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relacionamentos (use o nome da classe como string para evitar referências circulares)
    historico: Mapped["Historico"] = relationship("Historico", back_populates="usuario", uselist=False)
    session: Mapped["UserSession"] = relationship("UserSession", back_populates="usuario", uselist=False)
    agendamentos: Mapped[list["Agenda"]] = relationship("Agenda", back_populates="usuario")

    def __repr__(self):
        return f"<Usuario(id={self.user_id}, nome={self.nome})>"