import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.database_manager import DatabaseManager
from src.schemas.slot_extraction_schema import SlotExtraction
from src.utils.system_message import MESSAGES

logger = logging.getLogger(__name__)

class ServiceFinder:
    """Lógica de negócio para buscar serviços no banco de dados."""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def handle_buscar_servicos_estruturado(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, dados: SlotExtraction) -> bool:
            """Processa a intenção BUSCAR_SERVICO com o termo extraído pela LLM."""
            termo = dados.servico_nome or update.message.text 

            if not termo or termo.lower() in ['buscar_servico', 'servicos']:
                await update.message.reply_text("Por favor, diga qual serviço ou preço você gostaria de buscar.")
                return True
            
            user_id = update.effective_user.id
            nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name

            logger.info(f"Busca acionada com termo extraído: {termo}")
            resultados = self.db_manager.buscar_servicos(termo)

            if resultados:
                 resposta = "Serviços encontrados:\n" + "\n".join([
                      f"- {r['nome']}: {r['descricao']} (Preço: R${r['preco']:.2f}, Duração: {r['duracao_minutos']} min)"
                      for r in resultados
                 ])
            else:
                 resposta = f"{nome}, nenhum serviço encontrado com o termo '{termo}'."

            await update.message.reply_text(resposta)
            return True
