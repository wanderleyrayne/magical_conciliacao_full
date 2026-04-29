import tkinter as tk
from tkinter import ttk
import pandas as pd
from utils.paths import app_path, user_data_path
from core.settings_manager import SettingsManager


class ResultsWindow:
    def __init__(self, master, df_resultado: pd.DataFrame, repo=None):
        self.top  = tk.Toplevel(master)
        self.repo = repo

        try:
            icon_path = app_path("assets", "icon.ico")
            if icon_path.exists():
                self.top.iconbitmap(str(icon_path))
        except Exception:
            pass

        self.settings        = SettingsManager(str(user_data_path("data", "conciliacao.db")))
        self.visible_columns = self.settings.get_visible_columns()
        self.top.title("Resultado da Conciliação")
        self.top.geometry("1450x820")
        self.df = df_resultado.copy() if df_resultado is not None else pd.DataFrame()
        self._prepare_dataframe()
        self._build_layout()

    def _prepare_dataframe(self):
        if self.df is None or self.df.empty:
            self.df = pd.DataFrame(); return
        self.df = self.df.copy()
        self.df = self.df.where(pd.notna(self.df), None)
        self.df["data_ordem"] = self.df.apply(
            lambda r: r.get("data_banco") or r.get("data_erp"), axis=1)
        self.df["data_ordem"] = pd.to_datetime(self.df["data_ordem"], errors="coerce")
        self.df = self.df.sort_values(
            by=["data_ordem","tipo_conciliacao","status"],
            ascending=[True,True,True]).reset_index(drop=True)

    def _build_layout(self):
        hdr = tk.Frame(self.top, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Resultado da Conciliação",
                 fg="white", bg="#1e293b",
                 font=("Arial",12,"bold")).pack(side="left", padx=12, pady=10)

        # Filtros
        fil = tk.Frame(self.top)
        fil.pack(fill="x", padx=12, pady=(8,0))
        tk.Label(fil, text="Status:").pack(side="left")
        self.status_var = tk.StringVar(value="TODOS")
        cb_st = ttk.Combobox(fil, textvariable=self.status_var, state="readonly",
                     values=["TODOS","CONCILIADO","SOMENTE_BANCO","SOMENTE_ERP","TRATADO_MANUAL"],
                     width=16)
        cb_st.pack(side="left", padx=6)
        cb_st.bind("<<ComboboxSelected>>", lambda e: self._refresh_grid())

        tk.Label(fil, text="Tipo:").pack(side="left", padx=(12,0))
        self.tipo_var = tk.StringVar(value="TODOS")
        cb_tp = ttk.Combobox(fil, textvariable=self.tipo_var, state="readonly",
                     values=["TODOS","DESPESA","RECEITA"], width=12)
        cb_tp.pack(side="left", padx=6)
        cb_tp.bind("<<ComboboxSelected>>", lambda e: self._refresh_grid())

        tk.Label(fil, text="Pesquisar:").pack(side="left", padx=(12,0))
        self.search_var = tk.StringVar()
        ttk.Entry(fil, textvariable=self.search_var, width=22).pack(side="left", padx=6)
        ttk.Button(fil, text="Pesquisar", command=self._refresh_grid).pack(side="left")
        ttk.Button(fil, text="Limpar", command=self._limpar_filtros).pack(side="left", padx=4)
        self.summary_label = tk.Label(fil, text="", font=("Arial",10,"bold"))
        self.summary_label.pack(side="right")

        # Barra de ações
        act = tk.Frame(self.top)
        act.pack(fill="x", padx=12, pady=(6,0))
        ttk.Button(act, text="Resumo parceiros",
                   command=self._open_partner_summary).pack(side="left")
        ttk.Button(act, text="↑ Lançar no ERP",
                   command=self._lancar_no_erp).pack(side="left", padx=(8,0))

        # Tabela
        tf = tk.Frame(self.top)
        tf.pack(fill="both", expand=True, padx=12, pady=(6,0))
        all_cols = ["tipo_conciliacao","status","diferenca_dias","data_erp","data_banco",
                    "descricao_erp","descricao_banco","favorecido_banco","documento_banco",
                    "entidade_encontrada","categoria_entidade","valor_erp","valor_banco","manual_note"]
        columns = [c for c in all_cols if c in self.visible_columns]
        self.tree = ttk.Treeview(tf, columns=columns, show="headings", selectmode="extended")
        self.tree.pack(side="left", fill="both", expand=True)
        sb_y = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        sb_y.pack(side="right", fill="y")
        sb_x = ttk.Scrollbar(self.top, orient="horizontal", command=self.tree.xview)
        sb_x.pack(fill="x", padx=12)
        self.tree.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)

        headings = {"tipo_conciliacao":"Tipo","status":"Status","diferenca_dias":"Dif. Dias",
                    "data_erp":"Data ERP","data_banco":"Data Banco",
                    "descricao_erp":"Descrição ERP","descricao_banco":"Descrição Banco",
                    "favorecido_banco":"Favorecido Banco","documento_banco":"Documento Banco",
                    "entidade_encontrada":"Entidade Encontrada","categoria_entidade":"Categoria Entidade",
                    "valor_erp":"Valor ERP","valor_banco":"Valor Banco","manual_note":"Observação"}
        widths = {"tipo_conciliacao":90,"status":120,"diferenca_dias":70,"data_erp":95,"data_banco":95,
                  "descricao_erp":240,"descricao_banco":220,"favorecido_banco":210,"documento_banco":130,
                  "entidade_encontrada":220,"categoria_entidade":200,"valor_erp":110,"valor_banco":110,"manual_note":220}
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")

        self.tree.tag_configure("CONCILIADO",    background="#dff3e3")
        self.tree.tag_configure("SOMENTE_BANCO", background="#f8d7da")
        self.tree.tag_configure("SOMENTE_ERP",   background="#fff3cd")
        self.tree.tag_configure("TRATADO_MANUAL",background="#e0f2fe")

        # Footer
        ft = tk.Frame(self.top, bd=1, relief="solid", padx=10, pady=8)
        ft.pack(fill="x", padx=12, pady=(0,12))
        self.lbl_desp = tk.Label(ft, text="", fg="#b91c1c", font=("Arial",10,"bold"))
        self.lbl_desp.pack(side="left", padx=(0,20))
        self.lbl_rec = tk.Label(ft, text="", fg="#166534", font=("Arial",10,"bold"))
        self.lbl_rec.pack(side="left")
        self.lbl_tot = tk.Label(ft, text="", font=("Arial",10,"bold"))
        self.lbl_tot.pack(side="right")
        self._refresh_grid()

    # =========================
    # AÇÕES
    # =========================

    def _open_partner_summary(self):
        try:
            from ui.partner_receipts_dialog import PartnerReceiptsDialog
            from core.revenue_partner_matcher import RevenuePartnerMatcher
            if self.repo is None: return
            summary = RevenuePartnerMatcher.build_partner_receipts_summary(self.df, self.repo)
            PartnerReceiptsDialog(self.top, summary)
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Erro", str(exc), parent=self.top)

    def _lancar_no_erp(self):
        try:
            from ui.erp_lancamento_window import ErpLancamentoWindow
            if self.repo is None: return
            ErpLancamentoWindow(self.top, self.repo)
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Erro", str(exc), parent=self.top)

    def _open_erp_history(self):
        try:
            from ui.erp_history_window import ErpHistoryWindow
            if self.repo is None: return
            ErpHistoryWindow(self.top, self.repo)
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Erro", str(exc), parent=self.top)

    def _limpar_filtros(self):
        self.status_var.set("TODOS")
        self.tipo_var.set("TODOS")
        self.search_var.set("")
        self._refresh_grid()

    # =========================
    # GRID
    # =========================

    def _filtered_df(self):
        if self.df.empty: return self.df
        df = self.df.copy()
        if self.status_var.get() != "TODOS":
            df = df[df["status"] == self.status_var.get()]
        if self.tipo_var.get() != "TODOS":
            df = df[df["tipo_conciliacao"] == self.tipo_var.get()]
        term = self.search_var.get().strip().upper()
        if term:
            df = df[df.apply(lambda r: any(
                term in str(v).upper() for v in r.values if v is not None), axis=1)]
        return df

    def _refresh_grid(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        df_view = self._filtered_df()
        for _, row in df_view.iterrows():
            tipo   = self._safe(row.get("tipo_conciliacao"))
            status = self._safe(row.get("status"))
            rm = {"tipo_conciliacao":tipo,"status":status,
                  "diferenca_dias":self._safe(row.get("diferenca_dias")),
                  "data_erp":self._date(row.get("data_erp")),
                  "data_banco":self._date(row.get("data_banco")),
                  "descricao_erp":self._safe(row.get("descricao_erp")),
                  "descricao_banco":self._safe(row.get("descricao_banco")),
                  "favorecido_banco":self._safe(row.get("favorecido_banco")),
                  "documento_banco":self._safe(row.get("documento_banco")),
                  "entidade_encontrada":self._safe(row.get("entidade_encontrada")),
                  "categoria_entidade":self._safe(row.get("categoria_entidade")),
                  "valor_erp":self._money(row.get("valor_erp"), tipo),
                  "valor_banco":self._money(row.get("valor_banco"), tipo),
                  "manual_note":self._safe(row.get("manual_note"))}
            self.tree.insert("", "end", values=[rm[c] for c in self.tree["columns"]],
                             tags=(status,))
        # Summary
        td = tr = 0.0
        for _, row in df_view.iterrows():
            tipo = str(row.get("tipo_conciliacao") or "").upper()
            v = row.get("valor_banco")
            if v is None or (isinstance(v,float) and pd.isna(v)):
                v = row.get("valor_erp")
            try: v = abs(float(v))
            except: v = 0.0
            if tipo == "DESPESA": td += v
            elif tipo == "RECEITA": tr += v
        self.summary_label.config(text=f"Filtrado: {len(df_view)}")
        self.lbl_desp.config(text=f"Despesas: {self._money(td,'DESPESA')}")
        self.lbl_rec.config(text=f"Receitas: {self._money(tr,'RECEITA')}")
        self.lbl_tot.config(text=f"Registros: {len(df_view)}")

    @staticmethod
    def _safe(v):
        if v is None: return ""
        s = str(v).strip()
        return "" if s.lower() in {"nan","nat","none"} else s

    @staticmethod
    def _date(v):
        if v is None: return ""
        try:
            dt = pd.to_datetime(v, errors="coerce")
            return "" if pd.isna(dt) else dt.strftime("%d/%m/%Y")
        except: return ""

    @staticmethod
    def _money(v, tipo=""):
        if v is None: return ""
        try: v = abs(float(v))
        except: return ""
        f = f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")
        return f if str(tipo).upper() == "RECEITA" else f"- {f}"