import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
import os
import json
from dotenv import load_dotenv
from src.utils.messages import MESSAGES
from datetime import datetime

load_dotenv()

class DatabaseManager:
    def __init__(self):
    # Configurações do PostgreSQL como atributos da classe
        self.db_host = os.getenv('DB_HOST')
        self.db_user = os.getenv('DB_USER')
        self.db_name = os.getenv('DB_NAME')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_port = os.getenv('DB_PORT')

        self.resposta_sucinta = MESSAGES['RESPOSTA_SUCINTA']
    # Função para obter conexão com o banco de dados
    def get_connection(self, db_name=None):
        """
        Estabelece uma conexão com o banco de dados PostgreSQL.
    
        Args:
            db_name (str, optional): Nome do banco de dados. Se None, usa self.db_name.
    
        Returns:
            psycopg2.connection: Conexão com o banco de dados.
        
        Raises:
            ValueError: Se db_name não for uma string ou se self.db_name não estiver definido.
            OperationalError: Se houver um erro de conexão com o banco.
            Exception: Para outros erros inesperados.
        """
        if not self.db_name:
            raise ValueError("O nome do banco de dados (self.db_name) não está definido.")

        database = db_name if db_name else self.db_name
        if db_name and not isinstance(db_name, str):
            raise ValueError("O nome do banco de dados (db_name) deve ser uma string.")
        
        try:
            conn = psycopg2.connect(
                database=database.strip()
                , host=self.db_host
                , user=self.db_user
                , password=self.db_password
                , port=self.db_port
            )
            return conn
        except OperationalError as e:
            print(f"Erro ao conectar ao banco PostgreSQL {database}: {e}")
            raise
        except Exception as e:
            print(f"Erro ao conectar ao banco PostgreSQL: {e}")
            raise

    # Função para conectar e criar tabela se não existir
    def init_db(self):
        try:
            conn = self.get_connection()
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
    def salvar_usuario(self, user_id, nome):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO usuarios (user_id, nome) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET nome = EXCLUDED.nome;
                """, (user_id, nome))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro ao salvar usuário: {e}")

    # Função para recuperar nome pelo user_id
    def get_nome_usuario(self, user_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute('SELECT nome FROM usuarios WHERE user_id = %s', (user_id,))
            resultado = cursor.fetchone()
            cursor.close()
            conn.close()
            return resultado['nome'] if resultado else None
        except Exception as e:
            print(f"Erro ao recuperar nome do usuário: {e}")
            return None
        
    def get_historico(self, user_id):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT conversas FROM historico WHERE user_id = %s", (user_id,))
            resultado = cursor.fetchone()
            cursor.close()
            conn.close()

            return json.loads(resultado[0]) if resultado[0] else [{"role": "system", "content": self.resposta_sucinta}]
        except Exception as e:
            print(f"Erro ao recuperar histórico do usuário: {e}")
            return [{"role": "system", "content": self.resposta_sucinta}]
        
    def salvar_mensagem_usuario(self, user_id, mensagem):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT conversas FROM historico WHERE user_id = %s", (user_id,))
            resultado = cursor.fetchone()
            mensagens_usuario = json.loads(resultado[0]) if resultado and resultado[0] else []

            mensagens_usuario.append({"role": "user", "content": mensagem, "timestamp": datetime.now().isoformat()})

            # Salva de volta (apenas mensagens do usuário)
            cursor.execute("""
                INSERT INTO historico (user_id, conversas) VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET conversas = EXCLUDED.conversas, created_at = CURRENT_TIMESTAMP;
                """, (user_id, json.dumps(mensagens_usuario)))
            
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro ao salvar mensagem do usuário: {e}")

if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.init_db()