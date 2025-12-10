# src/database/repositores/agenda_repo.py
import json
from src.config.logger import setup_logger
from datetime import datetime, timedelta, time, date
from typing import Optional, Union

# Importações Assíncronas
from sqlalchemy import select, func, text, and_
from sqlalchemy.ext.asyncio import AsyncSession 

# Importações da Base e dos Modelos (Ajuste conforme a sua estrutura)
from src.database.repositories.base_repo import BaseRepository
from src.database.models.agenda_model import Agenda

from src.utils.constants import SHIFT_TIMES, BUSINESS_HOURS, WEEKDAY_MAP

logger = setup_logger(__name__)

class AgendaRepository(BaseRepository[Agenda]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Agenda)
        # O self.session agora é a AsyncSession ativa

    async def verificar_disponibilidade(self, data: str) -> list[tuple[time, time]]:
        """Verifica todos os horários agendados e concluídos para uma data específica."""
        try:
            data_obj = datetime.strptime(data, '%Y-%m-%d').date()
        except ValueError as e:
            logger.info(f"Data inválida em verificar_disponibilidade: {data}. Erro: {e}.")
            return []

        stmt = select(Agenda.hora_inicio, Agenda.hora_fim).where(
                Agenda.data == data_obj,
                Agenda.status.in_(['agendado', 'concluido'])
            ).order_by(Agenda.hora_inicio)

        # Assume-se que a verificação é para qualquer profissional, já que não temos o campo
        return (await self.session.execute(stmt)).all()

    async def inserir_agendamento(self,
                                  user_id: int,
                                  servico_id: int,
                                  servico_nome: str,
                                  servico_minutos: int,
                                  data: str,
                                  hora_inicio: str) -> tuple[Optional[Agenda], Optional[str], str]:
        """Insere um novo agendamento verificando a disponibilidade"""

        try:
            data_dt = datetime.strptime(data, '%Y-%m-%d').date()
            hora_inicio_dt = datetime.strptime(hora_inicio, '%H:%M')
        except ValueError:
            return None, None, "Formato de data ou hora inválido."

        hora_inicio_time = hora_inicio_dt.time()

        # Verifica se data está no passado
        if data_dt < datetime.now().date():
            return None, None, "Não é possível agendar para datas ultrapassadas."
        
        # Verifica data é hoje, mas horário ultrapassado
        if data_dt == datetime.now().date() and hora_inicio_dt <= datetime.now():
            return None, None, "Não é possível agendar para horários ultrapassados."

        duracao_servico = servico_minutos

        # 2. Calcular hora_fim
        hora_fim_dt = hora_inicio_dt + timedelta(minutes=duracao_servico)
        hora_fim_time = hora_fim_dt.time()

        # 3. Verificar Conflitos (Race Condition check)
        agendamentos = await self.verificar_disponibilidade(data)

        for inicio_agendado, fim_agendado in agendamentos:
            # Lógica de colisão: Novo Inicio < Fim Existente E Novo Fim > Inicio Existente
            if (hora_inicio_time < fim_agendado and hora_fim_time > inicio_agendado):
                return None, None, "Horário indisponível. Conflito com agendamento existente."

        # 4. Inserir Agendamento
        novo_agendamento = Agenda(
            user_id=user_id,
            servico_id=servico_id,
            data=data_dt,
            hora_inicio=hora_inicio_time,
            hora_fim=hora_fim_time,
            status='agendado',
            created_at=datetime.now()
        )
        self.session.add(novo_agendamento)
        await self.session.flush()
        await self.session.refresh(novo_agendamento)

        logger.info(f"Agendamento ID: {novo_agendamento.agenda_id} serviço: {servico_nome} preparado para usuário {user_id}.")

        # Retorna o objeto adicionado (ainda sem o ID, que será preenchido após o commit no DataService)
        return novo_agendamento, servico_nome, "Agendamento pronto para ser confirmado."

    async def calculate_available_blocks(self,
                                         data: Union[str, date],
                                         duracao_minutos: int,
                                         shift_name: Optional[str] = None) -> list[str]:
        """Calcula slots livres baseados na duração do serviço. Considera BUSINESS_HOURS e SHIFT_TIMES."""

        # 1. Normalização da data. Garante 'data' é uma string YYYY-MM-DD
        if isinstance(data, date):
            data_obj = data
            data_str = data.strftime('%Y-%m-%d')
        elif isinstance(data, str):
            try:
                data_obj = datetime.strptime(data, '%Y-%m-%d').date()
                data_str = data
            except ValueError:
                return []
        else:
            logger.error(f"Tipo de dado inesperado recebido para 'data': {type(data)}")
            return []
        
        # 2. Definir Limites de Horário (Baseado no Dia da Semana)
        weekday_idx = data_obj.weekday() # 0 = Segunda, 6 = Domingo
        day_name = WEEKDAY_MAP.get(weekday_idx)
        business_rule = BUSINESS_HOURS.get(day_name)

        # Se não houver regra (None), significa que está fechado (ex: Domingo)
        if not business_rule:
            logger.info(f"Estabelecimento fechado em: {day_name}")
            return []
        
        # Define inicio/fim padrão do dia
        inicio_operacao = business_rule['start']
        fim_operacao = business_rule['end']

        # 3. Se houver filtro de turno, sobrescreve (respeitando limites se necessário)
        if shift_name and shift_name in SHIFT_TIMES:
            shift = SHIFT_TIMES[shift_name]
            shift_inicio = datetime.strptime(shift['inicio'], '%H:%M').time()
            shift_fim = datetime.strptime(shift['fim'], '%H:%M').time()
            
            # (Opcional) Poderíamos fazer a interseção entre Turno e Horário da Loja
            # Por enquanto, assumimos que o turno está dentro do horário
            inicio_operacao = shift_inicio
            fim_operacao = shift_fim

        # 4. Obter agendamentos ocupados
        agendamentos_ocupados = await self.verificar_disponibilidade(data_str)
        horarios_livres: list[str] = []

        # Usar uma data dummy para facilitar calculo de tempo
        dummy_date = datetime(2000, 1, 1).date()
        current_dt = datetime.combine(dummy_date, inicio_operacao)
        fim_operacao_dt = datetime.combine(dummy_date, fim_operacao)

        # 5. Iterar de 30 em 30 minutos (ou a cada 15 minuto se quiser ser granular)
        intervalo_step = timedelta(minutes=30)
        duracao_delta = timedelta(minutes=duracao_minutos)

        # Loop de verificação
        while current_dt + duracao_delta <= fim_operacao_dt:
            hora_inicio_bloco = current_dt.time()
            hora_fim_bloco = (current_dt + duracao_delta).time()

            is_available = True

            # Checa se o bloco de tempo colide com algum agendamento ocupado
            for inicio_agendado, fim_agendado in agendamentos_ocupados:
                if (hora_inicio_bloco < fim_agendado and hora_fim_bloco > inicio_agendado):
                    is_available = False
                    break

            if is_available:
                horarios_livres.append(hora_inicio_bloco.strftime('%H:%M'))

            current_dt += intervalo_step
        return horarios_livres
