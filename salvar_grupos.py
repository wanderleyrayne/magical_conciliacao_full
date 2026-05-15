import sqlite3

configs = {
    "grupo_espaco_ser": "120363256893742170@g.us",
}

with sqlite3.connect('data/conciliacao.db') as conn:
    for chave, valor in configs.items():
        conn.execute(
            "INSERT INTO nuvem_config (chave, valor) VALUES (?, ?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor)
        )
    conn.commit()
    print("Salvo! Verificando...")
    rows = conn.execute(
        "SELECT chave, valor FROM nuvem_config WHERE chave LIKE '%grupo%'"
    ).fetchall()
    for r in rows:
        print(f"  {r[0]} = {r[1]}")