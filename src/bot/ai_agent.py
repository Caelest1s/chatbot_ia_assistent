import requests
import os # Para variaveis de ambiente 
from src.config import settings_loader
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from src.bot.database_manager import DatabaseManager
from src.utils import MESSAGES
import logging
from datetime import datetime

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) 

class AIAgent:
    def __init__(self):
        # Inicializa o bot do Telegram com configurações, cliente OpenAI e histórico em memória.
        self.telegram_api_key = os.getenv('TELEGRAM_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.resposta_sucinta = MESSAGES['RESPOSTA_SUCINTA']
        self.welcome_message = MESSAGES['WELCOME_MESSAGE']

        # Verifica chaves de API
        if not self.telegram_api_key or not self.openai_api_key:
            raise ValueError("Chaves de API (TELEGRAM ou OPENAI) não definidas.")
        
        # Inicializa o cliente OpenAI
        self.client = OpenAI(api_key=self.openai_api_key)
        
        # Inicializa o gerenciador de banco de dados
        self.db_manager = DatabaseManager()
        self.db_manager.init_db()

        # Inicializa o aplicativo do Telegram
        self.app = Application.builder().token(self.telegram_api_key).build()

        # Dicionário para armazenar o histórico em memória
        self.historico_por_usuario = {} # {user_id: [{"role": "...", "content": "...", "timestamp": "..."}]}

        # Limite de mensagens no histórico em memória (ajustável para 30)
        self.max_historico_length = 10 # System + últimas (N-1) interações

    def ask_gpt(self, question: str, user_id: int) -> tuple:
        # Chama a API da OpenAI com a pergunta do usuário e gerencia o histórico em memória.
        # Salva apenas a mensagem do usuário no BD.
        # Args:
            # question (str): Pergunta do usuário.
            # user_id (int): ID do usuário.
        # Returns:
            # tuple: (resposta da IA, histórico atualizado).

        # Recupera ou inicializa o histórico do usuário
        historico = self.historico_por_usuario.get(
            user_id, [{"role": "system", "content": self.resposta_sucinta}]
        )
        try:
            historico.append({"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
            logger.info(f"Histórico atualizado para o user_id {user_id}: {historico}")

            # Salva apenas a mensagem do usuário no BD
            self.db_manager.salvar_mensagem_usuario(user_id, question)

            #Chama a API com o histórico completo
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=historico,
                max_tokens=30,
                temperature=0.7
            )
            resposta = response.choices[0].message.content.strip()

            # Adiciona a resposta da IA ao histórico
            historico.append({"role": "assistant", "content": resposta, "timestamp": datetime.now().isoformat()})

            # Limita o histórico com janela deslizante
            if len(historico) > self.max_historico_length:
                historico = [historico[0]] + historico[- (self.max_historico_length - 1):]

            # Atualiza o histórico em memória
            self.historico_por_usuario[user_id] = historico
            return resposta, historico
        except Exception as e:
            logger.error(f"Erro ao chamar a API da Inteligência Artificial: {e}")
            return f"Erro ao chamar a IA: {str(e)}", historico

    # Inicializa o bot do Telegram
    async def start(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = update.message.from_user.first_name # Recupera o nome do usuário
        self.db_manager.salvar_usuario(user_id, nome)
        self.historico_por_usuario[user_id] = [{"role": "system", "content": self.resposta_sucinta}]
        await update.message.reply_text(f'Olá, {nome}! {self.welcome_message}')

    # Responde às mensagens com contexto
    async def answer(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) # Recupera nome do usuario no DB

        if not nome:
            nome = update.message.from_user.first_name # Fallback se não estiver no DB
            self.db_manager.salvar_usuario(user_id, nome)

        question = update.message.text
        historico = self.historico_por_usuario.get(
            user_id, [{"role": "system", "content": self.resposta_sucinta}]
        )

        # Verifica mensagens duplicadas
        if historico and historico[-1].get('role') == 'user' and historico[-1].get('content') == question:
            logger.info(f"Mensagem duplicada detectada para user_id {user_id}: {question}")
            await update.message.reply_text(f'{nome}, por favor, envie uma nova pergunta.')
            return

        resposta, historico = self.ask_gpt(question, user_id)
        await update.message.reply_text(f'{nome}, a IA respondeu: {resposta}') # A resposta da IA

    async def reset(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        self.historico_por_usuario[user_id] = [{"role": "system", "content": self.resposta_sucinta}] # Reseta o histórico na memória
        await update.message.reply_text('Conversação reiniciada. Pode perguntar algo novo!')

    # Configura os handlers e inicia o bot
    def run(self):
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.answer))
        self.app.add_handler(CommandHandler('reset', self.reset))
        logger.info("Iniciando o bot do Telegram...")
        self.app.run_polling()

if __name__ == '__main__':
    try:
        bot = AIAgent()
        bot.run()
    except Exception as e:
        logger.error(f"Erro de configuração: {e}")