import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json
from dotenv import load_dotenv
from messages import MESSAGES

load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT')

RESPOSTA_SUCINTA = MESSAGES['RESPOSTA_SUCINTA']

# Função para obter conexão com o banco de dados
def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
    )

# Função para conectar e criar tabela se não existir
def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                user_id BIGINT PRIMARY KEY,
                nome VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
                       
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
        cursor.close()
        conn.close()
        print("Tabelas inicializadas com sucesso!")
    except Exception as e:
        print(f"Erro ao inicializar as tabelas no banco: {e}")

# Função para salvar ou atualizar usuário
def salvar_usuario(user_id, nome):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (user_id, name) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET name = EXCLUDED.name;
            """, (user_id, nome))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar usuário: {e}")

# Função para recuperar nome pelo user_id
def get_nome_usuario(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT name FROM usuarios WHERE user_id = %s', (user_id,))
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()
        return resultado['name'] if resultado else None
    except Exception as e:
        print(f"Erro ao recuperar nome do usuário: {e}")
        return None
    
def get_historico(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT conversas FROM historico WHERE user_id = %s", (user_id,))
        resultado = cursor.fetchone()
        cursor.close()
        conn.close()

        return json.loads(resultado[0]) if resultado[0] else [{"role": "system", "content": RESPOSTA_SUCINTA}]
    except Exception as e:
        print(f"Erro ao recuperar histórico do usuário: {e}")
        return [{"role": "system", "content": RESPOSTA_SUCINTA}]
    
def salvar_historico(user_id, historico):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO historico (user_id, conversas) VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET conversas = EXCLUDED.conversas, created_at = CURRENT_TIMESTAMP;"""
            ,(user_id, json.dumps(historico)))
        
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar histórico do usuário: {e}")