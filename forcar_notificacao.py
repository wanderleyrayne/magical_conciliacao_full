"""
forcar_notificacao.py — Forca envio de notificacao de aprovacao (texto simples)
Execute da raiz: python forcar_notificacao.py
"""
import sqlite3, requests

def get_cfg(chave, default=""):
    with sqlite3.connect('data/conciliacao.db') as conn:
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
        ).fetchone()
        return row[0] if row and row[0] else default

evo_url   = get_cfg("evo_url")
evo_key   = get_cfg("evo_key")
instancia = get_cfg("evo_instancia", "wanderley")
pb_url    = get_cfg("pb_url")
pb_email  = get_cfg("pb_email")
pb_senha  = get_cfg("pb_senha")

print("=== Forcar Notificacao de Aprovacao Operacional ===\n")

resp = requests.post(
    f"{pb_url}/api/collections/_superusers/auth-with-password",
    json={"identity": pb_email, "password": pb_senha},
    timeout=10
)
token = resp.json().get("token","")
if not token:
    print("ERRO: Falha auth PocketBase")
    exit(1)

headers_pb = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

r = requests.get(
    f"{pb_url}/api/collections/planilhas/records",
    headers=headers_pb,
    params={"perPage": 50, "filter": 'status="ag_aprov_operacional"'},
    timeout=15
)
planilhas = r.json().get("items", [])

if not planilhas:
    print("Nenhuma planilha em Ag. Aprov. Operacional.")
    exit(0)

print("Planilhas em Ag. Aprov. Operacional:\n")
for i, p in enumerate(planilhas):
    vf = f"R$ {float(p.get('total_valor',0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    print(f"  [{i}] {p.get('casa','')} | {vf} | {p.get('nome_arquivo','')[:40]}")

print()
idx = input("Numero da planilha (Enter = todas): ").strip()
selecionadas = [planilhas[int(idx)]] if idx.isdigit() else planilhas

for p in selecionadas:
    casa        = p.get("casa","")
    lancado_por = p.get("lancado_por","Sistema")

    chave_grupo = f"grupo_{casa.lower().replace(' ','_')}"
    grupo_id    = get_cfg(chave_grupo)

    if not grupo_id:
        print(f"\n[{casa}] Grupo nao configurado.")
        grupo_id = input(f"  Cole o ID do grupo (ou Enter para pular): ").strip()
        if not grupo_id:
            continue
        with sqlite3.connect('data/conciliacao.db') as conn:
            conn.execute(
                "INSERT INTO nuvem_config (chave, valor) VALUES (?,?) "
                "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                (chave_grupo, grupo_id)
            )
            conn.commit()
        print(f"  Grupo salvo!")

    msg = (
        f"*{casa} \u2014 Lan\u00e7amento Conclu\u00eddo*\n\n"
        f"Casa: {casa}\n"
        f"Lan\u00e7ado por: {lancado_por}\n\n"
        f"Para APROVAR responda:\n"
        f"SIM ou OK\n\n"
        f"Para REPROVAR responda:\n"
        f"N\u00c3O [motivo]"
    )

    print(f"\n[{casa}] Enviando para {grupo_id}...")
    r = requests.post(
        f"{evo_url}/message/sendText/{instancia}",
        headers={"apikey": evo_key, "Content-Type": "application/json"},
        json={"number": grupo_id, "text": msg},
        timeout=20
    )
    if r.status_code in (200, 201):
        print(f"  OK Enviado!")
    else:
        print(f"  ERRO: {r.status_code} {r.text[:100]}")

print("\nConcluido!")