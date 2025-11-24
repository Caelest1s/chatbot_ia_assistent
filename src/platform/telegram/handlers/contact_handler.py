# src/platform/telegram/handlers/contact_handler.py

from telegram import Update
from telegram.ext import ContextTypes
from src.platform.telegram.ui.keyboards import get_main_menu_keyboard
from src.services.data_service import DataService # Importa o serviço
from src.config.logger import setup_logger

logger = setup_logger(__name__)

async def receive_contact_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Captura o número de telefone do Telegram e o envia para a camada de Serviço.
    """
    user_id = update.effective_user.id
    contact = update.message.contact
    
    if not contact or not contact.phone_number:
        await update.message.reply_text("Não consegui identificar seu número. Tente novamente.")
        return

    telefone_str = contact.phone_number
    nome = update.effective_user.first_name
    
    try:
        # 1. Instancia o DataService (Ajuste para sua injeção de dependência real)
        data_service: DataService = context.application.bot_data['data_service']
        
        # 2. Chama o método de negócio para SALVAR (A Lógica de negócio fica aqui)
        await data_service.salvar_usuario(
            user_id=user_id, 
            nome=nome, 
            telefone=telefone_str
        )
        
        context.user_data['telefone_db_status'] = True
        
        await update.message.reply_text(
            f"Obrigado(a), {nome}! Seu contato foi salvo. Você já pode usar nosso menu.",
            reply_markup=get_main_menu_keyboard()
        )
        logger.info(f"Telefone do usuário {user_id} salvo: {telefone_str}")
        
    except Exception as e:
        logger.error(f"Erro ao salvar telefone via Telegram: {e}")
        await update.message.reply_text("Desculpe, ocorreu um erro interno ao salvar seu contato.")