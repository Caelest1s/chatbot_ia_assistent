# =====================================================================================================
#                                           CONSTANTES
# =====================================================================================================
RESPOSTA_SUCINTA = 'Responda de forma simples e curta (máximo de 15 palavras).'
WELCOME_MESSAGE = 'Bem-vindo ao chat-bot. Pergunte algo que responderei com ajuda da IA'
PROMPT_EXTRATOR_DADOS_AI = """Você é um Processador de Linguagem Natural (PLN) e Extrator de Entidades focado em agendamento de salão de beleza.
        Sua única tarefa é analisar o texto do usuário e retornar **SOMENTE** um objeto JSON no formato Pydantic especificado, garantindo a qualidade dos dados.
        \n\n
        **REGRAS DE NORMALIZAÇÃO DE SERVIÇOS:**
        Para o campo 'servico_nome', você deve **aplicar a terminologia canônica e completa** (padrão do salão) 
        para otimizar a busca no banco de dados. 
        A LLM deve ser capaz de inferir estas regras, mesmo para termos não listados:
        1. **Corte:** 'corte cabelo' ou 'corte' deve ser padronizado para **'corte de cabelo'** 
        (ex: 'corte de cabelo masculino').
        2. **Química:** 'progressiva', 'alisamento' ou 'definitiva' devem ser padronizados
        para **'alisamento permanente'** ou **'alisamento progressiva'**.
        3. **Luzes:** 'mechas', 'reflexo' ou 'luzes' devem ser padronizados 
        para **'coloração parcial'** ou **'mechas e luzes'**.
        4. **Manicure:** 'unha' deve ser padronizado para **'manicure'**.
        5. **Sinônimos e Erros de Digitação:** Corrija erros e use o termo mais formal ou completo 
        (ex: 'massage' -> 'massagem terapêutica').
        \n\n
        O campo 'intent' deve ser AGENDAR, BUSCAR_SERVICO ou GENERICO.
        \n\n
        **FORMATO DE SAÍDA OBRIGATÓRIO (NÃO INCLUA TEXTO EXTRA):**
        # O restante do prompt (que inclui o format_instructions) será anexado aqui.
        Você é um assistente de salão de beleza. 
        Extraia a intenção e os slots (serviço, data, hora) da mensagem do usuário.
        Serviços disponíveis: {servicos_disponiveis}. Se a intenção for AGENDAR, preencha os slots. 
        Se pedir a lista de serviços, use SERVICOS. Se pedir para resetar a conversa, use RESET.',
        O serviço deve ser o mais próximo possível dos disponíveis."""

# --- MENSAGENS DE SLOT FILLING (Diálogo Multi-turno) ---
SLOT_FILLING_WELCOME = "Olá {nome}, vamos agendar seu horário! Qual serviço você deseja?"
SLOT_FILLING_ASK_SERVICE = "{nome}, qual serviço de beleza você gostaria de agendar? (Ex: Corte, Manicure)"
SLOT_FILLING_ASK_DATE = "{nome}, para quando seria o agendamento de {servico}? Use o formato DD/MM/AAAA. (Ex: 29/10/2025)"
SLOT_FILLING_ASK_TIME = "{nome}, qual horário você prefere no dia {data}? Use o formato HH:MM. (Ex: 10:30)"
SLOT_FILLING_GENERAL_PROMPT = "{nome}, por favor, me diga o serviço, data e hora que você deseja agendar."
SLOT_FILLING_INCOMPLETE = "{nome}, parece que faltam detalhes para o agendamento. Por favor, forneça o serviço, data e hora."
# --- MENSAGENS DE VALIDAÇÃO (Usadas em BotServices) ---
VALIDATION_SERVICE_NOT_FOUND = "{nome}, o serviço '{servico}' não foi encontrado. Por favor, tente um nome diferente ou use /servicos para ver as opções."
VALIDATION_PAST_DATE = "{nome}, não é possível agendar no passado. Por favor, escolha uma data e hora futuras."
VALIDATION_CLOSED_DAY = "{nome}, o salão está fechado na(o) {dia}. Por favor, escolha outro dia."
VALIDATION_OUTSIDE_HOURS = "{nome}, o horário de funcionamento na(o) {dia} é das {inicio} às {fim}. Por favor, escolha um horário dentro desse intervalo."
VALIDATION_FORMAT_ERROR = "{nome}, o formato de data (DD/MM/AAAA) ou hora (HH:MM) que você digitou está inválido. Poderia corrigir?"
ERROR_INTERNAL = "{nome}, ocorreu um erro interno ao processar seu pedido. Tente novamente mais tarde."
# --- COMMONS MESSAGES ---
AGENDAMENTO_FALHA_GENERICA = "Desculpe, não foi possível concluir o agendamento no momento devido a um problema interno. Tente novamente mais tarde ou seja mais específico."
AGENDAMENTO_SUCESSO = "Agendamento concluído com sucesso, {nome}! Agradecemos a preferência."
# =====================================================================================================
#                               Dicionário para acessar mensagens por nome
# =====================================================================================================
MESSAGES = {
    'WELCOME_MESSAGE': WELCOME_MESSAGE,
    'RESPOSTA_SUCINTA': RESPOSTA_SUCINTA,
    'PROMPT_EXTRATOR_DADOS_AI': PROMPT_EXTRATOR_DADOS_AI,
    # --- MENSAGENS DE SLOT FILLING (Diálogo Multi-turno) ---
    'SLOT_FILLING_WELCOME': SLOT_FILLING_WELCOME,
    'SLOT_FILLING_ASK_SERVICE': SLOT_FILLING_ASK_SERVICE,
    'SLOT_FILLING_ASK_DATE': SLOT_FILLING_ASK_DATE,
    'SLOT_FILLING_ASK_TIME': SLOT_FILLING_ASK_TIME,
    'SLOT_FILLING_GENERAL_PROMPT': SLOT_FILLING_GENERAL_PROMPT,
    'SLOT_FILLING_INCOMPLETE': SLOT_FILLING_INCOMPLETE,
    # --- MENSAGENS DE VALIDAÇÃO (Usadas em BotServices) ---
    'VALIDATION_SERVICE_NOT_FOUND': VALIDATION_SERVICE_NOT_FOUND,
    'VALIDATION_PAST_DATE': VALIDATION_PAST_DATE,
    'VALIDATION_CLOSED_DAY': VALIDATION_CLOSED_DAY,
    'VALIDATION_OUTSIDE_HOURS': VALIDATION_OUTSIDE_HOURS,
    'VALIDATION_FORMAT_ERROR': VALIDATION_FORMAT_ERROR,
    'ERROR_INTERNAL': ERROR_INTERNAL,
    # --- COMMONS MESSAGES ---
    'AGENDAMENTO_FALHA_GENERICA': AGENDAMENTO_FALHA_GENERICA,
    'AGENDAMENTO_SUCESSO': "Agendamento concluído com sucesso, {nome}! Agradecemos a preferência.",
}


# src/utils/messages.py

# Seu dicionário de mensagens, renomeado para evitar conflito de importação
# MESSAGES = {
#     'WELCOME_MESSAGE': 'Seja bem-vindo(a) ao Salão Glamour! Posso te ajudar a agendar um serviço, tirar dúvidas ou mostrar nossos serviços.',
#     'RESPOSTA_SUCINTA': 'Você é um assistente de chatbot de um salão de beleza e deve responder de forma sucinta e direta. Mantenha a persona de um assistente cordial.',
#     'SLOT_FILLING_WELCOME': 'Certo, {nome}! Vamos agendar. Qual serviço você gostaria de fazer?',
#     'SLOT_FILLING_ASK_SERVICE': '{nome}, qual serviço você gostaria de agendar? (Ex: "Corte feminino")',
#     'SLOT_FILLING_ASK_DATE': 'Ótimo. Para o serviço "{servico}", que dia você gostaria de agendar? (Use o formato DD/MM/AAAA)',
#     'SLOT_FILLING_ASK_TIME': 'E qual o melhor horário no dia {data}? (Ex: 14:30 ou 16h)',
#     'VALIDATION_SERVICE_NOT_FOUND': '{nome}, não encontrei um serviço chamado "{servico}". Por favor, escolha um serviço válido.',
#     'VALIDATION_PAST_DATE': 'Não podemos agendar para uma data ou hora que já passou. Por favor, escolha um horário futuro.',
#     'VALIDATION_OUTSIDE_HOURS': '{nome}, o salão está fechado na(o) {dia}. Nosso horário é de {inicio} a {fim}. Por favor, escolha outro horário.',
#     'VALIDATION_FORMAT_ERROR': '{nome}, o formato da data ou hora está incorreto. Por favor, tente novamente.',
#     'AGENDAMENTO_SUCESSO': 'Agendamento concluído! {nome}, seu horário está reservado.',
#     'ERROR_INTERNAL': '{nome}, desculpe, ocorreu um erro interno. Tente novamente mais tarde.',
#     'PROMPT_EXTRATOR_DADOS_AI': 'Você é um extrator de dados de intenção e slots. 
#           Sua única tarefa é analisar o texto do usuário e retornar o objeto JSON no formato Pydantic. 
#           Use a lista de serviços: {servicos_disponiveis} para identificar o `servico_nome`. 
#           Se o usuário perguntar algo genérico, use intent: GENERICO e coloque o texto na variável `servico_nome`. 
#           Se a intenção for agendar, use AGENDAR. Se for buscar informações, use BUSCAR_SERVICO. 
#           Se pedir a lista de serviços, use SERVICOS. Se pedir para resetar a conversa, use RESET.',
# }