import psycopg2
from psycopg2 import OperationalError
from dotenv import load_dotenv
import os

load_dotenv()

# Configurações do PostgreSQL
DB_HOST = os.getenv('DB_HOST')
DATABASE = os.getenv('DATABASE')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')

# Função para conectar ao banco de dados PostgreSQL
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST
            , database=DATABASE
            , user=DB_USER
            , password=DB_PASSWORD
            , port=DB_PORT
        )
        return conn
    except OperationalError as e:
        print(f"Erro ao conectar ao banco PostgreSQL {DATABASE}: {e}")
        raise
    except OperationalError as e:
        print(f"Erro ao conectar ao banco PostgreSQL: {e}")
        raise

def create_database():
    try:

        with get_db_connection() as conn:
            conn.autocommit = True # Necessário para criar banco
            with conn.cursor() as cursor:
                # Criar o banco bot_db se não existir
                cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
                exists = cursor.fetchone()
                if not exists:
                    cursor.execute(f"CREATE DATABASE {DB_NAME} OWNER {DB_USER};")
                    print(f"Banco de dados '{DB_NAME}' criado com sucesso.")
                else:
                    print(f"Banco de dados '{DB_NAME}' já existe.")

                cursor.close()
                conn.close()
    except OperationalError as e:
        print(f"Erro ao criar banco PostgreSQL: {e}")
    except Exception as e:
        print(f"Erro ao criar o banco de dados: {e}")

def create_tables():
    try:
        # Conectar ao banco de dados recém-criado
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Criar tabela de usuários
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    user_id BIGINT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
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

                conn.commit()
                print("Tabelas criadas com sucesso.")
                
                cursor.close()
                conn.close()
    except OperationalError as e:
        print(f"Erro ao criar tabelas no banco PostgreSQL: {e}")
    except Exception as e:
        print(f"Erro ao criar tabelas no banco: {e}")

def drop_database():
    try:
        with get_db_connection() as conn:
            conn.autocommit = True # Necessário para dropar banco
            with conn.cursor() as cursor:
                # Dropar o banco de dados se existir
                cursor.execute(f"""SELECT 1 
                    FROM pg_database 
                    WHERE datname = %s;""", (DB_NAME,))
                exists = cursor.fetchone()

                if exists:
                    # Terminar conexões ativas no banco antes de dropar
                    cursor.execute(f""" 
                        SELECT pg_terminate_backend(pg_stat_activity.pid)
                        FROM pg_stat_activity
                        WHERE pg_stat_activity.datname = %s
                        AND pid <> pg_backend_pid();
                        """, (DB_NAME,))
                    cursor.execute(f"DROP DATABASE {DB_NAME};")
                    print(f"Banco de dados '{DB_NAME}' dropado com sucesso.")
                else:
                    print(f"Banco de dados '{DB_NAME}' não existe.")

                cursor.close()
                conn.close()
    except OperationalError as e:
        print(f"Erro ao dropar banco {DB_NAME} PostgreSQL: {e}")
    except Exception as e:
        print(f"Erro ao dropar o banco de dados: {e}")

if __name__ == "__main__":
    # drop_database()
    create_database()
    create_tables()