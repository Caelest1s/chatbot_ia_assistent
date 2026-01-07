import json
from datetime import datetime, date
from langchain_core.runnables import RunnableLambda
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from src.schemas.slot_extraction_schema import SlotExtraction

class SlotFiller:
    """Especialista apenas em extração de slots e tratamento de dados."""
    def __init__(self, llm, services_context: str):
        self.llm = llm
        self.output_parser = PydanticOutputParser(pydantic_object=SlotExtraction)
        self.services_context = services_context

    def _prepare_input(self, input_data: dict, current_slots: dict):
        # Lógica de conversão de datas simplificada
        slots_to_dump = {}
        for k, v in current_slots.items():
            if isinstance(v, (date, datetime)):
                slots_to_dump[k] = v.strftime('%Y-%m-%d' if k == 'data' else '%H:%M')
            else:
                slots_to_dump[k] = v
        
        return {
            "texto_usuario": input_data["texto_usuario"],
            "missing_slot": input_data.get("missing_slot", "NENHUM"),
            "slot_data_atual": json.dumps(slots_to_dump, ensure_ascii=False),
            "servicos": self.services_context,
            "format_instructions": self.output_parser.get_format_instructions()
        }

    def get_extraction_chain(self, get_slots_fn: callable):
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Extraia os dados de agendamento.\n
             CONTEXTO DO BANCO: {slot_data_atual}\n
             SERVIÇOS: {servicos}\n

             FOCO ATUAL: O usuário está respondendo especificamente sobre o campo: '{missing_slot}'.
             Se a resposta for curta ou ambígua (ex: 'Tarde', 'Sim', 'Amanhã'), priorize preencher o campo '{missing_slot}'.
             {format_instructions}"""),

            ("human", "{texto_usuario}")
        ])

        async def prepare_async(input_data):
            current_slots = await get_slots_fn(input_data)
            return self._prepare_input(input_data, current_slots=current_slots)

        # get_slots_fn será chamado em tempo de execução para pegar os dados do BD
        return (
            RunnableLambda(prepare_async)
            | prompt 
            | self.llm 
            | self.output_parser
        )