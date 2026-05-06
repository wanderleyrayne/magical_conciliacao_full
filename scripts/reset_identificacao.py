import sqlite3
with sqlite3.connect('data/conciliacao.db') as c:
    c.execute("DELETE FROM nuvem_config WHERE chave='meu_numero'")
    c.commit()
print('OK - meu_numero removido')