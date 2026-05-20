"""
gerar_cnab_direto.py — Gera CNAB 240 direto de uma planilha sem passar pelo Workflow
Execute da raiz: python gerar_cnab_direto.py
"""
import sys, os, re
from pathlib import Path
from datetime import date as _date

# ── Imports do projeto ───────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from core.cnab_itau import (
    GeradorCNAB240,
    PIX_CHAVE_CPF, PIX_CHAVE_CNPJ,
    PIX_CHAVE_EMAIL, PIX_CHAVE_EVP,
    PIX_CHAVE_CELULAR, _normalizar_chave_pix,
)
from core.partner_rules import PARTNERS
import pandas as pd
import sqlite3

def get_banco_dados(parceiro):
    """Busca dados bancarios do parceiro no banco local."""
    try:
        db = Path("data/conciliacao.db")
        if not db.exists():
            db = Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao/data/conciliacao.db"
        with sqlite3.connect(str(db)) as conn:
            row = conn.execute(
                "SELECT dados FROM contas_bancarias WHERE parceiro=? LIMIT 1",
                (parceiro,)
            ).fetchone()
            if row and row[0]:
                import json
                return json.loads(row[0])
    except Exception:
        pass
    return {}

def get_cnpj(parceiro):
    for p in PARTNERS:
        if p["partner_name"].upper() == parceiro.upper():
            return re.sub(r'\D', '', p.get("cnpj",""))
    return "00000000000000"

# ── Interface ────────────────────────────────────────────────────────────────
print("=" * 55)
print("  GERADOR CNAB 240 — Sem Workflow")
print("=" * 55)

# Lista parceiros disponíveis
print("\nParceiros disponíveis:")
for i, p in enumerate(PARTNERS):
    print(f"  [{i}] {p['partner_name']}")

idx = input("\nNumero do parceiro: ").strip()
try:
    parceiro = PARTNERS[int(idx)]["partner_name"]
except Exception:
    parceiro = input("Nome do parceiro: ").strip()

print(f"\nParceiro: {parceiro}")

# Planilha
planilha = input("Caminho da planilha (ou Enter para abrir dialogo): ").strip().strip('"')
if not planilha:
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        planilha = filedialog.askopenfilename(
            title="Selecionar planilha",
            filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")]
        )
        root.destroy()
    except Exception:
        planilha = input("Cole o caminho completo da planilha: ").strip().strip('"')

if not planilha or not Path(planilha).exists():
    print("ERRO: Planilha não encontrada.")
    input("Enter para sair...")
    sys.exit(1)

print(f"Planilha: {Path(planilha).name}")

# Lê planilha
print("\nLendo planilha...")
try:
    try:
        df = pd.read_excel(planilha, sheet_name="Despesas", header=None)
    except Exception:
        df = pd.read_excel(planilha, header=None)

    # Encontra header
    header_row = 0
    for i in range(min(10, len(df))):
        if any("VALOR" in str(v).upper() for v in df.iloc[i].values):
            header_row = i
            break

    df.columns = df.iloc[header_row].astype(str).str.strip()
    df = df.iloc[header_row+1:].reset_index(drop=True).dropna(how="all")

    # Mapeia colunas
    col_map = {}
    for col in df.columns:
        c = str(col).upper().strip()
        if "VALOR" in c and "VALOR" not in col_map.values():
            col_map[col] = "VALOR"
        elif "FAVORECIDO" in c:
            col_map[col] = "FAVORECIDO"
        elif "PIX" in c and "CHAVE" in c:
            col_map[col] = "PIX_CHAVE"
        elif "FORMA" in c:
            col_map[col] = "FORMA_PGTO"
        elif "BANCO" in c and c == "BANCO":
            col_map[col] = "BANCO"
        elif "AG" in c and ("CIA" in c or "NCIA" in c):
            col_map[col] = "AGENCIA"
        elif c == "CONTA":
            col_map[col] = "CONTA"
        elif "DATA" in c and "PAGAMENTO" in c and "DATA" not in col_map.values():
            col_map[col] = "DATA"
        elif "DATA" in c and "DATA" not in col_map.values():
            col_map[col] = "DATA"
    df = df.rename(columns=col_map)

    print(f"Colunas encontradas: {list(df.columns)}")

except Exception as e:
    print(f"ERRO ao ler planilha: {e}")
    input("Enter para sair...")
    sys.exit(1)

# Filtro de data
hoje = _date.today()
print(f"\nData de hoje: {hoje.strftime('%d/%m/%Y')}")
filtrar = input("Filtrar apenas pagamentos de hoje? [S/n]: ").strip().lower()

if filtrar != 'n' and "DATA" in df.columns:
    antes = len(df)
    def eh_hoje(v):
        try:
            dt = pd.to_datetime(str(v).strip(), dayfirst=True, errors="coerce")
            if pd.isna(dt):
                return True
            return dt.date() == hoje
        except Exception:
            return True
    df = df[df["DATA"].apply(eh_hoje)].reset_index(drop=True)
    print(f"Linhas filtradas: {antes} → {len(df)} (hoje)")

# Processa pagamentos
print("\nProcessando pagamentos...")
pagamentos = []

for _, row in df.iterrows():
    try:
        v = str(row.get("VALOR", 0) or "0").strip()
        v = v.replace("R$","").replace(" ","")
        if v.lower() in ("nan","none",""):
            continue
        if "," in v and "." in v:
            v = v.replace(".","").replace(",",".")
        elif "," in v:
            v = v.replace(",",".")
        vp = abs(float(v))
        if vp <= 0:
            continue
    except Exception:
        continue

    forma_raw   = str(row.get("FORMA_PGTO","") or "").strip().upper()
    banco_col   = str(row.get("BANCO","") or "").strip()
    agencia_col = str(row.get("AGENCIA","") or "").strip()
    conta_col   = str(row.get("CONTA","") or "").strip()

    banco_num   = re.sub(r"\D","", banco_col)
    agencia_num = re.sub(r"\D","", agencia_col)

    if "-" in conta_col:
        partes    = conta_col.split("-")
        conta_num = re.sub(r"\D","", partes[0])
        dac_num   = re.sub(r"\D","", partes[-1]) if len(partes)>1 else "0"
    else:
        conta_num = re.sub(r"\D","", conta_col)
        dac_num   = "0"

    tem_conta   = bool(conta_num and conta_num not in ("0",""))
    chave       = str(row.get("PIX_CHAVE","") or "").strip()
    if chave in ("nan","None","0",""):
        chave = ""
    eh_qrcode   = len(chave) > 40
    eh_deposito = any(x in forma_raw for x in ("TED","DOC","DEPOSIT","TRANSFER","CC"))

    if tem_conta and eh_deposito:
        if banco_num in ("341","409") or "ITAU" in banco_col.upper():
            banco_num  = banco_num or "341"
            forma_cnab = "CC"
        else:
            forma_cnab = "TED"
        chave = ""
    elif chave:
        forma_cnab = "PIX"
    elif tem_conta:
        if banco_num in ("341","409") or "ITAU" in banco_col.upper():
            banco_num  = banco_num or "341"
            forma_cnab = "CC"
        else:
            forma_cnab = "TED"
    else:
        continue

    cpf = re.sub(r"\D","", chave)
    if not chave:
        tipo = PIX_CHAVE_CPF; cpf = ""
    elif eh_qrcode or "br.gov.bcb.pix" in chave.lower():
        tipo = PIX_CHAVE_EVP; cpf = chave
    elif "@" in chave:
        tipo = PIX_CHAVE_EMAIL; cpf = chave
    elif len(cpf) == 14:
        tipo = PIX_CHAVE_CNPJ
    elif len(cpf) in (10,11):
        tipo = PIX_CHAVE_CELULAR
    elif len(cpf) == 11:
        tipo = PIX_CHAVE_CPF
    else:
        tipo = PIX_CHAVE_EVP; cpf = chave

    data_pgto = str(row.get("DATA","") or "").strip()
    if not data_pgto or data_pgto in ("nan","None",""):
        data_pgto = hoje.strftime("%Y-%m-%d")
    else:
        try:
            data_pgto = pd.to_datetime(data_pgto, dayfirst=True).strftime("%Y-%m-%d")
        except Exception:
            data_pgto = hoje.strftime("%Y-%m-%d")

    chave_norm = _normalizar_chave_pix(chave, tipo) if chave else ""
    cpf_norm   = re.sub(r"[^0-9]", "", chave) if tipo in ("01","02") else cpf

    pagamentos.append({
        "nome":             str(row.get("FAVORECIDO","FAVORECIDO") or "FAVORECIDO")[:30],
        "cpf_cnpj":         cpf_norm,
        "pix_chave":        chave_norm,
        "pix_tipo_chave":   tipo,
        "valor":            vp,
        "forma_pgto":       forma_cnab,
        "banco_favorecido": banco_num or "341",
        "agencia":          agencia_num,
        "conta":            conta_num,
        "dac":              dac_num,
        "data":             data_pgto,
    })

if not pagamentos:
    print("ERRO: Nenhum pagamento válido encontrado.")
    input("Enter para sair...")
    sys.exit(1)

total = sum(p["valor"] for p in pagamentos)
total_fmt = f"R$ {total:,.2f}".replace(",","X").replace(".",",").replace("X",".")
print(f"\n{len(pagamentos)} pagamentos encontrados | Total: {total_fmt}")

# Conta bancária do parceiro
conta_dados = get_banco_dados(parceiro)
cnpj        = get_cnpj(parceiro)
agencia     = conta_dados.get("agencia","")
conta_num   = conta_dados.get("conta","")
dac         = conta_dados.get("dac","0")

if not agencia or not conta_num:
    print(f"\n⚠️  Dados bancários não encontrados para '{parceiro}'")
    agencia  = input("Agência (ex: 02971): ").strip()
    conta_num= input("Conta (ex: 98870): ").strip()
    dac      = input("DAC (ex: 0): ").strip() or "0"

conta_limpa = re.sub(r"[^0-9]","", conta_num)
if not dac or dac=="0" and "-" in conta_num:
    partes      = conta_num.split("-")
    conta_limpa = re.sub(r"\D","", partes[0])
    dac         = re.sub(r"\D","", partes[-1]) if len(partes)>1 else "0"

# Gera CNAB
config = {
    "cnpj":    cnpj,
    "agencia": agencia,
    "conta":   conta_limpa,
    "dac":     dac,
    "nome":    parceiro.upper()[:30],
}

print(f"\nConfig bancária: agencia={agencia} conta={conta_limpa} dac={dac} cnpj={cnpj}")

g = GeradorCNAB240(config)
for p in pagamentos:
    g.adicionar(p)

# Salva
downloads = Path.home() / "Downloads" / "CNAB" / parceiro
downloads.mkdir(parents=True, exist_ok=True)

arquivos = g.gerar(output_dir=str(downloads))

print(f"\n✅ CNAB gerado em: {downloads}")
for tipo, path in arquivos.items():
    if path:
        print(f"   {tipo}: {Path(path).name}")

import subprocess
subprocess.Popen(f'explorer "{downloads}"')

input("\nPressione Enter para sair...")