"""
workflow_window.py — Workflow Kanban de Lancamento e Pagamento
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import threading
from datetime import datetime


COLUNAS = [
    ("recebido",             "Recebido",              "#fef9c3", "#854d0e"),
    ("em_lancamento",        "No ERP",                "#dbeafe", "#1e40af"),
    ("ag_aprov_operacional", "Ag. Aprov. Operacional","#fce7f3", "#9d174d"),
    ("cnab_pendente",        "Gerar CNAB",            "#d1fae5", "#065f46"),
    ("cnab_gerado",          "No Itau",               "#e0e7ff", "#3730a3"),
    ("ag_aprov_financeira",  "Ag. Aprov. Financeira", "#fff7ed", "#9a3412"),
    ("pago",                 "Pago",                  "#bbf7d0", "#14532d"),
]

BOTOES_POR_STATUS = {
    "recebido":             [("Assumir ERP",          "_assumir_lancamento")],
    "em_lancamento":        [("Concluir lancamento",  "_concluir_lancamento")],
    "ag_aprov_operacional": [],
    "cnab_pendente":        [("Gerar CNAB",           "_marcar_cnab_gerado")],
    "cnab_gerado":          [("Confirmar envio Itau", "_confirmar_envio")],
    "ag_aprov_financeira":  [],
    "pago":                 [],
}


class WorkflowWindow:
    POLL_INTERVAL = 60_000

    def __init__(self, master, db_path: str = None):
        if not db_path:
            try:
                from utils.paths import user_data_path
                db_path = str(user_data_path("data", "conciliacao.db"))
            except Exception:
                import os
                db_path = str(__import__('pathlib').Path(
                    os.environ.get("APPDATA", "")) /
                    "Magical_Conciliacao" / "data" / "conciliacao.db")

        self.db_path  = db_path
        self.cloud    = None
        self._poll_id = None
        self._sel     = None

        self.win = tk.Toplevel(master)
        self.win.title("Workflow — Lancamento e Pagamento")
        self.win.geometry("1350x700")
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._init_cloud()
        self._build_ui()
        self._load()

    def _get_cfg(self, chave, default=""):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS nuvem_config "
                             "(chave TEXT PRIMARY KEY, valor TEXT)")
                row = conn.execute(
                    "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1",
                    (chave,)).fetchone()
                return row[0] if row and row[0] else default
        except Exception:
            return default

    def _init_cloud(self):
        try:
            pb_url   = self._get_cfg("pb_url")
            pb_email = self._get_cfg("pb_email")
            pb_senha = self._get_cfg("pb_senha")
            if pb_url and pb_email and pb_senha:
                from cloud_sync import CloudSync
                self.cloud = CloudSync(pb_url, pb_email, pb_senha)
                print("[WORKFLOW] Cloud OK")
        except Exception as e:
            print(f"[WORKFLOW] cloud erro: {e}")

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.win, bg="#0f172a", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Workflow — Lancamento e Pagamento",
                 bg="#0f172a", fg="white",
                 font=("Arial", 12, "bold")).pack(side="left", padx=12)

        # Toolbar
        tb = tk.Frame(self.win, bg="#f8fafc", pady=4)
        tb.pack(fill="x", padx=8)
        ttk.Button(tb, text="Atualizar", command=self._load).pack(side="left")
        self.lbl_status = tk.Label(tb, text="Carregando...",
                                    fg="#64748b", bg="#f8fafc",
                                    font=("Arial", 9))
        self.lbl_status.pack(side="left", padx=8)

        # Rodape
        rod = tk.Frame(self.win, bg="#f1f5f9", pady=6, relief="ridge", bd=1)
        rod.pack(fill="x", side="bottom")
        self._rod_frame = tk.Frame(rod, bg="#f1f5f9")
        self._rod_frame.pack()
        tk.Label(self._rod_frame,
                 text="Selecione um card para ver as acoes",
                 fg="#94a3b8", bg="#f1f5f9",
                 font=("Arial", 9, "italic")).pack()

        # Board — frame principal com scroll horizontal
        board_outer = tk.Frame(self.win, bg="#e2e8f0")
        board_outer.pack(fill="both", expand=True, padx=4, pady=4)

        # Canvas para scroll horizontal
        self._cv = tk.Canvas(board_outer, bg="#e2e8f0", highlightthickness=0)
        hs = ttk.Scrollbar(board_outer, orient="horizontal",
                            command=self._cv.xview)
        self._cv.configure(xscrollcommand=hs.set)
        hs.pack(side="bottom", fill="x")
        self._cv.pack(fill="both", expand=True)

        # Frame interno onde ficam as colunas
        self._board = tk.Frame(self._cv, bg="#e2e8f0")
        self._board_id = self._cv.create_window(
            (0, 0), window=self._board, anchor="nw")

        self._board.bind("<Configure>", lambda e: self._cv.configure(
            scrollregion=self._cv.bbox("all")))
        self._cv.bind("<Configure>", lambda e: self._cv.itemconfig(
            self._board_id, height=e.height))

        # Cria colunas
        self._col_frames = {}
        self._col_counts = {}

        for status, label, bg, fg in COLUNAS:
            col = tk.Frame(self._board, bg=bg, width=180,
                           relief="solid", bd=1)
            col.pack(side="left", fill="y", padx=3, pady=4)
            col.pack_propagate(False)

            # Header coluna
            tk.Label(col, text=label, bg=bg, fg=fg,
                     font=("Arial", 9, "bold"),
                     pady=6, wraplength=165,
                     justify="center").pack(fill="x")

            count_lbl = tk.Label(col, text="", bg=bg, fg=fg,
                                  font=("Arial", 8))
            count_lbl.pack()

            sep = tk.Frame(col, bg=fg, height=2)
            sep.pack(fill="x", pady=(2, 4))

            # Area dos cards
            cards_area = tk.Frame(col, bg=bg)
            cards_area.pack(fill="both", expand=True, padx=4)

            self._col_frames[status] = cards_area
            self._col_counts[status] = count_lbl

    def _load(self):
        if not self.cloud:
            self.lbl_status.config(
                text="PocketBase nao configurado", fg="#b45309")
            return

        def _fetch():
            try:
                todas = self.cloud.listar_todas(limit=200)
                print(f"[WORKFLOW] Fetched {len(todas)} registros")
                for p in todas:
                    print(f"  {p.get('id')} | {p.get('casa')} | {p.get('status')}")
                self.win.after(0, lambda: self._render(todas))
            except Exception as e:
                print(f"[WORKFLOW] fetch erro: {e}")
                self.win.after(0, lambda: self.lbl_status.config(
                    text=f"Erro: {e}", fg="#dc2626"))

        threading.Thread(target=_fetch, daemon=True).start()

        if self._poll_id:
            self.win.after_cancel(self._poll_id)
        self._poll_id = self.win.after(self.POLL_INTERVAL, self._load)

    def _render(self, planilhas: list):
        # Limpa todas as colunas
        for frame in self._col_frames.values():
            for w in frame.winfo_children():
                w.destroy()

        status_validos = set(self._col_frames.keys())
        ativos = [p for p in planilhas if p.get("status") in status_validos]

        print(f"[WORKFLOW] Renderizando {len(ativos)} ativos de {len(planilhas)} total")

        # Ordena por recebido_em decrescente (mais recente primeiro)
        from datetime import datetime as _dt

        def _sort_key(p):
            try:
                return _dt.strptime(
                    str(p.get("recebido_em") or "")[:16], "%d/%m/%Y %H:%M")
            except Exception:
                return _dt.min

        ativos.sort(key=_sort_key, reverse=True)

        contagem = {s: 0 for s in status_validos}
        for p in ativos:
            st = p.get("status", "recebido")
            contagem[st] = contagem.get(st, 0) + 1
            self._criar_card(p)

        for status, count_lbl in self._col_counts.items():
            n = contagem.get(status, 0)
            count_lbl.config(text=f"{n}" if n > 0 else "")

        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_status.config(
            text=f"{len(ativos)} ativo(s) · {now}", fg="#64748b")

        # Força atualização visual
        self.win.update_idletasks()

    def _criar_card(self, p: dict):
        status = p.get("status", "recebido")
        frame  = self._col_frames.get(status)
        if not frame:
            return

        fg_acc = "#1e293b"
        for s, lbl, bg, fg in COLUNAS:
            if s == status:
                fg_acc = fg
                break

        card = tk.Frame(frame, bg="white", relief="solid", bd=1, cursor="hand2")
        card.pack(fill="x", pady=3, padx=2)

        tk.Frame(card, bg=fg_acc, height=3).pack(fill="x")

        body = tk.Frame(card, bg="white", padx=6, pady=6)
        body.pack(fill="x")

        # Mostra só casa e nome do arquivo
        tk.Label(body, text=p.get("casa", "?"),
                 bg="white", fg="#0f172a",
                 font=("Arial", 9, "bold"), anchor="w").pack(fill="x")

        nome = str(p.get("nome_arquivo", "") or "").replace(".xlsx","").replace(".xls","")
        if nome:
            tk.Label(body, text=nome[:28],
                     bg="white", fg="#64748b",
                     font=("Arial", 8), anchor="w").pack(fill="x")

        tk.Label(body, text="Clique para detalhes",
                 bg="white", fg="#cbd5e1",
                 font=("Arial", 7, "italic"), anchor="w").pack(fill="x")

        pid = p["id"]
        def on_click(e, i=pid, s=status, data=p):
            self._selecionar(i, s)
            self._mostrar_detalhes(data)

        for w in [card, body] + list(body.winfo_children()):
            try:
                w.bind("<Button-1>", on_click)
            except Exception:
                pass

        print(f"[WORKFLOW] Card criado: {p.get('casa')} | {status}")

    def _mostrar_detalhes(self, p: dict):
        """Popup com detalhes completos do card."""
        status = p.get("status", "")
        status_label = {s: l for s, l, *_ in COLUNAS}.get(status, status)

        pop = tk.Toplevel(self.win)
        pop.title(f"Detalhes — {p.get('casa','')}")
        pop.geometry("380x320")
        pop.resizable(False, False)
        pop.grab_set()

        # Header
        fg_acc = "#1e293b"
        for s, lbl, bg, fg in COLUNAS:
            if s == status:
                fg_acc = fg
                bg_acc = bg
                break
        else:
            bg_acc = "#f8fafc"

        hdr = tk.Frame(pop, bg=fg_acc, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=p.get("casa","?"),
                 bg=fg_acc, fg="white",
                 font=("Arial", 12, "bold")).pack()
        tk.Label(hdr, text=status_label,
                 bg=fg_acc, fg="white",
                 font=("Arial", 9)).pack()

        # Detalhes
        body = tk.Frame(pop, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        def row(label, valor):
            f = tk.Frame(body)
            f.pack(fill="x", pady=2)
            tk.Label(f, text=label, fg="#64748b",
                     font=("Arial", 9), width=14, anchor="w").pack(side="left")
            tk.Label(f, text=str(valor or "—"), fg="#0f172a",
                     font=("Arial", 9, "bold"), anchor="w").pack(side="left")

        row("Recebido em:",  p.get("recebido_em", "—"))
        row("Planilha:",     str(p.get("nome_arquivo",""))[:35])
        row("Itens:",        p.get("total_itens", 0))
        row("Valor Total:",  self._brl(p.get("total_valor", 0)))
        row("Enviado por:",  p.get("enviado_por", "—"))
        row("Lancado por:",  p.get("lancado_por", "—"))
        row("CNAB por:",     p.get("cnab_gerado_por", "—"))
        row("Aprovado por:", p.get("aprovado_por", "—"))

        if p.get("motivo_reprovacao"):
            row("Motivo:", p.get("motivo_reprovacao"))

        ttk.Button(pop, text="Fechar", command=pop.destroy).pack(pady=(0,10))

    def _selecionar(self, pid, status):
        self._sel = (pid, status)
        self._atualizar_acoes(status)

    def _atualizar_acoes(self, status):
        for w in self._rod_frame.winfo_children():
            w.destroy()

        labels = {s: l for s, l, *_ in COLUNAS}
        tk.Label(self._rod_frame,
                 text=f"Selecionado: {labels.get(status, status)}",
                 fg="#475569", bg="#f1f5f9",
                 font=("Arial", 9)).pack(side="left", padx=10)

        botoes = BOTOES_POR_STATUS.get(status, [])
        if not botoes:
            tk.Label(self._rod_frame,
                     text="Aguardando aprovacao via WhatsApp",
                     fg="#94a3b8", bg="#f1f5f9",
                     font=("Arial", 9, "italic")).pack(side="left", padx=6)
        else:
            for lbl, metodo in botoes:
                ttk.Button(self._rod_frame, text=lbl,
                           command=getattr(self, metodo)).pack(
                    side="left", padx=6)

        ttk.Separator(self._rod_frame, orient="vertical").pack(
            side="left", fill="y", padx=8)
        ttk.Button(self._rod_frame, text="Fechar",
                   command=self._on_close).pack(side="left")

    def _get_sel(self):
        if not self._sel:
            messagebox.showwarning("Workflow",
                "Selecione um card primeiro.", parent=self.win)
            return None, None
        return self._sel

    def _get_card_vals(self, pid):
        try:
            todas = self.cloud.listar_todas(limit=200)
            return next((p for p in todas if p["id"] == pid), {})
        except Exception:
            return {}

    def _assumir_lancamento(self):
        pid, status = self._get_sel()
        if not pid:
            return
        meu_nome = self._get_cfg("meu_nome", "Usuario")
        vals = self._get_card_vals(pid)
        casa = vals.get("casa", "?")

        if not messagebox.askyesno("Assumir ERP",
            f"Assumir lancamento de '{casa}'?\n\n"
            f"O arquivo sera baixado e aberto no ERP.",
            parent=self.win):
            return

        def _do():
            try:
                self.cloud.iniciar_lancamento(pid, meu_nome)
                import tempfile, os
                destino = os.path.join(tempfile.gettempdir(), "magical_pendencias")
                caminho = self.cloud.download_arquivo(pid, destino)
                self.win.after(0, lambda: self._abrir_erp(pid, casa, caminho))
            except Exception as e:
                self.win.after(0, lambda: messagebox.showerror(
                    "Erro", str(e), parent=self.win))

        threading.Thread(target=_do, daemon=True).start()

    def _abrir_erp(self, pid, casa, caminho):
        self._load()
        if not caminho:
            messagebox.showwarning("Arquivo",
                "Arquivo nao encontrado no PocketBase.",
                parent=self.win)
        try:
            from ui.erp_lancamento_window import ErpLancamentoWindow
            erp = ErpLancamentoWindow(self.win)
            if hasattr(erp, 'partner_var'):
                from core.partner_rules import PARTNERS
                for p in PARTNERS:
                    if p.get("partner_name","").upper() == casa.upper():
                        erp.partner_var.set(p["partner_name"])
                        if hasattr(erp, '_on_partner_selected'):
                            erp._on_partner_selected()
                        break
            if caminho and hasattr(erp, '_load_file_from_path'):
                erp._load_file_from_path(caminho)
            elif caminho and hasattr(erp, '_load_and_validate'):
                erp.file_path = caminho
                erp._load_and_validate()
            erp._pendencia_id   = pid
            erp._pendencia_casa = casa
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir ERP: {e}",
                                  parent=self.win)

    def _concluir_lancamento(self):
        pid, status = self._get_sel()
        if not pid:
            return
        meu_nome = self._get_cfg("meu_nome", "Usuario")
        vals = self._get_card_vals(pid)
        casa = vals.get("casa", "?")

        if not messagebox.askyesno("Concluir lancamento",
            f"Confirmar lancamento de '{casa}' concluido no ERP?\n\n"
            f"Diretor Operacional sera notificado para aprovacao.",
            parent=self.win):
            return

        def _do():
            try:
                self.cloud.atualizar_status(
                    pid, "ag_aprov_operacional", lancado_por=meu_nome)
                self._notificar_grupo_casa(casa,
                    f"*Magical - Lancamento Concluido*\n\n"
                    f"Casa: {casa}\n"
                    f"Lancado por: {meu_nome}\n\n"
                    f"Para aprovar responda:\n"
                    f"APROVAR OPERACIONAL {casa.upper()}\n\n"
                    f"Para reprovar responda:\n"
                    f"REPROVAR OPERACIONAL {casa.upper()} [motivo]")
                self.win.after(0, self._load)
            except Exception as e:
                self.win.after(0, lambda: messagebox.showerror(
                    "Erro", str(e), parent=self.win))

        threading.Thread(target=_do, daemon=True).start()

    def _marcar_cnab_gerado(self):
        pid, status = self._get_sel()
        if not pid:
            return
        meu_nome = self._get_cfg("meu_nome", "Usuario")
        vals = self._get_card_vals(pid)
        casa = vals.get("casa", "?")
        valor = self._brl(vals.get("total_valor", 0))

        if not messagebox.askyesno("Gerar CNAB",
            f"Gerar CNAB 240 para '{casa}'?\nValor: {valor}",
            parent=self.win):
            return

        self.lbl_status.config(text="Gerando CNAB...", fg="#2563eb")

        def _do():
            try:
                import tempfile, os
                from pathlib import Path

                destino = os.path.join(tempfile.gettempdir(), "magical_pendencias")
                caminho = self.cloud.download_arquivo(pid, destino)
                if not caminho:
                    self.win.after(0, lambda: messagebox.showerror(
                        "Erro", "Arquivo nao encontrado.", parent=self.win))
                    return

                import pandas as pd, re as _re
                try:
                    df = pd.read_excel(caminho, sheet_name="Despesas", header=None)
                except Exception:
                    df = pd.read_excel(caminho, header=None)

                header_row = 0
                for i in range(min(10, len(df))):
                    if any("VALOR" in str(v).upper() for v in df.iloc[i].values):
                        header_row = i
                        break
                df.columns = df.iloc[header_row].astype(str).str.strip()
                df = df.iloc[header_row+1:].reset_index(drop=True).dropna(how="all")

                col_map = {}
                for col in df.columns:
                    c = str(col).upper()
                    if "VALOR" in c and "VALOR" not in col_map.values():
                        col_map[col] = "VALOR"
                    elif "FAVORECIDO" in c:
                        col_map[col] = "FAVORECIDO"
                    elif "PIX" in c and "CHAVE" in c:
                        col_map[col] = "PIX_CHAVE"
                    elif "CPF" in c or "CNPJ" in c:
                        col_map[col] = "CPF_CNPJ"
                    elif "FORMA" in c:
                        col_map[col] = "FORMA_PGTO"
                df = df.rename(columns=col_map)

                from core.cnab_itau import (
                    GeradorCNAB240,
                    PIX_CHAVE_CPF, PIX_CHAVE_CNPJ,
                    PIX_CHAVE_EMAIL, PIX_CHAVE_EVP,
                )

                pagamentos = []
                for _, row in df.iterrows():
                    try:
                        v = str(row.get("VALOR",0)).replace("R$","").replace(" ","")
                        if "," in v:
                            v = v.replace(".","").replace(",",".")
                        vp = abs(float(v))
                        if vp <= 0:
                            continue
                    except Exception:
                        continue

                    forma = str(row.get("FORMA_PGTO","PIX") or "PIX").upper()
                    forma_cnab = "TED" if "TED" in forma else "CC" if "CC" in forma else "PIX"

                    chave = str(row.get("PIX_CHAVE","") or row.get("CPF_CNPJ","") or "")
                    if chave in ("nan","None",""):
                        chave = ""

                    cpf = _re.sub(r"\D","", chave)
                    if len(cpf) == 11:
                        tipo = PIX_CHAVE_CPF
                    elif len(cpf) == 14:
                        tipo = PIX_CHAVE_CNPJ
                    elif "@" in chave:
                        tipo = PIX_CHAVE_EMAIL
                        cpf  = chave
                    elif chave:
                        tipo = PIX_CHAVE_EVP
                        cpf  = chave
                    else:
                        if forma_cnab == "PIX":
                            continue
                        tipo = PIX_CHAVE_CPF

                    pagamentos.append({
                        "nome": str(row.get("FAVORECIDO","FAVORECIDO") or "FAVORECIDO")[:30],
                        "cpf_cnpj": cpf,
                        "pix_chave": chave,
                        "pix_tipo_chave": tipo,
                        "valor": vp,
                        "forma_pgto": forma_cnab,
                        "banco_favorecido": "341",
                        "agencia": "", "conta": "", "dac": "0", "data": "",
                    })

                if not pagamentos:
                    self.win.after(0, lambda: messagebox.showwarning(
                        "CNAB", "Nenhum pagamento valido encontrado.",
                        parent=self.win))
                    return

                downloads = Path.home() / "Downloads" / "CNAB" / casa
                downloads.mkdir(parents=True, exist_ok=True)

                config = {"cnpj":"00000000000000","agencia":"00000",
                          "conta":"000000000","dac":"0","nome":"RAYNE TECNOLOGIA"}
                g = GeradorCNAB240(config)
                for p in pagamentos:
                    g.adicionar(p)
                arquivos = g.gerar(output_dir=str(downloads))

                vt = float(vals.get("total_valor", 0))
                self.cloud.confirmar_cnab_gerado(pid, casa, meu_nome, vt)

                self._notificar_grupo_casa_botoes(
                    casa=casa,
                    titulo="Magical — Lote de Pagamento no Itaú",
                    corpo=(
                        f"Casa: {casa}\nGerado por: {meu_nome}\n"
                        f"Total: {self._brl(vt)}\nPagamentos: {len(pagamentos)}\n\n"
                        f"Deseja aprovar o pagamento?"
                    ),
                    botoes=[
                        {"id": f"sim_fin_{casa.lower()}", "text": "✅ Sim"},
                        {"id": f"nao_fin_{casa.lower()}", "text": "❌ Não"},
                    ]
                )

                import subprocess
                subprocess.Popen(f'explorer "{downloads}"')

                resumo = []
                if arquivos.get("pix"):
                    resumo.append(f"PIX: {Path(arquivos['pix']).name}")
                if arquivos.get("ted_cc"):
                    resumo.append(f"TED/CC: {Path(arquivos['ted_cc']).name}")

                self.win.after(0, lambda r="\n".join(resumo): (
                    self._load(),
                    messagebox.showinfo("CNAB Gerado",
                        f"Arquivos em: Downloads/CNAB/{casa}/\n\n{r}\n\n"
                        f"Diretor Financeiro notificado.",
                        parent=self.win)
                ))
            except Exception as e:
                err = str(e)
                self.win.after(0, lambda m=err: messagebox.showerror(
                    "Erro", m, parent=self.win))

        threading.Thread(target=_do, daemon=True).start()

    def _confirmar_envio(self):
        pid, status = self._get_sel()
        if not pid:
            return
        meu_nome = self._get_cfg("meu_nome", "Usuario")
        vals = self._get_card_vals(pid)
        casa = vals.get("casa", "?")

        if not messagebox.askyesno("Confirmar envio",
            f"Confirmar que o CNAB de '{casa}' foi importado no Itau?",
            parent=self.win):
            return

        def _do():
            try:
                self.cloud.confirmar_cnab_enviado(pid, casa, meu_nome)
                self.win.after(0, self._load)
            except Exception as e:
                self.win.after(0, lambda: messagebox.showerror(
                    "Erro", str(e), parent=self.win))

        threading.Thread(target=_do, daemon=True).start()

    def _notificar_grupo_casa(self, casa, msg):
        try:
            evo_url   = self._get_cfg("evo_url")
            evo_key   = self._get_cfg("evo_key")
            instancia = self._get_cfg("evo_instancia", "wanderley")
            chave_cfg = f"grupo_{casa.lower().replace(' ','_')}"
            grupo_id  = self._get_cfg(chave_cfg)
            if not evo_url or not grupo_id:
                return
            from notificador import Notificador
            n = Notificador(evo_url, evo_key, instancia)
            if n.status_instancia().get("conectado"):
                n.enviar_grupo(grupo_id, msg)
        except Exception:
            pass

    def _brl(self, v):
        try:
            return (f"R$ {float(v or 0):,.2f}"
                    .replace(",","X").replace(".",",").replace("X","."))
        except Exception:
            return "R$ 0,00"

    def _on_close(self):
        if self._poll_id:
            self.win.after_cancel(self._poll_id)
        self.win.destroy()