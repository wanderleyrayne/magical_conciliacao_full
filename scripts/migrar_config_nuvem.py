"""
migrar_config_nuvem.py — Copia configuracoes de nuvem do banco dev para producao
Execute: python migrar_config_nuvem.py
"""
import sqlite3
from pathlib import Path
import os

DB_DEV  = Path("data") / "conciliacao.db"
DB_PROD = Path(os.environ.get("APPDATA", "")) / "Magical_Conciliacao" / "data" / "conciliacao.db"

print(f"Origem:  {DB_DEV}")
print(f"Destino: {DB_PROD}")

# Lê configs do banco dev
with sqlite3.connect(str(DB_DEV)) as conn:
    rows = conn.execute("SELECT chave, valor FROM nuvem_config").fetchall()

print(f"\n{len(rows)} configuracoes encontradas:")
for chave, valor in rows:
    print(f"  {chave:20} = {(valor or '')[:40]}")

# Copia para banco producao
with sqlite3.connect(str(DB_PROD)) as conn:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS nuvem_config "
        "(chave TEXT PRIMARY KEY, valor TEXT)"
    )
    for chave, valor in rows:
        conn.execute(
            "INSERT INTO nuvem_config(chave, valor) VALUES(?,?) "
            "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
            (chave, valor)
        )
    conn.commit()

print(f"\nOK — {len(rows)} configs copiadas para o banco de producao!")
print("Abra o sistema e teste a tela de Pendencias.")