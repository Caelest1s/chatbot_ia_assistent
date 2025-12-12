# src/services/slot_processor_service.py

import logging
from datetime import date, datetime
from typing import Optional

from src.database.repositories.agenda_repo import AgendaRepository
from src.utils.date_parser import parse_relative_date
from src.schemas.slot_extraction_schema import SlotExtraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.persistence_service import PersistenceService


logger = logging.getLogger(__name__)

class SlotProcessorService:
    """
    Serviço responsável pelo pós-processamento, normalização e enriquecimento dos slots 
    extraídos pela LLM antes de serem salvos na sessão (DataService).
    """

    def __init__(self, persistence_service: 'PersistenceService'):
        """Recebe o repositório como dependência para consultas ao DB."""
        self.persistence_service = persistence_service

    async def _normalize_service_details(self, slot_data: dict) -> dict:
        """
        Garante que 'servico_id' e 'duracao_minutos' sejam preenchidos 
        com base no 'servico_nome' usando o DB (Enriquecimento).
        """
        service_name = slot_data.get('servico_nome')

        if service_name and isinstance(service_name, str):
            # Chama o método do repositório para buscar os detalhes
            service_details = await self.persistence_service.get_service_details_by_name(service_name)
            
            if service_details:
                # Enriquecimento: Adiciona ID e Duração
                slot_data['servico_id'] = service_details['servico_id']
                slot_data['duracao_minutos'] = service_details['duracao_minutos'] 
                logger.debug(f"Slots enriquecidos com ID {service_details['servico_id']} \
                             e Duração {service_details['duracao_minutos']} min. Em serviço {service_name}.")
            else:
                # Falha no Enriquecimento: Se o nome não for encontrado
                logger.warning(f"Serviço '{service_name}' não encontrado no DB. Removendo slots de serviço.")
                slot_data.pop('servico_nome', None)
                slot_data.pop('servico_id', None)
                slot_data.pop('duracao_minutos', None) # Limpa tudo relacionado ao serviço
        
        return slot_data

    async def _resolve_date_slot(self, slot_data: dict) -> dict:
        """
        Resolve strings de data relativa (ex: 'amanhã') para o formato ISO 'AAAA-MM-DD'.
        """
        date_slot = slot_data.get('data')
        
        if date_slot and isinstance(date_slot, str):
            # Chama a função utilitária para análise robusta
            resolved = parse_relative_date(date_slot, datetime.now())
            
            if resolved:
                slot_data['data'] = resolved
            
        return slot_data

    async def process_slots(self, extracted_pydantic: SlotExtraction) -> dict:
        """
        Ponto de entrada que coordena a limpeza e enriquecimento dos slots.
        
        Args:
            extracted_pydantic: Objeto Pydantic retornado pelo LLMService.
        
        Returns:
            Um dicionário de slots processados e prontos para o DB.
        """
        # Converte o objeto Pydantic para um dicionário padrão para manipulação
        # O exclude_none=True garante que slots que não foram extraídos não serão processados.
        slots = extracted_pydantic.model_dump(exclude_none=True) 
        
        # 1. Resolução de Data Relativa (Transformação)
        slots = await self._resolve_date_slot(slots)
        
        # 2. Normalização de Serviço (Enriquecimento, requer acesso ao DB)
        # Nota: O AgendaRepository está acessível via self.agenda_repo
        slots = await self._normalize_service_details(slots)
        
        logger.info(f"Slots processados e enriquecidos prontos para salvar na sessão.")
        return slots