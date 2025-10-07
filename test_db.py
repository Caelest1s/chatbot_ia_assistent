import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'bot_db')
DB_USER = os.getenv('DB_USER', 'bot_user')
DB_PASSWORD = os.getenv('DB_PASSWORD', '1234')
DB_PORT = os.getenv('DB_PORT', '5432')

try:
    conn = psycopg2.connect(
        host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASSWORD, port=DB_PORT
    )
    print("Conexão bem-sucedida!")
    conn.close()
except Exception as e:
    print(f"Erro ao conectar: {e}")