# src/database/models/mensagem_model.py
from __future__ import annotations # 1. Para avaliação futura dos type hints

from sqlalchemy import BigInteger, Text, DateTime, ForeignKey, String, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column

from ..session import Base
from datetime import datetime
from typing import TYPE_CHECKING # 2. Para importação exclusiva do type checker

# 3. Importação condicional APENAS para o Pylance/Type Checker
if TYPE_CHECKING:
    from .user_model import Usuario

class Mensagem(Base):
    """
    Representa uma única mensagem na conversa, seja ela do usuário ou do bot.
    """
    __tablename__ = 'mensagem'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    usuario_id: Mapped[int] = mapped_column(
        Integer
        , ForeignKey('usuarios.id')
        , index=True
        , nullable=True
    )
    
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    origem: Mapped[str] = mapped_column(String(10), nullable=False) # bot or user
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relacionamento
    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="mensagens")

    def __repr__(self):
        return f"<Mensagem(user_id={self.usuario_id})>"
