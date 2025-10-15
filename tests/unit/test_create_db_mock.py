import os
import pytest
from unittest.mock import patch, MagicMock
from src.bot.create_database import CreateDatabase

@pytest.fixture
def db_manager():
    os.environ['DB_TEST_NAME'] = 'bot_db_test'
    manager = CreateDatabase()
    manager.db_name = os.getenv('DB_TEST_NAME')
    return manager

@patch("psycopg2.connect")
def test_get_db_connection(mock_connect, db_manager):
    mock_conn = MagicMock()
    mock_connect.return_value = mock_conn
    conn = db_manager.get_db_connection("postgres")
    mock_connect.assert_called_with(
        database="postgres",
        host=db_manager.db_host,
        user=db_manager.db_user,
        password=db_manager.db_password,
        port=db_manager.db_port
    )
    assert conn == mock_conn
    print("✅ get_db_connection OK")

@patch("psycopg2.connect")
def test_create_database_not_exists(mock_connect, db_manager):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    db_manager.create_database(db_manager.db_name)
    mock_cursor.execute.assert_any_call(
        f"CREATE DATABASE {db_manager.db_name} OWNER {db_manager.db_user};"
    )
    print(f"✅ create_database {db_manager.db_name} OK")

@patch("psycopg2.connect")
def test_create_tables(mock_connect, db_manager):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    db_manager.create_tables(db_manager.db_name)
    mock_conn.commit.assert_called_once()
    assert mock_cursor.execute.call_count >= 1
    print("✅ create_tables OK")

@patch("psycopg2.connect")
def test_drop_database_exists(mock_connect, db_manager):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_connect.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1,)
    db_manager.drop_database(db_manager.db_name)
    mock_cursor.execute.assert_any_call(f"DROP DATABASE {db_manager.db_name};")
    print(f"✅ drop_database {db_manager.db_name} OK")
