import requests
import os # Para variaveis de ambiente 
from src.config import settings_loader

from langchain_openai import ChatOpenAI
from langchain.memory import ChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from src.bot.database_manager import DatabaseManager
from src.utils import MESSAGES
import logging
from datetime import datetime, timedelta, time

import re

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
        
        self.llm = ChatOpenAI(
            api_key=self.openai_api_key,
            model="gpt-3.5-turbo", # gpt-4o-mini
            max_completion_tokens=100,
            temperature=0.7
        )

        # Inicializa o gerenciador de banco de dados
        self.db_manager = DatabaseManager()
        self.db_manager.init_db()

        # Inicializa o aplicativo do Telegram
        self.app = Application.builder().token(self.telegram_api_key).build()

        # Dicionário para armazenar o histórico em memória
        self.historico_por_usuario = {} # {user_id: ChatMessageHistory}

        # Limite de mensagens no histórico em memória (ajustável para 30)
        self.max_historico_length = 10 # System + últimas (N-1) interações

        # Adicionar prompt personalizado para buscas
        self.search_prompt = ChatPromptTemplate.from_messages([
            ("system", self.resposta_sucinta + "\n Se houver resultados de busca de serviços, inclua-os na resposta de forma clara e concisa.")
            , ("human", "pergunta: {question}\nResultados da busca: {search_results}")
        ])

    def ask_gpt(self, question: str, user_id: int) -> tuple:
        # Chama a API da OpenAI com a pergunta do usuário e gerencia o histórico em memória.
        # Salva apenas a mensagem do usuário no BD.
        # Args:
            # question (str): Pergunta do usuário.
            # user_id (int): ID do usuário.
        # Returns:
            # tuple: (resposta da IA, histórico atualizado).

        # Recupera ou inicializa o histórico do usuário
        if user_id not in self.historico_por_usuario:
            self.historico_por_usuario[user_id] = ChatMessageHistory()
            self.historico_por_usuario[user_id].add_message(SystemMessage(content=self.resposta_sucinta))

        historico = self.historico_por_usuario[user_id]
        
        try:
            # Verifica se a pergunta é sobre serviços
            match = re.search(r'\b(buscar|serviço|serviços|preço|preços|agendar)\s+(?:de\s+|da\s+|do\s+)?(\w+)', question, re.IGNORECASE)
            if match:
                termo = match.group(2).strip().lower()
                logger.info(f"Busca acionada com termo: {termo}")
                resultados = self.db_manager.buscar_servicos(termo)
                logger.info(f"Resultados da busca: {resultados}")
                if resultados:
                    search_results = "\n".join([
                        f"- {r['nome']}: {r['descricao']} (Preço: RS{r['preco']:.2f}, Duração: {r['duracao_minutos']} min)"
                        for r in resultados
                    ])
                else:
                    search_results = "nenhum serviço encontrado."
            else:
                search_results = "Nenhuma busca de serviços realizada."
                logger.info("Nenhuma busca de serviço acionada.")

            historico.add_message(HumanMessage(content=question, metadata={"timestamp": datetime.now().isoformat()}))
            logger.info(f"Histórico atualizado para o user_id {user_id}: {historico.messages}")

            # Salva apenas a mensagem do usuário no BD
            self.db_manager.salvar_mensagem_usuario(user_id, question)

            #Chama o modelo com o histórico completo
            prompt = self.search_prompt.format_messages(question = question, search_results = search_results)
            logger.info(f"Prompt enviado ao LangChain: {prompt}")
            response = self.llm.invoke(prompt)
            resposta = response.content.strip()

            # Adiciona a resposta da IA ao histórico
            historico.add_message(AIMessage(content=resposta, metadata={"timestamp": datetime.now().isoformat()}))

            # Limita o histórico com janela deslizante
            if len(historico.messages) > self.max_historico_length:
                historico.messages = [historico.messages[0]] + historico.messages[- (self.max_historico_length - 1):]

            # Atualiza o histórico em memória
            return resposta, historico
        except Exception as e:
            logger.error(f"Erro ao chamar a API da Inteligência Artificial: {e}")
            return f"Erro ao chamar a IA: {str(e)}", historico
        
    # Responde às mensagens com contexto
    async def answer(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        question = update.message.text
        logger.info(f"Mensagem recebida de {nome} (user_id: {user_id}): {question}")

        # Detectar intenção de agendamento via linguagem natural
        match = re.search(
            r'\b(agendar|marcar|reserva)\s+([\w\s]+?)\s*(?:para\s+|em\s+|no\s+|na\s+)?(\d{2}[/-]\d{2}[/-]\d{4})\s+(\d{1,2}:\d{2})',
            question,
            re.IGNORECASE
        )
        if match:
            logger.info(f"Match encontrado: {match.groups()}")
            _, servico_nome, data, hora = match.groups()  # Extrair os grupos da regex
            logger.info(f"Extraído: servico_nome={servico_nome}, data={data}, hora={hora}")
            try:
                # Normalizar data para YYYY-MM-DD
                data = data.replace('-', '/')  # Converter - para /
                data_dt = datetime.strptime(data, '%d/%m/%Y').strftime('%Y-%m-%d')
                # Normalizar hora para HH:MM
                hora_dt = datetime.strptime(hora, '%H:%M').strftime('%H:%M')
                # Buscar serviço
                servicos = self.db_manager.buscar_servicos(servico_nome.strip())
                if not servicos:
                    logger.info(f"Serviço não encontrado: {servico_nome}")
                    await update.message.reply_text(f'{nome}, serviço "{servico_nome}" não encontrado. Tente: /servicos para listar.')
                    return
                servico_id = servicos[0]['servico_id']
                # Inserir agendamento
                sucesso, mensagem = self.db_manager.inserir_agendamento(user_id, servico_id, data_dt, hora_dt)
                await update.message.reply_text(f'{nome}, {mensagem}')
                return
            except ValueError as e:
                logger.error(f"Formato inválido: {e}")
                await update.message.reply_text(
                    f'{nome}, formato inválido. Use: agendar <serviço> <DD/MM/AAAA> <HH:MM>\n'
                    f'Exemplo: agendar corte degradê 20/10/2025 09:00'
                )
                return
            except Exception as e:
                logger.error(f"Erro ao processar agendamento: {e}")
                await update.message.reply_text(f'{nome}, erro ao agendar: {str(e)}')
                return
        else:
            logger.info(f"Nenhum match de agendamento encontrado para: {question}")

        # Resposta padrão para outras mensagens
        historico = self.historico_por_usuario.get(user_id, ChatMessageHistory())
        if not historico.messages:
            historico.add_message(SystemMessage(content=self.resposta_sucinta))

        if historico.messages and historico.messages[-1].type == 'human' and historico.messages[-1].content == question:
            logger.info(f"Mensagem duplicada detectada para user_id {user_id}: {question}")
            await update.message.reply_text(f'{nome}, por favor, envie uma nova pergunta.')
            return

        resposta, historico = self.ask_gpt(question, user_id)
        await update.message.reply_text(f'{nome}, a IA respondeu: {resposta}')

# ================================== Handlers Command Custom ==================================
    async def agenda(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        args = context.args
        logger.info(f"Comando /agendar recebido de {nome} (user_id: {user_id}): {args}")

        if len(args) < 3:
            logger.info("Argumentos insuficientes para /agendar")
            await update.message.reply_text(
                f'{nome}, use o formato: /agendar <serviço> <data: DD/MM/AAAA> <hora: HH:MM>\n'
                f'Exemplo: /agendar corte degradê 20/10/2025 09:00'
            )
            return

        # Juntar palavras do serviço (permite nomes compostos)
        servico_nome = ' '.join(args[:-2]).strip()
        data = args[-2]
        hora = args[-1]
        logger.info(f"Extraído de /agendar: servico_nome={servico_nome}, data={data}, hora={hora}")

        try:
            # Normalizar data para YYYY-MM-DD
            data = data.replace('-', '/')  # Aceita - ou /
            data_dt = datetime.strptime(data, '%d/%m/%Y').strftime('%Y-%m-%d')
            # Normalizar hora para HH:MM
            hora_dt = datetime.strptime(hora, '%H:%M').strftime('%H:%M')
            # Buscar serviço
            servicos = self.db_manager.buscar_servicos(servico_nome)
            if not servicos:
                logger.info(f"Serviço não encontrado: {servico_nome}")
                await update.message.reply_text(f'{nome}, serviço "{servico_nome}" não encontrado. Tente: /servicos para listar.')
                return
            servico_id = servicos[0]['servico_id']
            # Inserir agendamento
            sucesso, mensagem = self.db_manager.inserir_agendamento(user_id, servico_id, data_dt, hora_dt)
            await update.message.reply_text(f'{nome}, {mensagem}')
        except ValueError as e:
            logger.error(f"Formato inválido: {e}")
            await update.message.reply_text(
                f'{nome}, formato inválido. Use: /agendar <serviço> <DD/MM/AAAA> <HH:MM>\n'
                f'Exemplo: /agendar corte degradê 20/10/2025 09:00'
            )
        except Exception as e:
            logger.error(f"Erro ao processar agendamento: {e}")
            await update.message.reply_text(f'{nome}, erro ao agendar: {str(e)}')

    async def servicos(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        servicos = self.db_manager.buscar_servicos('')
        if not servicos:
            await update.message.reply_text(f'{nome}, nenhum serviço disponível.')
            return
        resposta = "Serviços disponíveis:\n" + "\n".join([
            f"- {s['nome']}: {s['descricao']} (R${s['preco']:.2f}, {s['duracao_minutos']} min)"
            for s in servicos
        ])
        await update.message.reply_text(f'{nome}, {resposta}')
# ================================== Handler Command Default ==================================
    # Inicializa o bot do Telegram
    async def start(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        nome = update.message.from_user.first_name # Recupera o nome do usuário
        self.db_manager.salvar_usuario(user_id, nome)
        self.historico_por_usuario[user_id] = ChatMessageHistory()
        self.historico_por_usuario[user_id].add_message(SystemMessage(content=self.resposta_sucinta))
        await update.message.reply_text(f'Olá, {nome}! {self.welcome_message}')

    async def reset(self, update: Update, context: CallbackContext):
        user_id = update.message.from_user.id
        self.historico_por_usuario[user_id] = ChatMessageHistory() # Reseta o histórico na memória
        self.historico_por_usuario[user_id].add_message(SystemMessage(content=self.resposta_sucinta))
        await update.message.reply_text('Conversação reiniciada. Pode perguntar algo novo!')

    # Configura os handlers e inicia o bot
    def run(self):
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.answer))
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('reset', self.reset))
        self.app.add_handler(CommandHandler('servicos', self.servicos))
        self.app.add_handler(CommandHandler('agenda', self.agenda))
        logger.info("Iniciando o bot do Telegram...")
        self.app.run_polling()

if __name__ == '__main__':
    try:
        bot = AIAgent()
        bot.run()
    except Exception as e:
        logger.error(f"Erro de configuração: {e}")