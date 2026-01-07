# src/services/slot_processor_service.py

import logging
from datetime import date, datetime

from src.utils.date_parser import parse_relative_date
from src.schemas.slot_extraction_schema import SlotExtraction
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.persistence_service import PersistenceService
    from src.utils.date_parser import parse_relative_date

logger = logging.getLogger(__name__)

class SlotProcessorService:
    """Refina e enriquece os dados extraídos pelo LLM.Transforma texto bruto (ex: 'corte') em dados de negócio (ID, Duração)."""

    def __init__(self, persistence_service: 'PersistenceService'):
        self.persistence_service = persistence_service

    async def process_slots(self, extracted_pydantic: SlotExtraction) -> dict:
        """Ponto de entrada principal. Recebe o Pydantic e devolve um dict pronto para o BD."""

        # 1. Converte Pydantic para Dict (remove campos não preenchidos)
        slots = extracted_pydantic.model_dump(exclude_unset=True) 

        if not slots:
            return {}
        
        # 2. Resolução de Data Relativa (ex: 'amanhã' -> '2025-10-25')
        slots = await self._resolve_date_slot(slots)
        
        # 3. Normalização de Serviço, enriquecimento (Busca ID e Duração no Banco)
        slots = await self._normalize_service_details(slots)
        
        logger.info(f"Slots processados e enriquecidos prontos para serem salvos na sessão.")
        return slots
    
    async def _resolve_date_slot(self, slot_data: dict) -> dict:
        """Converte strings de data relativa para formato ISO (ex: 'amanhã' -> 'YYYY-MM-DD')."""
        
        date_value = slot_data.get('data')
        
        if date_value and isinstance(date_value, str):
            # Chama a função utilitária para análise robusta
            resolved = parse_relative_date(date_value, datetime.now())
            
            if resolved:
                slot_data['data'] = resolved
                logger.debug(f"Data resolvida: {date_value} -> {resolved}")
            
        return slot_data
    
    async def _normalize_service_details(self, slot_data: dict) -> dict:
        """Busca detalhes do serviço no DB. Se não encontrar, limpa o slot para o bot perguntar novamente por um serviço válido."""
        # IMPORTANTE: Use a mesma chave definida no seu SlotExtraction (ex: 'servico')
        service_name = slot_data.get('servico')

        if service_name and isinstance(service_name, str):
            # Chama o método do repositório para buscar os detalhes
            service_details = await self.persistence_service.get_service_details_by_name(service_name)
            
            if service_details:
                # Enriquece o dicionário com dados oficiais do banco (ID's e duração)
                slot_data['servico'] = service_details['nome'] # Nome oficial DB
                slot_data['servico_id'] = service_details['servico_id']
                slot_data['duracao_minutos'] = service_details['duracao_minutos'] 
                logger.debug(f"Serviço '{service_name}' reconhecido como ID {service_details['servico_id']}")
            else:
                # Se o serviço não existe no catálogo, removemos para forçar nova pergunta
                logger.warning(f"Serviço '{service_name}' não encontrado no catálogo (DB). Removendo slots de serviço.")
                slot_data.pop('servico', None)
        
        return slot_data