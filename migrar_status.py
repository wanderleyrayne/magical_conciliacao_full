"""
migrar_status.py — Migra status antigos para o novo fluxo do Workflow
Execute da raiz: python migrar_status.py
"""
import sqlite3
import requests
import os
from pathlib import Path

POSSIVEIS_DB = [
    Path(__file__).parent / "data" / "conciliacao.db",
    Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
]

DB_PATH = next((p for p in POSSIVEIS_DB if p.exists()), None)
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
    json={"identity": pb_email, "password": pb_senha}, timeout=15)
token   = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("Login OK\n")

# Mapeamento status antigo → novo
MAPA = {
    "lancado":      "cnab_pendente",        # ERP lancado → aguarda gerar CNAB
    "cnab_enviado": "ag_aprov_financeira",  # enviado ao banco → aguarda aprovacao financeira
    "aprovado":     "pago",                 # aprovado → pago
}

resp2 = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers, params={"perPage": 200}, timeout=15)
items = resp2.json().get("items", [])

print(f"Total registros: {len(items)}")
migrados = 0

for item in items:
    status_atual = item.get("status", "")
    novo = MAPA.get(status_atual)
    if novo:
        r = requests.patch(
            f"{pb_url}/api/collections/planilhas/records/{item['id']}",
            headers=headers,
            json={"status": novo},
            timeout=15,
        )
        ok = r.status_code in (200, 201)
        print(f"  {item['id']} | {item.get('casa','?'):15} | {status_atual} → {novo} | {'OK' if ok else 'ERRO'}")
        migrados += 1
    else:
        print(f"  {item['id']} | {item.get('casa','?'):15} | {status_atual} (sem alteracao)")

print(f"\n{migrados} registros migrados.")
print("Abra o Workflow no sistema — os cards devem aparecer agora!")