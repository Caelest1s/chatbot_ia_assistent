import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.bot.main import AIAgent

# -----------------------------
# Fixture do AIAgent com mocks
# -----------------------------
@pytest.fixture
def mocked_ai_agent():
    with patch("src.bot.ai_agent.OpenAI") as mock_openai, \
         patch("src.bot.ai_agent.DatabaseManager") as mock_db_manager, \
         patch("src.bot.ai_agent.Application") as mock_app, \
         patch("os.getenv") as mock_getenv:
        
        # Mock das variáveis de ambiente
        mock_getenv.side_effect = lambda key: "fake_key"
        
        # Mock do cliente OpenAI
        mock_client_instance = MagicMock()
        mock_client_instance.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Resposta de teste"))]
        )
        mock_openai.return_value = mock_client_instance

        # Mock do DatabaseManager
        mock_db_instance = MagicMock()
        mock_db_manager.return_value = mock_db_instance

        agent = AIAgent()
        yield agent, mock_client_instance, mock_db_instance

# -----------------------------
# Teste da função ask_gpt
# -----------------------------
def test_ask_gpt(mocked_ai_agent):
    agent, mock_client, mock_db = mocked_ai_agent

    user_id = 123
    question = "Qual é a capital do Brasil?"

    resposta, historico = agent.ask_gpt(question, user_id)

    # Verifica se retornou a resposta mockada
    assert resposta == "Resposta de teste"

    # Verifica se o histórico contém user e assistant
    assert historico[1]['role'] == "user"
    assert historico[2]['role'] == "assistant"

    # Verifica se o DatabaseManager foi chamado para salvar a mensagem do usuário
    mock_db.salvar_mensagem_usuario.assert_called_with(user_id, question)

    # Verifica limite de histórico
    agent.max_historico_length = 2
    _, historico_limitado = agent.ask_gpt("Nova pergunta", user_id)
    assert len(historico_limitado) <= 2

# -----------------------------
# Teste da função start
# -----------------------------
@pytest.mark.asyncio
async def test_start(mocked_ai_agent):
    agent, _, mock_db = mocked_ai_agent

    update = MagicMock()
    update.message.from_user.id = 1
    update.message.from_user.first_name = "Jefferson"
    update.message.reply_text = AsyncMock()

    context = AsyncMock()

    await agent.start(update, context)

    # Verifica se usuário foi salvo
    mock_db.salvar_usuario.assert_called_with(1, "Jefferson")

    # Verifica histórico inicial
    assert agent.historico_por_usuario[1][0]['role'] == "system"

    # Verifica envio de mensagem
    update.message.reply_text.assert_called()

# -----------------------------
# Teste da função answer
# -----------------------------
@pytest.mark.asyncio
async def test_answer(mocked_ai_agent):
    agent, _, mock_db = mocked_ai_agent
    user_id = 1

    # Prepara usuário no DB
    mock_db.get_nome_usuario.return_value = "Jefferson"

    update = MagicMock()
    update.message.from_user.id = user_id
    update.message.from_user.first_name = "Jefferson"
    update.message.text = "Pergunta teste"
    update.message.reply_text = AsyncMock()
    context = AsyncMock()

    await agent.answer(update, context)

    # Verifica se mensagem foi salva
    mock_db.salvar_mensagem_usuario.assert_called_with(user_id, "Pergunta teste")

    # Verifica resposta enviada
    update.message.reply_text.assert_called()

# -----------------------------
# Teste da função reset
# -----------------------------
@pytest.mark.asyncio
async def test_reset(mocked_ai_agent):
    agent, _, _ = mocked_ai_agent
    user_id = 1

    agent.historico_por_usuario[user_id] = [{"role": "user", "content": "msg"}]

    update = MagicMock()
    update.message.from_user.id = user_id
    update.message.reply_text = AsyncMock()
    context = AsyncMock()

    await agent.reset(update, context)

    # Histórico resetado
    assert agent.historico_por_usuario[user_id][0]['role'] == "system"
    update.message.reply_text.assert_called()
