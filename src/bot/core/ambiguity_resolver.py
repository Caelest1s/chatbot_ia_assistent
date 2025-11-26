# src/core/ambiguity_resolver.py

import re
from typing import Optional
from sqlalchemy.orm import Session
from src.database.models import Servico
from src.database.repositories import ServicoRepository

class AmbiguityResolver:
    """
    Classe responsável por resolver ambiguidades em nomes de serviços usando a 
    resposta do usuário e os IDs de serviço.
    """

    def __init__(self, db_session: Session):
        self.servico_repo = ServicoRepository(db_session)

    def resolve_ambiguity_from_short_reply(
        self
        , user_message: str
        , ambiguity_data: dict[str, any]
    ) -> Optional[Servico]:
        """
        Tenta resolver a ambiguidade quando o usuário responde com um termo curto.
        Busca os serviços pelos IDs e compara a resposta do usuário com o nome do serviço.
        
        Args:
            user_message: A mensagem curta do usuário (ex: 'masculino').
            ambiguity_data: O dicionário da sessão contendo 'options' (lista de IDs).

        Returns:
            O objeto Servico desambiguado (nome canônico), ou None.
        """
        service_ids = ambiguity_data.get('options', [])
        reply_lower = user_message.lower().strip()

        if not service_ids:
            return None
        
        # Busca todos os objetos Servico pelos IDs
        possible_services = self.servico_repo.find_services_by_ids(service_ids)

        if not possible_services:
            return None
        
        # 1. Tenta correspondência direta com a palavra-chave (ex: 'masculino')
        for servico in possible_services:
            nome_servico_lower = servico.nome.lower()

            # Checa se a resposta (ex: 'masculino') está contida no nome (ex: 'corte de cabelo masculino')
            if reply_lower in nome_servico_lower:
                return servico
            
            # 2. Correspondência de Similaridade (Opcional, mas útil para sinônimos)
            # Você pode adicionar lógica de similaridade fuzzy aqui se necessário, 
            # mas para "masculino" vs "Corte de Cabelo Masculino" o passo 1 é suficiente.
        
        return None