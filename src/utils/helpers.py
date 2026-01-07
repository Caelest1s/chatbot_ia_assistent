# src/utils/helpers.py

class SafeDict(dict):
    """
    Dicionário customizado que evita KeyError durante o .format_map() ou .format()
    Se uma chave não existir, ele retorna a chave entre chaves (ex: {data})
    """
    def __missing__(self, key):
        return f"[{key} não informado]"