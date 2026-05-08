"""
fix_status_pocketbase.py — Atualiza campo status na colecao planilhas
e migra registros para os novos valores do Workflow.
Execute da raiz: python fix_status_pocketbase.py
"""
import sqlite3, requests, os, json
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

pb_url   = get_cfg("pb_url")
pb_email = get_cfg("pb_email")
pb_senha = get_cfg("pb_senha")

resp = requests.post(
    f"{pb_url}/api/collections/_superusers/auth-with-password",
    json={"identity": pb_email, "password": pb_senha}, timeout=15)
token   = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("Login OK\n")

# Novos valores aceitos
NOVOS_STATUS = [
    "recebido",
    "em_lancamento",
    "ag_aprov_operacional",
    "cnab_pendente",
    "cnab_gerado",
    "ag_aprov_financeira",
    "pago",
    "reprovado",
]

# Busca a colecao planilhas
print("1. Atualizando schema da colecao planilhas...")
resp_col = requests.get(f"{pb_url}/api/collections/planilhas", headers=headers, timeout=15)
col = resp_col.json()

# Atualiza campo status para aceitar novos valores
campos_atualizados = False
for campo in col.get("fields", []):
    if campo.get("name") == "status":
        tipo = campo.get("type", "")
        print(f"   Campo status tipo: {tipo}")
        if tipo == "select":
            campo["values"] = NOVOS_STATUS
            campos_atualizados = True
            print(f"   Valores atualizados: {NOVOS_STATUS}")
        elif tipo == "text":
            print("   Campo e texto — nao precisa atualizar schema")
        break

if campos_atualizados:
    resp_patch = requests.patch(
        f"{pb_url}/api/collections/planilhas",
        headers=headers, json=col, timeout=15)
    print(f"   Schema atualizado: {resp_patch.status_code}")
    if resp_patch.status_code not in (200, 201):
        print(f"   Erro: {resp_patch.text[:200]}")

# Migra registros
print("\n2. Migrando registros...")
MAPA = {
    "lancado":      "cnab_pendente",
    "cnab_enviado": "ag_aprov_financeira",
    "aprovado":     "pago",
}

items = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers, params={"perPage": 200}, timeout=15
).json().get("items", [])

print(f"   Total registros: {len(items)}\n")
migrados = 0

for item in items:
    status = item.get("status", "")
    novo   = MAPA.get(status)
    if novo:
        r = requests.patch(
            f"{pb_url}/api/collections/planilhas/records/{item['id']}",
            headers=headers,
            json={"status": novo},
            timeout=15)
        ok = r.status_code in (200, 201)
        print(f"   {item['id']} | {item.get('casa','?'):15} | {status} -> {novo} | {'OK' if ok else 'ERRO: ' + r.text[:80]}")
        migrados += 1
    else:
        print(f"   {item['id']} | {item.get('casa','?'):15} | {status} (sem alteracao)")

print(f"\n{migrados} registros migrados.")
print("Abra o Workflow — os cards devem aparecer nas colunas corretas!")