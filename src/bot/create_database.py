import psycopg2
from psycopg2 import sql, OperationalError
from src.config import settings_loader
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) 

class CreateDatabase:
    def __init__(self):
        # Configurações do PostgreSQL
        self.database = os.getenv('DATABASE')
        self.db_host = os.getenv('DB_HOST')
        self.db_user = os.getenv('DB_USER')
        self.db_name = os.getenv('DB_NAME')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_port = os.getenv('DB_PORT')

        logger.info(f"Usuário do banco carregado: {self.db_user}")  # confirmação

    # Função para conectar ao banco de dados PostgreSQL
    def get_db_connection(self, db_name: str):

        if not db_name:
            raise ValueError("O nome do banco de dados (db_name) deve ser fornecido.")
        try:
            conn = psycopg2.connect(
                database=db_name
                , host=self.db_host
                , user=self.db_user
                , password=self.db_password
                , port=self.db_port
            )
            logger.info(f"Conexão com o banco '{db_name}' estabelecida com sucesso.")
            return conn
        # OperationalError para problemas de conexão
        except OperationalError as e:
            logger.error(f"Erro ao conectar ao banco PostgreSQL {db_name}: {e}")
            raise
        except Exception as e:
            logger.exception(f"Erro ao conectar ao banco PostgreSQL: {e}")
            raise

    def create_database(self, db_name=None):
        db_name = db_name or self.db_name # Usar o nome do banco principal se nenhum nome for fornecido
        try:
            conn = self.get_db_connection(self.database)
            conn.autocommit = True # Necessário para criar banco
            with conn.cursor() as cursor:
                # Criar o banco bot_db se não existir
                cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
                exists = cursor.fetchone()
                if not exists:
                    query = sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(db_name)
                        , sql.Identifier(self.db_user)
                    )
                    logger.info(query.as_string(conn)) # mostrar resultado da query
                    cursor.execute(query)
                    logger.info(f"Banco de dados '{db_name}' criado com sucesso.")
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

    def create_tables(self, db_name=None):
        db_name = db_name or self.db_name
        try:
            # Conectar ao banco de dados recém-criado
            conn = self.get_db_connection(db_name)
            cursor = conn.cursor()
            
            # Criar tabela de usuários
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id BIGINT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Criar tabela de historico 
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico (
                user_id BIGINT PRIMARY KEY REFERENCES usuarios(user_id),
                conversas TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Criar tabela serviços
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS servicos(
                servico_id BIGINT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                descricao TEXT,
                preco DECIMAL(8, 2) NOT NULL,
                duracao_minutos INT,
                ativo BOOLEAN DEFAULT TRUE
            );
            """)

            # Criar tabela agenda
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agenda (
                agenda_id BIGSERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES usuarios(user_id) ON DELETE CASCADE,
                servico_id BIGINT REFERENCES servicos(servico_id) ON DELETE SET NULL,
                dia_semana VARCHAR(10) NOT NULL CHECK (dia_semana IN (
                    'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado', 'domingo'
                )),
                horario TIME NOT NULL CHECK (horario >= '08:00' AND horario <= '22:00'),
                data DATE NOT NULL,
                status VARCHAR(20) DEFAULT 'pendente' CHECK (status IN ('pendente', 'confirmado', 'cancelado')),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Criar índice único para evitar duplicidade de agendamento por usuário
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_agenda_user_data_horario
                ON agenda (user_id, data, horario);
            """)

            conn.commit()
            logger.info("Tabelas criadas com sucesso.")
            
            cursor.close()
            conn.close()
        except OperationalError as e:
            logger.error(f"Erro ao criar tabelas no banco PostgreSQL: {e}")
            raise
        except Exception as e:
            logger.info(f"Erro ao criar tabelas no banco: {e}")
            raise

    def drop_database(self, db_name=None):
        db_name = db_name or self.db_name
        if not db_name:
            raise ValueError("O nome do banco de dados deve ser fornecido para drop.")
        try:
            conn = self.get_db_connection(self.database)
            conn.autocommit = True # Necessário para dropar banco

            with conn.cursor() as cursor:
                # Dropar o banco de dados se existir
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (db_name,))
                exists = cursor.fetchone()

                if exists:
                    # Encerrar conexões ativas no banco antes de dropar
                    cursor.execute(""" 
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = %s
                        AND pid <> pg_backend_pid();
                        """, (db_name,))
                    logger.info(f"Todas as conesões do banco '{db_name}' foram encerradas.")

                    cursor.execute(
                        sql.SQL("DROP DATABASE {}").format(sql.Identifier(db_name))
                    )
                    logger.info(f"Banco de dados '{db_name}' dropado com sucesso.")
                else:
                    logger.info(f"Banco de dados '{db_name}' não existe.")

                # cursor.close()
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
    db_manager.drop_database()
    db_manager.create_database()
    db_manager.create_tables()

    # TEST_DB
    # db_test_name = os.getenv('DB_TEST_NAME')
    # db_manager.db_name = db_test_name
    # db_manager.drop_database(db_name=db_test_name)
    # db_manager.create_database(db_name=db_test_name)
    # db_manager.create_tables(db_name=db_test_name)
