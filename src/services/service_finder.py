# src/services/service_finder.py

import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.services.persistence_service import PersistenceService
from src.schemas.slot_extraction_schema import SlotExtraction
from src.utils.system_message import MESSAGES

logger = logging.getLogger(__name__)

class ServiceFinder:
    """
    [ASYNC] Lógica de negócio para buscar serviços no banco de dados.
    Responsável por processar a intenção BUSCAR_SERVICO.
    """
    # Lógica de negócio para buscar serviços no banco de dados

    def __init__(self, data_service: PersistenceService):
        self.data_service = data_service

    async def handle_buscar_servicos_estruturado(
            self, 
            update: Update, 
            context: ContextTypes.DEFAULT_TYPE, 
            dados: SlotExtraction) -> bool:
        """
        [ASYNC] Processa a intenção BUSCAR_SERVICO com o termo extraído pela LLM,
        executando a busca no DataService de forma assíncrona.
        """

        user_id = update.effective_user.id
        # Termo é o nome do serviço extraído pela LLM ou a mensagem crua do usuário
        termo = dados.servico_nome or update.message.text

        if not termo or termo.lower() in ['buscar_servico', 'servicos']:
            await update.message.reply_text("Por favor, diga qual serviço ou preço você gostaria de buscar.")
            return True

        # 1. Obtém o nome do usuário (Assíncrono)
        
        nome = await self.data_service.get_nome_usuario(
            user_id) or update.message.from_user.first_name

        logger.info(f"Busca acionada com termo extraído: {termo}")

        # 2. Executa a busca de serviços (Assíncrono)
        resultados = await self.data_service.buscar_servicos(termo)

        # 3. Formata e Envia a Resposta
        if resultados:
            resposta = "Serviços encontrados:\n" + "\n".join([
                f"- {r['nome']}: {r['descricao']} (Preço: R${r['preco']:.2f}, Duração: {r['duracao_minutos']} min)"
                for r in resultados
            ])
        else:
            resposta = f"{nome}, nenhum serviço encontrado com o termo '{termo}'."

        await update.message.reply_text(resposta)
        return True
