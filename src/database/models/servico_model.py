# src/database/models/servico_model.py
from __future__ import annotations
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, Boolean, Text, Integer, DECIMAL
from sqlalchemy.orm import relationship, Mapped, mapped_column
from ...database.session import Base  # Importa Base do diretório pai (database)

if TYPE_CHECKING:
    from .agenda_model import Agenda

class Servico(Base):
    __tablename__ = 'servicos'

    servico_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=True)
    preco: Mapped[float] = mapped_column(DECIMAL(8, 2), nullable=False)
    duracao_minutos: Mapped[int] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relacionamento Inverso
    agendamentos: Mapped[list["Agenda"]] = relationship("Agenda", back_populates="servico")

    def __repr__(self):
        return f"<Servico(id={self.servico_id}, nome='{self.nome}', preco={self.preco})>"