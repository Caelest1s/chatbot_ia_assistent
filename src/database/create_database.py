# src/database/create_database.py
import psycopg2
from psycopg2 import sql, OperationalError
from src.config import settings_loader
import os
import logging
import asyncio

from src.database.session import engine, Base
from src.database.models import *

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CreateDatabase:
    def __init__(self):
        # Configurações do PostgreSQL (carregadas via os.getenv após settings_loader)
        self.database = os.getenv('DATABASE')
        self.db_host = os.getenv('DB_HOST')
        self.db_user = os.getenv('DB_USER')
        self.db_name = os.getenv('DB_NAME')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_port = os.getenv('DB_PORT')

        # confirmação
        logger.info(f"Usuário do banco carregado: {self.db_user}")

    # Função para conectar ao banco de dados PostgreSQL
    def get_db_connection(self, db_name: str):

        if not db_name:
            raise ValueError(
                "O nome do banco de dados (db_name) deve ser fornecido.")
        try:
            conn = psycopg2.connect(
                database=db_name
                , host=self.db_host
                , user=self.db_user
                , password=self.db_password
                , port=self.db_port
            )
            logger.info(
                f"Conexão com o banco '{db_name}' estabelecida com sucesso.")
            return conn
        # OperationalError para problemas de conexão
        except OperationalError as e:
            logger.error(
                f"Erro ao conectar ao banco PostgreSQL {db_name}: {e}")
            raise
        except Exception as e:
            logger.exception(f"Erro ao conectar ao banco PostgreSQL: {e}")
            raise

    def create_database(self, db_name=None):
        # Usar o nome do banco principal se nenhum nome for fornecido
        db_name = db_name or self.db_name
        try:
            conn = self.get_db_connection(self.database)
            conn.autocommit = True  # Necessário para criar banco
            with conn.cursor() as cursor:
                # Criar o banco bot_db se não existir
                cursor.execute(
                    f"SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
                exists = cursor.fetchone()
                if not exists:
                    query = sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(db_name), sql.Identifier(self.db_user)
                    )
                    # mostrar resultado da query
                    logger.info(query.as_string(conn))
                    cursor.execute(query)
                    logger.info(
                        f"Banco de dados '{db_name}' criado com sucesso.")
                else:
                    logger.info(f"Banco de dados '{db_name}' já existe.")

                cursor.close()
                conn.close()
        except OperationalError as e:
            logger.error(f"Erro ao criar banco PostgreSQL: {e}")
            raise
        except Exception as e:
            logger.exception(f"Erro ao criar o banco de dados: {e}")
            raise

    # Função auxiliar para executar create_all de forma assíncrona
    async def _async_create_tables(self):
        """Função assíncrona que executa a criação das tabelas."""
        # Base.metadata.create_all() é a função sincrona, 
        # mas como estamos usando AsyncEngine, precisamos usar .run_sync
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def create_tables(self, db_name=None):
        """Cria todas as tabelas definidas nos modelos do SQLAlchemy, de forma assíncrona."""
        db_name = db_name or self.db_name  # Mantido para log
        try:
            asyncio.run(self._async_create_tables())

            logger.info(
                f"Tabelas criadas com sucesso no banco '{db_name}' usando SQLAlchemy Assíncrono.")
        except Exception as e:
            logger.info(f"Erro ao criar tabelas com SQLAlchemy: {e}")
            raise

    def drop_database(self, db_name=None):
        db_name = db_name or self.db_name
        if not db_name:
            raise ValueError(
                "O nome do banco de dados deve ser fornecido para drop.")
        try:
            conn = self.get_db_connection(self.database)
            conn.autocommit = True  # Necessário para dropar banco

            with conn.cursor() as cursor:
                # Dropar o banco de dados se existir
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
                exists = cursor.fetchone()

                if exists:
                    # Encerrar conexões ativas no banco antes de dropar
                    cursor.execute(""" 
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s
                        AND pid <> pg_backend_pid();
                        """, (db_name,))
                    logger.info(
                        f"Todas as conexões do banco '{db_name}' foram encerradas.")

                    cursor.execute(
                        sql.SQL("DROP DATABASE {}").format(
                            sql.Identifier(db_name))
                    )
                    logger.info(
                        f"Banco de dados '{db_name}' dropado com sucesso.")
                else:
                    logger.info(f"Banco de dados '{db_name}' não existe.")

            conn.close()
        except OperationalError as e:
            logger.error(f"Erro ao dropar banco {db_name} PostgreSQL: {e}")
            raise
        except Exception as e:
            logger.exception(f"Erro ao dropar o banco de dados: {e}")
            raise


if __name__ == "__main__":
    db_manager = CreateDatabase()
    # MAIN_DB
    # Execução para criar e dropar o banco principal
    db_manager.drop_database()
    db_manager.create_database()
    db_manager.create_tables()

    # TEST_DB
    # db_test_name = os.getenv('DB_TEST_NAME')
    # db_manager.db_name = db_test_name
    # db_manager.drop_database(db_name=db_test_name)
    # db_manager.create_database(db_name=db_test_name)
    # db_manager.create_tables(db_name=db_test_name)
