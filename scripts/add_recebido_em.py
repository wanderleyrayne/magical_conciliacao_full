"""
add_recebido_em.py — Adiciona campo recebido_em na colecao planilhas
Execute: python add_recebido_em.py
"""
import requests
from datetime import datetime

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

# Busca coleção
resp = requests.get(f"{PB_URL}/api/collections/planilhas", headers=headers)
col  = resp.json()

campos = [f["name"] for f in col.get("fields", [])]
print(f"Campos atuais: {campos}")

if "recebido_em" not in campos:
    col["fields"].append({
        "name":     "recebido_em",
        "type":     "text",
        "required": False,
    })
    resp2 = requests.patch(
        f"{PB_URL}/api/collections/planilhas",
        headers=headers,
        json=col,
    )
    print(f"Campo adicionado: {resp2.status_code}")
else:
    print("Campo recebido_em ja existe")

# Atualiza registros existentes sem data
resp3 = requests.get(
    f"{PB_URL}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 100},
)
items = resp3.json().get("items", [])
agora = datetime.now().strftime("%d/%m/%Y %H:%M")

for item in items:
    if not item.get("recebido_em"):
        r = requests.patch(
            f"{PB_URL}/api/collections/planilhas/records/{item['id']}",
            headers=headers,
            json={"recebido_em": agora},
        )
        print(f"  {item['id']} | {item.get('casa')} | {agora} | {'OK' if r.status_code in (200,201) else 'ERRO'}")

print("\nConcluido!")