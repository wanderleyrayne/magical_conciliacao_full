"""
debug_workflow.py — Verifica registros no PocketBase e seus status
Execute da raiz: python debug_workflow.py
"""
import sqlite3
import requests
import os
from pathlib import Path

POSSIVEIS_DB = [
    Path(__file__).parent / "data" / "conciliacao.db",
    Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
]

DB_PATH = None
for p in POSSIVEIS_DB:
    if p.exists():
        DB_PATH = p
        break

if not DB_PATH:
    print("Banco nao encontrado!")
    exit(1)

def get_cfg(chave):
    with sqlite3.connect(str(DB_PATH)) as conn:
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
        ).fetchone()
        return row[0] if row and row[0] else ""

pb_url   = get_cfg("pb_url")
pb_email = get_cfg("pb_email")
pb_senha = get_cfg("pb_senha")

resp = requests.post(
    f"{pb_url}/api/collections/_superusers/auth-with-password",
    json={"identity": pb_email, "password": pb_senha},
    timeout=15,
)
token   = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
print("Login OK\n")

resp2 = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 50},
    timeout=15,
)
items = resp2.json().get("items", [])
print(f"Total registros: {len(items)}\n")

# Status aceitos pelo Workflow
STATUS_WORKFLOW = {
    "recebido", "em_lancamento", "ag_aprov_operacional",
    "cnab_pendente", "cnab_gerado", "ag_aprov_financeira", "pago"
}

for item in items:
    status = item.get("status","")
    ok = "✅" if status in STATUS_WORKFLOW else "❌ FORA DO WORKFLOW"
    print(f"  {item['id']} | {item.get('casa','?'):15} | status='{status}' {ok}")

print("\nStatus aceitos pelo Workflow:")
for s in sorted(STATUS_WORKFLOW):
    print(f"  - {s}")