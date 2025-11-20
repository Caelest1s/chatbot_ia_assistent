# src/database/models/historico_model.py
from __future__ import annotations # 1. Para avaliação futura dos type hints

from sqlalchemy import BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column

from ...database.session import Base
from datetime import datetime
from typing import TYPE_CHECKING # 2. Para importação exclusiva do type checker

# 3. Importação condicional APENAS para o Pylance/Type Checker
if TYPE_CHECKING:
    from .user_model import Usuario

class Historico(Base):
    __tablename__ = 'historico'

    user_id: Mapped[int] = mapped_column(
        BigInteger
        , ForeignKey('usuarios.user_id')
        , primary_key=True)
    
    conversas: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime
        , default=datetime.now
        , onupdate=datetime.now
    )

    # Relacionamento
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="historico")

    def __repr__(self):
        return f"<Historico(user_id={self.user_id})>"
