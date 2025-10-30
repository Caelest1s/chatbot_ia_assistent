import logging
import colorlog
import sys

# Variável de controle para garantir que a configuração seja feita apenas uma vez
_logger_configured = False

def setup_logger(name: str) -> logging.Logger:
    """
    Configura e retorna um logger colorido, garantindo que não haja duplicação
    de handlers e desabilitando a propagação para evitar logs duplicados
    com o logger raiz.
    """

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # ----------------------------------------------------
    # 1. EVITAR HANDLERS DUPLICADOS
    # Se o logger já tem handlers, apenas o retornamos.
    # Isso impede que a função seja chamada em loop e duplique a saída.
    if logger.handlers:
        return logger
    # ----------------------------------------------------

    # 2. CONFIGURAR HANDLER E FORMATTER
    handler = colorlog.StreamHandler(sys.stdout)
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S", # Use um formato mais completo
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red,bg_white'
        },
        secondary_log_colors={},
        style='%'
    )

    global _logger_configured

    # 1. Obter o logger (usamos o logging padrão, mas o colorlog o aprimora)

    # 2. Configurar o nível globalmente para o logger base
    # (Pode ser ajustado para logging.INFO em produção)

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # ----------------------------------------------------
    # 3. IMPEDIR A PROPAGAÇÃO (CHAVE PARA RESOLVER A DUPLICAÇÃO)
    # Isso impede que os logs deste logger sejam passados para o logger raiz,
    # que é quem geralmente tem um handler padrão que duplica a mensagem.
    logger.propagate = False 
    # ----------------------------------------------------

    return logger

# ----------------------------------------------------
# 4. TRATAR LOGS DE BIBLIOTECAS DE TERCEIROS (OPCIONAL, MAS RECOMENDADO)
# Para logs como "HTTP Request: POST..." que vêm da LangChain/OpenAI,
# Configurar o nível do logger raiz ou dos loggers específicos dessas libs.
# Garante que apenas as mensagens relevantes apareçam.

def configure_root_and_external_loggers():
    """Configura o logger raiz e loggers de libs externas."""
    # Desabilita completamente o logger raiz (ou o define como CRITICAL)
    # para que APENAS os loggers criados com setup_logger funcionem.
    root_logger = logging.getLogger()
    
    # Se você quiser apenas ver ERRORs e CRITICALs do root logger
    # root_logger.setLevel(logging.ERROR) 
    
    # Se você quiser que o logger raiz não tenha handlers (para evitar duplicação)
    # Mas deixe o nível para DEBUG para que as libs externas passem os logs
    # para você, se necessário.
    root_logger.handlers = []
    root_logger.setLevel(logging.DEBUG)
    
    # Exemplo: Aumentar o nível de log do HTTP para evitar muito barulho
    logging.getLogger("httpx").setLevel(logging.WARNING) 
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

# Chama a configuração no final do módulo, garantindo que o root logger seja tratado
configure_root_and_external_loggers()

# Exemplo de teste para verificar a não duplicação
# test_logger = setup_logger("TESTE_DUPLICACAO")
# test_logger.info("Primeiro log.")
# test_logger_2 = setup_logger("TESTE_DUPLICACAO") # Chama novamente
# test_logger_2.info("Segundo log (não deve duplicar).")