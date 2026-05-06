"""
debug_cloud.py — Testa CloudSync diretamente
Execute: python debug_cloud.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path("data") / "conciliacao.db"

def get_cfg(chave, default=""):
    with sqlite3.connect(str(DB_PATH)) as conn:
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
        ).fetchone()
        return row[0] if row and row[0] else default

pb_url   = get_cfg("pb_url")
pb_email = get_cfg("pb_email")
pb_senha = get_cfg("pb_senha")

print(f"PB URL:   {pb_url}")
print(f"PB Email: {pb_email}")

from cloud_sync import CloudSync
cs = CloudSync(pb_url, pb_email, pb_senha)

print(f"\n1. Ping: {cs.ping()}")

print("\n2. Token:")
token = cs._get_token()
print(f"   {'OK' if token else 'FALHOU'}")

print("\n3. Listando planilhas (sem filtro):")
import requests
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
resp = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 10},
    timeout=15,
)
print(f"   Status: {resp.status_code}")
data = resp.json()
print(f"   Total items: {data.get('totalItems', '?')}")
items = data.get("items", [])
print(f"   Items: {len(items)}")
for item in items:
    print(f"   - {item.get('casa')} | {item.get('nome_arquivo')} | status={item.get('status')}")

print("\n4. Via cloud_sync.listar_todas:")
todas = cs.listar_todas(limit=50)
print(f"   Retornou: {len(todas)} itens")