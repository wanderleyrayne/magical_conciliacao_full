"""
fix_pocketbase_status.py — Corrige valores do campo status na colecao planilhas
Execute: python fix_pocketbase_status.py
"""
import requests

PB_URL = "https://pocketbase-railway-production-336e.up.railway.app"
EMAIL  = "wanderleyrayne@hotmail.com"
SENHA  = "Tito@2017"

# Login
resp = requests.post(
    f"{PB_URL}/api/collections/_superusers/auth-with-password",
    json={"identity": EMAIL, "password": SENHA},
)
token   = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
print("Login OK")

# Busca a coleção planilhas
resp = requests.get(f"{PB_URL}/api/collections/planilhas", headers=headers)
col  = resp.json()

# Atualiza o campo status com valores corretos
for field in col.get("fields", []):
    if field.get("name") == "status":
        field["values"] = [
            "recebido", "em_lancamento", "lancado",
            "cnab_gerado", "cnab_enviado", "aprovado", "reprovado"
        ]
        print(f"Campo status atualizado: {field['values']}")
        break

# Salva a coleção atualizada
resp2 = requests.patch(
    f"{PB_URL}/api/collections/planilhas",
    headers=headers,
    json=col,
)
print(f"Update status: {resp2.status_code}")
if resp2.status_code in (200, 201):
    print("OK — valores do status corrigidos!")
else:
    print(f"Erro: {resp2.text[:200]}")