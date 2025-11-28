# src/platform/telegram/handlers/start_handler.py

from telegram import Update
from telegram.ext import ContextTypes
from typing import TYPE_CHECKING
# Importa o teclado da sua nova UI do Telegram
from src.platform.telegram.ui.keyboards import get_contact_request_keyboard, get_main_menu_keyboard
# Importa seu serviço de negócio (mantendo a separação!)
from src.services.data_service import DataService
# Importa o LLMService para limpeza de histórico
from src.bot.llm_service import LLMService 
from src.utils.system_message import MESSAGES # Para a mensagem de boas-vindas


# Se estiver usando tipagem estática (opcional, mas recomendado)
if TYPE_CHECKING:
    from telegram.ext import Application
    
    # Define a estrutura de dependências esperada no bot_data
    class BotDataDependencies(dict):
        data_service: DataService
        llm_service: LLMService


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler do comando /start. Gerencia o registro inicial, 
    limpa o histórico e solicita o telefone se necessário.
    """
    if not update.effective_user or not update.message:
        return

    user_id = update.effective_user.id
    nome = update.effective_user.first_name
    
    # 1. 🚨 Acesso às Dependências
    # Assume-se que DataService e LLMService estão injetados em context.application.bot_data
    # Use context.bot_data se injetar no contexto do bot em vez do application.
    deps = context.application.bot_data # type: BotDataDependencies
    data_service: DataService = deps['data_service']
    llm_service: LLMService = deps['llm_service']

    # 2. ✅ Lógica de Registro e Limpeza
    
    # Salva ou atualiza o usuário no DB, garantindo que o registro exista. 
    # Passamos telefone=None, pois não o coletamos no /start.
    await data_service.salvar_usuario(user_id=user_id, nome=nome, telefone=None)
    
    # Limpa estados
    llm_service.history_manager.reset_history(user_id)
    await data_service.clear_session_state(user_id) # Sessão de agendamento (garantir que não há slots preenchidos)
    await data_service.clear_historico(user_id) # HISTÓRICO PERSISTENTE (mensagens salvas no DB)
    
    # 3. 📞 Checagem do Telefone
    
    # Realiza a checagem no DB usando o novo método
    telefone_db = await data_service.get_telefone_usuario(user_id) 
    
    if telefone_db:
        # Usuário já registrado e com telefone. Manda menu principal.
        await update.message.reply_text(
            f"Bem-vindo(a) de volta, {nome}! {MESSAGES['WELCOME_MESSAGE']}",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Usuário novo ou sem telefone. Solicita o contato.
        await update.message.reply_text(
            f"Olá, {nome}! Para prosseguir, por favor, clique no botão abaixo para compartilhar seu contato.",
            reply_markup=get_contact_request_keyboard()
        )