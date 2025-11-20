# src/database/base.py
from sqlalchemy.orm import DeclarativeBase, declared_attr, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import BigInteger, Integer, DateTime
from datetime import datetime

# ----------------------------------------------------------------------
# Classe Base para os Modelos

class Base(DeclarativeBase):
    """Classe base declarativa."""

    # Define a classe como abstrata, ela não deve ter uma tabela criada no BD.
    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower()
    
    # Define um 'id' padrão para modelos que usam.
    # Usamos 'Integer' (Serial/Auto-incrementado) em vez de 'BigInteger' para PKs auto-incrementadas, 
    # a menos que seja especificamente necessário (ex: IDs de Telegram que são BIGINT).

    # Colunas de auditoria (melhoria)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)

# ----------------------------------------------------------------------
# Função de Inicialização Assíncrona do Banco de Dados

async def init_db(engine: AsyncEngine):
    """
    Cria todas as tabelas no banco de dados.
    Deve ser chamada no app.py/main.py no início da aplicação.
    """
    # Importar pacotes de modelos para que a Base.metadata os conheça
    try:
        import src.database.models 
    except ImportError:
        pass # Ignora se não existir esse subpacote

    async with engine.begin() as conn:
        # Usa run_sync para executar DDL (criação de tabelas) de forma síncrona dentro do contexto assíncrono
        await conn.run_sync(Base.metadata.create_all)
        print("Tabelas do banco de dados sincronizadas com sucesso.")