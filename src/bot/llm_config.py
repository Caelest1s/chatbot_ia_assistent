# # src/bot/llm_config.py
import os
import json
import asyncio
from src.config.logger import setup_logger

from typing import Callable

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain.output_parsers import PydanticOutputParser

from src.schemas.slot_extraction_schema import SlotExtraction
from src.prompts.system.llm_orchestrator import LLMOrchestrator
from src.bot.extraction.slot_filler import SlotFiller
from src.services.persistence_service import PersistenceService

from src.prompts.router.classification_router import ClassificationRouter

from src.tools.available_tools import ALL_TOOLS

logger = setup_logger(__name__)

class LLMConfig:
    """Configura o modelo LLM e os prompts base."""
    def __init__(self, openai_api_key: str, services_list: list[str], persistence_service: PersistenceService):
        
        # 1. Configuração do LLM Base
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",    # ou gpt-3.5-turbo
            temperature=0.0, 
            max_completion_tokens=300,
        )
        self.persistence_service = persistence_service
        self.services_list = services_list
        self.services_context = ", ".join(services_list) if services_list else "Nenhum"
        
        # 2. INSTANCIA O NOVO ROTEADOR DINÂMICO, isso permite que o LLM decida qual função chamar
        self.router = ClassificationRouter(llm=self.llm)
        self.llm_with_tools = self.llm.bind_tools(ALL_TOOLS) if ALL_TOOLS else self.llm

    def _get_extraction_chain(self) -> Runnable:
        """Configura a chain de extração de slots (Pydantic)."""
        output_parser = PydanticOutputParser(pydantic_object=SlotExtraction)

        # Carregar prompt de extração (pode ser movido para .txt depois)
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Extraia os dados de agendamento. Serviços: {servicos}\n{format_instructions}")
            ("human", "{texto_usuario}")
        ]).partial(
            servicos=self.services_context, 
            format_instructions=output_parser.get_format_instructions()
        )

        return prompt | self.llm | output_parser
    
    def _get_tool_chain(self) -> Runnable:
        """Chain que processa perguntas usando Tools."""
        # Aqui o LLM recebe o texto e decide se chama a Tool de preço, disponibilidade, etc.
        return (lambda x: x['texto_usuario']) | self.llm_with_tools
    
    def _get_general_chain(self) -> Runnable:
        system_prompt = (
            "Você é assistente virtual do {nome_negocio}, "
            "um negócio de {dominio}. "
            "Ofereça um atendimento educado, objetivo e profissional. "
            "Sempre direcione o cliente para as opções de atendimento disponíveis."
        )

        prompt_template = ChatPromptTemplate.from_messages([("system", system_prompt), ("human", "{texto_usuario}")])
        return prompt_template | self.llm
    
    def create_bot_orchestrator(self, reset_fn: Callable, user_id: int) -> Runnable:
        """Monta o orquestrador injetando o roteador dinâmico e o especialista em extração."""
        
        # 1. Instancia o especialista em extração
        filler = SlotFiller(self.llm, self.services_context)

        # 2. Busca os slots atuais do banco
        async def get_slots_async(input_data):
            try:
                state = await self.persistence_service.get_session_state(user_id)
                return state.get('slot_data', {}) if state else {}
            except Exception as e:
                logger.warning(f"Erro assíncrono ao buscar slots: {e}")
                return {}
            
        # 3. Criamos a chain de extração USANDO o filler e a função de slots
        extraction_chain = filler.get_extraction_chain(get_slots_fn=get_slots_async)
        
        # 4. CRIAMOS O ORQUESTRADOR PASSANDO O NOSSO NOVO ROTEADOR
        orchestrator = LLMOrchestrator(
            llm=self.llm,
            router_chain=self.router.get_router_chain(),
            extraction_chain=extraction_chain,
            tool_chain=self._get_tool_chain(),
            general_chain=self._get_general_chain(),
            reset_function=reset_fn
        )
        return orchestrator.get_orchestrator_chain()
