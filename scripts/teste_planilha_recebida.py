"""
teste_planilha_recebida.py — Simula recebimento de planilha e envia notificacao
Execute: python teste_planilha_recebida.py
"""

import sqlite3

DB_PATH = r"data\conciliacao.db"

def get_cfg(chave, default=""):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
            ).fetchone()
            return row[0] if row and row[0] else default
    except Exception:
        return default

# Carrega configurações
evo_url      = get_cfg("evo_url")
evo_key      = get_cfg("evo_key")
instancia    = get_cfg("evo_instancia", "wanderley")
num_wanderley= get_cfg("num_wanderley")
pb_url       = get_cfg("pb_url")
pb_email     = get_cfg("pb_email")
pb_senha     = get_cfg("pb_senha")
meu_nome     = get_cfg("meu_nome", "Sistema")

print(f"EVO URL:    {evo_url}")
print(f"Instancia:  {instancia}")
print(f"Wanderley:  {num_wanderley}")
print(f"PB URL:     {pb_url}")
print()

# 1. Salva planilha no PocketBase
print("1. Salvando planilha no PocketBase...")
pid = None
try:
    from cloud_sync import CloudSync
    cs = CloudSync(pb_url, pb_email, pb_senha)

    pid = cs.salvar_planilha_recebida(
        casa        = "CHATEAU",
        nome_arquivo= "CHATEAU_Contas_Pagar_Teste.xlsx",
        enviado_por = "Gerente Chateau",
        total_itens = 12,
        valor_total = 35966.55,
    )
    print(f"   OK — ID: {pid}")
except Exception as e:
    print(f"   ERRO: {e}")

# 2. Envia notificação WhatsApp
print("\n2. Enviando notificação WhatsApp...")
try:
    from notificador import Notificador
    n = Notificador(evo_url, evo_key, instancia)

    st = n.status_instancia()
    print(f"   Status instancia: {st}")

    if st.get("conectado"):
        msg = n.msg_planilha_recebida(
            casa        = "CHATEAU",
            total_itens = 12,
            valor_total = 35966.55,
            enviado_por = "Gerente Chateau",
        )
        print(f"   Mensagem:\n{msg}\n")

        # Envia para seu numero
        r = n.enviar_contato(num_wanderley, msg)
        print(f"   Resultado: {r}")
    else:
        print("   WhatsApp nao conectado!")
except Exception as e:
    print(f"   ERRO: {e}")

print("\nTeste concluido!")
print(f"Verifique o PocketBase: {pb_url}/_/")