"""
debug_cloud_sync.py — Verifica o que listar_todas retorna
Execute da raiz: python debug_cloud_sync.py
"""
import sqlite3
import os
from pathlib import Path

POSSIVEIS_DB = [
    Path(__file__).parent / "data" / "conciliacao.db",
    Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
]
DB_PATH = next((p for p in POSSIVEIS_DB if p.exists()), None)

def get_cfg(chave):
    with sqlite3.connect(str(DB_PATH)) as conn:
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
        ).fetchone()
        return row[0] if row and row[0] else ""

pb_url   = get_cfg("pb_url")
pb_email = get_cfg("pb_email")
pb_senha = get_cfg("pb_senha")

from cloud_sync import CloudSync
cloud = CloudSync(pb_url, pb_email, pb_senha)

print("Chamando listar_todas...")
todas = cloud.listar_todas(limit=100)
print(f"Total retornado: {len(todas)}")
print(f"Tipo: {type(todas)}")

if todas:
    print(f"\nPrimeiro item:")
    print(f"  Tipo: {type(todas[0])}")
    print(f"  Conteudo: {todas[0]}")
    print(f"\nCampos disponiveis: {list(todas[0].keys()) if isinstance(todas[0], dict) else 'NAO E DICT'}")
    print(f"\nStatus dos itens:")
    for item in todas:
        if isinstance(item, dict):
            print(f"  id={item.get('id')} | casa={item.get('casa')} | status={item.get('status')}")
        else:
            print(f"  Item nao e dict: {item}")
else:
    print("Lista vazia!")