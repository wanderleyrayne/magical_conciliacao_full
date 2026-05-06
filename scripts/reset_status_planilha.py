"""
reset_status_planilha.py — Reseta status de planilhas no PocketBase
Execute: python reset_status_planilha.py
"""
import requests

PB_URL = "https://pocketbase-railway-production-336e.up.railway.app"
EMAIL  = "wanderleyrayne@hotmail.com"
SENHA  = "Tito@2017"

resp = requests.post(
    f"{PB_URL}/api/collections/_superusers/auth-with-password",
    json={"identity": EMAIL, "password": SENHA},
)
token   = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("Login OK\n")

# Lista todos os registros
resp = requests.get(
    f"{PB_URL}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 50},
)
items = resp.json().get("items", [])
print(f"Registros encontrados: {len(items)}\n")

for i, item in enumerate(items):
    print(f"[{i+1}] ID: {item['id']}")
    print(f"     Casa: {item.get('casa')}")
    print(f"     Planilha: {item.get('nome_arquivo')}")
    print(f"     Status: {item.get('status')}")
    print()

if not items:
    print("Nenhum registro encontrado.")
    exit()

# Seleciona qual resetar
escolha = input("Digite o numero do registro para resetar status (ou 'todos' para resetar todos): ").strip()

STATUS_NOVO = input("Novo status [recebido/em_lancamento/lancado/cnab_gerado]: ").strip() or "recebido"

if escolha.lower() == "todos":
    targets = items
else:
    try:
        idx = int(escolha) - 1
        targets = [items[idx]]
    except Exception:
        print("Opcao invalida.")
        exit()

for item in targets:
    r = requests.patch(
        f"{PB_URL}/api/collections/planilhas/records/{item['id']}",
        headers=headers,
        json={"status": STATUS_NOVO, "lancado_por": ""},
    )
    status = "OK" if r.status_code in (200, 201) else f"ERRO: {r.text[:80]}"
    print(f"  {item.get('casa')} | {item.get('nome_arquivo')} → {STATUS_NOVO} | {status}")

print("\nConcluido!")