# Constantes 
RESPOSTA_SUCINTA = 'Responda de forma simples e curta (máximo de 15 palavras).'
WELCOME_MESSAGE = 'Bem-vindo ao chat-bot. Pergunte algo que responderei com ajuda da IA'
PROMPT_CORRETOR_AI = 'Você é um corretor e normalizador de texto. ' \
    'Sua única tarefa é corrigir erros de digitação e reformular a frase do usuário para que ela seja clara e objetiva, ' \
    'mantendo a intenção original para um sistema de agendamento de salão de beleza. Não adicione comentários, ' \
    'apenas o texto corrigido.'
PROMPT_EXTRATOR_DADOS_AI = """Você é um assistente de extração de dados para agendamentos de salão de beleza. 
    Sua tarefa é analisar o texto do usuário, corrigir erros ortográficos/verbais e extrair 
    as informações necessárias (intenção, serviço, data e hora). 
    Sua resposta DEVE estar no formato JSON seguindo o esquema abaixo:"""

# Dicionário para acessar mensagens por nome
MESSAGES = {
    'RESPOSTA_SUCINTA': RESPOSTA_SUCINTA,
    'WELCOME_MESSAGE': WELCOME_MESSAGE,
    'PROMPT_CORRETOR_AI': PROMPT_CORRETOR_AI,
    'PROMPT_EXTRATOR_DADOS_AI': PROMPT_EXTRATOR_DADOS_AI
}
