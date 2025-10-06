import requests
from dotenv import load_dotenv
import os # Para variaveis de ambiente 
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from database import init_db, salvar_usuario, get_nome_usuario

# Configurações
load_dotenv()  # Carrega variáveis de ambiente do arquivo .env
TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
RESPOSTA_SUCINTA = 'Responda de forma simples e curta (máximo de 15 palavras).'

client = OpenAI(
    api_key=OPENAI_API_KEY
)

historico_por_usuario = {} # {user_id: [{"role": "user", "content": ...}, ...]}

# Função para chamar a API do Grok com respostas curtas
def ask_gpt(question: str, user_id: int) -> str:
    try:
        # Inicializa o histórico do usuário se não existir
        if user_id not in historico_por_usuario:
            historico_por_usuario[user_id] = [
                # role -> [user (person), assistant(IA), system (config)]
                {"role": "system", "content": RESPOSTA_SUCINTA}
            ]
        historico = historico_por_usuario[user_id]

        # Adiciona a nova pergunta do usuário ao histórico
        historico.append({"role": "user", "content": question})

        #Chama a API com o histórico completo
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=historico,
            max_tokens=25,
            temperature=0.7
        )

        resposta = response.choices[0].message.content.strip()

        # Adiciona a resposta da IA ao histórico
        historico.append({"role": "assistant", "content": resposta})
        
        if len(historico) > 3: # Mantém apenas as últimas 5 interações
            historico_por_usuario[user_id] = historico[-5:]

        return resposta, historico
    except Exception as e:
        return f"Erro ao chamar a IA: {str(e)}"

# Inicializa o DB
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    nome = update.message.from_user.first_name # Recupera o nome do usuário
    salvar_usuario(user_id, nome) # Salva no DB

    historico_por_usuario[user_id] = [
        {"role": "system", "content": RESPOSTA_SUCINTA}
    ]

    await update.message.reply_text(
        f'Olá, {nome}! Bem-vindo ao chat-bot. Pergunte algo que responderei com ajuda da IA'
    )

async def answer(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    nome = get_nome_usuario(user_id) # Recupera do DB
    if not nome:
        nome = update.message.from_user.first_name # Fallback se não estiver no DB
        salvar_usuario(user_id, nome)

    question = update.message.text
    resposta, _ = ask_gpt(question, user_id) # Chama a IA
    await update.message.reply_text(f'{nome}, {resposta}') # A resposta da IA

def main():
    init_db() # Inicializa o DB
    app = Application.builder().token(TELEGRAM_API_KEY).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer))
    app.run_polling()

if __name__ == '__main__':
    main()