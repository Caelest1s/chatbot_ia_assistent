import os
import pytest
from src.bot.create_database import CreateDatabase

@pytest.fixture(scope="module")
def db_manager():
    os.environ['DB_TEST_NAME'] = 'bot_db_integration_test'
    manager = CreateDatabase()
    manager.db_name = os.getenv('DB_TEST_NAME')
    return manager

def test_database_creation_and_drop(db_manager):
    """
    Cria banco de teste, cria tabelas, verifica existência e drop.
    """
    # DROP preventivo
    try:
        db_manager.drop_database(db_manager.db_name)
    except Exception:
        pass

    # CREATE DATABASE e CREATE TABLES
    db_manager.create_database(db_manager.db_name)
    db_manager.create_tables(db_manager.db_name)

    # Conecta ao banco real de teste
    conn = db_manager.get_db_connection(db_manager.db_name)
    cursor = conn.cursor()

    # Verifica tabelas
    for table in ['usuarios', 'historico', 'servicos']:
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table}'
            );
        """)
        exists = cursor.fetchone()[0]
        assert exists, f"Tabela '{table}' não foi criada"
        print(f"✅ Tabela '{table}' existe")

    cursor.close()
    conn.close()

    # DROP DATABASE
    db_manager.drop_database(db_manager.db_name)
    print(f"✅ Banco de teste '{db_manager.db_name}' dropado com sucesso")
