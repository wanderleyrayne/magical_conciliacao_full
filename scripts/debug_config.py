"""
debug_config.py — Verifica onde estao as configuracoes de nuvem
Execute: python debug_config.py
"""
import sqlite3
import os
from pathlib import Path

# Tenta os dois locais possiveis
caminhos = [
    Path(os.environ.get("APPDATA", "")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
    Path("data") / "conciliacao.db",
]

for db_path in caminhos:
    print(f"\nVerificando: {db_path}")
    if not db_path.exists():
        print("  -> nao existe")
        continue

    print("  -> encontrado!")
    try:
        with sqlite3.connect(str(db_path)) as conn:
            # Verifica se tabela existe
            tbls = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            print(f"  Tabelas: {[t[0] for t in tbls]}")

            if ("nuvem_config",) in tbls:
                rows = conn.execute(
                    "SELECT chave, valor FROM nuvem_config"
                ).fetchall()
                print(f"  nuvem_config ({len(rows)} registros):")
                for chave, valor in rows:
                    v = valor[:30] if valor else "(vazio)"
                    print(f"    {chave:20} = {v}")
            else:
                print("  nuvem_config: NAO EXISTE")
    except Exception as e:
        print(f"  Erro: {e}")