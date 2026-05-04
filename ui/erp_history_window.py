"""
ui/erp_history_window.py — Histórico de lançamentos enviados ao ERP via API.

Exibe: parceiro, planilha, data/hora, total de linhas, enviados, erros,
valor total, status, ID do lançamento e detalhes de cada item.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json


class ErpHistoryWindow:
    def __init__(self, master, repo):
        self.repo = repo
        self.win  = tk.Toplevel(master)
        self.win.title("Histórico de Lançamentos no ERP")
        self.win.geometry("1100x620")
        self.win.resizable(True, True)
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self.win, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Histórico de Lançamentos — ERP MeEventos",
                 fg="white", bg="#1e293b",
                 font=("Arial", 11, "bold")).pack(side="left", padx=12, pady=10)

        # Filtros
        fil = tk.Frame(self.win)
        fil.pack(fill="x", padx=10, pady=(8, 0))

        tk.Label(fil, text="Parceiro:").pack(side="left")
        self.parceiro_var = tk.StringVar(value="TODOS")
        self.cb_parceiro  = ttk.Combobox(fil, textvariable=self.parceiro_var,
                                          state="readonly", width=18)
        self.cb_parceiro.pack(side="left", padx=6)
        self.cb_parceiro.bind("<<ComboboxSelected>>", lambda e: self._load_batches())

        tk.Label(fil, text="Data:").pack(side="left", padx=(12,0))
        self.data_var = tk.StringVar(value="")
        data_entry = ttk.Entry(fil, textvariable=self.data_var, width=12)
        data_entry.pack(side="left", padx=4)
        tk.Label(fil, text="(dd/mm/aaaa)", fg="#94a3b8",
                 font=("Arial", 8)).pack(side="left")

        def _set_hoje():
            from datetime import date
            self.data_var.set(date.today().strftime("%d/%m/%Y"))
            self._load_batches()

        ttk.Button(fil, text="Hoje", command=_set_hoje).pack(side="left", padx=4)
        ttk.Button(fil, text="Limpar", command=lambda: (
            self.data_var.set(""), self._load_batches()
        )).pack(side="left")

        # Filtro simulação
        self.mostrar_simulacao = tk.BooleanVar(value=False)
        ttk.Checkbutton(fil, text="Mostrar simulações",
                        variable=self.mostrar_simulacao,
                        command=self._load_batches).pack(side="left", padx=(16,0))

        ttk.Button(fil, text="↺ Atualizar",
                   command=self._load_batches).pack(side="left", padx=8)

        self.lbl_total = tk.Label(fil, text="", font=("Arial", 9, "bold"))
        self.lbl_total.pack(side="right")

        # Painel principal — batches (acima) + itens (abaixo)
        pane = tk.PanedWindow(self.win, orient="vertical", sashrelief="flat")
        pane.pack(fill="both", expand=True, padx=10, pady=8)

        # ── Tabela de batches ──────────────────────────────────────────────
        top_f = tk.LabelFrame(pane, text="Lotes enviados")
        pane.add(top_f, minsize=200)

        batch_cols = ("id","data_hora","parceiro","planilha",
                      "total","enviados","simulados","erros","valor","dry_run")
        self.batch_tree = ttk.Treeview(top_f, columns=batch_cols,
                                        show="headings", height=8,
                                        selectmode="browse")
        for col, hd, w in [
            ("id",        "ID",         45),
            ("data_hora", "Data/Hora", 135),
            ("parceiro",  "Parceiro",  130),
            ("planilha",  "Planilha",  220),
            ("total",     "Total",      55),
            ("enviados",  "Enviados",   65),
            ("simulados", "Simulados",  70),
            ("erros",     "Erros",      55),
            ("valor",     "Valor total",100),
            ("dry_run",   "Modo",       80),
        ]:
            self.batch_tree.heading(col, text=hd)
            self.batch_tree.column(col, width=w, anchor="w")

        bt_sb = ttk.Scrollbar(top_f, orient="vertical",
                              command=self.batch_tree.yview)
        self.batch_tree.configure(yscrollcommand=bt_sb.set)
        self.batch_tree.pack(side="left", fill="both", expand=True)
        bt_sb.pack(side="right", fill="y")

        self.batch_tree.tag_configure("ok",   background="#dff3e3")
        self.batch_tree.tag_configure("erro", background="#f8d7da")
        self.batch_tree.tag_configure("sim",  background="#e0f2fe")
        self.batch_tree.bind("<<TreeviewSelect>>", self._on_batch_select)

        # ── Tabela de itens ────────────────────────────────────────────────
        bot_f = tk.LabelFrame(pane, text="Itens do lote selecionado")
        pane.add(bot_f, minsize=150)

        item_cols = ("linha","parceiro","status","id_api","id_evento","categoria","valor","descricao","mensagem")
        self.item_tree = ttk.Treeview(bot_f, columns=item_cols,
                                       show="headings", height=6)
        for col, hd, w in [
            ("linha",     "Linha",      50),
            ("parceiro",  "Parceiro",  100),
            ("status",    "Status",     80),
            ("id_api",    "ID API",     70),
            ("id_evento", "ID Evento",  80),
            ("categoria", "Categoria", 200),
            ("valor",     "Valor",      90),
            ("descricao", "Descrição", 220),
            ("mensagem",  "Mensagem",  160),
        ]:
            self.item_tree.heading(col, text=hd)
            self.item_tree.column(col, width=w, anchor="w")

        it_sb = ttk.Scrollbar(bot_f, orient="vertical",
                              command=self.item_tree.yview)
        self.item_tree.configure(yscrollcommand=it_sb.set)
        self.item_tree.pack(side="left", fill="both", expand=True)
        it_sb.pack(side="right", fill="y")
        self.item_tree.bind("<Double-1>", self._on_item_double)

        self.item_tree.tag_configure("LANCADO",  background="#dff3e3")
        self.item_tree.tag_configure("SIMULADO", background="#e0f2fe")
        self.item_tree.tag_configure("ERRO_API", background="#f8d7da")

        # Footer
        ft = tk.Frame(self.win, padx=10, pady=8)
        ft.pack(fill="x")
        tk.Label(ft, text="Duplo-clique em um item para ver o payload JSON completo.",
                 fg="#64748b", font=("Arial", 8)).pack(side="left")
        ttk.Button(ft, text="Fechar",
                   command=self.win.destroy).pack(side="right")

        self._load_batches()

    def _brl(self, v):
        try:
            return f"R$ {abs(float(v or 0)):,.2f}".replace(
                ",","X").replace(".",",").replace("X",".")
        except Exception:
            return "—"

    def _load_batches(self):
        for item in self.batch_tree.get_children():
            self.batch_tree.delete(item)
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)

        try:
            batches = self.repo.list_erp_launch_batches(limit=200)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc), parent=self.win)
            return

        # Popula filtro de parceiros
        parceiros = sorted({b.get("partner_name","") for b in batches if b.get("partner_name")})
        self.cb_parceiro["values"] = ["TODOS"] + parceiros

        filtro = self.parceiro_var.get()
        if filtro != "TODOS":
            batches = [b for b in batches
                       if b.get("partner_name","").upper() == filtro.upper()]

        # Filtro de data
        data_filtro = self.data_var.get().strip()
        if data_filtro:
            try:
                import pandas as _pd
                dt_filtro = _pd.to_datetime(data_filtro, dayfirst=True)
                data_fmt  = dt_filtro.strftime("%Y-%m-%d")
                batches = [b for b in batches
                           if str(b.get("created_at","")).startswith(data_fmt)]
            except Exception:
                pass

        # Filtro simulação
        if not self.mostrar_simulacao.get():
            batches = [b for b in batches if not b.get("dry_run")]

        total_valor = 0.0

        for b in batches:
            bid      = b.get("id", "")
            # Data/hora do banco — campo created_at
            created  = str(b.get("created_at") or "")[:16].replace("T"," ")
            parceiro = b.get("partner_name", "")
            planilha = b.get("file_name", "")
            total    = b.get("total_rows", 0)
            dry      = "Simulação" if b.get("dry_run") else "Real"

            # Conta enviados/simulados/erros pelos itens reais
            try:
                items    = self.repo.get_erp_launch_items(bid)
                enviados = sum(1 for it in items if it.get("status") == "LANCADO")
                simulados= sum(1 for it in items if it.get("status") == "SIMULADO")
                erros    = sum(1 for it in items if it.get("status") == "ERRO_API")
                val      = sum(
                    abs(float(it.get("valor") or 0))
                    for it in items
                    if it.get("status") in ("LANCADO", "SIMULADO")
                )
            except Exception:
                enviados = b.get("total_enviado", 0)
                simulados= b.get("total_simulado", 0)
                erros    = b.get("total_erro", 0)
                val      = 0.0

            total_valor += val
            tag = "sim" if b.get("dry_run") else ("erro" if erros > 0 else "ok")

            self.batch_tree.insert("", "end", iid=str(bid), values=(
                bid, created, parceiro, planilha,
                total, enviados, simulados, erros,
                self._brl(val), dry
            ), tags=(tag,))

        total = len(batches)
        self.lbl_total.config(
            text=f"{total} lote(s) · Total enviado: {self._brl(total_valor)}")

    def _on_batch_select(self, event=None):
        for item in self.item_tree.get_children():
            self.item_tree.delete(item)

        sel = self.batch_tree.selection()
        if not sel:
            return

        batch_id = int(sel[0])
        try:
            items = self.repo.get_erp_launch_items(batch_id)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc), parent=self.win)
            return

        for it in items:
            try:
                payload  = json.loads(it.get("payload_json") or "{}")
                valor    = self._brl(it.get("valor") or payload.get("valor", 0))
                desc     = str(it.get("descricao") or payload.get("descricao") or "")[:60]
                # Categoria: nome se disponível, senão ID
                cat_nome = str(it.get("categoria") or "")
                cat_id   = str(it.get("id_categoria") or payload.get("idcategoria") or "")
                categoria_display = (
                    f"{cat_nome} [{cat_id}]" if cat_nome and cat_id else
                    cat_nome or cat_id or "—"
                )
                # ID Evento: valor salvo ou do payload
                id_evento = str(it.get("id_evento") or payload.get("idevento") or "—")
            except Exception:
                valor = "—"
                desc  = ""
                categoria_display = "—"
                id_evento = "—"

            status = it.get("status", "")
            self.item_tree.insert("", "end", values=(
                it.get("linha_excel", ""),
                it.get("partner_name", ""),
                status,
                it.get("id_api", "") or "—",
                id_evento,
                categoria_display,
                valor,
                desc,
                str(it.get("mensagem") or "")[:60],
            ), tags=(status,))

    def _on_item_double(self, event=None):
        sel = self.item_tree.selection()
        if not sel:
            return

        batch_sel = self.batch_tree.selection()
        if not batch_sel:
            return

        batch_id = int(batch_sel[0])
        idx      = list(self.item_tree.get_children()).index(sel[0])

        try:
            items = self.repo.get_erp_launch_items(batch_id)
            it    = items[idx]
        except Exception:
            return

        pop = tk.Toplevel(self.win)
        pop.title(f"Payload — Item #{it.get('id','')}")
        pop.geometry("560x420")

        try:
            payload      = json.loads(it.get("payload_json") or "{}")
            txt_content  = json.dumps(payload, indent=2, ensure_ascii=False)
        except Exception:
            txt_content  = str(it.get("payload_json",""))

        # Adiciona info extra acima do JSON
        info = (
            f"Status:     {it.get('status','')}\n"
            f"ID API:     {it.get('id_api','—')}\n"
            f"ID Evento:  {it.get('id_evento','—')}\n"
            f"Categoria:  {it.get('categoria','')} [{it.get('id_categoria','—')}]\n"
            f"Mensagem:   {it.get('mensagem','')}\n"
            f"{'─'*60}\n"
            f"Payload JSON:\n{txt_content}"
        )

        txt = tk.Text(pop, wrap="word", font=("Courier New", 9))
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", info)
        txt.config(state="disabled")

        bf = tk.Frame(pop)
        bf.pack(fill="x", padx=10, pady=(0,8))

        def copiar():
            pop.clipboard_clear()
            pop.clipboard_append(txt_content)

        ttk.Button(bf, text="Copiar JSON", command=copiar).pack(side="left")
        ttk.Button(bf, text="Fechar", command=pop.destroy).pack(side="right")