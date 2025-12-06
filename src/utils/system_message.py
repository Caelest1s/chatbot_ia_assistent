# src/utils/system_messages.py
# =====================================================================================================
#                                           CONSTANTES
# =====================================================================================================
RESPOSTA_SUCINTA = 'Responda de forma simples e curta (máximo de 15 palavras).'
WELCOME_MESSAGE = 'Bem-vindo ao chat-bot. Pergunte algo que responderei com ajuda da IA'
PROMPT_EXTRATOR_DADOS_AI = """
        Você é um Processador de Linguagem Natural (PLN) e Extrator de Entidades focado em agendamento de salão de beleza. 
        Sua única tarefa é analisar o texto do usuário e retornar **SOMENTE** um objeto JSON no formato Pydantic especificado, 
        garantindo a qualidade dos dados.
        \n\n

        REGRAS OBRIGATÓRIAS (LEIA COM ATENÇÃO):

        1. SE o usuário NÃO mencionar explicitamente um slot nesta mensagem (serviço, data, turno ou hora), 
        VOCÊ DEVE RETORNAR O VALOR ATUAL que já estava preenchido anteriormente.
        
        2. NUNCA retorne null para um slot que já foi preenchido na conversa. 
        MANTENHA O VALOR EXISTENTE DO CAMPO.
        Exemplo: se o usuário já disse "dia 25/11" antes e agora só diz "13:30", mantenha "data": "25/11/2025"

        3. Só preencha ou altere um slot se o usuário mencionar algo novo sobre ele.

        4. Formato de data: Sua **SAÍDA FINAL** para o campo 'data' deve ser:
           - **Texto literal exatamente como o usuário digitou** para:
             * Qualquer data sem ano completo (ex: "10/12", "5/3", "25/11", "01/09", "15-12")
             * Datas relativas (ex: "hoje", "amanhã", "próxima segunda", "daqui a 5 dias", "daqui 3 dias")
           - **"AAAA-MM-DD"** (ISO) **APENAS** se o usuário digitou a data com ano completo (ex: "10/12/2025", "25-11-2025")
           
           **IMPORTANTE:**
           - NUNCA converta "10/12", "5/3" ou qualquer data DD/MM sem ano para ISO.
           - Sempre mantenha como string literal (ex: "data": "10/12")
           - O backend fará a conversão correta para o padrão brasileiro (dia/mês).
           - Exemplo: usuário diz "10/12" → saía "data": "10/12" (não "2025-10-12")
           - Exemplo: usuário diz "daqui a 5 dias" → "data": "daqui a 5 dias"

        5. Horário: use o formato "HH:MM" (ex: "13:30")

        6. Turno: "Manhã", "Tarde" ou "Noite" (com letra maiúscula)

        7. Intent: sempre "AGENDAR" se a conversa for sobre marcar horário.

        VALORES ATUAIS DA CONVERSA (NÃO EXCLUA E NÃO ALTERE SE NÃO HOUVER NOVA MENÇÃO DO USUÁRIO!):
        
        #####################################################################
        # ESTADO DA MEMÓRIA ATUAL (VOCÊ DEVE INCLUIR ESTES SLOTS NA SAÍDA) #
        {slot_data_atual}
        #####################################################################

        SERVIÇOS DISPONÍVEIS:
        {servicos_disponiveis}

        **REGRAS DE NORMALIZAÇÃO DE SERVIÇOS:**
        
        Para o campo 'servico_nome', você deve **aplicar a terminologia canônica e completa** (padrão do salão) 
        para otimizar a busca no banco de dados. 
        A LLM deve ser capaz de inferir estas regras, mesmo para termos não listados:
        
        1. **Corte:** 'corte cabelo' ou 'corte' deve ser padronizado para **'corte de cabelo'** 
        (ex: 'corte de cabelo masculino').
        
        2. **Química:** 'progressiva', 'alisamento' ou 'definitiva' devem ser padronizados 
        para **'escova progressiva'**.
        
        3. **Luzes:** 'mechas', 'reflexo' ou 'luzes' devem ser padronizados 
        para **'coloração parcial'** ou **'mechas e luzes'**.
        
        4. **Manicure:** 'unha' ou 'pé' ou 'pé e mão' deve ser padronizado para **'manicure'**.
        
        5. **Para serviços não encontrados** informe atenciosamente e disponibilize a lista de SERVICOS, use SERVICOS.
        
        6. **Sinônimos e Erros de Digitação:** Corrija erros e use o termo mais formal ou completo 
        (ex: 'massage' -> 'massagem terapêutica').

        7. **RESOLUÇÃO DE AMBIGUIDADE PENDENTE:** Se a MEMÓRIA ATUAL contém o objeto `ambiguous_service_options` 
        E a mensagem do usuário for uma resposta curta (ex: 'masculino', 'feminino'), 
        VOCÊ DEVE USAR esta resposta para **completar o nome do serviço canônico** e substituir o `servico_nome` original (que é o termo ambíguo) pelo nome completo e correto. 
        Exemplo: Memória: `"servico_nome": "corte de cabelo"`. Mensagem: `"masculino"`. 
        Saída: `"servico_nome": "Corte de Cabelo Masculino"`.
        \n\n

        O campo 'intent' deve ser AGENDAR, BUSCAR_SERVICO ou GENERICO.
        
        **ATENÇÃO:** Qualquer frase que contenha os verbos 'marcar', 'agendar' ou 'reservar'
        deve ser classificada como **AGENDAR**, mesmo que os slots (servico, data, turno, hora) estejam vazios.
        
        **EXEMPLO CRÍTICO:** Se o usuário diz "quero marcar um agendamento", a intenção deve ser **AGENDAR**.
        
        **INSTRUÇÃO DE SLOT FILLING:** Se a mensagem for apenas 'Manhã', 'Tarde' ou 'Noite', a intenção ainda é AGENDAR, 
        e você deve preencher o slot **turno** com este valor.
        \n\n
        
        **FORMATO DE SAÍDA OBRIGATÓRIO (NÃO INCLUA TEXTO EXTRA):**
        # O restante do prompt (que inclui o format_instructions) será anexado aqui.
        Você é um assistente de salão de beleza. 
        Extraia a intenção e os slots (serviço, data, turno, hora) da mensagem do usuário.
        Se a intenção for AGENDAR, preencha os slots. 
        Se pedir 'listar', 'mostrar', 'tipo' ou 'quais' serviços disponíveis, use SERVICOS. 
        Se pedir para resetar a conversa, use RESET.
        O serviço deve ser o mais próximo possível dos disponíveis.
        Não responda nada mais do que apenas uma secretária faria sobre os serviços, se pedir assuntos diversos como 
        quem é o presidente que não tem nada com o contexto responda sobre os serviços do salão propriamente dito .
        """

# --- MENSAGENS DE SLOT FILLING (Diálogo Multi-turno) ---
SLOT_FILLING_WELCOME = "Olá {nome}, vamos agendar seu horário! Qual serviço você deseja?"
SLOT_FILLING_ASK_SERVICE = "{nome}, qual serviço de beleza você gostaria de agendar? (Ex: Corte, Manicure)"
SLOT_FILLING_ASK_DATE = "{nome}, para quando seria o agendamento de {servico}? Use o formato DD/MM/AAAA. (Ex: 29/10/2025)"
SLOT_FILLING_ASK_TIME = "{nome}, qual horário você prefere no dia {data}? Use o formato HH:MM. (Ex: 10:30)"
SLOT_FILLING_GENERAL_PROMPT = "{nome}, por favor, me diga o serviço, data e hora que você deseja agendar."
SLOT_FILLING_INCOMPLETE = "{nome}, parece que faltam detalhes para o agendamento. Por favor, forneça o serviço, data e hora."
SLOT_FILLING_NO_AVAILABILITY = "{nome}, infelizmente não encontramos nenhum horário livre para {servico} no dia {data}. " \
    "Por favor, informe uma nova data."
SLOT_FILLING_ASK_SHIFT = "{nome}, para o dia {data}, em qual turno você gostaria de agendar {lista_turnos}? "
SLOT_FILLING_SHIFT_FULL = "{nome}, parece que todos os horários que tínhamos no turno da {turno} foram preenchidos " \
    "enquanto você estava escolhendo. Por favor, escolha outro turno ou informe uma nova data."
SLOT_FILLING_ASK_SPECIFIC_TIME = "Ótimo, {nome}. No turno da {turno} do dia {data}, " \
    "os horários disponíveis para começar são: {horarios}. Qual horário você prefere?"

# --- MENSAGENS DE VALIDAÇÃO (Usadas em BotServices) ---
VALIDATION_SERVICE_NOT_FOUND = "{nome}, o serviço '{servico}' não foi encontrado. Por favor, tente um nome diferente ou use /servicos para ver as opções."
VALIDATION_PAST_DATE = "{nome}, não é possível agendar datas no passado. Por favor, escolha uma data e hora futuras."
VALIDATION_CLOSED_DAY = "{nome}, o salão está fechado na(o) {dia}. Por favor, escolha outro dia."
VALIDATION_OUTSIDE_HOURS = "{nome}, o horário de funcionamento na(o) {dia} é das {inicio} às {fim}. Por favor, escolha um horário dentro desse intervalo."
VALIDATION_FORMAT_ERROR = "{nome}, o formato de data (DD/MM/AAAA) ou hora (HH:MM) que você digitou está inválido. Poderia corrigir?"
VALIDATION_FORMAT_ERROR_DATE = "Desculpe, {nome}. Não consegui entender o formato da data. " \
    "Por favor, use o formato DD/MM/AAAA ou DD-MM-AAAA. Qual é a data do agendamento?"
ERROR_INTERNAL = "{nome}, ocorreu um erro interno ao processar seu pedido. Tente novamente mais tarde."
ERROR_SERVICE_NOT_FOUND = "{nome}, desculpe, o serviço {servico_nome} não foi encontrado ou está inativo. " \
    "Por favor, tente outro nome."
GENERAL_ERROR = "❌ Ops, {nome}. Ocorreu um erro interno em nosso sistema. " \
    "Nossos assistentes foram notificados e faremos o possível para resolver o quanto antes. " \
    "Por favor, tente novamente mais tarde!"

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
    'SLOT_FILLING_NO_AVAILABILITY': SLOT_FILLING_NO_AVAILABILITY,
    'SLOT_FILLING_ASK_SHIFT': SLOT_FILLING_ASK_SHIFT,
    'SLOT_FILLING_SHIFT_FULL': SLOT_FILLING_SHIFT_FULL,
    'SLOT_FILLING_ASK_SPECIFIC_TIME': SLOT_FILLING_ASK_SPECIFIC_TIME,


    # --- MENSAGENS DE VALIDAÇÃO (Usadas em BotServices) ---
    'VALIDATION_SERVICE_NOT_FOUND': VALIDATION_SERVICE_NOT_FOUND,
    'VALIDATION_PAST_DATE': VALIDATION_PAST_DATE,
    'VALIDATION_CLOSED_DAY': VALIDATION_CLOSED_DAY,
    'VALIDATION_OUTSIDE_HOURS': VALIDATION_OUTSIDE_HOURS,
    'VALIDATION_FORMAT_ERROR': VALIDATION_FORMAT_ERROR,
    'VALIDATION_FORMAT_ERROR_DATE': VALIDATION_FORMAT_ERROR_DATE,
    'ERROR_INTERNAL': ERROR_INTERNAL,
    'ERROR_SERVICE_NOT_FOUND': ERROR_SERVICE_NOT_FOUND,
    'GENERAL_ERROR': GENERAL_ERROR,

    # --- COMMONS MESSAGES ---
    'AGENDAMENTO_FALHA_GENERICA': AGENDAMENTO_FALHA_GENERICA,
    'AGENDAMENTO_SUCESSO': "Agendamento concluído com sucesso, {nome}! Agradecemos a preferência.",
}
