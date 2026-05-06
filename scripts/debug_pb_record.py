"""
debug_pb_record.py — Verifica formato dos campos do PocketBase
Execute: python debug_pb_record.py
"""
import sqlite3, requests
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

resp = requests.post(
    f"{pb_url}/api/collections/_superusers/auth-with-password",
    json={"identity": pb_email, "password": pb_senha},
)
token   = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}"}

print("=== Teste 1: sem fields ===")
resp1 = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 1},
)
item = resp1.json().get("items", [{}])[0]
print(f"Chaves: {list(item.keys())}")
print(f"created: {repr(item.get('created'))}")
print()

print("=== Teste 2: fields=@created,* ===")
resp2 = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 1, "fields": "@created,@updated,*"},
)
item2 = resp2.json().get("items", [{}])[0]
print(f"Chaves: {list(item2.keys())}")
print(f"@created: {repr(item2.get('@created'))}")
print(f"created:  {repr(item2.get('created'))}")
print()

print("=== Registro completo ===")
for k, v in item2.items():
    print(f"  {k}: {repr(v)[:60]}")