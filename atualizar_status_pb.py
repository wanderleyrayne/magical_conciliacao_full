"""
atualizar_status_pb.py — Atualiza colecao planilhas no PocketBase
com os novos status do fluxo de duas aprovacoes.

Execute: python atualizar_status_pb.py
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

# Busca colecao planilhas
resp = requests.get(f"{PB_URL}/api/collections/planilhas", headers=headers)
col  = resp.json()

# Novos status validos
novos_status = [
    "recebido",
    "em_lancamento",
    "ag_aprov_operacional",   # aguardando aprovacao do Diretor Operacional
    "cnab_pendente",           # aprovado op. -> aguardando gerar CNAB
    "cnab_gerado",             # CNAB gerado -> aguardando envio Itau
    "ag_aprov_financeira",    # aguardando aprovacao do Diretor Financeiro
    "pago",                    # aprovado financeiro -> concluido
    "reprovado",               # reprovado em qualquer etapa
]

# Atualiza campo status
campos = col.get("fields", [])
for campo in campos:
    if campo.get("name") == "status":
        campo["values"] = novos_status
        print(f"Status atualizado: {novos_status}")
        break
else:
    # Campo nao existe como select, adiciona como text
    print("Campo status nao encontrado como select — mantendo como texto")

resp2 = requests.patch(
    f"{PB_URL}/api/collections/planilhas",
    headers=headers,
    json=col,
)
print(f"Collection atualizada: {resp2.status_code}")

# Migra registros com status antigos para novos equivalentes
MAPA_MIGRACAO = {
    "lancado":      "cnab_pendente",   # era lancado, agora aguarda CNAB
    "cnab_enviado": "ag_aprov_financeira",  # era enviado, agora ag. aprovacao fin.
    "aprovado":     "pago",            # era aprovado, agora pago
}

resp3 = requests.get(
    f"{PB_URL}/api/collections/planilhas/records",
    headers=headers,
    params={"perPage": 200},
)
items = resp3.json().get("items", [])
print(f"\nMigrando {len(items)} registros...")

migrados = 0
for item in items:
    status_atual = item.get("status", "")
    novo_status  = MAPA_MIGRACAO.get(status_atual)
    if novo_status:
        r = requests.patch(
            f"{PB_URL}/api/collections/planilhas/records/{item['id']}",
            headers=headers,
            json={"status": novo_status},
        )
        ok = r.status_code in (200, 201)
        print(f"  {item['id']} | {status_atual} → {novo_status} | {'OK' if ok else 'ERRO'}")
        migrados += 1

print(f"\n{migrados} registros migrados.")
print("Concluido!")