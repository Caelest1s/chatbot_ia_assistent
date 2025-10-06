import requests
from dotenv import load_dotenv
import os # Para variaveis de ambiente 
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from database import init_db, salvar_usuario, get_nome_usuario
from datetime import datetime

# Configurações
load_dotenv()  # Carrega variáveis de ambiente do arquivo .env
TELEGRAM_API_KEY = os.getenv('TELEGRAM_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
RESPOSTA_SUCINTA = 'Responda de forma simples e curta (máximo de 15 palavras).'
WELCOME_MESSAGE = 'Bem-vindo ao chat-bot. Pergunte algo que responderei com ajuda da IA'

client = OpenAI(api_key=OPENAI_API_KEY)

historico_por_usuario = {} # {user_id: [{"role": "user", "content": ...}, ...]}

# Função para chamar a API do GPT com respostas curtas
def ask_gpt(question: str, historico: list) -> tuple:
    try:
        # Adiciona a nova pergunta do usuário ao histórico
        historico.append({"role": "user", "content": question})

        # Depuração: Mostra o histórico antes da chamada
        # print(f"Histórico enviado para a IA: {historico}")

        #Chama a API com o histórico completo
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=historico,
            max_tokens=25,
            temperature=0.7
        )
        resposta = response.choices[0].message.content.strip()

        # Adiciona a *resposta* da IA ao histórico (correção)
        historico.append({"role": "assistant", "content": resposta})
        
        # Limita o histórico para evitar excesso de tokens
        if len(historico) > 3: # Mantém apenas as últimas 3 interações
            historico = [historico[0]] + historico[-3:] # Mantém o system e as últimas 3 interações

        return resposta, historico
    except Exception as e:
        return f"Erro ao chamar a IA: {str(e)}", historico

# Inicializa o bot do Telegram
async def start(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    nome = update.message.from_user.first_name # Recupera o nome do usuário
    salvar_usuario(user_id, nome) # Salva no DB

    # Inicializa o histórico do usuário
    context.user_data['historico'] = [
        {"role": "system", "content": RESPOSTA_SUCINTA}
    ]

    await update.message.reply_text(
        f'Olá, {nome}! Bem-vindo ao chat-bot. {WELCOME_MESSAGE}'
    )

# Responde às mensagens com contexto
async def answer(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    nome = get_nome_usuario(user_id) # Recupera do DB

    if not nome:
        nome = update.message.from_user.first_name # Fallback se não estiver no DB
        salvar_usuario(user_id, nome)

    question = update.message.text

    # Recupera o histórico do usuário ou inicializa se não existir
    historico = context.user_data.get('historico', [
        {"role": "system", "content": RESPOSTA_SUCINTA}
    ])

    # Verifica mensagens duplicadas
    if historico and historico[-1].get('role') == 'user' and historico[-1].get('content') == question:
        print(f"Mensagem duplicada detectada para user_id {user_id}: {question}")
        await update.message.reply_text(f'{nome}, por favor, envie uma nova pergunta.')
        return

    historico[-1]['timestamp'] = datetime.now().isoformat() # Marca o timestamp da última mensagem
    resposta, historico = ask_gpt(question, historico) # Passa historico diretamente
    context.user_data['historico'] = historico # Atualiza o histórico

    # Depuração: Mostra o histórico atualizado
    print(f"Histórico atualizado para o user_id {user_id}: {historico}")
    
    if resposta.startswith("Erro"):
        await update.message.reply_text(resposta)
    else:
        await update.message.reply_text(f'{nome}, a IA respondeu: {resposta}') # A resposta da IA

async def reset(update: Update, context: CallbackContext):
    context.user_data['historico'] = [
        {"role": "system", "content": RESPOSTA_SUCINTA}
    ]
    await update.message.reply_text('Conversação reiniciada. Pode perguntar algo novo!') # Reseta o histórico

def main():
    if not TELEGRAM_API_KEY or not OPENAI_API_KEY:
        print("Erro: Chaves de API não definidas.")
        return

    init_db() # Inicializa o DB
    # Configura o bot do Telegram
    app = Application.builder().token(TELEGRAM_API_KEY).build()
    # Handlers de comandos e mensagens
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, answer))
    # Handler para resetar a conversa
    app.add_handler(CommandHandler('reset', reset))
    app.run_polling()

if __name__ == '__main__':
    main()