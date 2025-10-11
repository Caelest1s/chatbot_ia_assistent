import pytest
from create_database import create_database, create_tables, get_db_connection
from dotenv import load_dotenv
import os

load_dotenv()

# Configurações Test do PostgreSQL
DATABASE = os.getenv('DATABASE')
DB_HOST = os.getenv('DB_HOST')
DB_USER_TEST = os.getenv('DB_USER_TEST')
DB_NAME_TEST = os.getenv('DB_NAME_TEST')
DB_PASSWORD_TEST = os.getenv('DB_PASSWORD_TEST')
DB_PORT_TEST = os.getenv('DB_PORT_TEST')

def test_create_database_and_tables():
    create_database()
    create_tables()
    conn = get_db_connection()