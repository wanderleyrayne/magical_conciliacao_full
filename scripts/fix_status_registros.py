"""
fix_status_registros.py — Atualiza status dos registros existentes no PocketBase
Execute: python fix_status_registros.py
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
print("Login OK")

# Busca todos os registros
resp = requests.get(
    f"{PB_URL}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 100},
)
items = resp.json().get("items", [])
print(f"Registros encontrados: {len(items)}")

# Mapa de correção de status
fix_map = {
    "recebida":      "recebido",
    "lancada":       "lancado",
    "aprovada":      "aprovado",
    "reprovada":     "reprovado",
}

for item in items:
    status_atual = item.get("status", "")
    status_novo  = fix_map.get(status_atual)
    if status_novo:
        r = requests.patch(
            f"{PB_URL}/api/collections/planilhas/records/{item['id']}",
            headers=headers,
            json={"status": status_novo},
        )
        print(f"  {item['id']} | {item.get('casa')} | {status_atual} → {status_novo} | {'OK' if r.status_code in (200,201) else r.text[:80]}")
    else:
        print(f"  {item['id']} | {item.get('casa')} | {status_atual} (sem alteração)")

print("\nConcluído!")