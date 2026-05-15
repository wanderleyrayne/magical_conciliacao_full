"""
pre_teste.py — Verifica configuracoes antes do teste completo
Execute da raiz: python pre_teste.py
"""
import sqlite3, requests

def get_cfg(chave, default=""):
    with sqlite3.connect('data/conciliacao.db') as conn:
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
        ).fetchone()
        return row[0] if row and row[0] else default

print("=" * 50)
print("PRE-TESTE MAGICAL WORKFLOW")
print("=" * 50)

evo_url   = get_cfg("evo_url")
evo_key   = get_cfg("evo_key")
instancia = get_cfg("evo_instancia", "wanderley")
grupo_es  = get_cfg("grupo_espaco_ser")
grupo_bpo = get_cfg("grupo_aprovacao")

print(f"\n1. Evolution API: {evo_url}")
print(f"   Instancia: {instancia}")

# Testa conexao WhatsApp
try:
    r = requests.get(
        f"{evo_url}/instance/connectionState/{instancia}",
        headers={"apikey": evo_key},
        timeout=10
    )
    state = r.json().get("instance", {}).get("state", "?")
    ok = "✅" if state == "open" else "❌"
    print(f"   WhatsApp: {ok} {state}")
except Exception as e:
    print(f"   WhatsApp: ❌ {e}")

print(f"\n2. Grupos configurados:")
print(f"   Espaco Ser: {'✅ ' + grupo_es if grupo_es else '❌ NAO CONFIGURADO'}")
print(f"   BPO:        {'✅ ' + grupo_bpo if grupo_bpo else '❌ NAO CONFIGURADO'}")

# Testa webhook
print(f"\n3. Webhook Railway:")
try:
    pb_url = get_cfg("pb_url")
    webhook_url = "https://magical-webhook-production.up.railway.app/health"
    r = requests.get(webhook_url, timeout=10)
    ok = "✅" if r.status_code == 200 else "❌"
    print(f"   Status: {ok} {r.status_code}")
except Exception as e:
    print(f"   Status: ❌ {e}")

# Planilhas em ag_aprov_operacional
print(f"\n4. Planilhas prontas para teste:")
pb_url   = get_cfg("pb_url")
pb_email = get_cfg("pb_email")
pb_senha = get_cfg("pb_senha")
try:
    resp = requests.post(
        f"{pb_url}/api/collections/_superusers/auth-with-password",
        json={"identity": pb_email, "password": pb_senha}, timeout=10
    )
    token = resp.json().get("token","")
    r = requests.get(
        f"{pb_url}/api/collections/planilhas/records",
        headers={"Authorization": f"Bearer {token}"},
        params={"perPage": 20, "filter": 'status="ag_aprov_operacional"'},
        timeout=15
    )
    items = r.json().get("items", [])
    if items:
        for p in items:
            vf = f"R$ {float(p.get('total_valor',0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")
            print(f"   ✅ {p.get('casa','')} | {vf} | {p.get('nome_arquivo','')[:35]}")
    else:
        print("   Nenhuma em Ag. Aprov. Operacional ainda")
except Exception as e:
    print(f"   ❌ {e}")

print("\n" + "=" * 50)
print("Tudo OK? Avance o card manualmente no Workflow")
print("e aguarde a notificacao no grupo do Espaco Ser!")
print("=" * 50)