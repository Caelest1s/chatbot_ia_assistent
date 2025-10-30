import logging
from telegram import Update
from telegram.ext import ContextTypes
import asyncio
from src.bot.database_manager import DatabaseManager
from src.services.appointment_service import AppointmentService
from src.schemas.slot_extraction_schema import SlotExtraction
from src.utils.system_message import MESSAGES
from src.utils.constants import REQUIRED_SLOTS
from src.utils.logger import setup_logger

logger = logging.getLogger(__name__)

class SlotFillingManager:
    """Gerencia o diálogo multi-turno para preencher os slots de agendamento (AGENDAR)."""
    def __init__(self, db_manager: DatabaseManager, appointment_service: AppointmentService):
        self.db_manager = db_manager
        self.appointment_service = appointment_service

    async def _ask_for_next_slot(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
        nome: str, updated_slots: dict, missing_slots: list):
            """Envia a mensagem ao usuário pedindo o próximo slot em falta."""
            next_slot = missing_slots[0]

            if next_slot == 'servico_nome':
                 response = MESSAGES['SLOT_FILLING_ASK_SERVICE'].format(nome=nome)
            elif next_slot == 'data':
                response = MESSAGES['SLOT_FILLING_ASK_DATE'].format(nome=nome, servico=updated_slots.get('servico_nome', 'o serviço'))
            elif next_slot == 'hora':
                response = MESSAGES['SLOT_FILLING_ASK_TIME'].format(nome=nome, data=updated_slots.get('data', 'a data'))
            else:
                response = MESSAGES['SLOT_FILLING_GENERAL_PROMPT'].format(nome=nome)

            await update.message.reply_text(response)

    async def handle_slot_filling(self, update: Update, context: ContextTypes.DEFAULT_TYPE, new_slots: SlotExtraction):
        """Gerencia o fluxo principal do Slot Filling, incluindo a resolução de ambiguidades."""
        user_id = update.effective_user.id
        nome = await asyncio.to_thread(self.db_manager.get_nome_usuario,user_id) or update.effective_user.first_name

        session_state = await asyncio.to_thread(self.db_manager.get_session_state, user_id)
        current_slots = session_state.get('slot_data', {})
        updated_slots = current_slots.copy()

        # 1. Mesclar slots extraídos
        for slot_name in REQUIRED_SLOTS:
            new_value = getattr(new_slots, slot_name, None)
            if new_value:
                updated_slots[slot_name] = new_value.strip()

        # 2. TRATAMENTO E VALIDAÇÃO DE SERVIÇO
        servico_nome_atual = updated_slots.get('servico_nome')
        session_ambiguity = current_slots.get('ambiguous_service_options')
        
        # 2.0. AJUSTE CRÍTICO: FORÇAR RESET DE AMBIGUIDADE PENDENTE
        # Se um NOVO servico_nome foi extraído (e não é uma resposta a uma pergunta),
        # limpamos qualquer estado de ambiguidade persistente.
        is_new_service_term = servico_nome_atual and 'servico_nome' not in current_slots
        
        if is_new_service_term and session_ambiguity:
             logger.warning("Ambiguidade pendente detectada, mas novo serviço fornecido. Resetando ambiguidade pendente.")
             del updated_slots['ambiguous_service_options']
             session_ambiguity = None # Atualiza a variável local para o próximo passo

        # 2.1. Tentar Resolver Ambiguidade (Fluxo de Resposta à Pergunta)
        if servico_nome_atual and session_ambiguity:
            
            # Usa o termo original + o termo da resposta (ex: "corte de cabelo feminino")
            original_term = session_ambiguity.get('original_term', '')
            term_to_search = f"{original_term} {servico_nome_atual}"
            
            resolved_servicos = await asyncio.to_thread(self.db_manager.buscar_servicos, term_to_search)
            
            # Tenta buscar apenas pelo termo curto como fallback (ex: 'feminino' sozinho)
            if not resolved_servicos:
                 resolved_servicos = await asyncio.to_thread(self.db_manager.buscar_servicos, servico_nome_atual)

            if len(resolved_servicos) == 1:
                # Ambiguidade RESOLVIDA!
                updated_slots['servico_nome'] = resolved_servicos[0]['nome']
                # 👈 ESTE TRECHO DEVE SER REFORÇADO:
                if 'ambiguous_service_options' in updated_slots:
                    del updated_slots['ambiguous_service_options'] 
                servico_nome_atual = updated_slots['servico_nome'] 
            else:
                # Ambiguidade NÃO resolvida ou ambíguo de novo.
                await update.message.reply_text(
                    f"Ainda não consegui entender qual serviço você deseja. "
                    "Por favor, diga o nome **exato** do serviço que você viu na lista (ex: Corte de Cabelo Feminino)."
                )
                await asyncio.to_thread(self.db_manager.update_session_state, user_id, current_intent='AGENDAR', slot_data=updated_slots)
                return True # Interrompe o fluxo e espera a próxima mensagem.

        # 2.2. Validar o Serviço (Detecção inicial, só executa se o serviço ainda não foi resolvido)
        if servico_nome_atual and 'ambiguous_service_options' not in updated_slots:
            
            servicos_encontrados = await asyncio.to_thread(self.db_manager.buscar_servicos, servico_nome_atual)

            if len(servicos_encontrados) == 0:
                # Caso: Serviço não encontrado.
                
                nomes_servicos = await asyncio.to_thread(self.db_manager.get_available_services_names)
                sugestao = ""
                if nomes_servicos:
                    if len(nomes_servicos) <= 4:
                        sugestao = " Nossos serviços principais são: " + ", ".join(nomes_servicos) + "."
                    else:
                        sugestao = " Você pode usar o comando /servicos para ver a lista completa."
                        
                resposta_erro = MESSAGES['VALIDATION_SERVICE_NOT_FOUND'].format(nome=nome, servico=servico_nome_atual)
                resposta_completa = f"{resposta_erro}.{sugestao}"

                await update.message.reply_text(resposta_completa)
                
                del updated_slots['servico_nome']
                await asyncio.to_thread(self.db_manager.update_session_state, user_id, current_intent='AGENDAR', slot_data=updated_slots)
                return True 
            
            elif len(servicos_encontrados) > 1:
                # Ambiguidade DETECTADA! (Primeira vez que o termo gera múltiplos resultados)
                
                # 1. Salva o contexto de ambiguidade na sessão (ISSO JÁ OCORREU E ESTÁ NO SEU LOG)
                updated_slots['ambiguous_service_options'] = {
                    'original_term': servico_nome_atual,
                    'options': [s['servico_id'] for s in servicos_encontrados]
                }
                
                # 2. MONTAGEM DA MENSAGEM:
                opcoes = "\n".join([f"- {s['nome']} (R${s['preco']:.2f})" for s in servicos_encontrados])
                await update.message.reply_text(f"Encontrei mais de uma opção para '{servico_nome_atual}':\n{opcoes}\nQual deles você gostaria de agendar?")
                
                # 3. Persiste o estado e interrompe
                await asyncio.to_thread(self.db_manager.update_session_state, user_id, current_intent='AGENDAR', slot_data=updated_slots)
                return True 
                
            elif len(servicos_encontrados) == 1:
                # Serviço único:
                updated_slots['servico_nome'] = servicos_encontrados[0]['nome']
                if 'ambiguous_service_options' in updated_slots:
                     del updated_slots['ambiguous_service_options'] 

        # 3. Verificar slots faltantes
        # Garante que o serviço ambíguo não é considerado um slot faltante para forçar a pergunta
        missing_slots = [slot for slot in REQUIRED_SLOTS if slot not in updated_slots]
        
        if 'ambiguous_service_options' in updated_slots and 'servico_nome' in missing_slots:
             missing_slots.remove('servico_nome') 
        
        if not missing_slots:
            # 4. Todos os slots preenchidos: Finalizar Agendamento
            
            dados_completos = SlotExtraction(intent='AGENDAR', **updated_slots)
            
            is_successful, _ = await self.appointment_service.handle_agendamento_estruturado(update, context, dados_completos)

            if is_successful:
                await asyncio.to_thread(self.db_manager.clear_session_state, user_id)
            
            return is_successful

        else:
            # 5. Slots Faltando: Solicitar o Próximo Slot
            await asyncio.to_thread(self.db_manager.update_session_state, user_id, current_intent='AGENDAR', slot_data=updated_slots)
            await self._ask_for_next_slot(update, context, nome, updated_slots, missing_slots)
            return True