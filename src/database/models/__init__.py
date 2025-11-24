# Importa todos os modelos para que eles sejam registrados no Base do SQLAlchemy
from .user_model import Usuario
from .mensagem_model import Mensagem
from .session_model import UserSession
from .servico_model import Servico
from .agenda_model import Agenda

# 'from src.database.models import *', 
# garante que todas as classes de modelo estarão disponíveis.
__all__ = [
    "Usuario"
    , "Mensagem"
    , "UserSession"
    , "Servico"
    , "Agenda"
    ,
]