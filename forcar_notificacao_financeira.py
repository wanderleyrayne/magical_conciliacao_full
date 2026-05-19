"""
forcar_notificacao_financeira.py — Reenvia notificacao de aprovacao financeira (texto simples)
Execute da raiz: python forcar_notificacao_financeira.py
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

print("=== Forcar Notificacao de Aprovacao Financeira ===\n")

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

# Busca planilhas em cnab_gerado (No Itau) ou ag_aprov_financeira
for status_filtro in ["cnab_gerado", "ag_aprov_financeira"]:
    r = requests.get(
        f"{pb_url}/api/collections/planilhas/records",
        headers=headers_pb,
        params={"perPage": 50, "filter": f'status="{status_filtro}"'},
        timeout=15
    )
    items = r.json().get("items", [])
    if items:
        print(f"Planilhas em '{status_filtro}':")
        for i, p in enumerate(items):
            vf = f"R$ {float(p.get('total_valor',0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")
            print(f"  [{i}] {p.get('casa','')} | {vf} | {p.get('nome_arquivo','')[:35]}")
        break
else:
    print("Nenhuma planilha em 'No Itau' ou 'Ag. Aprov. Financeira'.")
    exit(0)

print()
idx = input("Numero da planilha (Enter = todas): ").strip()
selecionadas = [items[int(idx)]] if idx.isdigit() else items

for p in selecionadas:
    casa        = p.get("casa","")
    gerado_por  = p.get("cnab_gerado_por","") or p.get("lancado_por","Sistema")
    vf          = f"R$ {float(p.get('total_valor',0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")
    total_pgtos = p.get("total_itens", 0)

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

    msg = (
        f"*{casa} \u2014 Lote de Pagamento no Ita\u00fa*\n\n"
        f"Casa: {casa}\n"
        f"Gerado por: {gerado_por}\n"
        f"Total: {vf}\n"
        f"Pagamentos: {total_pgtos}\n\n"
        f"Para APROVAR o pagamento responda:\n"
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