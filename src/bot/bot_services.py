from datetime import datetime
import logging

from src.bot.database_manager import DatabaseManager
from src.schemas.slot_extraction_schema import SlotExtraction
from telegram import Update
from telegram.ext import CallbackContext
from src.utils.system_message import MESSAGES
from src.utils.constants import BUSINESS_HOURS, WEEKDAY_MAP

logger = logging.getLogger(__name__)

class BotServices:
    """Implementa a lógica de negócios para agendamento e busca de serviços."""
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager

    async def handle_agendamento_estruturado(self, update: Update, context: CallbackContext ,dados: SlotExtraction) -> bool:
        """
        Processa a intenção AGENDAR com dados extraídos pela LLM.
        Esta função é chamada APENAS quando TODOS os slots são preenchidos
        (pelo Slot Filling ou Agendamento Rápido /agenda).
        Retorna True se tratado com sucesso ou falha tratada, False se erro interno grave.
        """
        user_id = update.effective_user.id

        nome = self.db_manager.get_nome_usuario(user_id) or update.message.from_user.first_name

        # O Slot Filling garante que os dados estejam preenchidos,
        # mas a validação de formato e negócio é essencial.
        
        servico_nome = dados.servico_nome.strip()
        data_str = dados.data
        hora_str = dados.hora

        # 1. VALIDAÇÃO DE SERVIÇO (verifica se é válido, não mais ambíguo)
        servicos_encontrados = self.db_manager.buscar_servicos(servico_nome)
        
        # Se 0 serviços, o Slot Filling deveria ter capturado, mas verificamos novamente.
        if len(servicos_encontrados) == 0:
            await update.message.reply_text(MESSAGES['VALIDATION_SERVICE_NOT_FOUND'].format(nome=nome, servico=servico_nome))
            # Não limpa o estado, mantendo o AGENDAR ativo
            return True 
            
        # Pega o primeiro e único serviço encontrado (presumindo que o nome é unívoco ou o primeiro é o correto)
        servico = servicos_encontrados[0]
        servico_id = servico['servico_id']
        
        try:
            # 2. VALIDAÇÃO DE DATA E HORA (Formato)
            # Tenta combinar e converter para DT
            data_str = dados.data
            hora_str = dados.hora.replace('h', ':00').replace('H', ':00').strip() # Converte '12h' para '12:00'

            data_hora_agendamento = datetime.strptime(f"{data_str} {hora_str}", '%d/%m/%Y %H:%M')
            
            # 3. VALIDAÇÕES DE NEGÓCIOS (Passado, Horário de Funcionamento)
            if data_hora_agendamento < datetime.now():
                await update.message.reply_text(MESSAGES['VALIDATION_PAST_DATE'])
                return True

            # Lógica de validação de horário de funcionamento (mantida do seu código)
            dia_semana_num = data_hora_agendamento.weekday()
            dia_semana_chave = WEEKDAY_MAP.get(dia_semana_num)
            horario_dia = BUSINESS_HOURS.get(dia_semana_chave)
            
            if horario_dia is None: 
                await update.message.reply_text(f'{nome}, o salão está fechado na(o) {dia_semana_chave.capitalize()}. Por favor, escolha outro dia.')
                return True
            
            hora_agendada = data_hora_agendamento.time()
            hora_inicio = horario_dia["start"]
            hora_fim = horario_dia["end"]

            # Note que a validação de range de horário está duplicada e pode ser simplificada
            if not (hora_inicio <= hora_agendada < hora_fim):
                 await update.message.reply_text(
                    MESSAGES['VALIDATION_OUTSIDE_HOURS'].format(
                        nome=nome, 
                        dia=dia_semana_chave.capitalize(), 
                        inicio=hora_inicio.strftime("%H:%M"), 
                        fim=hora_fim.strftime("%H:%M")
                    )
                )
                 return True

            # 4. CHAMADA FINAL DE AGENDAMENTO
            data_dt = data_hora_agendamento.strftime('%Y-%m-%d')
            hora_dt = data_hora_agendamento.strftime('%H:%M')
            
            sucesso, mensagem = self.db_manager.inserir_agendamento(user_id, servico_id, data_dt, hora_dt)
            
            await update.message.reply_text(f'{nome}, {mensagem}')
            
            # 5. RETORNO FINAL: True se tratado (sucesso ou falha de negócio), False se for erro técnico.
            # No caso de sucesso (True), o BotHandler limpa o estado.
            # No caso de falha no agendamento (Horário indisponível), a mensagem é enviada, 
            # e retornamos True, o que *encerra o fluxo* (o handler limpa a sessão, talvez você não queira isso!)
            
            # Recomendação: Para "Horário indisponível", não limpe o estado.
            # Contudo, para simplificar o fluxo de handlers, vamos manter o padrão:
            return True # Indica que o serviço respondeu.

        except ValueError:
            # Erro de formato (DD/MM/AAAA ou HH:MM não estavam corretos)
            logger.error(f"Erro de formato ao agendar: data={data_str}, hora={hora_str}")
            await update.message.reply_text(MESSAGES['VALIDATION_FORMAT_ERROR'].format(nome=nome))
            return False

        except Exception as e:
            logger.error(f"Erro ao agendar com dados estruturados: {e}")
            await update.message.reply_text(MESSAGES['ERROR_INTERNAL'].format(nome=nome))
            return False
    
    async def handle_buscar_servicos_estruturado(self, update: Update, context: CallbackContext, dados: SlotExtraction) -> bool:
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