# src/prompts/router/classification_router.py
# Template: Roteador de Intenção e Classificador de Tarefas

import os
import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda
from langchain.output_parsers import PydanticOutputParser

from src.schemas.router_schema import RouterClassification

logger = logging.getLogger(__name__)

class ClassificationRouter:
    """Roteador de Intenção e Classificador de Tarefas."""
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.output_parser = PydanticOutputParser(pydantic_object=RouterClassification)
        # 1. Localização e Leitura do Prompt
        self.current_dir = os.path.dirname(os.path.abspath(__file__))

        # 1. Carrega os conteúdos dos arquivos para a memória da instância
        self.general_instruction = self._load_prompt('router_system_prompt.txt')
        self.slot_focus_instruction = self._load_prompt('slot_focus_prompt.txt')
        
    def _load_prompt(self, filename: str) -> str:
        path = os.path.join(self.current_dir, filename)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Erro ao carregar {filename}: {e}")
            return "Classifique a intenção do usuário para agendamento."

    def get_router_chain(self) -> Runnable:
        """
        Retorna a chain de classificação. 
        O RunnableLambda permite que a decisão do prompt seja feita no momento da execução, de forma dinâmica.
        """
        def route_input(input_data: dict):
            # Identifica se há um slot sendo focado
            missing_slot = input_data.get("missing_slot")
            texto_usuario = input_data.get("texto_usuario")

            partial_vars = {
                "format_instructions": self.output_parser.get_format_instructions()
            }

            # 2. Escolhe a instrução baseada no contexto
            if missing_slot and missing_slot != "NENHUM":
                instruction = self.slot_focus_instruction
                partial_vars["missing_slot"] = missing_slot
                logger.info(f"Roteador: Usando modo FOCO no slot: {missing_slot}")
            else:
                instruction = self.general_instruction
                logger.info("Roteador: Usando modo GERAL")

            # 2. Cria o prompt dinamicamente
            # O uso de input_variables=[] e validate_template=False evita erros de chaves extras
            prompt = ChatPromptTemplate.from_messages([
                ("system", instruction + "\n\n{format_instructions}"),
                ("human", "{texto_usuario}")
            ])

            # 3. Aplica as variáveis (Somente as que existem no template escolhido)
            try:
                # Filtramos partial_vars para conter apenas o que o template pede
                input_vars_needed = prompt.input_variables
                filtered_vars = {k: v for k, v in partial_vars.items() if k in input_vars_needed}
                
                chain = prompt.partial(**filtered_vars) | self.llm | self.output_parser
                return chain
            except Exception as e:
                logger.error(f"Erro ao montar chain do roteador: {e}")
                # Fallback seguro para o prompt geral caso o de foco falhe
                return ChatPromptTemplate.from_messages([
                    ("system", self.general_instruction + "\n\n{format_instructions}"),
                    ("human", "{texto_usuario}")
                ]).partial(format_instructions=self.output_parser.get_format_instructions()) | self.llm | self.output_parser

        # Retornamos uma chain que decide o prompt em tempo de execução. O RunnableLambda é essencial
        return RunnableLambda(route_input)
