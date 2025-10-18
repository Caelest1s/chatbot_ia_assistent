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

                cursor.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_agenda_user_data_horario
                    ON agenda (user_id, data, horario);
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
                    WHERE nome ILIKE %s OR descricao ILIKE %s
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

    # def listar_horarios_disponiveis(conn, data):
    #     # Lista horários disponíveis para agendamento em uma data específica.
    #     cursor = conn.cursor()

    #     # Gera a lista de horários de 08h às 22h, de hora em hora
    #     inicio = time(8, 0)
    #     fim = time(22, 0)
    #     intervalo = timedelta(hours=1)
    #     horarios = []
    #     atual = datetime.combine(data, inicio)
    #     while atual.time() <= fim:
    #         horarios.append(atual.time())
    #         atual += intervalo

    #     # Busca horários já ocupados nessa data
    #     cursor.execute("""
    #         SELECT horario FROM agenda
    #         WHERE data = %s AND status IN ('pendente', 'confirmado')
    #     """, (data,))
    #     ocupados = {row[0] for row in cursor.fetchall()}

    #     # Retorna apenas os disponíveis
    #     disponiveis = [h for h in horarios if h not in ocupados]
    #     cursor.close()
    #     return disponiveis
    
    # def agendar_horario(conn, user_id, servico_id, data, horario):
    #     # Agenda um horário se disponível. return True se agendado, False se ocupado.
    #     cursor = conn.cursor()

    #     # Verifica se já existe agendamento para o mesmo horário e data
    #     cursor.execute("""
    #         SELECT COUNT(*) FROM agenda
    #         WHERE data = %s AND horario = %s
    #         AND status IN ('pendente', 'confirmado')
    #     """, (data, horario))
    #     existe = cursor.fetchone()[0] > 0

    #     if existe:
    #         cursor.close()
    #         return False  # Já ocupado

    #     # Insere novo agendamento
    #     cursor.execute("""
    #         INSERT INTO agenda (user_id, servico_id, data, horario, status)
    #         VALUES (%s, %s, %s, %s, 'pendente')
    #     """, (user_id, servico_id, data, horario))
    #     conn.commit()
    #     cursor.close()
    #     return True
    
    # def confirmar_horario(conn, agenda_id):
    #     # Confirma um horário pendente.
    #     cursor = conn.cursor()
    #     cursor.execute("""
    #         UPDATE agenda
    #         SET status = 'confirmado'
    #         WHERE agenda_id = %s AND status = 'pendente'
    #     """, (agenda_id,))
    #     conn.commit()
    #     atualizado = cursor.rowcount > 0
    #     cursor.close()
    #     return atualizado
    
    # def cancelar_horario(conn, agenda_id):
    #     # Cancela um horário (mantém histórico).
    #     cursor = conn.cursor()
    #     cursor.execute("""
    #         UPDATE agenda
    #         SET status = 'cancelado'
    #         WHERE agenda_id = %s AND status IN ('pendente', 'confirmado')
    #     """, (agenda_id,))
    #     conn.commit()
    #     cancelado = cursor.rowcount > 0
    #     cursor.close()
    #     return cancelado

if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.init_db()

    resultados = db_manager.buscar_servicos("manicure")
    print(resultados)