"""
cadastrar_usuarios.py — Cadastra usuarios no PocketBase com numeros WhatsApp
Execute: python cadastrar_usuarios.py
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

usuarios = [
    {
        "nome":      "Wanderley",
        "perfil":    "financeiro_ti",
        "whatsapp":  "5521967503863",
        "ativo":     True,
    },
    {
        "nome":      "Michell",
        "perfil":    "operacional_erp",
        "whatsapp":  "5521979694752",
        "ativo":     True,
    },
    {
        "nome":      "Marcielo",
        "perfil":    "financeiro_cnab",
        "whatsapp":  "5521965801974",
        "ativo":     True,
    },
]

# Busca existentes para não duplicar
resp = requests.get(
    f"{PB_URL}/api/collections/usuarios/records",
    headers=headers,
    params={"perPage": 50},
)
existentes = {u.get("whatsapp"): u["id"] for u in resp.json().get("items", [])}
print(f"Usuarios existentes: {len(existentes)}")

for u in usuarios:
    wpp = u["whatsapp"]
    if wpp in existentes:
        # Atualiza
        r = requests.patch(
            f"{PB_URL}/api/collections/usuarios/records/{existentes[wpp]}",
            headers=headers,
            json=u,
        )
        status = "atualizado" if r.status_code in (200,201) else f"ERRO: {r.text[:80]}"
    else:
        # Cria
        r = requests.post(
            f"{PB_URL}/api/collections/usuarios/records",
            headers=headers,
            json=u,
        )
        status = "criado" if r.status_code in (200,201) else f"ERRO: {r.text[:80]}"

    print(f"  {u['nome']:12} | {u['perfil']:20} | {wpp} | {status}")

print("\nOK! Usuarios cadastrados no PocketBase.")