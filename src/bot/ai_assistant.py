from datetime import datetime
import logging
from typing import Optional, Tuple

from langchain_openai import ChatOpenAI
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser

from src.schemas.slot_extraction_schema import SlotExtraction
from src.bot.database_manager import DatabaseManager

logger = logging.getLogger(__name__)

class AIAssistant:
    """Gerencia a interação com a LLM (Langchain) e o histórico de conversas."""
    def __init__(self, openai_api_key: str, messages: dict, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.resposta_sucinta = messages['RESPOSTA_SUCINTA']
        self.prompt_extrator_dados_ai = messages['PROMPT_EXTRATOR_DADOS_AI']
        self.max_historico_length = 10 # Limite de mensagens

        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-3.5-turbo", # gpt-4o-mini
            max_completion_tokens=100,
            temperature=0.7
        )

        # Configuração do Prompt de Busca Genérica
        self.search_prompt = ChatPromptTemplate.from_messages([
            ("system", self.resposta_sucinta + "\n Se houver resultados de busca de serviços, inclua-os na resposta de forma clara e concisa.")
            , ("human", "{question}")
        ])

        # Configuração do Prompt de Extração Pydantic
        self.output_parser = PydanticOutputParser(pydantic_object=SlotExtraction)

        # Gera uma lista de serviços para dar contexto à IA
        services_list = ", ".join(self.db_manager.get_available_services_names())
        contextual_prompt = self.prompt_extrator_dados_ai.format(servicos_disponiveis=services_list) # Assumindo que seu prompt aceita a variável {servicos_disponiveis}

        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", contextual_prompt + "\n{format_instructions}")
            , ("human", "{texto_usuario}")
        ]).partial(format_instructions=self.output_parser.get_format_instructions())

        # Dicionário para armazenar o histórico em memória
        self.historico_por_usuario = {} 
        self.max_historico_length = {} # {user_id: ChatMessageHistory}

    def _get_or_create_history(self, user_id: int) -> ChatMessageHistory:
        """Recupera ou inicializa o histórico de mensagens para o usuário."""
        if user_id not in self.historico_por_usuario:
            self.historico_por_usuario[user_id] = ChatMessageHistory()
            self.historico_por_usuario[user_id].add_message(SystemMessage(content=self.resposta_sucinta))
        return self.historico_por_usuario[user_id]
    
    def reset_history(self, user_id: int):
        """Reinicia o histórico de conversação do usuário."""
        self.historico_por_usuario[user_id] = ChatMessageHistory()
        self.historico_por_usuario[user_id].add_message(SystemMessage(content=self.resposta_sucinta))

    def extract_intent_and_data(self, text: str) -> SlotExtraction:
        """Chama a LLM para extrair a intenção e dados estruturados."""
        try:
            prompt_extraction = self.extraction_prompt.format_messages(texto_usuario = text)
            extraction_response = self.llm.invoke(prompt_extraction)
            logger.info(f"Resposta bruta da extração: '{extraction_response.content}'")
            
            # parseia a resposta JSON para o objeto Pydantic
            dados_estruturados: SlotExtraction = self.output_parser.parse(extraction_response.content)
            logger.info(f"Dados extraídos (JSON/Pydantic) pela IA: {dados_estruturados.model_dump()}")
            return dados_estruturados
        except Exception as e:
            logger.error(f"Erro ao extrair JSON ou parsear: {e}. Retornando SlotExtraction GENERICO.")
            # Se a extração falhar, volta para a pergunta original e trata como GENERICO
            return SlotExtraction(intent='GENERICO', servico_nome=text)
        
    def ask_gpt(self, question: str, user_id: int) -> str:
        """Chama a LLM para perguntas genéricas com histórico."""
        historico = self._get_or_create_history(user_id)
        
        try:
            historico.add_message(HumanMessage(content=question, metadata={"timestamp": datetime.now().isoformat()}))
            self.db_manager.salvar_mensagem_usuario(user_id, question) # Salva no BD

            # Obtém a lista de mensagens do histórico (incluindo SystemMessage)
            prompt = historico.messages
            logger.info(f"Prompt enviado ao LangChain (com histórico) para user_id {user_id}")
            response = self.llm.invoke(prompt)
            resposta = response.content.strip()

            # Adiciona a resposta da IA ao histórico
            historico.add_message(AIMessage(content=resposta, metadata={"timestamp": datetime.now().isoformat()}))

            # Limita o histórico com janela deslizante (mantendo a SystemMessage na 1ª posição)
            if len(historico.messages) > self.max_historico_length:
                historico.messages = [historico.messages[0]] + historico.messages[- (self.max_historico_length - 1):]

            return resposta
        
        except Exception as e:
            logger.error(f"Erro ao chamar a API da Inteligência Artificial: {e}")
            return f"Erro ao chamar a IA: {str(e)}"