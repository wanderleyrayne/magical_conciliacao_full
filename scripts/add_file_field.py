"""
add_file_field.py — Adiciona campo de arquivo na coleção planilhas
Execute: python add_file_field.py
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
headers = {"Authorization": f"Bearer {token}"}
print("Login OK")

# Busca coleção planilhas
resp = requests.get(f"{PB_URL}/api/collections/planilhas", headers=headers)
col  = resp.json()

# Verifica se campo arquivo já existe
campos = [f["name"] for f in col.get("fields", [])]
print(f"Campos atuais: {campos}")

if "arquivo" in campos:
    print("Campo 'arquivo' já existe!")
else:
    # Adiciona campo de arquivo
    col["fields"].append({
        "name":    "arquivo",
        "type":    "file",
        "required": False,
        "options": {
            "maxSelect": 1,
            "maxSize":   10485760,  # 10MB
            "mimeTypes": [
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
                "text/csv",
            ],
        },
    })

    resp2 = requests.patch(
        f"{PB_URL}/api/collections/planilhas",
        headers={**headers, "Content-Type": "application/json"},
        json=col,
    )
    print(f"Update: {resp2.status_code}")
    if resp2.status_code in (200, 201):
        print("OK — campo 'arquivo' adicionado!")
    else:
        print(f"Erro: {resp2.text[:300]}")