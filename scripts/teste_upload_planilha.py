"""
teste_upload_planilha.py — Testa upload de planilha para o PocketBase
Execute: python teste_upload_planilha.py
"""
import sqlite3
from pathlib import Path
from tkinter.filedialog import askopenfilename
import tkinter as tk

DB_PATH = Path("data") / "conciliacao.db"

def get_cfg(chave, default=""):
    with sqlite3.connect(str(DB_PATH)) as conn:
        row = conn.execute(
            "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
        ).fetchone()
        return row[0] if row and row[0] else default

pb_url   = get_cfg("pb_url")
pb_email = get_cfg("pb_email")
pb_senha = get_cfg("pb_senha")

# Seleciona arquivo via dialogo
root = tk.Tk()
root.withdraw()
arquivo_path = askopenfilename(
    title="Selecione a planilha para enviar",
    filetypes=[("Excel", "*.xlsx *.xls"), ("Todos", "*.*")]
)
root.destroy()

if not arquivo_path:
    print("Nenhum arquivo selecionado.")
    exit()

print(f"Arquivo: {arquivo_path}")
nome = Path(arquivo_path).name

from cloud_sync import CloudSync
cs = CloudSync(pb_url, pb_email, pb_senha)

print("\n1. Salvando no PocketBase com upload...")
pid = cs.salvar_planilha_recebida(
    casa         = "CHATEAU",
    nome_arquivo = nome,
    enviado_por  = "Gerente Chateau",
    total_itens  = 10,
    valor_total  = 35966.55,
    arquivo_path = arquivo_path,
)
print(f"   ID: {pid}")

if pid:
    print("\n2. Testando download...")
    import tempfile, os
    destino = os.path.join(tempfile.gettempdir(), "magical_test")
    caminho = cs.download_arquivo(pid, destino)
    print(f"   Baixado em: {caminho}")

    print("\nOK! Agora abra Pendencias e clique em 'Assumir lancamento ERP'")
else:
    print("ERRO ao salvar planilha")