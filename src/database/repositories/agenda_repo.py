# src/database/repositores/agenda_repo.py
import json
from src.config.logger import setup_logger
from datetime import datetime, timedelta, time, date
from typing import Optional, Union

# Importações Assíncronas
from sqlalchemy import select, func, text, and_
from sqlalchemy.ext.asyncio import AsyncSession  # A chave para o modo assíncrono

# Importações da Base e dos Modelos (Ajuste conforme a sua estrutura)
from src.database.repositories.base_repo import BaseRepository
from src.database.models.agenda_model import Agenda
from src.database.models.servico_model import Servico

from src.utils.constants import SHIFT_TIMES

logger = setup_logger(__name__)


class AgendaRepository(BaseRepository[Agenda]):
    def __init__(self, session: AsyncSession):
        # O modelo principal do repositório é Agenda
        super().__init__(session, Agenda)
        # O self.session agora é a AsyncSession ativa

    # =========================================================
    # FUNÇÕES DE SERVIÇO
    # =========================================================
    async def get_servico_by_id(self, servico_id: int) -> Optional[Servico]:
        # AsyncSession.get() é o método ideal para buscar por chave primária
        return await self.session.get(Servico, servico_id)

    async def buscar_servicos(self, termo: str) -> list[dict]:
        """Busca serviços ativos com base no termo (ILIKE) de forma assíncrona."""
        search_term = f'%{termo}%'

        stmt = select(
            Servico.servico_id,
            Servico.nome,
            Servico.descricao,
            Servico.preco,
            Servico.duracao_minutos
        ).where(
            Servico.ativo == True,
            (func.lower(Servico.nome).like(func.lower(search_term)))
            | (func.lower(Servico.descricao).like(func.lower(search_term)))
        )

        resultados = (await self.session.execute(stmt)).all()

        return [
            {
                "servico_id": row[0],
                "nome": row[1],
                "descricao": row[2],
                "preco": float(row[3]),
                "duracao_minutos": row[4],
            }
            for row in resultados
        ]

    async def get_available_services_names(self) -> list[str]:
        """Retorna uma lista de nomes de serviços ativos de forma assíncrona."""
        stmt = select(Servico.nome).where(
            Servico.ativo == True).order_by(Servico.nome)
        resultados = (await self.session.scalars(stmt)).all()
        return resultados

    async def verificar_disponibilidade(self, data: str) -> list[tuple[time, time]]:
        """Verifica todos os horários agendados e concluídos para uma data específica."""

        try:
            data_obj = datetime.strptime(data, '%Y-%m-%d').date()
        except ValueError as e:
            logger.info(f"Formato de data inválido em verificar_disponibilidade: {data}. Erro: {e}.")
            return []

        stmt = select(
            Agenda.hora_inicio,
            Agenda.hora_fim
        ).where(
            Agenda.data == data_obj,
            Agenda.status.in_(['agendado', 'concluido'])
        ).order_by(Agenda.hora_inicio)

        # Assume-se que a verificação é para qualquer profissional, já que não temos o campo
        return (await self.session.execute(stmt)).all()

    # =========================================================
    # FUNÇÃO DE INSERÇÃO DE AGENDAMENTO
    # =========================================================
    async def inserir_agendamento(self,
                                  user_id: int,
                                  servico_id: int,
                                  data: str,
                                  hora_inicio: str) -> tuple[Optional[Agenda], Optional[str], str]:
        """Insere um novo agendamento de forma assíncrona, verificando a disponibilidade"""

        try:
            data_dt = datetime.strptime(data, '%Y-%m-%d').date()
            hora_inicio_dt = datetime.strptime(hora_inicio, '%H:%M')
        except ValueError:
            return None, None, "Formato de data ou hora inválido."

        hora_inicio_time = hora_inicio_dt.time()

        if data_dt < datetime.now().date():
            return None, None, "Não é possível agendar para datas passadas."

        # 1. Obter duração do serviço
        servico = await self.get_servico_by_id(servico_id)
        if not servico:
            return None, None, "Serviço não encontrado para o ID fornecido."

        duracao = servico.duracao_minutos
        servico_nome = servico.nome

        # 2. Calcular hora_fim
        hora_fim_dt = hora_inicio_dt + timedelta(minutes=duracao)
        hora_fim_time = hora_fim_dt.time()

        # 3. Verificar Conflitos
        agendamentos = await self.verificar_disponibilidade(data)

        for inicio_agendado, fim_agendado in agendamentos:
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

        logger.info(
            f"Agendamento para o usuário {user_id} com o serviço {servico_nome} preparado para commit.")

        # Retorna o objeto adicionado (ainda sem o ID, que será preenchido após o commit no DataService)
        return novo_agendamento, servico_nome, "Agendamento pronto para ser confirmado."

    async def get_servico_by_name(self, nome: str) -> Optional[Servico]:
        """Busca um serviço ativo pelo seu nome exato (case insensitive)."""
        stmt = select(Servico).where(
            Servico.ativo == True,
            func.lower(Servico.nome) == func.lower(nome)
        )
        # scalar_one_or_none é ideal para buscar um único resultado
        return (await self.session.scalars(stmt)).one_or_none()

    async def calculate_available_blocks(self,
                                         data: Union[str, date],
                                         duracao_minutos: int,
                                         shift_name: Optional[str] = None) -> list[str]:
        """
        Calcula todos os horários livres (no formato HH:MM) para a data e duração do serviço.
        Pode ser filtrado por um turno específico.
        """

        # 🎯 CORREÇÃO CRÍTICA: Garantir que 'data' é uma string YYYY-MM-DD para o DB
        if isinstance(data, date):
            data_str_final = data.strftime('%Y-%m-%d')
        elif isinstance(data, str):
            data_str_final = data
        else:
            logger.error(f"Tipo de dado inesperado recebido para 'data': {type(data)}")
            return []

        # 1. Definir a janela de tempo total
        if shift_name and shift_name in SHIFT_TIMES:
            shift = SHIFT_TIMES[shift_name]
            inicio_operacao = datetime.strptime(
                shift['inicio'], '%H:%M').time()
            fim_operacao = datetime.strptime(shift['fim'], '%H:%M').time()
        else:
            # Padrão: 8h às 22h
            inicio_operacao = time(8, 0)
            fim_operacao = time(22, 0)

        # 2. Obter agendamentos existentes (time, time)
        # O método verificar_disponibilidade já retorna os agendamentos ocupados.
        agendamentos_ocupados = await self.verificar_disponibilidade(data_str_final)

        horarios_livres: list[str] = []

        # Converte a hora de início para datetime para facilitar o cálculo
        current_dt = datetime.combine(datetime.min, inicio_operacao)
        fim_operacao_dt = datetime.combine(datetime.min, fim_operacao)

        # 3. Iterar de 30 em 30 minutos (ou a cada 1 minuto se quiser ser granular)
        intervalo_step = timedelta(minutes=30)

        while current_dt + timedelta(minutes=duracao_minutos) <= fim_operacao_dt:

            hora_inicio_bloco = current_dt.time()
            hora_fim_bloco = (
                current_dt + timedelta(minutes=duracao_minutos)).time()

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
