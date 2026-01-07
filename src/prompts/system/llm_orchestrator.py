# src/prompts/system/llm_orchestrator.py
# Template: Extrator de dados
from typing import Callable
from langchain_core.runnables import RunnableLambda, RunnableBranch, RunnablePassthrough
from langchain_openai import ChatOpenAI

from src.prompts.router.classification_router import ClassificationRouter
from src.schemas.router_schema import RouterClassification

class LLMOrchestrator:
	"""
    Orquestrador principal que coordena o roteamento e a execução 
    de chains específicas (Extração, Tools, Conversa).
    """

	def __init__(self, llm: ChatOpenAI, router_chain: any, extraction_chain: any, tool_chain: any, general_chain: any, reset_function: Callable):
		self.llm = llm
		self.router_chain = router_chain
		
		# Chains que o orquestrador vai coordenar
		self.extraction_chain = extraction_chain
		self.tool_chain = tool_chain
		self.general_chain = general_chain
		self.reset_function = reset_function

	def get_orchestrator_chain(self):
		"""Constrói a chain final: 1. Classifica -> 2. Decide a Rota -> 3. Executa a Chain Destino"""

		# Passo 1: Chain de Classificação
		router_chain = self.router_chain

		# Passo 2: Definição das rotas (Branching)
        # O resultado do passo anterior (x) contém 'classification' e 'texto_usuario'
		chain_decisor = RunnableBranch(
			# 1. Fluxo de Agendamento (Slot Extraction)
			(lambda x: x['classification'].intent == 'AGENDAR', self.extraction_chain),

			# 2. Fluxo de Consulta (Tool-Calling / Function Calling)
			(lambda x: x['classification'].intent == 'BUSCAR_SERVICO', self.tool_chain),

			# 3. Fluxo de Listagem de Menu (Pode ser uma Tool ou General com Contexto)
			(lambda x: x['classification'].intent == 'SERVICOS', self.tool_chain),

			# 4. Fluxo de Reset (Executa uma função de limpeza e retorna confirmação)
			(lambda x: x['classification'].intent == 'RESET', RunnableLambda(lambda x: self._handle_reset(x))),
			# (lambda x: x['classification'].intent == 'RESET', RunnableLambda(lambda x: self.reset_function(x))),

			# GENERICO: Resposta conversacional (Default)
			self.general_chain # Rota padrão 
		)

		# 3. Preservamos o texto original do usuário
        # O RunnablePassthrough.assign garante que a chain seguinte receba tanto o texto original quanto a classificação.
		full_chain = (RunnablePassthrough.assign(classification=router_chain) | chain_decisor)

		return full_chain

	async def _handle_reset(self, data):
		"""Executa a função de reset e retorna uma mensagem padrão."""
		user_id = data.get("user_id")
		await self.reset_function(user_id)
		return "Tudo bem, limpei nosso histórico. Como posso te ajudar do zero?"