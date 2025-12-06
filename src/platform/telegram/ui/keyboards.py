# src/platform/telegram/ui/keyboards.py

from telegram import KeyboardButton, ReplyKeyboardMarkup

def get_contact_request_keyboard() -> ReplyKeyboardMarkup:
    """
    Cria o teclado que solicita o compartilhamento do número de telefone (Específico para Telegram).
    """
    button = KeyboardButton(
        text="Compartilhar meu Telefone 📞",
        request_contact=True
    )
    
    keyboard = ReplyKeyboardMarkup(
        [[button]],
        one_time_keyboard=True, 
        resize_keyboard=True
    )
    return keyboard

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Cria o teclado principal do bot (Específico para Telegram).
    """
    keyboard = [
        ["Agendar Serviço", "Meus Agendamentos"],
        ["Resetar Diálogo"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)