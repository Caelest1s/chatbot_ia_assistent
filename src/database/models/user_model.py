# src/database/models/user_model.py
from __future__ import annotations  # 1. Para avaliação futura dos type hints
from typing import TYPE_CHECKING, Optional    # 2. Para importação exclusiva do type checker

from sqlalchemy import BigInteger, String, DateTime, Date, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column
from datetime import datetime, date
from ...database.session import Base # Importa Base do diretório pai (database)

# 3. Importação condicional APENAS para o Pylance/Type Checker
if TYPE_CHECKING:
    from .mensagem_model import Mensagem
    from .session_model import UserSession
    from .agenda_model import Agenda

class Usuario(Base):
    __tablename__ = 'usuarios'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # user_id do Telegram (Identificador Externo)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True) 
    # index -> Otimiza a busca por este campo

    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    telefone: Mapped[Optional[str]] = mapped_column(String(20))
    birthday: Mapped[date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Relacionamentos (use o nome da classe como string para evitar referências circulares)
    mensagens: Mapped[list["Mensagem"]] = relationship("Mensagem", back_populates="usuario")
    session: Mapped["UserSession"] = relationship("UserSession", back_populates="usuario", uselist=False)
    agendamentos: Mapped[list["Agenda"]] = relationship("Agenda", back_populates="usuario")

    def __repr__(self):
        return f"<Usuario(id={self.id}, telegram_id={self.user_id} nome={self.nome}, tel={self.telefone})>"