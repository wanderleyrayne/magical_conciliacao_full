"""
teste_upload_planilha.py — Sobe uma planilha de teste para o PocketBase
Execute da raiz ou da pasta scripts: python teste_upload_planilha.py
"""
import sqlite3
import requests
import os
from pathlib import Path

# Tenta encontrar o banco em varios lugares
POSSIVEIS_DB = [
    Path(__file__).parent.parent / "data" / "conciliacao.db",  # raiz/data/
    Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
    Path(__file__).parent / "data" / "conciliacao.db",
]

DB_PATH = None
for p in POSSIVEIS_DB:
    if p.exists():
        DB_PATH = p
        print(f"Banco encontrado: {p}")
        break

if not DB_PATH:
    print("Banco nao encontrado. Caminhos tentados:")
    for p in POSSIVEIS_DB:
        print(f"  {p}")
    exit(1)

def get_cfg(chave, default=""):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS nuvem_config "
                     "(chave TEXT PRIMARY KEY, valor TEXT)")
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1",
            (chave,)).fetchone()
        return row[0] if row and row[0] else default

pb_url   = get_cfg("pb_url")
pb_email = get_cfg("pb_email")
pb_senha = get_cfg("pb_senha")

print(f"PB URL: {pb_url}")

if not pb_url:
    print("ERRO: pb_url nao configurado no banco!")
    exit(1)

# Autentica
resp = requests.post(
    f"{pb_url}/api/collections/_superusers/auth-with-password",
    json={"identity": pb_email, "password": pb_senha},
    timeout=20,
)
token   = resp.json()["token"]
headers = {"Authorization": f"Bearer {token}"}
print("Login PocketBase OK\n")

# Escolhe arquivo para upload
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
arquivo = filedialog.askopenfilename(
    title="Selecione a planilha para upload",
    filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")]
)
root.destroy()

if not arquivo:
    print("Nenhum arquivo selecionado.")
    exit(0)

print(f"Arquivo: {arquivo}")

# Casa
casas = [
    "CONTEMPORANEO","ESPACO SER","EVORA","LAGO","CHALE",
    "CHATEAU","CASA DO LAGO","VILLA FONTANA","OLEGARIO","MAGICAL","TESTE","TESTE2"
]
print("\nEscolha a casa:")
for i, c in enumerate(casas, 1):
    print(f"  {i}. {c}")
idx = int(input("Numero: ")) - 1
casa = casas[idx]

from datetime import datetime
agora = datetime.now().strftime("%d/%m/%Y %H:%M")

# Cria registro
resp2 = requests.post(
    f"{pb_url}/api/collections/planilhas/records",
    headers={**headers, "Content-Type": "application/json"},
    json={
        "casa":         casa,
        "nome_arquivo": Path(arquivo).name,
        "enviado_por":  "Teste Manual",
        "total_itens":  0,
        "total_valor":  0,
        "status":       "recebido",
        "recebido_em":  agora,
    },
    timeout=20,
)
pid = resp2.json().get("id")
print(f"\nRegistro criado: {pid}")

# Upload do arquivo
with open(arquivo, "rb") as f:
    conteudo = f.read()

resp3 = requests.patch(
    f"{pb_url}/api/collections/planilhas/records/{pid}",
    headers={"Authorization": f"Bearer {token}"},
    files={"arquivo": (Path(arquivo).name, conteudo,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    timeout=60,
)
print(f"Upload: {'OK' if resp3.status_code in (200,201) else 'ERRO ' + str(resp3.status_code)}")
print(f"\nPlanilha '{Path(arquivo).name}' enviada para casa '{casa}'!")
print(f"Acesse o Workflow no sistema para ver o card.")