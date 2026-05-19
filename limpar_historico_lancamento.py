"""
limpar_historico_lancamento.py — Limpa historico para permitir relancamento
Funciona tanto no ambiente de desenvolvimento quanto no .exe
Coloque na raiz do projeto e execute: python limpar_historico_lancamento.py
"""
import sqlite3, os, sys
from datetime import date
from pathlib import Path

def encontrar_banco():
    candidatos = [
        Path("data/conciliacao.db"),
        Path(__file__).parent / "data" / "conciliacao.db",
        Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
        Path.home() / "AppData" / "Roaming" / "Magical_Conciliacao" / "data" / "conciliacao.db",
        Path.home() / "AppData" / "Local" / "Magical_Conciliacao" / "data" / "conciliacao.db",
    ]
    for c in candidatos:
        if c.exists():
            return c
    return None

db_path = encontrar_banco()

if not db_path:
    print("ERRO: Banco de dados nao encontrado!")
    caminho_manual = input("Cole o caminho completo do banco: ").strip().strip('"')
    db_path = Path(caminho_manual)
    if not db_path.exists():
        print("Arquivo nao encontrado.")
        input("Pressione Enter para sair...")
        sys.exit(1)

print(f"Banco: {db_path}\n")

with sqlite3.connect(str(db_path)) as conn:
    batches = conn.execute("""
        SELECT b.id, b.partner_name, b.file_name, b.created_at,
               COUNT(i.id) as total,
               SUM(CASE WHEN i.status='LANCADO' THEN 1 ELSE 0 END) as lancados,
               SUM(CASE WHEN i.status='ERRO_API' THEN 1 ELSE 0 END) as erros
        FROM erp_launch_batches b
        LEFT JOIN erp_launch_items i ON i.batch_id = b.id
        WHERE b.dry_run = 0
        GROUP BY b.id
        ORDER BY b.id DESC
        LIMIT 20
    """).fetchall()

if not batches:
    print("Nenhum lote encontrado.")
    input("Pressione Enter para sair...")
    sys.exit(0)

print(f"{'ID':<5} {'Parceiro':<22} {'Arquivo':<33} {'Data':<17} {'Total':>6} {'OK':>5} {'Erro':>5}")
print("-"*95)
for b in batches:
    print(f"{b[0]:<5} {str(b[1]):<22} {str(b[2])[:32]:<33} {str(b[3])[:16]:<17} {b[4]:>6} {b[5] or 0:>5} {b[6] or 0:>5}")

print()
print("Opcoes:")
print("  [1] Limpar UM lote (por ID)")
print("  [2] Limpar TODOS os lotes de um parceiro")
print("  [3] Limpar lotes de HOJE de um parceiro")
print("  [4] Sair")

op = input("\nEscolha: ").strip()

with sqlite3.connect(str(db_path)) as conn:
    if op == "1":
        bid = input("ID do lote: ").strip()
        n = conn.execute("SELECT COUNT(*) FROM erp_launch_items WHERE batch_id=?", (bid,)).fetchone()[0]
        if input(f"Deletar {n} itens do lote {bid}? [s/N] ").strip().lower() == "s":
            conn.execute("DELETE FROM erp_launch_items WHERE batch_id=?", (bid,))
            conn.execute("DELETE FROM erp_launch_batches WHERE id=?", (bid,))
            conn.commit()
            print(f"OK Lote {bid} removido!")

    elif op == "2":
        parceiro = input("Nome do parceiro: ").strip()
        n = conn.execute("""
            SELECT COUNT(*) FROM erp_launch_items i
            JOIN erp_launch_batches b ON i.batch_id=b.id
            WHERE b.partner_name=? AND b.dry_run=0
        """, (parceiro,)).fetchone()[0]
        if input(f"Deletar {n} itens de '{parceiro}'? [s/N] ").strip().lower() == "s":
            ids = [r[0] for r in conn.execute(
                "SELECT id FROM erp_launch_batches WHERE partner_name=? AND dry_run=0",
                (parceiro,)).fetchall()]
            for bid in ids:
                conn.execute("DELETE FROM erp_launch_items WHERE batch_id=?", (bid,))
                conn.execute("DELETE FROM erp_launch_batches WHERE id=?", (bid,))
            conn.commit()
            print(f"OK {len(ids)} lote(s) removidos!")

    elif op == "3":
        parceiro = input("Nome do parceiro: ").strip()
        hoje = date.today().strftime("%Y-%m-%d")
        n = conn.execute("""
            SELECT COUNT(*) FROM erp_launch_items i
            JOIN erp_launch_batches b ON i.batch_id=b.id
            WHERE b.partner_name=? AND date(b.created_at)=? AND b.dry_run=0
        """, (parceiro, hoje)).fetchone()[0]
        if input(f"Deletar {n} itens de hoje de '{parceiro}'? [s/N] ").strip().lower() == "s":
            ids = [r[0] for r in conn.execute("""
                SELECT id FROM erp_launch_batches
                WHERE partner_name=? AND date(created_at)=? AND dry_run=0
            """, (parceiro, hoje)).fetchall()]
            for bid in ids:
                conn.execute("DELETE FROM erp_launch_items WHERE batch_id=?", (bid,))
                conn.execute("DELETE FROM erp_launch_batches WHERE id=?", (bid,))
            conn.commit()
            print(f"OK {len(ids)} lote(s) de hoje removidos!")

    else:
        print("Saindo.")

print("\nCarregue a planilha novamente - todas as linhas aparecerão como Pronto!")
input("Pressione Enter para sair...")