import logging
from telegram import Update
from telegram.ext import ContextTypes
from src.bot.database_manager import DatabaseManager
from src.schemas.slot_extraction_schema import SlotExtraction
from src.services.appointment_validator import AppointmentValidator
from src.utils.system_message import MESSAGES

logger = logging.getLogger(__name__)

class AppointmentService:
    """Lógica de negócio para a criação de agendamentos."""
    def __init__(self, db_manager: DatabaseManager, validator: AppointmentValidator):
        self.db_manager = db_manager
        self.validator = validator

    async def handle_agendamento_estruturado(self, update: Update, 
        context: ContextTypes.DEFAULT_TYPE, dados: SlotExtraction) -> tuple[bool, str]:
        """
        Processa a intenção AGENDAR com dados extraídos.
        Retorna (True, 'Mensagem de sucesso/erro tratada') ou (False, 'Erro interno não tratado').
        """
        user_id = update.effective_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.effective_user.first_name

        servico_nome = dados.servico_nome.strip()
        data_str = dados.data
        hora_str = dados.hora

        # 1. VALIDAÇÃO DE SERVIÇO (Garante que é unívoco)
        servicos_encontrados = self.db_manager.buscar_servicos(servico_nome)
        if len(servicos_encontrados) != 1:
            # O SlotFillingManager deveria prevenir isso, mas é uma segurança.
            await update.message.reply_text(MESSAGES['VALIDATION_SERVICE_NOT_FOUND'].format(nome=nome, servico=servico_nome))
            return True, f"Serviço ambíguo ou não encontrado: {servico_nome}"
        
        servico = servicos_encontrados[0]
        servico_id = servico['servico_id']

        # 2. VALIDAÇÕES DE DATA E HORA
        data_hora_agendamento, erro_msg = self.validator.validate_date_time_format(data_str, hora_str)
        if erro_msg:
            await update.message.reply_text(erro_msg.format(nome=nome))
            return True, erro_msg
        
        erro_msg = self.validator.validate_past_time(data_hora_agendamento)
        if erro_msg:
            await update.message.reply_text(erro_msg.format(nome=nome))
            return True, erro_msg
        
        erro_msg = self.validator.validate_business_hours(data_hora_agendamento)
        if erro_msg:
            await update.message.reply_text(erro_msg.format(nome=nome))
            return True, erro_msg
        
        try:
            # 3. CHAMADA FINAL DE AGENDAMENTO
            data_dt = data_hora_agendamento.strftime('%Y-%m-%d')
            hora_dt = data_hora_agendamento.strftime('%H:%M')

            sucesso, mensagem = self.db_manager.inserir_agendamento(user_id, servico_id, data_dt, hora_dt)

            # A mensagem de sucesso ou falha (ex: horário indisponível) vem do DBManager
            await update.message.reply_text(f'{nome}, {mensagem}')
            return True, mensagem
        
        except Exception as e:
            logger.error(f"Erro ao agendar com dados estruturados: {e}")
            await update.message.reply_text(MESSAGES['ERROR_INTERNAL'].format(nome=nome))
            return False, f"Erro interno: {e}"