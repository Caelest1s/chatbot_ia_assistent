from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from src.schemas.slot_extraction_schema import SlotExtraction
from src.utils.system_message import MESSAGES

class LLMConfig:
    """Configura o modelo LLM e os prompts base."""
    def __init__(self, openai_api_key: str, services_list: list):
        # 1. Configuração do Modelo
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-3.5-turbo", # gpt-4o-mini
            max_completion_tokens=100,
            temperature=0.4
        )

        # 2. Configuração do Prompt de Busca Genérica (Conversação com Histórico)
        self.search_prompt = ChatPromptTemplate.from_messages([
            ("system", MESSAGES['RESPOSTA_SUCINTA'] + "\n Se houver resultados de busca de serviços, "
                "inclua-os na resposta de forma clara e concisa.")
                , ("human", "{question}")
        ])

        # 3. Configuração do Prompt de Extração Pydantic
        self.output_parser = PydanticOutputParser(pydantic_object=SlotExtraction)

        # Prepara o contexto de serviços
        services_context = ", ".join(services_list)
        contextual_prompt = MESSAGES['PROMPT_EXTRATOR_DADOS_AI'].format(servicos_disponiveis=services_context)

        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", contextual_prompt + "\n {format_instructions}")
                , ("human", "{texto_usuario}")
        ]).partial(format_instructions=self.output_parser.get_format_instructions())