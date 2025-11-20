# src/database/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine
import os

from src.database.base import Base
from src.config.logger import setup_logger
from src.config.settings_loader import load_settings

logger = setup_logger(__name__)

def get_async_engine() -> AsyncEngine:
    """Cria e retorna o objeto AsyncEngine do SQLAlchemy"""

    # 1. Recuperar variáveis de ambiente
    db_host = os.getenv('DB_HOST')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_name = os.getenv('DB_NAME')
    db_port = os.getenv('DB_PORT')

    # MUITO IMPORTANTE: Mudar o driver para 'asyncpg' - assincrono
    # Formato: postgresql+asyncpg://user:password@host:port/dbname
    DATABASE_URL = (
        f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    )

    # 3. Criar o Engine
    # echo=True é útil para debug, pois mostra todas as queries SQL geradas
    try:
        engine = create_async_engine(
            DATABASE_URL,
            echo=True, # Desative para produção; ative para debug
            pool_recycle=3600, # Recycle connections every hour
            # pool_pre_ping=True # Verifica a conexão antes de usá-la do pool
        )
        logger.info("Engine do SQLAchemy assíncrono criado com sucesso.")
        return engine
    except Exception as e:
        logger.error(f"Erro ao criar o AsyncEngine do SQLAlchemy: {e}")
        # É crucial subir o erro para que a aplicação não inicie sem BD
        raise

# O Engine será criado apenas uma vez
engine: AsyncEngine = get_async_engine()

# Configuração do Async Session Maker
# Usamos async_sessionmaker para sessões assíncronas

# A Session é a "área de staging" para operações no BD (transações)
# autoflush=False: Evita o commit automático após cada operação.
# autocommit=False: Inicia uma nova transação por padrão.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False, # Evita expirar objetos após commit
)

# Funções utilitárias assíncronas (Async Context Manager)
async def get_db_session():
    """Dependência assíncrona para obter uma sessão de banco de dados."""
    async with AsyncSessionLocal() as session:
        yield session
