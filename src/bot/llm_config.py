# # src/bot/llm_config.py (bloco de inicialização)
import json
from datetime import datetime, date

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable

from src.schemas.slot_extraction_schema import SlotExtraction
from src.utils.system_message import MESSAGES

class LLMConfig:
    """Configura o modelo LLM e os prompts base."""
    def __init__(self, openai_api_key: str, services_list: list):
        # 1. Configuração do Modelo
        self.llm = ChatOpenAI(
            api_key=openai_api_key,
            model="gpt-4o-mini",    # ou gpt-3.5-turbo
            max_completion_tokens=100,
            temperature=0.0         # temperatura 0 para extração confiável
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
        services_context = ", ".join(services_list) if services_list else "Nenhum serviço disponível"


        contextual_prompt = MESSAGES['PROMPT_EXTRATOR_DADOS_AI'].format(
            slot_data_atual="{slot_data_atual}"
            , servicos_disponiveis=services_context
        )

        self.extraction_prompt = ChatPromptTemplate.from_messages([
            ("system", contextual_prompt + "\n {format_instructions}")
                , ("human", "{texto_usuario}")
        ]).partial(format_instructions=self.output_parser.get_format_instructions())

    def get_extraction_chain(self, current_slots: dict) -> Runnable:
        """Retorna a chain com os slots atuais injetados no prompt."""
        
        # ⚠️ TRATAMENTO DE DATE/DATETIME:
        # Se você estiver passando objetos datetime.date para cá (o que a LangChain não consegue serializar),
        # você deve convertê-los em string AQUI. No entanto, se o seu slot_filling_manager.py
        # já estiver tratando isso, apenas fazemos o dump.
        
        # O mais seguro é converter manualmente aqui:
        slots_to_dump = {}
        for k, v in current_slots.items():
            if isinstance(v, (date, datetime)):
                slots_to_dump[k] = v.strftime('%Y-%m-%d' if k == 'data' else '%Y-%m-%d %H:%M:%S')
            else:
                slots_to_dump[k] = v
        
        # Converte os slots atuais para JSON formatado para injeção
        # Usamos `ensure_ascii=False` para lidar com caracteres não-ASCII (como 'ã', 'ç')
        slots_json = json.dumps(slots_to_dump, ensure_ascii=False, indent=2) if slots_to_dump else "{}"

        # 1. Fixar a variável de memória 'slot_data_atual' na template usando .partial().
        prompt_with_memory = self.extraction_prompt.partial(
            slot_data_atual=slots_json
        )

        # 2. Constrói a Runnable completa (Chain)
        # A entrada final da chain será o 'texto_usuario', que é a única variável restante.
        # Formata a template e cria a chain:
        return prompt_with_memory | self.llm | self.output_parser