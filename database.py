import sqlite3

# Função para conectar e criar tabela se não existir
def init_db():
    # Cria o arquivo DB se não existir
    conn = sqlite3.connect('usuarios.db') 
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    
# Função para salvar ou atualizar usuário
def salvar_usuario(user_id, nome):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO usuarios (user_id, nome) VALUES (?, ?)
    ''', (user_id, nome))
    conn.commit()
    conn.close()

# Função para recuperar nome pelo user_id
def get_nome_usuario(user_id):
    conn = sqlite3.connect('usuarios.db')
    cursor = conn.cursor()
    cursor.execute('SELECT nome FROM usuarios WHERE user_id = ?', (user_id,))
    resultado = cursor.fetchone()
    conn.close()
    return resultado[0] if resultado else None