import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta, time
import json
import os
from src.config import load_settings
from src.utils import MESSAGES
import logging                    

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
            logger.info(f"Erro ao conectar ao banco PostgreSQL {database}: {e}")
            raise
        except Exception as e:
            logger.info(f"Erro ao conectar ao banco PostgreSQL: {e}")
            raise

    # Função para conectar e criar tabela se não existir
    def init_db(self):
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
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

                cursor.execute("""
                CREATE TABLE IF NOT EXISTS agenda (
                    agenda_id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES usuarios(user_id) ON DELETE CASCADE,
                    servico_id BIGINT REFERENCES servicos(servico_id) ON DELETE RESTRICT,
                    hora_inicio TIME NOT NULL CHECK (hora_inicio >= '08:00' AND hora_inicio <= '22:00'),
                    hora_fim TIME NOT NULL CHECK (hora_fim >= '08:00' AND hora_fim <= '23:30'),
                    data DATE NOT NULL,
                    status VARCHAR(20) DEFAULT 'agendado' CHECK (status IN ('agendado', 'cancelado', 'concluido')),
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """)

                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_agenda_user_data_hora_inicio
                    ON agenda (user_id, data, hora_inicio);
                """)

                conn.commit()
            logger.info("Tabelas inicializadas com sucesso!")
        except Exception as e:
            logger.info(f"Erro ao inicializar as tabelas no banco: {e}")
        finally:
            conn.close()

    # Função para salvar ou atualizar usuário
    def salvar_usuario(self, user_id, nome):
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (user_id, nome) VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET nome = EXCLUDED.nome;
                    """, (user_id, nome))
                
                conn.commit()
        except Exception as e:
            logger.info(f"Erro ao salvar usuário: {e}")
            raise
        finally:
            conn.close()

    # Função para recuperar nome pelo user_id
    def get_nome_usuario(self, user_id):
        try:
            conn = self.get_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute('SELECT nome FROM usuarios WHERE user_id = %s', (user_id,))
                resultado = cursor.fetchone()
                return resultado['nome'] if resultado else None
        except Exception as e:
            logger.info(f"Erro ao recuperar nome do usuário: {e}")
            return None
        finally:
            conn.close()
        
    def get_historico(self, user_id):
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT conversas FROM historico WHERE user_id = %s", (user_id,))
                resultado = cursor.fetchone()
            return json.loads(resultado[0]) if resultado[0] else [{"role": "system", "content": self.resposta_sucinta}]
        except Exception as e:
            logger.info(f"Erro ao recuperar histórico do usuário: {e}")
            return [{"role": "system", "content": self.resposta_sucinta}]
        finally:
            conn.close()
        
    def salvar_mensagem_usuario(self, user_id, mensagem):
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
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
        except Exception as e:
            logger.info(f"Erro ao salvar mensagem do usuário: {e}")
            raise
        finally:
            conn.close()

    def buscar_servicos(self, termo: str) -> list:
        # Busca serviços na tabela de serviços com base em um termo

        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                query = """
                    SELECT servico_id, nome, descricao, preco, duracao_minutos
                    FROM servicos
                    WHERE (nome ILIKE %s OR descricao ILIKE %s)
                    AND ativo = TRUE;
                """
                cursor.execute(query, (f'%{termo}%', f'%{termo}%'))
                resultados = cursor.fetchall()
                logger.info(f"Serviços encontrados para termo '{termo}: {resultados}")
                return [
                    {
                        "servico_id": row[0]
                        , "nome": row[1]
                        , "descricao": row[2]
                        , "preco": float(row[3])
                        , "duracao_minutos": row[4]
                    }
                    for row in resultados
                ]
        except Exception as e:
            logger.error(f"Erro ao buscar serviços: {e}")
            return []
        finally:
            conn.close()

    def verificar_disponibilidade(self, data: str, hora_inicio: str, id_barbeiro: int = None):
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                query = """
                    SELECT hora_inicio, hora_fim
                    FROM agenda
                    WHERE data = %s
                    AND status IN ('agendado', 'concluido')
                """
                params = [data]
                if id_barbeiro:
                    query += " AND id_barbeiro = %s"
                    params.append(id_barbeiro)
                cursor.execute(query, params)
                agendamentos = cursor.fetchall()
                return agendamentos  # Lista de tuplas (hora_inicio, hora_fim)
        except Exception as e:
            logger.error(f"Erro ao verificar disponibilidade: {e}")
            return []
        finally:
            conn.close()

    def inserir_agendamento(self, user_id: int, servico_id: int, data: str, hora_inicio: str):
        # Verifica que DATA seja futura
        if datetime.strptime(data, '%Y-%m-%d').date() < datetime.now().date():
            return False, "Não é possível agendar para datas passadas."
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                # Obter duração do serviço
                cursor.execute("SELECT duracao_minutos FROM servicos WHERE servico_id = %s", (servico_id,))
                result = cursor.fetchone()
                if not result:
                    return False, "Serviço não encontrado."
                duracao = result[0]
                # Calcular hora_fim
                hora_inicio_dt = datetime.strptime(hora_inicio, '%H:%M')
                hora_fim_dt = hora_inicio_dt + timedelta(minutes=duracao)
                hora_fim = hora_fim_dt.strftime('%H:%M')
                # Verificar conflitos
                agendamentos = self.verificar_disponibilidade(data, hora_inicio)
                for inicio, fim in agendamentos:
                    if (time.fromisoformat(hora_inicio) < fim and hora_fim_dt.time() > inicio):
                        return False, "Horário indisponível."
                # Inserir agendamento
                cursor.execute("""
                    INSERT INTO agenda (user_id, servico_id, hora_inicio, hora_fim, data, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING agenda_id
                """, (user_id, servico_id, hora_inicio, hora_fim, data, 'agendado'))
                agenda_id = cursor.fetchone()[0]
                conn.commit()
                return True, f"Agendamento #{agenda_id} confirmado para {data} às {hora_inicio}."
        except Exception as e:
            logger.error(f"Erro ao inserir agendamento: {e}")
            return False, f"Erro ao agendar: {str(e)}"
        finally:
            conn.close()

if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.init_db()
