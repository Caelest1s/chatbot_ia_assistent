# Importa todos os modelos para que eles sejam registrados no Base do SQLAlchemy
from .user_model import Usuario
from .historico_model import Historico
from .session_model import UserSession
from .servico_model import Servico
from .agenda_model import Agenda

# 'from src.database.models import *', 
# garante que todas as classes de modelo estarão disponíveis.
__all__ = [
    "Usuario"
    , "Historico"
    , "UserSession"
    , "Servico"
    , "Agenda"
    ,
]