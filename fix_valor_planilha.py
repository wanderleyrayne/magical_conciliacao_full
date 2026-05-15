"""
fix_valor_planilha.py — Recalcula total_valor de uma planilha no PocketBase
filtrando apenas linhas com data de hoje.

Uso: python fix_valor_planilha.py [ID_DA_PLANILHA]
     python fix_valor_planilha.py          (lista todas pendentes)
"""
import sys, io, sqlite3
from datetime import date as _date
from pathlib import Path

# Lê config do banco local
def get_cfg(chave, default=""):
    try:
        db = Path("data/conciliacao.db")
        if not db.exists():
            db = Path(__file__).parent / "data" / "conciliacao.db"
        if not db.exists():
            db = Path.home() / "AppData/Roaming/Magical_Conciliacao/data/conciliacao.db"
        with sqlite3.connect(str(db)) as conn:
            row = conn.execute(
                "SELECT valor FROM app_settings WHERE key=? LIMIT 1", (chave,)
            ).fetchone()
            return row[0] if row else default
    except Exception:
        return default

_db_path = (Path("data/conciliacao.db") if Path("data/conciliacao.db").exists()
            else Path(__file__).parent / "data" / "conciliacao.db")
print(f"Usando banco: {_db_path} (existe: {_db_path.exists()})")
pb_url   = get_cfg("pb_url") or input("PocketBase URL: ").strip()
pb_email = get_cfg("pb_email") or input("Email: ").strip()
pb_senha = get_cfg("pb_senha") or input("Senha: ").strip()

import requests

# Auth
resp = requests.post(
    f"{pb_url}/api/collections/_superusers/auth-with-password",
    json={"identity": pb_email, "password": pb_senha},
    timeout=10
)
token = resp.json().get("token","")
if not token:
    print("ERRO: Falha na autenticacao")
    sys.exit(1)

headers = {"Authorization": f"Bearer {token}"}

def listar_planilhas():
    r = requests.get(
        f"{pb_url}/api/collections/planilhas/records",
        headers=headers,
        params={"perPage": 50, "filter": 'status!="pago"&&status!="reprovado"'},
        timeout=15
    )
    return r.json().get("items", [])

def recalcular(pid):
    # Busca planilha
    r = requests.get(
        f"{pb_url}/api/collections/planilhas/records/{pid}",
        headers=headers, timeout=10
    )
    if r.status_code != 200:
        print(f"ERRO: Planilha {pid} nao encontrada")
        return

    p = r.json()
    nome_arquivo = p.get("arquivo","") or p.get("nome_arquivo","")
    casa = p.get("casa","")
    status = p.get("status","")
    valor_atual = p.get("total_valor", 0)

    print(f"\nPlanilha: {pid}")
    print(f"  Casa:         {casa}")
    print(f"  Status:       {status}")
    print(f"  Arquivo:      {nome_arquivo}")
    print(f"  Valor atual:  R$ {float(valor_atual):,.2f}".replace(",","X").replace(".",",").replace("X","."))

    if not nome_arquivo:
        print("  ERRO: Sem arquivo anexado")
        return

    # Baixa arquivo
    r2 = requests.get(
        f"{pb_url}/api/files/planilhas/{pid}/{nome_arquivo}",
        headers=headers, timeout=30
    )
    if r2.status_code != 200:
        print(f"  ERRO: Nao foi possivel baixar o arquivo ({r2.status_code})")
        return

    conteudo = r2.content
    print(f"  Arquivo baixado: {len(conteudo)} bytes")

    # Recalcula com filtro de data
    hoje = _date.today()
    total_itens = 0
    total_valor = 0.0

    try:
        import openpyxl, pandas as pd
        wb = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))

        header_row = None
        val_col    = None
        data_col   = None

        for i, row in enumerate(rows[:10]):
            for j, cell in enumerate(row):
                cel = str(cell).upper().strip()
                if cel in ("VALOR","VALOR TOTAL") and val_col is None:
                    header_row = i
                    val_col    = j
                if cel == "DATA" and data_col is None:
                    data_col = j
            if header_row is not None:
                break

        print(f"  Cabecalho linha {header_row} | col VALOR={val_col} | col DATA={data_col}")

        if header_row is not None and val_col is not None:
            ignoradas = 0
            for row in rows[header_row+1:]:
                if not any(c for c in row if c is not None):
                    continue

                # Filtra por data
                if data_col is not None:
                    cell_data = row[data_col]
                    if cell_data is not None:
                        try:
                            dt = pd.to_datetime(str(cell_data), dayfirst=True, errors="coerce")
                            if pd.notna(dt) and dt.date() != hoje:
                                ignoradas += 1
                                continue
                        except Exception:
                            pass
                    else:
                        ignoradas += 1
                        continue

                try:
                    v = float(str(row[val_col] or "0")
                              .replace(",",".").replace("R$","").strip())
                    if v > 0:
                        total_valor += v
                        total_itens += 1
                except Exception:
                    pass

            print(f"  Linhas de hoje: {total_itens} | Ignoradas (outra data): {ignoradas}")

        wb.close()

    except Exception as e:
        print(f"  ERRO ao ler planilha: {e}")
        return

    total_fmt = f"R$ {total_valor:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    print(f"  Novo valor calculado: {total_fmt} ({total_itens} itens)")

    confirm = input(f"\n  Atualizar PocketBase com {total_fmt}? [s/N] ").strip().lower()
    if confirm != "s":
        print("  Cancelado.")
        return

    # Atualiza PocketBase
    r3 = requests.patch(
        f"{pb_url}/api/collections/planilhas/records/{pid}",
        headers={**headers, "Content-Type": "application/json"},
        json={"total_valor": round(total_valor, 2), "total_itens": total_itens},
        timeout=15
    )
    if r3.status_code in (200, 201):
        print(f"  ✅ Atualizado com sucesso!")
    else:
        print(f"  ERRO: {r3.status_code} {r3.text[:100]}")


# Main
if len(sys.argv) > 1:
    recalcular(sys.argv[1])
else:
    # Lista todas planilhas pendentes
    planilhas = listar_planilhas()
    if not planilhas:
        print("Nenhuma planilha ativa encontrada.")
        sys.exit(0)

    print(f"\n{'ID':<25} {'Casa':<20} {'Status':<25} {'Valor Atual'}")
    print("-" * 85)
    for p in planilhas:
        vf = f"R$ {float(p.get('total_valor',0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")
        print(f"{p['id']:<25} {p.get('casa',''):<20} {p.get('status',''):<25} {vf}")

    print()
    pid = input("Cole o ID da planilha para recalcular (ou Enter para sair): ").strip()
    if pid:
        recalcular(pid)