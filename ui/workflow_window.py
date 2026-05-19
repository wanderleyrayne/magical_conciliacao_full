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
        """Popup com detalhes completos do card + botoes de avanco/retrocesso."""
        status = p.get("status", "")
        pid    = p.get("id", "")

        # Ordem das colunas para navegacao
        ordem  = [c[0] for c in COLUNAS]
        idx    = ordem.index(status) if status in ordem else -1

        status_labels = {s: l for s, l, *_ in COLUNAS}
        status_label  = status_labels.get(status, status)

        pop = tk.Toplevel(self.win)
        pop.title(f"Detalhes — {p.get('casa','')}")
        pop.geometry("400x400")
        pop.resizable(False, False)
        pop.grab_set()

        # Header colorido
        fg_acc = "#1e293b"
        for s, lbl, bg, fg in COLUNAS:
            if s == status:
                fg_acc = fg
                break

        hdr = tk.Frame(pop, bg=fg_acc, pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text=p.get("casa","?"),
                 bg=fg_acc, fg="white",
                 font=("Arial", 12, "bold")).pack()
        tk.Label(hdr, text=status_label,
                 bg=fg_acc, fg="white",
                 font=("Arial", 9)).pack()

        # Detalhes
        body = tk.Frame(pop, padx=16, pady=10)
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

        # Separador
        ttk.Separator(pop, orient="horizontal").pack(fill="x", padx=16, pady=6)

        # Botoes de navegacao manual
        nav_frame = tk.Frame(pop, padx=16, pady=4)
        nav_frame.pack(fill="x")

        tk.Label(nav_frame, text="Mover card manualmente:",
                 fg="#64748b", font=("Arial", 8)).pack(anchor="w", pady=(0,4))

        btn_frame = tk.Frame(nav_frame)
        btn_frame.pack(fill="x")

        meu_nome = self._get_cfg("meu_nome", "Usuario")

        def mover(novo_status):
            if not self.cloud:
                return
            try:
                self.cloud.atualizar_status(pid, novo_status, lancado_por=meu_nome)
                self._load()
                pop.destroy()
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=pop)

        # Botao Voltar
        if idx > 0:
            status_anterior = ordem[idx - 1]
            label_anterior  = status_labels.get(status_anterior, status_anterior)
            ttk.Button(btn_frame,
                       text=f"← {label_anterior}",
                       command=lambda s=status_anterior: mover(s)
                       ).pack(side="left", padx=(0,6))

        # Botao Avancar
        if idx >= 0 and idx < len(ordem) - 1:
            status_proximo = ordem[idx + 1]
            label_proximo  = status_labels.get(status_proximo, status_proximo)
            ttk.Button(btn_frame,
                       text=f"{label_proximo} →",
                       command=lambda s=status_proximo: mover(s)
                       ).pack(side="left")

        # Fechar
        ttk.Button(pop, text="Fechar", command=pop.destroy).pack(pady=(4, 10))

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
                # Busca itens do lote para gerar PDF
                itens_pdf = []
                try:
                    import sqlite3 as _sq, json as _json
                    with _sq.connect(self.db_path) as _conn:
                        _rows = _conn.execute(
                            "SELECT payload_json, descricao, categoria, valor "
                            "FROM erp_launch_items "
                            "WHERE partner_name=? AND status IN ('LANCADO','SIMULADO') "
                            "ORDER BY id DESC LIMIT 100",
                            (casa,)
                        ).fetchall()
                    for r in _rows:
                        try:
                            p = _json.loads(r[0] or "{}")
                            itens_pdf.append({
                                "_descricao": r[1] or p.get("descricao",""),
                                "_categoria": r[2] or "",
                                "_valor":     float(r[3] or p.get("valor",0)),
                                "_payload":   p,
                            })
                        except Exception:
                            pass
                except Exception:
                    pass

                # Gera PDF
                pdf_path = None
                if itens_pdf:
                    try:
                        pdf_path = self._gerar_pdf_lote(
                            pid, casa, meu_nome, itens_pdf)
                    except Exception as ep:
                        print(f"[WORKFLOW] PDF erro: {ep}")

                # Atualiza status
                self.cloud.atualizar_status(
                    pid, "ag_aprov_operacional", lancado_por=meu_nome)

                # Envia PDF + botoes para grupo da casa
                grupo_id = self._get_cfg(
                    f"grupo_{casa.lower().replace(' ','_')}")
                evo_url  = self._get_cfg("evo_url")
                evo_key  = self._get_cfg("evo_key")
                instancia= self._get_cfg("evo_instancia", "wanderley")

                if evo_url and grupo_id:
                    from notificador import Notificador
                    import os
                    n = Notificador(evo_url, evo_key, instancia)
                    if n.status_instancia().get("conectado"):
                        if pdf_path and os.path.exists(pdf_path):
                            n.enviar_documento(
                                grupo_id, pdf_path,
                                caption=(
                                    f"Magical - Relatorio de Pagamentos\n"
                                    f"Casa: {casa} | Lancado por: {meu_nome}"
                                ),
                                nome_arquivo=os.path.basename(pdf_path)
                            )
                        msg_aprov = (
                            f"*{casa} — Lançamento Concluído*\n\n"
                            f"Casa: {casa}\n"
                            f"Lançado por: {meu_nome}\n\n"
                            f"Para APROVAR responda:\n"
                            f"SIM ou OK\n\n"
                            f"Para REPROVAR responda:\n"
                            f"NÃO [motivo]"
                        )
                        n.enviar_grupo(grupo_id, msg_aprov)

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
                    c = str(col).upper().strip()
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
                    elif c in ("BANCO",):
                        col_map[col] = "BANCO"
                    elif "AG" in c and ("CIA" in c or "NCIA" in c or c == "AGENCIA"):
                        col_map[col] = "AGENCIA"
                    elif c == "CONTA":
                        col_map[col] = "CONTA"
                    elif "DATA" in c and "PAGAMENTO" in c and "DATA" not in col_map.values():
                        col_map[col] = "DATA"
                    elif "DATA" in c and "DATA" not in col_map.values():
                        col_map[col] = "DATA"
                df = df.rename(columns=col_map)

                # ── Filtro de data ─────────────────────────────────────────
                hoje_dt = pd.Timestamp.today().normalize()
                datas_unicas = set()
                if "DATA" in df.columns:
                    for v in df["DATA"].dropna():
                        try:
                            dt = pd.to_datetime(str(v).strip(), dayfirst=True, errors="coerce")
                            if pd.notna(dt):
                                datas_unicas.add(dt.normalize())
                        except Exception:
                            pass

                tem_retroativas = any(d < hoje_dt for d in datas_unicas)
                tem_futuras     = any(d > hoje_dt for d in datas_unicas)
                data_filtro     = hoje_dt

                if tem_retroativas or tem_futuras:
                    avisos = []
                    if tem_retroativas:
                        datas_r = sorted(d for d in datas_unicas if d < hoje_dt)
                        avisos.append("Datas passadas: " + ", ".join(d.strftime("%d/%m/%Y") for d in datas_r))
                    if tem_futuras:
                        datas_f = sorted(d for d in datas_unicas if d > hoje_dt)
                        avisos.append("Datas futuras: " + ", ".join(d.strftime("%d/%m/%Y") for d in datas_f))

                    msg_aviso = (
                        f"A planilha contém datas diferentes de hoje ({hoje_dt.strftime('%d/%m/%Y')}):\n\n"
                        + "\n".join(avisos)
                        + "\n\nIncluir SOMENTE pagamentos de hoje no CNAB?"
                    )
                    import queue as _queue
                    resp_q = _queue.Queue()
                    def _perguntar():
                        r = messagebox.askyesno("Filtro de Data", msg_aviso, parent=self.win)
                        resp_q.put(r)
                    self.win.after(0, _perguntar)
                    so_hoje = resp_q.get(timeout=60)
                    if not so_hoje:
                        data_filtro = None

                if data_filtro is not None and "DATA" in df.columns:
                    def _eh_data_filtro(v):
                        try:
                            dt = pd.to_datetime(str(v).strip(), dayfirst=True, errors="coerce")
                            if pd.isna(dt):
                                return True
                            return dt.normalize() == data_filtro
                        except Exception:
                            return True
                    df = df[df["DATA"].apply(_eh_data_filtro)].reset_index(drop=True)
                    print(f"[CNAB] Filtro data={data_filtro.strftime('%d/%m/%Y')}: {len(df)} linhas")


                from core.cnab_itau import (
                    GeradorCNAB240,
                    PIX_CHAVE_CPF, PIX_CHAVE_CNPJ,
                    PIX_CHAVE_EMAIL, PIX_CHAVE_EVP,
                    PIX_CHAVE_CELULAR, _normalizar_chave_pix,
                )

                pagamentos = []
                for _, row in df.iterrows():
                    try:
                        v = str(row.get("VALOR",0) or "0").strip()
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

                    forma_raw = str(row.get("FORMA_PGTO","") or "").strip().upper()

                    # Dados bancarios
                    banco_col = str(row.get("BANCO","") or "").strip()
                    agencia_col = str(row.get("AGENCIA","") or "").strip()
                    conta_col = str(row.get("CONTA","") or "").strip()

                    banco_num = _re.sub(r"\D","", banco_col)
                    agencia_num = _re.sub(r"\D","", agencia_col)
                    # Separa DV da conta ex: "3726-1" -> conta=3726, dac=1
                    if "-" in conta_col:
                        partes = conta_col.split("-")
                        conta_num = _re.sub(r"\D","", partes[0])
                        dac_num   = _re.sub(r"\D","", partes[-1]) if len(partes)>1 else "0"
                    else:
                        conta_num = _re.sub(r"\D","", conta_col)
                        dac_num   = "0"

                    tem_conta = bool(conta_num and conta_num not in ("0",""))
                    tem_banco = bool(banco_num and banco_num not in ("0",""))

                    # Chave PIX — limpa zeros e "nan"
                    chave = str(row.get("PIX_CHAVE","") or "").strip()
                    if chave in ("nan","None","0",""):
                        chave = ""
                    # QR Code longo = EVP
                    eh_qrcode = len(chave) > 40

                    # Determina forma de pagamento
                    # Regra: FORMA=TED/DOC/DEPOSITO/CC com conta bancaria -> TED/CC
                    # Regra: tem PIX CHAVE valida -> PIX (mesmo se tiver conta)
                    # Regra: sem chave e tem conta -> CC/TED
                    eh_deposito = any(x in forma_raw for x in ("TED","DOC","DEPOSIT","TRANSFER","CC"))
                    eh_pix_forma = any(x in forma_raw for x in ("PIX","")) or forma_raw in ("0","","PIX")

                    if tem_conta and eh_deposito:
                        # Forca TED/CC
                        if banco_num in ("341","409") or banco_col.upper() in ("ITAU","ITAÚ"):
                            banco_num = banco_num or "341"
                            forma_cnab = "CC"
                        else:
                            forma_cnab = "TED"
                        chave = ""  # nao usa chave PIX neste caso
                    elif chave:
                        forma_cnab = "PIX"
                    elif tem_conta:
                        # Sem chave PIX mas tem conta bancaria
                        if banco_num in ("341","409") or banco_col.upper() in ("ITAU","ITAÚ"):
                            banco_num = banco_num or "341"
                            forma_cnab = "CC"
                        else:
                            forma_cnab = "TED"
                    else:
                        # Sem chave e sem conta — ignora
                        continue

                    # Detecta tipo de chave PIX
                    cpf = _re.sub(r"\D","", chave)
                    if not chave:
                        tipo = PIX_CHAVE_CPF
                        cpf  = ""
                    elif eh_qrcode or "br.gov.bcb.pix" in chave.lower():
                        tipo = PIX_CHAVE_EVP
                        cpf  = chave
                    elif "@" in chave:
                        tipo = PIX_CHAVE_EMAIL
                        cpf  = chave
                    elif len(cpf) == 14:
                        tipo = PIX_CHAVE_CNPJ
                    elif chave.strip().startswith("(") or (
                        len(cpf) in (10,11) and "." not in chave and "/" not in chave
                        and not (chave.count("-") == 2 and "." in chave)):
                        tipo = PIX_CHAVE_CELULAR
                    elif len(cpf) == 11:
                        tipo = PIX_CHAVE_CPF
                    else:
                        tipo = PIX_CHAVE_EVP
                        cpf  = chave

                    from datetime import date as _date_hoje
                    # Data de pagamento: usa a data da planilha ou hoje
                    data_pgto = str(row.get("DATA","") or "").strip()
                    if not data_pgto or data_pgto in ("nan","None",""):
                        data_pgto = _date_hoje.today().strftime("%Y-%m-%d")

                    # Normaliza chave PIX
                    chave_norm = _normalizar_chave_pix(chave, tipo) if chave else ""
                    cpf_norm   = _re.sub(r"[^0-9]", "", chave) if tipo in ("01","02") else cpf

                    pagamentos.append({
                        "nome":            str(row.get("FAVORECIDO","FAVORECIDO") or "FAVORECIDO")[:30],
                        "cpf_cnpj":        cpf_norm,
                        "pix_chave":       chave_norm,
                        "pix_tipo_chave":  tipo,
                        "valor":           vp,
                        "forma_pgto":      forma_cnab,
                        "banco_favorecido": banco_num or "341",
                        "agencia":         agencia_num,
                        "conta":           conta_num,
                        "dac":             dac_num,
                        "data":            data_pgto,
                    })

                if not pagamentos:
                    self.win.after(0, lambda: messagebox.showwarning(
                        "CNAB", "Nenhum pagamento valido encontrado.",
                        parent=self.win))
                    return

                downloads = Path.home() / "Downloads" / "CNAB" / casa
                downloads.mkdir(parents=True, exist_ok=True)

                # Busca dados bancarios da casa no banco local
                import sqlite3 as _sqlite3, json as _json2
                def _get_conta(parceiro):
                    try:
                        with _sqlite3.connect(self.db_path) as conn:
                            row = conn.execute(
                                "SELECT dados FROM contas_bancarias WHERE parceiro=? LIMIT 1",
                                (parceiro,)).fetchone()
                            return _json2.loads(row[0]) if row and row[0] else {}
                    except Exception:
                        return {}

                # Busca CNPJ do parceiro
                def _get_cnpj(parceiro):
                    try:
                        from core.partner_rules import PARTNERS
                        for p in PARTNERS:
                            if p["partner_name"].upper() == parceiro.upper():
                                return p.get("cnpj","").replace(".","").replace("/","").replace("-","")
                    except Exception:
                        pass
                    return "00000000000000"

                conta_dados = _get_conta(casa)
                cnpj        = _get_cnpj(casa)
                agencia     = conta_dados.get("agencia", "00000")
                conta_num   = conta_dados.get("conta", "000000000")
                dac         = conta_dados.get("dac", "0")

                # Remove tracos e espacos da conta (ex: "98707-4" -> "987074")
                # Se o usuario incluiu o DV na conta, separa o ultimo digito
                import re as _re2
                conta_limpa = _re2.sub(r"[^0-9]", "", str(conta_num))
                # Se nao tem DAC configurado e conta tem DV junto
                if (not dac or dac == "0") and "-" in str(conta_num):
                    partes = str(conta_num).split("-")
                    conta_limpa = _re2.sub(r"\D", "", partes[0])
                    dac = _re2.sub(r"\D", "", partes[-1]) if len(partes) > 1 else "0"

                config = {
                    "cnpj":    cnpj,
                    "agencia": agencia,
                    "conta":   conta_limpa,
                    "dac":     dac,
                    "nome":    casa.upper()[:30],
                }
                g = GeradorCNAB240(config)
                for p in pagamentos:
                    g.adicionar(p)
                arquivos = g.gerar(output_dir=str(downloads))

                vt = float(vals.get("total_valor", 0))
                self.cloud.confirmar_cnab_gerado(pid, casa, meu_nome, vt)

                msg_fin = (
                    f"*{casa} — Lote de Pagamento no Itaú*\n\n"
                    f"Casa: {casa}\n"
                    f"Gerado por: {meu_nome}\n"
                    f"Total: {self._brl(vt)}\n"
                    f"Pagamentos: {len(pagamentos)}\n\n"
                    f"Para APROVAR o pagamento responda:\n"
                    f"SIM ou OK\n\n"
                    f"Para REPROVAR responda:\n"
                    f"NÃO [motivo]"
                )
                self._notificar_grupo_casa(casa, msg_fin)

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


    def _gerar_pdf_lote(self, pid, casa, meu_nome, itens):
        """Gera PDF do lote de pagamentos. Retorna caminho do arquivo."""
        import tempfile, re
        from datetime import datetime
        from pathlib import Path

        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import (SimpleDocTemplate, Table,
                                             TableStyle, Paragraph, Spacer)
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
        except ImportError:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "pip", "install",
                           "reportlab", "--break-system-packages"],
                          capture_output=True)
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import (SimpleDocTemplate, Table,
                                             TableStyle, Paragraph, Spacer)
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER

        total = sum(abs(float(it.get("_valor", 0))) for it in itens
                    if isinstance(it, dict))

        def brl(v):
            try:
                return (f"R$ {abs(float(v)):,.2f}"
                        .replace(",","X").replace(".",",").replace("X","."))
            except Exception:
                return "R$ 0,00"

        hoje         = datetime.now()
        total_fmt    = brl(total)
        data_fmt     = hoje.strftime("%d.%m")
        data_extenso = hoje.strftime("%d/%m/%Y")

        nome_base = f"PAGAMENTOS {casa.upper()} {data_fmt} - {total_fmt}.pdf"
        nome_base = re.sub(r'[<>:"/\\|?*]', '', nome_base)

        tmp_dir = Path(tempfile.gettempdir()) / "magical_pdfs"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        destino = str(tmp_dir / nome_base)

        doc = SimpleDocTemplate(
            destino, pagesize=A4,
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
        )
        styles = getSampleStyleSheet()
        s_tit = ParagraphStyle("t", parent=styles["Heading1"],
                                fontSize=13, textColor=colors.HexColor("#0f172a"),
                                spaceAfter=2)
        s_sub = ParagraphStyle("s", parent=styles["Normal"],
                                fontSize=9, textColor=colors.HexColor("#475569"),
                                spaceAfter=10)
        s_rod = ParagraphStyle("r", parent=styles["Normal"],
                                fontSize=7, textColor=colors.HexColor("#94a3b8"),
                                alignment=TA_CENTER)

        story = []
        story.append(Paragraph("Relatorio de Pagamentos", s_tit))
        story.append(Paragraph(
            f"Casa: {casa}   |   Data: {data_extenso}   |   "
            f"Total: {total_fmt}   |   Lancado por: {meu_nome}", s_sub))

        col_w  = [6.5*cm, 4*cm, 2*cm, 2.5*cm]
        header = ["Descricao / Favorecido", "Categoria", "ID Evento", "Valor"]
        rows   = [header]

        for it in itens:
            if not isinstance(it, dict):
                continue
            try:
                desc  = str(it.get("_descricao",""))[:55]
                cat   = str(it.get("_categoria",""))[:25]
                id_ev = str(it.get("_payload",{}).get("idevento","") or "—")
                valor = brl(it.get("_valor", 0))
                rows.append([desc, cat, id_ev, valor])
            except Exception:
                pass

        rows.append(["", "TOTAL GERAL", "", total_fmt])

        AZUL  = colors.HexColor("#0f172a")
        CINZA = colors.HexColor("#f8fafc")
        AZUL_L= colors.HexColor("#dbeafe")
        BORDA = colors.HexColor("#e2e8f0")

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),  (-1,0),  AZUL),
            ("TEXTCOLOR",     (0,0),  (-1,0),  colors.white),
            ("FONTNAME",      (0,0),  (-1,0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),  (-1,0),  9),
            ("ALIGN",         (0,0),  (-1,0),  "CENTER"),
            ("TOPPADDING",    (0,0),  (-1,0),  7),
            ("BOTTOMPADDING", (0,0),  (-1,0),  7),
            ("FONTSIZE",      (0,1),  (-1,-2), 8),
            ("ROWBACKGROUNDS",(0,1),  (-1,-2), [colors.white, CINZA]),
            ("GRID",          (0,0),  (-1,-1), 0.4, BORDA),
            ("VALIGN",        (0,0),  (-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,1),  (-1,-2), 4),
            ("BOTTOMPADDING", (0,1),  (-1,-2), 4),
            ("ALIGN",         (3,1),  (3,-1),  "RIGHT"),
            ("BACKGROUND",    (0,-1), (-1,-1), AZUL_L),
            ("FONTNAME",      (0,-1), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",      (0,-1), (-1,-1), 9),
            ("ALIGN",         (1,-1), (3,-1),  "RIGHT"),
            ("TOPPADDING",    (0,-1), (-1,-1), 6),
            ("BOTTOMPADDING", (0,-1), (-1,-1), 6),
        ]))

        story.append(tbl)
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            f"Gerado em {hoje.strftime('%d/%m/%Y %H:%M')} | Magical Conciliacao",
            s_rod))

        doc.build(story)
        return destino

    def _notificar_grupo_casa(self, casa, msg):
        try:
            import requests as _req
            evo_url   = self._get_cfg("evo_url")
            evo_key   = self._get_cfg("evo_key")
            instancia = self._get_cfg("evo_instancia", "wanderley")
            chave_cfg = f"grupo_{casa.lower().replace(' ','_')}"
            grupo_id  = self._get_cfg(chave_cfg)
            print(f"[NOTIF] casa={casa} chave={chave_cfg} grupo={grupo_id} url={evo_url}")
            if not evo_url or not grupo_id:
                print(f"[NOTIF] SKIP — evo_url ou grupo_id vazio")
                return
            r = _req.post(
                f"{evo_url}/message/sendText/{instancia}",
                headers={"apikey": evo_key, "Content-Type": "application/json"},
                json={"number": grupo_id, "text": msg},
                timeout=20
            )
            print(f"[NOTIF] status={r.status_code} resp={r.text[:80]}")
        except Exception as e:
            print(f"[NOTIF] ERRO: {e}")

    def _notificar_grupo_casa_botoes(self, casa, titulo, corpo, botoes):
        """Envia mensagem com botoes clicaveis para o grupo da casa."""
        try:
            import requests
            evo_url   = self._get_cfg("evo_url")
            evo_key   = self._get_cfg("evo_key")
            instancia = self._get_cfg("evo_instancia", "wanderley")
            chave_cfg = f"grupo_{casa.lower().replace(' ','_')}"
            grupo_id  = self._get_cfg(chave_cfg)
            if not evo_url or not grupo_id:
                return
            payload = {
                "number":  grupo_id,
                "title":   titulo,
                "body":    corpo,
                "footer":  "Magical Conciliacao",
                "buttons": [{"type": "reply",
                             "reply": {"id": b["id"], "title": b["text"]}}
                            for b in botoes],
            }
            r = requests.post(
                f"{evo_url}/message/sendButtons/{instancia}",
                headers={"apikey": evo_key, "Content-Type": "application/json"},
                json=payload, timeout=20)
            if r.status_code not in (200, 201):
                opcoes = " | ".join(b["text"] for b in botoes)
                self._notificar_grupo_casa(
                    casa, titulo + "\n\n" + corpo + "\n\n" + opcoes)
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