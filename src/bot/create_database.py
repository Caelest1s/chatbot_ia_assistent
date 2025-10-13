import psycopg2
from psycopg2 import OperationalError
from src.config import settings_loader
import os

class CreateDatabase:
    def __init__(self):
        # Configurações do PostgreSQL
        self.database = os.getenv('DATABASE')
        self.db_host = os.getenv('DB_HOST')
        self.db_user = os.getenv('DB_USER')
        self.db_name = os.getenv('DB_NAME')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_port = os.getenv('DB_PORT')

        print(f"Usuário do banco carregado: {self.db_user}")  # confirmação

    # Função para conectar ao banco de dados PostgreSQL
    def get_db_connection(self, db_name: str):
        try:
            conn = psycopg2.connect(
                database=db_name
                , host=self.db_host
                , user=self.db_user
                , password=self.db_password
                , port=self.db_port
            )
            return conn
        except OperationalError as e:
            print(f"Erro ao conectar ao banco PostgreSQL {db_name}: {e}")
            raise
        except Exception as e:
            print(f"Erro ao conectar ao banco PostgreSQL: {e}")
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
                    cursor.execute(f"CREATE DATABASE {db_name} OWNER {self.db_user};")
                    print(f"Banco de dados '{db_name}' criado com sucesso.")
                else:
                    print(f"Banco de dados '{db_name}' já existe.")

                cursor.close()
                conn.close()
        except OperationalError as e:
            print(f"Erro ao criar banco PostgreSQL: {e}")
        except Exception as e:
            print(f"Erro ao criar o banco de dados: {e}")

    def create_tables(self):
        try:
            # Conectar ao banco de dados recém-criado
            conn = self.get_db_connection(self.db_name)
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

            conn.commit()
            print("Tabelas criadas com sucesso.")
            
            cursor.close()
            conn.close()
        except OperationalError as e:
            print(f"Erro ao criar tabelas no banco PostgreSQL: {e}")
        except Exception as e:
            print(f"Erro ao criar tabelas no banco: {e}")

    def drop_database(self):
        try:
            conn = self.get_db_connection(self.database)
            conn.autocommit = True # Necessário para dropar banco

            with conn.cursor() as cursor:
                # Dropar o banco de dados se existir
                cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = %s;", (self.db_name,))
                exists = cursor.fetchone()

                if exists:
                    # Terminar conexões ativas no banco antes de dropar
                    cursor.execute(f""" 
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = %s
                        AND pid <> pg_backend_pid();
                        """, (self.db_name,))
                    cursor.execute(f"DROP DATABASE {self.db_name};")
                    print(f"Banco de dados '{self.db_name}' dropado com sucesso.")
                else:
                    print(f"Banco de dados '{self.db_name}' não existe.")

                # cursor.close()
                # conn.close()
        except OperationalError as e:
            print(f"Erro ao dropar banco {self.db_name} PostgreSQL: {e}")
        except Exception as e:
            print(f"Erro ao dropar o banco de dados: {e}")

if __name__ == "__main__":
    db_manager = CreateDatabase()
    db_test_name = os.getenv('DB_TEST_NAME')

    # db_manager.drop_database()
    db_manager.create_database(db_name=db_test_name)
    # db_manager.db_name = db_test_name
    # db_manager.create_tables()