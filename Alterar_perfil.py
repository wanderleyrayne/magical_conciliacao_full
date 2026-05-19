"""
reset_perfil.py — Restaura perfil para financeiro_ti
Execute: python reset_perfil.py
"""
import sqlite3
from pathlib import Path

# Tenta os dois bancos
caminhos = [
    Path("data") / "conciliacao.db",
    Path.home() / "AppData" / "Roaming" / "Magical_Conciliacao" / "data" / "conciliacao.db",
]

for db_path in caminhos:
    if not db_path.exists():
        print(f"Nao encontrado: {db_path}")
        continue

    print(f"Atualizando: {db_path}")
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "UPDATE nuvem_config SET valor='financeiro_ti' WHERE chave='meu_perfil'"
        )
        conn.execute(
            "UPDATE nuvem_config SET valor='Wanderley' WHERE chave='meu_nome'"
        )
        conn.commit()
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave='meu_perfil'"
        ).fetchone()
        print(f"  Perfil atual: {row[0] if row else '?'}")

print("\nOK! Reinicie o sistema.")