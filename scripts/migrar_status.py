"""
migrar_status.py — Migra status antigos para o novo fluxo do Workflow
Execute da raiz: python migrar_status.py
"""
import sqlite3, requests, os
from pathlib import Path

POSSIVEIS_DB = [
    Path(__file__).parent / "data" / "conciliacao.db",
    Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
]
DB_PATH = next((p for p in POSSIVEIS_DB if p.exists()), None)

def get_cfg(chave):
    with sqlite3.connect(str(DB_PATH)) as conn:
        row = conn.execute("SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)).fetchone()
        return row[0] if row and row[0] else ""

token = requests.post(
    f"{get_cfg('pb_url')}/api/collections/_superusers/auth-with-password",
    json={"identity": get_cfg("pb_email"), "password": get_cfg("pb_senha")}, timeout=15
).json()["token"]

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
pb_url  = get_cfg("pb_url")
print("Login OK\n")

MAPA = {
    "lancado":      "cnab_pendente",
    "cnab_enviado": "ag_aprov_financeira",
    "aprovado":     "pago",
}

items = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers, params={"perPage": 200}, timeout=15
).json().get("items", [])

print(f"Total: {len(items)}\n")
migrados = 0

for item in items:
    status = item.get("status", "")
    novo   = MAPA.get(status)
    if novo:
        r  = requests.patch(
            f"{pb_url}/api/collections/planilhas/records/{item['id']}",
            headers=headers, json={"status": novo}, timeout=15)
        ok = r.status_code in (200, 201)
        print(f"  {item['id']} | {item.get('casa','?'):15} | {status} -> {novo} | {'OK' if ok else 'ERRO'}")
        migrados += 1
    else:
        print(f"  {item['id']} | {item.get('casa','?'):15} | {status} (sem alteracao)")

print(f"\n{migrados} migrados.")