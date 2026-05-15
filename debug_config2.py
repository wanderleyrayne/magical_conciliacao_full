import sqlite3
with sqlite3.connect('data/conciliacao.db') as conn:
    rows = conn.execute('SELECT chave, valor FROM nuvem_config').fetchall()
    for r in rows:
        k = r[0].lower()
        if 'grupo' in k or 'evo' in k or 'pb' in k or 'num' in k:
            print(f"{r[0]} = {r[1]}")