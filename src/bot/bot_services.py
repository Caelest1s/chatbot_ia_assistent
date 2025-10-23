from datetime import datetime
import logging

from src.bot.database_manager import DatabaseManager
from src.schemas.intencao_schema import Intencao
from telegram import Update

from src.utils.constants import BUSINESS_HOURS, WEEKDAY_MAP

logger = logging.getLogger(__name__)

class BotServices:
    """Implementa a lógica de negócios para agendamento e busca de serviços."""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def handle_agendamento_estruturado(self, update: Update, dados: Intencao) -> bool:
        """Processa a intenção AGENDAR com dados extraídos pela LLM."""
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name

        # Validação dos dados obrigatórios
        if not all([dados.servico_nome, dados.data, dados.hora]):
            await update.message.reply_text(f'{nome}, por favor, forneça o serviço, data (DD/MM/AAAA) e hora (HH:MM) completos para o agendamento.')
            return True # Retorna True para indicar que a requisição foi tratada
        
        # Uso direto dos campos extraídos
        servico_nome = dados.servico_nome
        data_str = dados.data
        hora_str = dados.hora
        
        try:
            # Tenta converter para objetos datetime para validação
            data_hora_agendamento = datetime.strptime(f"{data_str} {hora_str}", '%d/%m/%Y %H:%M')

            # --- NOVAS VALIDAÇÔES DE NEGÓCIOS ---

            # 2. Validação contra o Passado
            if data_hora_agendamento < datetime.now():
                await update.message.reply_text(f'{nome}, não posso agendar no passado. Por favor, escolha uma data e hora futuras.')
                return True

            # 3. Validação de Horário de Funcionamento
            # 3.1 Checa o dia da semana (0=Segunda, 6=Domingo)

            dia_semana_num = data_hora_agendamento.weekday()
            dia_semana_chave = WEEKDAY_MAP.get(dia_semana_num)
            horario_dia = BUSINESS_HOURS.get(dia_semana_chave)

            if horario_dia is None: # Se for None, o salão está fechado (ex: Domingo)
                await update.message.reply_text(f'{nome}, o salão está fechado na(o) {dia_semana_chave.capitalize()}. Por favor, escolha outro dia.')
                return True
            
            # 3.2 Checa se o horário está dentro do range
            hora_agendada = data_hora_agendamento.time()
            hora_inicio = horario_dia["start"]
            hora_fim = horario_dia["end"]

            if not (hora_inicio <= hora_agendada < hora_fim):
                await update.message.reply_text(
                    f'{nome}, o horário de funcionamento na(o) {dia_semana_chave.capitalize()} é das {hora_inicio.strftime("%H:%M")} às {hora_fim.strftime("%H:%M")}. Por favor, escolha um horário dentro desse intervalo.'
                )
                return True
            
            # --- FIM DAS VALIDAÇÕES DE NEGÓCIO ---

            # 4. Processamento Final (Agendamento no DB)
            # Padronização de Data/Hora para o BD
            data_dt = data_hora_agendamento.strftime('%Y-%m-%d')
            hora_dt = data_hora_agendamento.strftime('%H:%M')
            
            servicos = self.db_manager.buscar_servicos(servico_nome.strip())
            
            if not servicos:
                await update.message.reply_text(f'{nome}, serviço "{servico_nome}" não encontrado. Tente /servicos.')
                return True
                
            servico_id = servicos[0]['servico_id']
            sucesso, mensagem = self.db_manager.inserir_agendamento(user_id, servico_id, data_dt, hora_dt)
            await update.message.reply_text(f'{nome}, {mensagem}')
            return True
        except ValueError:
            # Captura erros se o formato de data/hora (DD/MM/AAAA HH:MM) for incorreto
            logger.error(f"Erro de formato ao agendar: data={data_str}, hora={hora_str}")
            await update.message.reply_text(f'{nome}, formato de data ou hora inválido. Use DD/MM/AAAA e HH:MM.')
            return True

        except Exception as e:
            logger.error(f"Erro ao agendar com dados estruturados: {e}")
            await update.message.reply_text(f'{nome}, erro interno ao agendar: {str(e)}')
            return 
    
    async def handle_buscar_servicos_estruturado(self, update: Update, dados: Intencao) -> bool:
        """Processa a intenção BUSCAR_SERVICO com o termo extraído pela LLM."""
        termo = dados.servico_nome
        if not termo:
            await update.message.reply_text("Por favor, diga qual serviço ou preço você gostaria de buscar.")
            return True
            
        user_id = update.message.from_user.id
        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name
        
        logger.info(f"Busca acionada com termo extraído: {termo}")
        resultados = self.db_manager.buscar_servicos(termo)
        
        if resultados:
            resposta = "Serviços encontrados:\n" + "\n".join([
                f"- {r['nome']}: {r['descricao']} (Preço: R${r['preco']:.2f}, Duração: {r['duracao_minutos']} min)"
                for r in resultados
            ])
        else:
            resposta = f"{nome}, nenhum serviço encontrado com o termo '{termo}'."
            
        await update.message.reply_text(resposta)
        return True