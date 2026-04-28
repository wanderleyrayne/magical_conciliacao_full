import tkinter as tk
from tkinter import ttk
import pandas as pd
from pathlib import Path
from utils.paths import app_path
from core.settings_manager import SettingsManager
from utils.paths import user_data_path


class ResultsWindow:
    def __init__(self, master, df_resultado: pd.DataFrame):
        self.top = tk.Toplevel(master)
        # Ícone da aplicação
        try:
            icon_path = app_path("assets", "icon.ico")
            if icon_path.exists():
                self.top.iconbitmap(str(icon_path))
        except Exception:
            pass
        
        self.settings = SettingsManager(str(user_data_path("data", "conciliacao.db")))
        self.visible_columns = self.settings.get_visible_columns()

        self.top.title("Resultado da Conciliação")
        self.top.geometry("1450x780")

        self.df = df_resultado.copy() if df_resultado is not None else pd.DataFrame()
        self._prepare_dataframe()
        self._build_layout()

    def _prepare_dataframe(self):
        if self.df is None or self.df.empty:
            self.df = pd.DataFrame()
            return

        self.df = self.df.copy()
        self.df = self.df.where(pd.notna(self.df), None)

        def choose_date(row):
            if row.get("data_banco") is not None:
                return row.get("data_banco")
            return row.get("data_erp")

        self.df["data_ordem"] = self.df.apply(choose_date, axis=1)
        self.df["data_ordem"] = pd.to_datetime(self.df["data_ordem"], errors="coerce")
        self.df = self.df.sort_values(
            by=["data_ordem", "tipo_conciliacao", "status"],
            ascending=[True, True, True]
        ).reset_index(drop=True)

    def _build_layout(self):
        header = tk.Frame(self.top, bg="#1e293b", height=48)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Resultado da Conciliação",
            fg="white",
            bg="#1e293b",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=12, pady=10)

        filters = tk.Frame(self.top)
        filters.pack(fill="x", padx=12, pady=10)

        tk.Label(filters, text="Status:").pack(side="left")
        self.status_var = tk.StringVar(value="TODOS")
        self.status_combo = ttk.Combobox(
            filters,
            textvariable=self.status_var,
            state="readonly",
            values=["TODOS", "CONCILIADO", "SOMENTE_BANCO", "SOMENTE_ERP"]
        )
        self.status_combo.pack(side="left", padx=6)
        self.status_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_grid())

        tk.Label(filters, text="Tipo:").pack(side="left", padx=(12, 0))
        self.tipo_var = tk.StringVar(value="TODOS")
        self.tipo_combo = ttk.Combobox(
            filters,
            textvariable=self.tipo_var,
            state="readonly",
            values=["TODOS", "DESPESA", "RECEITA"]
        )
        self.tipo_combo.pack(side="left", padx=6)
        self.tipo_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_grid())

        tk.Label(filters, text="Categoria:").pack(side="left", padx=(12, 0))
        self.categoria_var = tk.StringVar(value="TODAS")
        categorias = self._listar_categorias()
        self.categoria_combo = ttk.Combobox(
            filters,
            textvariable=self.categoria_var,
            state="readonly",
            values=["TODAS"] + categorias
        )
        self.categoria_combo.pack(side="left", padx=6)
        self.categoria_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_grid())

        self.summary_label = tk.Label(filters, text="", font=("Arial", 10, "bold"))
        self.summary_label.pack(side="right")

        table_frame = tk.Frame(self.top)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        all_columns = [
            "tipo_conciliacao",
            "status",
            "diferenca_dias",
            "data_erp",
            "data_banco",
            "descricao_erp",
            "descricao_banco",
            "favorecido_banco",
            "documento_banco",
            "entidade_encontrada",
            "categoria_entidade",
            "valor_erp",
            "valor_banco",
            "manual_note",
        ]

        columns = [c for c in all_columns if c in self.visible_columns]
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar_y.pack(side="right", fill="y")

        scrollbar_x = ttk.Scrollbar(self.top, orient="horizontal", command=self.tree.xview)
        scrollbar_x.pack(fill="x", padx=12)

        self.tree.configure(
            yscrollcommand=scrollbar_y.set,
            xscrollcommand=scrollbar_x.set
        )

        headings = {
            "tipo_conciliacao": "Tipo",
            "status": "Status",
            "diferenca_dias": "Dif. Dias",
            "data_erp": "Data ERP",
            "data_banco": "Data Banco",
            "descricao_erp": "Descrição ERP",
            "descricao_banco": "Descrição Banco",
            "favorecido_banco": "Favorecido Banco",
            "documento_banco": "Documento Banco",
            "entidade_encontrada": "Entidade Encontrada",
            "categoria_entidade": "Categoria Entidade",
            "valor_erp": "Valor ERP",
            "valor_banco": "Valor Banco",
            "manual_note": "Observação",
        }

        widths = {
            "tipo_conciliacao": 90,
            "status": 120,
            "diferenca_dias": 70,
            "data_erp": 95,
            "data_banco": 95,
            "descricao_erp": 240,
            "descricao_banco": 220,
            "favorecido_banco": 210,
            "documento_banco": 130,
            "entidade_encontrada": 220,
            "categoria_entidade": 200,
            "valor_erp": 110,
            "valor_banco": 110,
            "manual_note": 220,
        }
        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")

        self.tree.tag_configure("CONCILIADO", background="#dff3e3")
        self.tree.tag_configure("SOMENTE_BANCO", background="#f8d7da")
        self.tree.tag_configure("SOMENTE_ERP", background="#fff3cd")

        footer = tk.Frame(self.top, bd=1, relief="solid", padx=10, pady=8)
        footer.pack(fill="x", padx=12, pady=(0, 12))

        self.total_despesas_label = tk.Label(
            footer, text="", fg="#b91c1c", font=("Arial", 10, "bold")
        )
        self.total_despesas_label.pack(side="left", padx=(0, 20))

        self.total_receitas_label = tk.Label(
            footer, text="", fg="#166534", font=("Arial", 10, "bold")
        )
        self.total_receitas_label.pack(side="left", padx=(0, 20))

        self.total_registros_label = tk.Label(
            footer, text="", font=("Arial", 10, "bold")
        )
        self.total_registros_label.pack(side="right")

        self._refresh_grid()

    def _listar_categorias(self):
        if self.df.empty or "categoria_entidade" not in self.df.columns:
            return []

        valores = []
        for v in self.df["categoria_entidade"].dropna().tolist():
            txt = str(v).strip()
            if txt and txt.lower() not in {"nan", "nat", "none"}:
                valores.append(txt)

        return sorted(list(set(valores)))

    def _filtered_df(self) -> pd.DataFrame:
        if self.df.empty:
            return self.df

        df = self.df.copy()

        status = self.status_var.get()
        if status != "TODOS":
            df = df[df["status"] == status]

        tipo = self.tipo_var.get()
        if tipo != "TODOS":
            df = df[df["tipo_conciliacao"] == tipo]

        categoria = self.categoria_var.get()
        if categoria != "TODAS":
            df = df[df["categoria_entidade"] == categoria]

        return df

    def _refresh_grid(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        df_view = self._filtered_df()

        for _, row in df_view.iterrows():
            tipo = self._safe_str(row.get("tipo_conciliacao"))
            status = self._safe_str(row.get("status"))

            row_values_map = {
                "tipo_conciliacao": tipo,
                "status": status,
                "diferenca_dias": self._safe_str(row.get("diferenca_dias")),
                "data_erp": self._fmt_date(row.get("data_erp")),
                "data_banco": self._fmt_date(row.get("data_banco")),
                "descricao_erp": self._safe_str(row.get("descricao_erp")),
                "descricao_banco": self._safe_str(row.get("descricao_banco")),
                "favorecido_banco": self._safe_str(row.get("favorecido_banco")),
                "documento_banco": self._safe_str(row.get("documento_banco")),
                "entidade_encontrada": self._safe_str(row.get("entidade_encontrada")),
                "categoria_entidade": self._safe_str(row.get("categoria_entidade")),
                "valor_erp": self._fmt_money_by_type(row.get("valor_erp"), tipo),
                "valor_banco": self._fmt_money_by_type(row.get("valor_banco"), tipo),
                "manual_note": self._safe_str(row.get("manual_note")),
            }

            values = [row_values_map[col] for col in self.tree["columns"]]

            self.tree.insert("", "end", values=values, tags=(status,))

        self._update_summary(df_view)

    def _update_summary(self, df_view: pd.DataFrame):
        total_despesas = 0.0
        total_receitas = 0.0

        if not df_view.empty:
            df_desp = df_view[df_view["tipo_conciliacao"] == "DESPESA"].copy()
            df_rec = df_view[df_view["tipo_conciliacao"] == "RECEITA"].copy()

            if not df_desp.empty:
                total_despesas = self._sum_best_value(df_desp)

            if not df_rec.empty:
                total_receitas = self._sum_best_value(df_rec)

        self.summary_label.config(text=f"Total filtrado: {len(df_view)}")
        self.total_despesas_label.config(
            text=f"Total de despesas: {self._fmt_money_by_type(total_despesas, 'DESPESA')}"
        )
        self.total_receitas_label.config(
            text=f"Total de receitas: {self._fmt_money_by_type(total_receitas, 'RECEITA')}"
        )
        self.total_registros_label.config(text=f"Registros: {len(df_view)}")

    def _sum_best_value(self, df: pd.DataFrame) -> float:
        total = 0.0
        for _, row in df.iterrows():
            valor = row.get("valor_banco")
            if valor is None or pd.isna(valor):
                valor = row.get("valor_erp")
            try:
                total += abs(float(valor))
            except Exception:
                pass
        return total

    @staticmethod
    def _safe_str(value):
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""
        return text

    @staticmethod
    def _fmt_date(value):
        if value is None:
            return ""
        try:
            dt = pd.to_datetime(value, errors="coerce")
            if pd.isna(dt):
                return ""
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return ""

    @staticmethod
    def _fmt_money_by_type(value, tipo):
        if value is None:
            return ""
        try:
            v = abs(float(value))
        except Exception:
            return ""

        if str(tipo).upper() == "RECEITA":
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        return f"- R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")