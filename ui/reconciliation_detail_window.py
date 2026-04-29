import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd

from database.repository import SystemRepository
from core.settings_manager import SettingsManager, DEFAULT_VISIBLE_COLUMNS
from core.revenue_partner_matcher import RevenuePartnerMatcher
from ui.partner_receipts_dialog import PartnerReceiptsDialog
from utils.paths import app_path, user_data_path


class ReconciliationDetailWindow:
    COLUMN_LABELS = {
        "sel": "Sel.",
        "id": "ID",
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

    DEFAULT_COLUMN_WIDTHS = {
        "sel": 45,
        "id": 65,
        "tipo_conciliacao": 90,
        "status": 120,
        "diferenca_dias": 80,
        "data_erp": 95,
        "data_banco": 95,
        "descricao_erp": 260,
        "descricao_banco": 260,
        "favorecido_banco": 210,
        "documento_banco": 150,
        "entidade_encontrada": 210,
        "categoria_entidade": 180,
        "valor_erp": 120,
        "valor_banco": 120,
        "manual_note": 180,
    }

    def __init__(self, master, run_id: int, db_path=None):
        self.top = tk.Toplevel(master)
        self.run_id = run_id

        if db_path is None:
            db_path = str(user_data_path("data", "conciliacao.db"))

        self.repo = SystemRepository(db_path)
        self.settings = SettingsManager(db_path)

        self.top.title(f"Detalhe da Conciliação #{run_id}")
        self.top.geometry("1520x860")
        self.top.minsize(1200, 720)

        try:
            icon_path = app_path("assets", "icon.ico")
            if icon_path.exists():
                self.top.iconbitmap(str(icon_path))
        except Exception:
            pass

        self.original_df = self.repo.get_reconciliation_results_df(run_id)
        self.df = self.original_df.copy()

        self.visible_columns = self._get_visible_columns()

        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="TODOS")
        self.tipo_var = tk.StringVar(value="TODOS")

        self._build_layout()
        self._apply_filters()

    # =========================
    # LAYOUT
    # =========================
    def _build_layout(self):
        header = tk.Frame(self.top, bg="#1e293b", height=48)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"Detalhe da Conciliação #{self.run_id}",
            fg="white",
            bg="#1e293b",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=12, pady=10)

        filters = tk.Frame(self.top)
        filters.pack(fill="x", padx=10, pady=10)

        tk.Label(filters, text="Pesquisar:").pack(side="left")
        search_entry = ttk.Entry(filters, textvariable=self.search_var, width=36)
        search_entry.pack(side="left", padx=(6, 8))
        search_entry.bind("<Return>", lambda e: self._apply_filters())

        ttk.Button(filters, text="Pesquisar", command=self._apply_filters).pack(side="left")
        ttk.Button(filters, text="Limpar busca", command=self._clear_search).pack(side="left", padx=(6, 14))

        tk.Label(filters, text="Status:").pack(side="left")
        status_combo = ttk.Combobox(
            filters,
            textvariable=self.status_var,
            values=["TODOS", "CONCILIADO", "SOMENTE_BANCO", "SOMENTE_ERP", "TRATADO_MANUAL", "IGNORADO"],
            width=18,
            state="readonly"
        )
        status_combo.pack(side="left", padx=(6, 14))
        status_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())

        tk.Label(filters, text="Tipo:").pack(side="left")
        tipo_combo = ttk.Combobox(
            filters,
            textvariable=self.tipo_var,
            values=["TODOS", "RECEITA", "DESPESA"],
            width=14,
            state="readonly"
        )
        tipo_combo.pack(side="left", padx=(6, 0))
        tipo_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_filters())

        actions = tk.Frame(self.top)
        actions.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(actions, text="Resumo parceiros", command=self._open_partner_summary).pack(side="left")
        ttk.Button(actions, text="Atribuir a parceiro ▾", command=self._atribuir_a_parceiro).pack(side="left", padx=(8, 0))

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(
            actions, text="⇄ Conciliação manual",
            command=self._enviar_ao_erp
        ).pack(side="left")

        ttk.Separator(actions, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(
            actions, text="↑ Lançar no ERP",
            command=self._lancar_somente_banco_no_erp
        ).pack(side="left")

        table_frame = tk.Frame(self.top)
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.columns = self._build_columns()

        self.tree = ttk.Treeview(
            table_frame,
            columns=self.columns,
            show="headings",
            selectmode="extended"
        )
        self.tree.pack(side="left", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll_y.pack(side="right", fill="y")

        scroll_x = ttk.Scrollbar(self.top, orient="horizontal", command=self.tree.xview)
        scroll_x.pack(fill="x", padx=10)

        self.tree.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        for col in self.columns:
            self.tree.heading(col, text=self.COLUMN_LABELS.get(col, col))
            self.tree.column(
                col,
                width=self.DEFAULT_COLUMN_WIDTHS.get(col, 120),
                anchor="center" if col not in {"descricao_erp", "descricao_banco", "favorecido_banco", "entidade_encontrada", "categoria_entidade", "manual_note"} else "w"
            )

        self.tree.tag_configure("CONCILIADO", background="#dff3e3")
        self.tree.tag_configure("SOMENTE_BANCO", background="#f8d7da")
        self.tree.tag_configure("SOMENTE_ERP", background="#fff3cd")
        self.tree.tag_configure("TRATADO_MANUAL", background="#dbeafe")
        self.tree.tag_configure("IGNORADO", background="#e5e7eb")

        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)
        self.tree.bind("<Double-1>", self._toggle_sel_column)

        footer = tk.Frame(self.top, bd=1, relief="solid")
        footer.pack(fill="x", padx=10, pady=(0, 10))

        left_footer = tk.Frame(footer)
        left_footer.pack(side="left", padx=10, pady=8)

        self.records_label = tk.Label(left_footer, text="Registros filtrados: 0", font=("Arial", 10, "bold"))
        self.records_label.pack(anchor="w")

        right_footer = tk.Frame(footer)
        right_footer.pack(side="right", padx=10, pady=8)

        self.partner_rule_label = tk.Label(
            right_footer,
            text="",
            font=("Arial", 9, "bold"),
            fg="#334155"
        )
        self.partner_rule_label.pack(anchor="e")

        self.total_selecionado_label = tk.Label(
            right_footer,
            text="Selecione linhas para somar",
            font=("Arial", 10, "bold")
        )
        self.total_selecionado_label.pack(anchor="e", pady=(4, 0))

    # =========================
    # DADOS / COLUNAS
    # =========================
    def _get_visible_columns(self):
        cols = self.settings.get_visible_columns()
        if not cols:
            cols = DEFAULT_VISIBLE_COLUMNS[:]
        cols = list(cols)

        # garante colunas essenciais
        essentials = ["id", "tipo_conciliacao", "status", "data_erp", "data_banco"]
        for col in reversed(essentials):
            if col not in cols:
                cols.insert(0, col)

        return cols

    def _build_columns(self):
        cols = ["id"]
        for col in self.visible_columns:
            if col != "id":
                cols.append(col)
        return cols

    def _reload_data(self):
        self.original_df = self.repo.get_reconciliation_results_df(self.run_id)
        self.df = self.original_df.copy()
        self._apply_filters()

    # =========================
    # PESQUISA / FILTRO
    # =========================
    def _clear_search(self):
        self.search_var.set("")
        self.status_var.set("TODOS")
        self.tipo_var.set("TODOS")
        self._apply_filters()

    def _normalize_search_value(self, value):
        text = self._safe_str(value).upper()
        digits = "".join(ch for ch in text if ch.isdigit())
        return text, digits

    def _row_matches_search(self, row, term):
        term_text = self._safe_str(term).upper()
        term_digits = "".join(ch for ch in term_text if ch.isdigit())

        fields = [
            row.get("descricao_erp"),
            row.get("descricao_banco"),
            row.get("favorecido_banco"),
            row.get("documento_banco"),
            row.get("entidade_encontrada"),
            row.get("categoria_entidade"),
            row.get("valor_erp"),
            row.get("valor_banco"),
            row.get("status"),
            row.get("tipo_conciliacao"),
            row.get("manual_note"),
        ]

        for field in fields:
            field_text, field_digits = self._normalize_search_value(field)

            if term_text and term_text in field_text:
                return True

            if term_digits and field_digits and term_digits in field_digits:
                return True

        return False

    def _apply_filters(self):
        df = self.original_df.copy()

        status_filter = self._safe_str(self.status_var.get()).upper()
        tipo_filter   = self._safe_str(self.tipo_var.get()).upper()
        search_term   = self.search_var.get().strip()

        if status_filter and status_filter != "TODOS" and "status" in df.columns:
            df = df[df["status"].astype(str).str.upper() == status_filter]

        if tipo_filter and tipo_filter != "TODOS" and "tipo_conciliacao" in df.columns:
            df = df[df["tipo_conciliacao"].astype(str).str.upper() == tipo_filter]

        if search_term:
            df = df[df.apply(lambda row: self._row_matches_search(row, search_term), axis=1)]

        self.df = df.reset_index(drop=True)
        self._load_tree_data()

        # Analytics popup: detecta se o termo de busca corresponde a um parceiro
        if search_term and len(search_term) >= 3:
            self._maybe_show_partner_analytics(search_term, df)

    def _load_tree_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for _, row in self.df.iterrows():
            values = []
            for col in self.columns:
                value = row.get(col, "")

                if col in {"valor_erp", "valor_banco"}:
                    value = self._fmt_money_excel(value)
                elif col in {"data_erp", "data_banco"}:
                    value = self._fmt_date(value)
                else:
                    value = self._safe_str(value)

                values.append(value)

            status_tag = self._safe_str(row.get("status")).upper()
            self.tree.insert("", "end", values=values, tags=(status_tag,))

        self.records_label.config(text=f"Registros filtrados: {len(self.df)}")
        self.total_selecionado_label.config(text="Selecione linhas para somar")
        self.partner_rule_label.config(text="")

    # =========================
    # SELEÇÃO / SOMA
    # =========================
    def _toggle_sel_column(self, event=None):
        # Mantido como placeholder para compatibilidade visual.
        pass

    def _get_selected_rows_total(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return 0.0, 0

        id_index = self.columns.index("id")
        total = 0.0
        count = 0

        for item in selected_items:
            values = self.tree.item(item, "values")
            if not values:
                continue

            try:
                result_id = int(values[id_index])
            except Exception:
                continue

            row = self.df[self.df["id"] == result_id]
            if row.empty:
                continue

            try:
                row = row.iloc[0]
            except (IndexError, KeyError):
                continue

            valor = row.get("valor_banco")
            if valor is None or pd.isna(valor):
                valor = row.get("valor_erp")

            try:
                total += abs(float(valor or 0))
            except Exception:
                pass

            count += 1

        return round(total, 2), count

    def _on_row_select(self, event=None):
        total, count = self._get_selected_rows_total()

        self.partner_rule_label.config(text="")

        if count == 0:
            self.total_selecionado_label.config(
                text="Selecione linhas para somar"
            )
            return

        self.total_selecionado_label.config(
            text=f"Linhas selecionadas: {count} | Total: {self._fmt_money_excel(total)}"
        )

        selected_items = self.tree.selection()
        id_index = self.columns.index("id")
        tipos = set()

        for item in selected_items:
            values = self.tree.item(item, "values")
            if not values:
                continue

            try:
                result_id = int(values[id_index])
            except Exception:
                continue

            row = self.df[self.df["id"] == result_id]
            if row.empty:
                continue

            try:
                row = row.iloc[0]
            except (IndexError, KeyError):
                continue
            tipos.add(self._safe_str(row.get("tipo_conciliacao")).upper())

        if tipos != {"RECEITA"}:
            return

        self._update_partner_rule_summary(total)

    # =========================
    # RESUMO PARCEIROS / REGRA MENSAL
    # =========================
    def _open_partner_summary(self):
        try:
            banco_rows = []

            for _, row in self.df.iterrows():
                if pd.notna(row.get("data_banco")) and pd.notna(row.get("valor_banco")):
                    tipo = "ENTRADA" if str(row.get("tipo_conciliacao", "")).upper() == "RECEITA" else "SAIDA"

                    banco_rows.append({
                        "data": row.get("data_banco"),
                        "descricao": row.get("descricao_banco", ""),
                        "favorecido": row.get("favorecido_banco", ""),
                        "documento": row.get("documento_banco", ""),
                        "valor": row.get("valor_banco", 0),
                        "tipo": tipo,
                        "categoria": "",
                        "forma_pagamento": "",
                        "pago": "",
                        # atribuição manual de aportador do grupo
                        "attributed_partner": row.get("attributed_partner", ""),
                    })

            df_banco = pd.DataFrame(banco_rows).drop_duplicates()

            if df_banco.empty:
                messagebox.showwarning("Aviso", "Não foi possível montar o resumo dos parceiros.")
                return

            partner_receipts_summary = RevenuePartnerMatcher.build_partner_receipts_summary(
                df_banco=df_banco,
                repo=self.repo
            )

            if not partner_receipts_summary:
                messagebox.showwarning("Aviso", "Não há resumo de parceiros para esta execução.")
                return

            PartnerReceiptsDialog(self.top, partner_receipts_summary)

        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível abrir o resumo dos parceiros.\n\nDetalhes: {exc}")

    def _extract_partner_and_month_from_selection(self):
        selected_items = self.tree.selection()
        if not selected_items:
            return None, None, "Nenhuma linha selecionada."

        id_index = self.columns.index("id")
        partners = set()
        months = set()

        for item in selected_items:
            values = self.tree.item(item, "values")
            if not values:
                continue

            try:
                result_id = int(values[id_index])
            except Exception:
                continue

            row = self.df[self.df["id"] == result_id]
            if row.empty:
                continue

            try:
                row = row.iloc[0]
            except (IndexError, KeyError):
                continue

            partner = self._identify_partner_from_row(row)
            if partner:
                partners.add(partner)

            ref_month = self._extract_reference_month_from_row(row)
            if ref_month:
                months.add(ref_month)

        if len(partners) != 1:
            return None, None, "Selecione linhas de um único parceiro para comparar com a regra mensal."

        if len(months) != 1:
            return None, None, "Selecione linhas de um único mês para comparar com a regra mensal."

        return list(partners)[0], list(months)[0], ""

    def _identify_partner_from_row(self, row):
        text = " ".join([
            self._safe_str(row.get("descricao_erp")),
            self._safe_str(row.get("descricao_banco")),
            self._safe_str(row.get("favorecido_banco")),
            self._safe_str(row.get("entidade_encontrada")),
            self._safe_str(row.get("documento_banco")),
        ]).upper()

        from core.partner_rules import PARTNERS

        def clean_doc(value):
            return "".join(ch for ch in str(value or "") if ch.isdigit())

        partners = [p for p in PARTNERS if not p.get("is_hub")]

        def partner_weight(partner):
            aliases = [self._safe_str(a).upper() for a in partner.get("aliases", [])]
            legal_name = self._safe_str(partner.get("legal_name")).upper()
            longest_alias = max([len(a) for a in aliases], default=0)
            return max(longest_alias, len(legal_name))

        partners = sorted(partners, key=partner_weight, reverse=True)

        for partner in partners:
            cnpj = clean_doc(partner.get("cnpj"))
            if cnpj and cnpj in text:
                return partner["partner_name"]

        for partner in partners:
            legal_name = self._safe_str(partner.get("legal_name")).upper()
            if legal_name and legal_name in text:
                return partner["partner_name"]

        for partner in partners:
            aliases = [self._safe_str(a).upper() for a in partner.get("aliases", [])]
            aliases = sorted(aliases, key=len, reverse=True)

            for alias in aliases:
                if alias and alias in text:
                    return partner["partner_name"]

        return None

    def _extract_reference_month_from_row(self, row):
        for field in ["data_banco", "data_erp"]:
            value = row.get(field)
            try:
                dt = pd.to_datetime(value, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime("%Y-%m")
            except Exception:
                continue
        return None

    def _update_partner_rule_summary(self, total_selected):
        selected_items = self.tree.selection()
        if not selected_items:
            self.partner_rule_label.config(text="")
            return

        id_index = self.columns.index("id")
        tipos = set()

        for item in selected_items:
            values = self.tree.item(item, "values")
            if not values:
                continue

            try:
                result_id = int(values[id_index])
            except Exception:
                continue

            row = self.df[self.df["id"] == result_id]
            if row.empty:
                continue

            try:
                row = row.iloc[0]
            except (IndexError, KeyError):
                continue
            tipos.add(self._safe_str(row.get("tipo_conciliacao")).upper())

        if tipos != {"RECEITA"}:
            self.partner_rule_label.config(text="")
            return

        partner_name, reference_month, message = self._extract_partner_and_month_from_selection()

        if not partner_name or not reference_month:
            self.partner_rule_label.config(text=message)
            return

        rule = self.repo.get_partner_month_rule(reference_month, partner_name)

        if not rule:
            self.partner_rule_label.config(
                text=f"Parceiro: {partner_name} | Mês: {reference_month} | Regra mensal: não cadastrada"
            )
            return

        total_expected = float(rule.get("total_expected") or 0)
        diff = round(float(total_selected or 0) - total_expected, 2)

        if abs(diff) < 0.01:
            status = "OK"
        elif total_selected < total_expected:
            status = "PARCIAL"
        else:
            status = "EXCEDENTE"

        diff_fmt = self._fmt_money_excel(abs(diff))
        expected_fmt = self._fmt_money_excel(total_expected)

        if status == "OK":
            extra = "Sem diferença"
        elif status == "PARCIAL":
            extra = f"Faltando: {diff_fmt}"
        else:
            extra = f"Excedente: {diff_fmt}"

        self.partner_rule_label.config(
            text=f"Parceiro: {partner_name} | Mês: {reference_month} | Regra: {expected_fmt} | Status: {status} | {extra}"
        )

    # =========================
    # AÇÕES MANUAIS
    # =========================
    def _atribuir_a_parceiro(self):
        """
        Atribui um depósito de aportador do grupo (ex: sócio) a um parceiro específico.
        O usuário seleciona uma linha SOMENTE_BANCO e escolhe o parceiro de destino.
        O valor passa a ser somado no Resumo de Parceiros para o parceiro escolhido.
        """
        result_id = self._get_single_selected_id()
        if result_id is None:
            return

        row = self.df[self.df["id"] == result_id]
        if row.empty:
            messagebox.showwarning("Aviso", "Linha não encontrada.")
            return
        try:
            row = row.iloc[0]
        except (IndexError, KeyError):
            return

        from core.partner_rules import PARTNERS, GROUP_CONTRIBUTORS
        from core.revenue_partner_matcher import RevenuePartnerMatcher

        # Verifica se é um aportador conhecido — aviso informativo, não bloqueia
        banco_row = {
            "descricao": row.get("descricao_banco", ""),
            "favorecido": row.get("favorecido_banco", ""),
            "documento": row.get("documento_banco", ""),
        }
        contributor = RevenuePartnerMatcher.identify_group_contributor(banco_row)

        # Monta a janela de atribuição
        win = tk.Toplevel(self.top)
        win.title("Atribuir aporte a parceiro")
        win.geometry("480x300")
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text="Atribuir aporte a parceiro", font=("Arial", 11, "bold"),
                 bg="#1e293b", fg="white").pack(fill="x", ipady=8)

        info_frame = tk.Frame(win, padx=16, pady=10)
        info_frame.pack(fill="x")

        favorecido = self._safe_str(row.get("favorecido_banco")) or self._safe_str(row.get("descricao_banco"))

        # Resolve valor: pega o primeiro numérico válido entre valor_banco e valor_erp
        def _parse_val(v):
            try:
                return float(v) if v is not None and str(v).strip().lower() not in {"nan", "none", ""} else None
            except Exception:
                return None
        _valor_num = _parse_val(row.get("valor_banco")) or _parse_val(row.get("valor_erp")) or 0.0
        valor = self._fmt_money_excel(_valor_num)

        tk.Label(info_frame, text=f"Depósito:  {favorecido}", anchor="w",
                 font=("Arial", 9)).pack(fill="x")
        tk.Label(info_frame, text=f"Valor:        {valor}", anchor="w",
                 font=("Arial", 9, "bold")).pack(fill="x")

        if contributor:
            tk.Label(info_frame,
                     text=f"Aportador identificado: {contributor['label']}",
                     anchor="w", fg="#0f6e56", font=("Arial", 9, "italic")).pack(fill="x", pady=(4, 0))
        else:
            tk.Label(info_frame,
                     text="Aportador não está na lista de contribuidores conhecidos.",
                     anchor="w", fg="#854f0b", font=("Arial", 9, "italic")).pack(fill="x", pady=(4, 0))

        tk.Label(info_frame, text="Selecione o parceiro de destino:", anchor="w",
                 font=("Arial", 9)).pack(fill="x", pady=(12, 4))

        partner_names = sorted([p["partner_name"] for p in PARTNERS if not p.get("is_hub")])
        partner_var = tk.StringVar()

        combo = ttk.Combobox(info_frame, textvariable=partner_var,
                             values=partner_names, state="readonly", width=32)
        combo.pack(anchor="w")

        note_frame = tk.Frame(win, padx=16)
        note_frame.pack(fill="x", pady=(8, 0))
        tk.Label(note_frame, text="Observação (opcional):", anchor="w",
                 font=("Arial", 9)).pack(fill="x")
        note_entry = ttk.Entry(note_frame, width=52)
        note_entry.pack(fill="x")

        btn_frame = tk.Frame(win, padx=16, pady=12)
        btn_frame.pack(fill="x")

        def confirmar():
            partner_chosen = partner_var.get().strip()
            if not partner_chosen:
                messagebox.showwarning("Aviso", "Selecione um parceiro.", parent=win)
                return

            note = note_entry.get().strip() or f"Aporte atribuído ao parceiro: {partner_chosen}"

            ok = self.repo.attribute_contribution(result_id, partner_chosen, note)
            if ok:
                win.destroy()
                self._reload_data()
                messagebox.showinfo(
                    "Sucesso",
                    f"Aporte atribuído ao parceiro '{partner_chosen}'.\n"
                    "O Resumo de Parceiros já considera este valor."
                )
            else:
                messagebox.showerror("Erro", "Não foi possível salvar a atribuição.", parent=win)

        ttk.Button(btn_frame, text="Confirmar atribuição", command=confirmar).pack(side="left")
        ttk.Button(btn_frame, text="Cancelar", command=win.destroy).pack(side="left", padx=8)

    def _get_single_selected_id(self):
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showwarning("Aviso", "Selecione exatamente uma linha.")
            return None

        values = self.tree.item(selected[0], "values")
        if not values:
            messagebox.showwarning("Aviso", "Linha inválida.")
            return None

        try:
            return int(values[self.columns.index("id")])
        except Exception:
            messagebox.showerror("Erro", "ID inválido.")
            return None

    def _get_selected_ids(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione ao menos uma linha.")
            return []

        ids = []
        id_index = self.columns.index("id")

        for item in selected:
            values = self.tree.item(item, "values")
            if not values:
                continue
            try:
                ids.append(int(values[id_index]))
            except Exception:
                continue

        return ids

    def _conciliar_manual_single(self):
        result_id = self._get_single_selected_id()
        if result_id is None:
            return

        if self.repo.update_reconciliation_result_status(result_id, "CONCILIADO", "Ajuste manual individual"):
            self._reload_data()

    def _tratar_manual_single(self):
        result_id = self._get_single_selected_id()
        if result_id is None:
            return

        if self.repo.update_reconciliation_result_status(result_id, "TRATADO_MANUAL", "Tratado manualmente"):
            self._reload_data()

    def _ignorar_single(self):
        result_id = self._get_single_selected_id()
        if result_id is None:
            return

        if self.repo.update_reconciliation_result_status(result_id, "IGNORADO", "Ignorado manualmente"):
            self._reload_data()

    def _conciliar_manual_bulk(self):
        ids = self._get_selected_ids()
        if not ids:
            return

        total = self.repo.bulk_update_reconciliation_results(ids, "CONCILIADO", "Ajuste manual em lote")
        if total:
            self._reload_data()

    def _tratar_manual_bulk(self):
        ids = self._get_selected_ids()
        if not ids:
            return

        total = self.repo.bulk_update_reconciliation_results(ids, "TRATADO_MANUAL", "Tratado manualmente em lote")
        if total:
            self._reload_data()

    def _ignorar_bulk(self):
        ids = self._get_selected_ids()
        if not ids:
            return

        total = self.repo.bulk_update_reconciliation_results(ids, "IGNORADO", "Ignorado em lote")
        if total:
            self._reload_data()

    # =========================
    # CONCILIAÇÃO MANUAL (UNIFICADA)
    # =========================

    def _enviar_ao_erp(self):
        """
        Conciliação manual unificada — vincula SOMENTE_BANCO com SOMENTE_ERP
        e marca tudo como CONCILIADO localmente. Nenhuma chamada à API.

        Modos:
        - Só SOMENTE_BANCO selecionado → busca sugestões automáticas do ERP
        - Misto ou só SOMENTE_ERP     → exibe o que foi selecionado
        Em ambos os casos o usuário pode adicionar/remover linhas de qualquer lado.
        """
        ids = self._get_selected_ids()
        if not ids:
            return

        rows_banco, rows_erp = [], []
        for result_id in ids:
            match = self.original_df[self.original_df["id"] == result_id]
            if match.empty:
                continue
            try:
                row = match.iloc[0]
            except (IndexError, KeyError):
                continue
            status = str(row.get("status", "")).upper()
            if status == "SOMENTE_BANCO":
                rows_banco.append((result_id, row))
            elif status == "SOMENTE_ERP":
                rows_erp.append((result_id, row))
            else:
                messagebox.showwarning(
                    "Aviso",
                    f"Linha ID {result_id} tem status '{status}'.\n\n"
                    "Selecione apenas linhas SOMENTE_BANCO ou SOMENTE_ERP.",
                    parent=self.top)
                return

        if not rows_banco and not rows_erp:
            return

        # ── Janela ────────────────────────────────────────────────────────
        win = tk.Toplevel(self.top)
        win.title("Conciliação Manual")
        win.geometry("820x640")
        win.resizable(True, True)
        win.grab_set()

        hdr = tk.Frame(win, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Conciliação Manual",
                 fg="white", bg="#1e293b",
                 font=("Arial", 11, "bold")).pack(side="left", padx=12, pady=10)
        tk.Label(hdr,
                 text="Vincule lançamentos do banco com o ERP e salve localmente como CONCILIADO.",
                 fg="#94a3b8", bg="#1e293b",
                 font=("Arial", 9)).pack(side="left", padx=4)

        body = tk.Frame(win, padx=12, pady=8)
        body.pack(fill="both", expand=True)

        # IDs dinâmicos (mutáveis conforme usuário adiciona/remove)
        ids_banco = {rid for rid, _ in rows_banco}
        ids_erp   = {rid for rid, _ in rows_erp}

        # Label de totais — atualizada em tempo real
        totais_var = tk.StringVar()
        totais_lbl = tk.Label(body, textvariable=totais_var,
                               font=("Arial", 10, "bold"), anchor="w")

        # Referências mutáveis para as árvores — preenchidas após criação
        _trees = {"banco": None, "erp": None}

        def _recalc():
            if _trees["banco"] is None or _trees["erp"] is None:
                return
            tb = te = 0.0
            for item in _trees["banco"].get_children():
                v = _trees["banco"].item(item, "values")
                try:
                    tb += abs(float(str(v[3]).replace("R$","").replace(".",
                              "").replace(",",".").strip()))
                except Exception:
                    pass
            for item in _trees["erp"].get_children():
                v = _trees["erp"].item(item, "values")
                try:
                    te += abs(float(str(v[3]).replace("R$","").replace(".",
                              "").replace(",",".").strip()))
                except Exception:
                    pass

            def brl(x):
                return f"R$ {x:,.2f}".replace(",","X").replace(".",",").replace("X",".")

            diff = round(te - tb, 2)
            if abs(diff) < 0.02:
                status_txt = "✓ Valores iguais — pronto para conciliar"
                clr = "#166534"
            elif diff < 0:
                status_txt = f"⚠ ERP menor — falta {brl(abs(diff))}"
                clr = "#92400e"
            else:
                status_txt = f"⚠ ERP maior — excede {brl(abs(diff))}"
                clr = "#92400e"
            totais_var.set(
                f"Banco: {brl(tb)}  ·  ERP: {brl(te)}  ·  {status_txt}")
            totais_lbl.config(fg=clr)

        def brl_fmt(v):
            try:
                return f"R$ {abs(float(v or 0)):,.2f}".replace(
                    ",","X").replace(".",",").replace("X",".")
            except Exception:
                return "—"

        # ── Sugestão automática (subset sum + similaridade + validação de identidade) ──
        def _score(a, b):
            sa = set(str(a).upper().split())
            sb = set(str(b).upper().split())
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / max(len(sa), len(sb))

        def _doc_clean(v):
            import re as _re
            return _re.sub(r'\D', '', str(v or ''))

        def _get_entity_info(doc=None, nome=None):
            """
            Busca entidade na entities_master por documento ou nome.
            Suporta nomes parciais: "RAFAELA RAMOS" encontra "RAFAELA GONCALVES RAMOS".
            """
            try:
                with self.repo.db.connect() as conn:
                    # 1. Match exato por documento (CPF/CNPJ)
                    if doc:
                        doc_clean = _doc_clean(doc)
                        if doc_clean and len(doc_clean) >= 8:
                            row = conn.execute(
                                """SELECT razao_social, cargo_ocupacao, categoria
                                   FROM entities_master
                                   WHERE REPLACE(REPLACE(REPLACE(documento,'.',''),'/',''),'-','') = ?
                                   LIMIT 1""",
                                (doc_clean,)
                            ).fetchone()
                            if row:
                                return dict(row)

                    if not nome or str(nome).strip() in ("", "nan"):
                        return None

                    nome_up = str(nome).upper().strip()

                    # 2. Match exato por nome
                    row = conn.execute(
                        """SELECT razao_social, cargo_ocupacao, categoria
                           FROM entities_master
                           WHERE UPPER(razao_social) = ?
                              OR UPPER(razao_social_short) = ?
                              OR UPPER(nome_busca) = ?
                           LIMIT 1""",
                        (nome_up, nome_up, nome_up)
                    ).fetchone()
                    if row:
                        return dict(row)

                    # 3. Token containment — "RAFAELA RAMOS" → "RAFAELA GONCALVES RAMOS"
                    # Extrai tokens do nome buscado (mín 4 chars para evitar ruído)
                    tokens_query = [t for t in re.findall(
                        r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ]{4,}', nome_up) if t not in
                        ('PARA', 'PELA', 'PELO', 'PAGAMENTO', 'PASSAGEM',
                         'ALMOCO', 'REEMBOLSO', 'REPASSE', 'RECEBIMENTO')]

                    if not tokens_query:
                        return None

                    # Busca todas as entidades e calcula containment
                    all_ents = conn.execute(
                        """SELECT razao_social, razao_social_short,
                                  nome_busca, cargo_ocupacao, categoria
                           FROM entities_master
                           WHERE razao_social IS NOT NULL"""
                    ).fetchall()

                    best_score = 0.0
                    best_row   = None

                    for ent in all_ents:
                        ent_tokens = set(re.findall(
                            r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ]{3,}',
                            ' '.join(filter(None, [
                                str(ent["razao_social"]       or ''),
                                str(ent["razao_social_short"] or ''),
                                str(ent["nome_busca"]         or ''),
                            ])).upper()
                        ))
                        if not ent_tokens:
                            continue

                        q_set  = set(tokens_query)
                        common = q_set & ent_tokens
                        if not common:
                            continue

                        # Containment: % dos tokens da query presentes na entidade
                        score = len(common) / len(q_set)
                        if score > best_score:
                            best_score = score
                            best_row   = ent

                    # Threshold 0.6 — "RAFAELA" (1 token) → 100% containment = 1.0
                    # "PASSAGEM RAFAELA" → "RAFAELA" = 1/1 = 1.0 (PASSAGEM filtrado)
                    if best_score >= 0.6 and best_row:
                        return dict(best_row)

            except Exception:
                pass
            return None

        def _same_person(favor_banco, doc_banco, desc_erp):
            """
            Verifica se o favorecido do banco e a descrição do ERP
            pertencem à mesma pessoa/entidade.

            Retorna (same: bool, confidence: float, reason: str)
            """
            # Palavras genéricas que não são nomes — ignora no matching
            STOP_WORDS = {
                'PAGAMENTOS', 'PAGAMENTO', 'PASSAGEM', 'ALMOCO', 'ALMOÇO',
                'REEMBOLSO', 'REPASSE', 'RECEBIMENTO', 'RECEBIMENTOS',
                'PARA', 'PELA', 'PELO', 'PIX', 'TED', 'DOC', 'ENVIADO',
                'FORNECEDORES', 'FORNECEDOR', 'PRESTACAO', 'SERVICOS',
                'INICIO', 'PAGAMENTOS', 'DRE', 'MKT', 'MARKETING',
                'VENDEDOR', 'GERENTE', 'COORDENADOR', 'ESCRITORIO',
                'VT', 'VA', 'VR', 'BONUS', 'CAMPANHA', 'CONTRATO',
            }

            def _clean_tokens(text):
                """Extrai tokens relevantes removendo stop words."""
                tokens = _tokenize(text)
                return tokens - STOP_WORDS

            # 1. Score de texto direto com tokens limpos
            clean_banco = _clean_tokens(favor_banco)
            clean_erp   = _clean_tokens(desc_erp)

            if clean_banco and clean_erp:
                common    = clean_banco & clean_erp
                # Containment: % dos tokens do banco presentes no ERP
                contain_b = len(common) / len(clean_banco)
                # Containment inverso
                contain_e = len(common) / len(clean_erp) if clean_erp else 0
                # Jaccard
                jaccard   = len(common) / len(clean_banco | clean_erp)
                text_score = max(jaccard, contain_b * 0.9, contain_e * 0.9)
            else:
                text_score = _score(favor_banco, desc_erp)

            # Threshold mais baixo (0.4) — captura "PASSAGEM MICHELL" vs "MICHELL DE MELO FERREIRA"
            if text_score >= 0.4:
                return True, text_score, "nome similar"

            # 2. CPF/CNPJ do banco aparece na descrição do ERP
            doc = _doc_clean(doc_banco)
            if doc and len(doc) >= 8 and doc in _doc_clean(desc_erp):
                return True, 0.95, "CPF/CNPJ coincide"

            # 3. Busca na base de entidades
            ent_banco = _get_entity_info(doc=doc_banco, nome=favor_banco)
            if not ent_banco:
                # Sem base — threshold conservador
                return text_score >= 0.25, max(text_score, 0.25), "sem base"

            # Extrai nome próprio da descrição ERP (ignora stop words)
            import re as _re
            words_erp = [w for w in _re.findall(
                r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ]{3,}', str(desc_erp).upper())
                if w not in STOP_WORDS and len(w) >= 4]

            ent_erp = None
            for word in words_erp:
                ent_erp = _get_entity_info(nome=word)
                if ent_erp:
                    break
                if words_erp.index(word) + 1 < len(words_erp):
                    combo = f"{word} {words_erp[words_erp.index(word)+1]}"
                    ent_erp = _get_entity_info(nome=combo)
                    if ent_erp:
                        break

            if ent_erp is None:
                return text_score >= 0.25, max(text_score, 0.3), "ERP não na base"

            # 4. Compara cargo/categoria
            cargo_banco = str(ent_banco.get("cargo_ocupacao") or "").upper()
            cargo_erp   = str(ent_erp.get("cargo_ocupacao")   or "").upper()
            nome_banco  = str(ent_banco.get("razao_social")    or "").upper()
            nome_erp    = str(ent_erp.get("razao_social")      or "").upper()

            if nome_banco and nome_erp and nome_banco == nome_erp:
                return True, 0.95, "mesma pessoa (base)"

            if cargo_banco and cargo_erp and cargo_banco == cargo_erp:
                if text_score >= 0.2:
                    return True, 0.6, f"mesmo cargo ({cargo_banco})"
                else:
                    return False, 0.2, f"mesmo cargo mas pessoas diferentes"

            return False, 0.05, f"pessoas distintas: {cargo_banco} ≠ {cargo_erp}"

        def _find_suggestions(val_banco, favor_banco, desc_banco, data_banco,
                               doc_banco=""):
            """
            Engine de sugestão com janela adaptativa e múltiplas opções.
            Retorna lista de opções: [(conf, combo, janela_dias, aviso)]
            """
            try:
                import pandas as _pd
                dt_b = _pd.to_datetime(data_banco, errors="coerce")
            except Exception:
                dt_b = None

            df_erp = self.original_df[
                self.original_df["status"].astype(str).str.upper() == "SOMENTE_ERP"
            ].copy()
            if df_erp.empty:
                return []

            try:
                from core.match_model import MatchModelManager, extract_features as _extract
                _mgr = MatchModelManager(self.repo)
                use_model = True
            except Exception:
                use_model = False

            target = round(val_banco, 2)

            def _build_deps(janela_dias):
                deps = []
                for _, r in df_erp.iterrows():
                    dias_diff = 0
                    try:
                        import pandas as _pd2
                        dt_e = _pd2.to_datetime(r.get("data_erp"), errors="coerce")
                        if dt_b is not None and not _pd2.isna(dt_e):
                            diff = abs((dt_e - dt_b).days)
                            if diff > janela_dias:
                                continue
                            dias_diff = diff
                    except Exception:
                        pass
                    try:
                        v = abs(float(r.get("valor_erp") or 0))
                    except Exception:
                        v = 0.0
                    desc_erp = str(r.get("descricao_erp") or "")
                    same, id_conf, reason = _same_person(favor_banco, doc_banco, desc_erp)
                    if not same:
                        continue
                    deps.append({
                        "rid": int(r.get("id", 0)), "row": r,
                        "value": v, "desc": desc_erp,
                        "id_conf": id_conf, "reason": reason,
                        "dias_diff": dias_diff,
                    })
                return deps

            def _subset_sum(deps):
                results = []
                def bt(idx, rem, chosen):
                    if abs(rem) < 0.02:
                        results.append(list(chosen)); return
                    if idx >= len(deps) or rem < -0.02: return
                    bt(idx+1, round(rem - deps[idx]["value"], 2), chosen + [deps[idx]])
                    bt(idx+1, rem, chosen)
                bt(0, target, [])
                return results

            def _score_combo(combo, janela_dias):
                if use_model:
                    scores = []
                    for d in combo:
                        try:
                            feats = _extract(
                                favor_banco=favor_banco, desc_banco=desc_banco,
                                doc_banco=doc_banco, desc_erp=d["desc"], favor_erp="",
                                data_banco=data_banco,
                                data_erp=str(d["row"].get("data_erp") or "")[:10],
                                valor_banco=val_banco, valor_erp=d["value"],
                            )
                            prob, _, _ = _mgr.predict(feats)
                            scores.append(prob)
                        except Exception:
                            scores.append(d["id_conf"])
                    base_conf = sum(scores) / len(scores) if scores else 0.5
                else:
                    base_conf = sum(d["id_conf"] for d in combo) / len(combo)
                penalty = 0.0 if janela_dias <= 15 else 0.15 if janela_dias <= 60 else 0.30
                size_penalty = max(0, (len(combo) - 2) * 0.03)
                return round(max(0.0, base_conf - penalty - size_penalty), 2)

            opcoes = []
            seen_rids = set()

            for janela, aviso_template in [
                (15,  None),
                (60,  "⚠ Datas distantes ({dias} dias) — possível pagamento atrasado"),
                (180, "⚠ Janela ampla ({dias} dias) — verificar se são do mesmo período"),
            ]:
                deps = _build_deps(janela)
                if not deps:
                    continue
                for combo in _subset_sum(deps):
                    rids_key = frozenset(d["rid"] for d in combo)
                    if rids_key in seen_rids:
                        continue
                    seen_rids.add(rids_key)
                    conf = _score_combo(combo, janela)
                    if conf < 0.25:
                        continue
                    max_dias = max(d["dias_diff"] for d in combo)
                    aviso = (aviso_template.format(dias=max_dias)
                             if aviso_template else None)
                    opcoes.append((conf, combo, janela, aviso))

            opcoes.sort(key=lambda x: (-x[0], x[2], len(x[1])))
            return opcoes[:3]


        # ── Tabela BANCO ───────────────────────────────────────────────────
        banco_lf = tk.LabelFrame(body, text="Lançamentos do Banco (SOMENTE_BANCO)",
                                  padx=8, pady=6)
        banco_lf.pack(fill="both", expand=True, pady=(0, 6))

        banco_cols = ("id","data","descricao","valor","favorecido")
        banco_tree = ttk.Treeview(banco_lf, columns=banco_cols,
                                   show="headings", height=4)
        for col, hd, w in [("id","ID",50),("data","Data",90),
                             ("descricao","Descrição Banco",260),
                             ("valor","Valor",90),("favorecido","Favorecido",180)]:
            banco_tree.heading(col, text=hd)
            banco_tree.column(col, width=w, anchor="w")
        banco_sb = ttk.Scrollbar(banco_lf, orient="vertical",
                                  command=banco_tree.yview)
        banco_tree.configure(yscrollcommand=banco_sb.set)
        banco_tree.pack(side="left", fill="both", expand=True)
        banco_sb.pack(side="right", fill="y")
        _trees["banco"] = banco_tree
        banco_tree.tag_configure("banco", background="#f8d7da")

        def banco_insert(rid, row):
            val = abs(float(row.get("valor_banco") or 0))
            banco_tree.insert("", "end", iid=str(rid), values=(
                rid,
                str(row.get("data_banco") or "")[:10],
                str(row.get("descricao_banco") or "")[:45],
                brl_fmt(val),
                str(row.get("favorecido_banco") or "")[:30],
            ), tags=("banco",))
            ids_banco.add(rid)
            _recalc()

        for rid, row in rows_banco:
            banco_insert(rid, row)

        banco_btn_f = tk.Frame(banco_lf)
        banco_btn_f.pack(side="bottom", fill="x", pady=(4, 0))

        def rem_banco():
            for item in banco_tree.selection():
                try:
                    rid = int(banco_tree.item(item, "values")[0])
                    ids_banco.discard(rid)
                    banco_tree.delete(item)
                except Exception:
                    pass
            _recalc()

        def add_banco_popup():
            _add_popup(
                titulo="Adicionar SOMENTE_BANCO",
                status_f="SOMENTE_BANCO",
                cols=[("id","ID",50),("data","Data Banco",90),
                      ("desc","Descrição Banco",280),
                      ("val","Valor",90),("fav","Favorecido",160)],
                get_row_vals=lambda r: (
                    int(r.get("id",0)),
                    str(r.get("data_banco",""))[:10],
                    str(r.get("descricao_banco",""))[:50],
                    brl_fmt(r.get("valor_banco")),
                    str(r.get("favorecido_banco",""))[:30],
                ),
                ids_atuais=ids_banco,
                on_add=banco_insert,
            )

        ttk.Button(banco_btn_f, text="+ Adicionar",
                   command=add_banco_popup).pack(side="left", padx=(0,6))
        ttk.Button(banco_btn_f, text="− Remover selecionado",
                   command=rem_banco).pack(side="left")
        banco_tree.bind("<Double-1>", lambda e: rem_banco())

        # ── Tabela ERP ─────────────────────────────────────────────────────
        erp_lf = tk.LabelFrame(body, text="Lançamentos do ERP (SOMENTE_ERP)",
                                padx=8, pady=6)
        erp_lf.pack(fill="both", expand=True, pady=(0, 6))

        erp_cols = ("id","data","descricao","valor","sug")
        erp_tree = ttk.Treeview(erp_lf, columns=erp_cols,
                                 show="headings", height=4)
        for col, hd, w in [("id","ID",50),("data","Data ERP",90),
                             ("descricao","Descrição ERP",340),
                             ("valor","Valor",90),("sug","",70)]:
            erp_tree.heading(col, text=hd)
            erp_tree.column(col, width=w, anchor="w")
        erp_sb = ttk.Scrollbar(erp_lf, orient="vertical",
                                command=erp_tree.yview)
        erp_tree.configure(yscrollcommand=erp_sb.set)
        erp_tree.pack(side="left", fill="both", expand=True)
        erp_sb.pack(side="right", fill="y")
        erp_tree.tag_configure("erp",  background="#fff3cd")
        erp_tree.tag_configure("sug",  background="#dff3e3")
        _trees["erp"] = erp_tree

        def erp_insert(rid, row, tag="erp", label=""):
            val = abs(float(row.get("valor_erp") or 0))
            erp_tree.insert("", "end", iid=str(rid), values=(
                rid,
                str(row.get("data_erp") or "")[:10],
                str(row.get("descricao_erp") or "")[:55],
                brl_fmt(val),
                label,
            ), tags=(tag,))
            ids_erp.add(rid)
            _recalc()

        for rid, row in rows_erp:
            erp_insert(rid, row)

        # Sugestão automática se só banco foi selecionado
        if rows_banco and not rows_erp:
            val_b  = abs(float(rows_banco[0][1].get("valor_banco") or 0))
            fav_b  = str(rows_banco[0][1].get("favorecido_banco") or "")
            desc_b = str(rows_banco[0][1].get("descricao_banco") or "")
            data_b = str(rows_banco[0][1].get("data_banco") or "")[:10]
            doc_b  = str(rows_banco[0][1].get("documento_banco") or "")

            sugestoes = _find_suggestions(val_b, fav_b, desc_b, data_b, doc_b)
            if sugestoes:
                sug_outer = tk.Frame(erp_lf, bg="#f0fdf4", padx=8, pady=6,
                                      relief="flat")
                sug_outer.pack(fill="x", side="bottom", pady=(4, 0))

                tk.Label(sug_outer,
                         text=f"💡  {len(sugestoes)} sugestão(ões) encontrada(s):",
                         font=("Arial", 9, "bold"),
                         fg="#166534", bg="#f0fdf4").pack(anchor="w", pady=(0, 4))

                for idx_s, (conf, combo, janela, aviso) in enumerate(sugestoes):
                    conf_pct = int(conf * 100)
                    conf_cor = ("#166534" if conf_pct >= 75
                                else "#92400e" if conf_pct >= 50
                                else "#64748b")
                    letra    = chr(65 + idx_s)   # A, B, C

                    card_f = tk.Frame(sug_outer, bg="#ffffff",
                                       padx=8, pady=6,
                                       relief="solid", bd=1)
                    card_f.pack(fill="x", pady=(0, 4))

                    # Cabeçalho do card
                    hdr_f = tk.Frame(card_f, bg="#ffffff")
                    hdr_f.pack(fill="x")
                    tk.Label(hdr_f,
                             text=f"Opção {letra}  —  confiança {conf_pct}%"
                                  + (f"  ·  janela {janela} dias" if janela > 15 else ""),
                             font=("Arial", 9, "bold"),
                             fg=conf_cor, bg="#ffffff").pack(side="left")

                    soma = sum(d["value"] for d in combo)
                    tk.Label(hdr_f,
                             text=f"  {brl_fmt(soma)}"
                                  + ("  ✓ fecha" if abs(soma - val_b) < 0.02 else ""),
                             font=("Arial", 9, "bold"),
                             fg="#166534", bg="#ffffff").pack(side="left")

                    # Aviso de janela ampla
                    if aviso:
                        tk.Label(card_f, text=aviso,
                                 font=("Arial", 8), fg="#92400e",
                                 bg="#ffffff", anchor="w").pack(fill="x")

                    # Itens da combinação
                    for d in combo:
                        dt_erp = str(d["row"].get("data_erp") or "")[:10]
                        dias   = d["dias_diff"]
                        diff_txt = f"  ({dias}d de distância)" if dias > 0 else ""
                        tk.Label(card_f,
                                 text=f"  ERP #{d['rid']}  ·  {dt_erp}"
                                      f"  ·  {brl_fmt(d['value'])}"
                                      f"  ·  {d['desc'][:40]}{diff_txt}",
                                 font=("Courier New", 8),
                                 fg="#166534", bg="#ffffff",
                                 anchor="w").pack(fill="x")

                    # Botão aceitar esta opção
                    def aceitar(c=combo, sf=sug_outer):
                        for d in c:
                            if str(d["rid"]) not in erp_tree.get_children():
                                erp_insert(d["rid"], d["row"],
                                           tag="sug", label="✓ sugestão")
                        sf.pack_forget()

                    ttk.Button(card_f, text=f"✓ Aceitar opção {letra}",
                               command=aceitar).pack(anchor="e", pady=(4, 0))

        erp_btn_f = tk.Frame(erp_lf)
        erp_btn_f.pack(side="bottom", fill="x", pady=(4, 0))

        def rem_erp():
            for item in erp_tree.selection():
                try:
                    rid = int(erp_tree.item(item, "values")[0])
                    ids_erp.discard(rid)
                    erp_tree.delete(item)
                except Exception:
                    pass
            _recalc()

        def add_erp_popup():
            _add_popup(
                titulo="Adicionar SOMENTE_ERP",
                status_f="SOMENTE_ERP",
                cols=[("id","ID",50),("data","Data ERP",90),
                      ("desc","Descrição ERP",360),("val","Valor",90)],
                get_row_vals=lambda r: (
                    int(r.get("id",0)),
                    str(r.get("data_erp",""))[:10],
                    str(r.get("descricao_erp",""))[:60],
                    brl_fmt(r.get("valor_erp")),
                ),
                ids_atuais=ids_erp,
                on_add=lambda rid, row: erp_insert(rid, row),
            )

        ttk.Button(erp_btn_f, text="+ Adicionar",
                   command=add_erp_popup).pack(side="left", padx=(0,6))
        ttk.Button(erp_btn_f, text="− Remover selecionado",
                   command=rem_erp).pack(side="left")
        erp_tree.bind("<Double-1>", lambda e: rem_erp())

        # ── Popup genérico de busca/adição ─────────────────────────────────
        def _add_popup(titulo, status_f, cols, get_row_vals,
                        ids_atuais, on_add):
            pop = tk.Toplevel(win)
            pop.title(titulo)
            pop.geometry("700x380")
            pop.grab_set()

            srch_var = tk.StringVar()
            sf = tk.Frame(pop, padx=10, pady=6)
            sf.pack(fill="x")
            tk.Label(sf, text="Filtrar:").pack(side="left")
            ttk.Entry(sf, textvariable=srch_var, width=45).pack(
                side="left", padx=6)

            pt = ttk.Treeview(pop, columns=[c[0] for c in cols],
                               show="headings", height=11,
                               selectmode="extended")
            for col, hd, w in cols:
                pt.heading(col, text=hd)
                pt.column(col, width=w, anchor="w")
            pf = tk.Frame(pop, padx=10)
            pf.pack(fill="both", expand=True)
            pt.pack(side="left", fill="both", expand=True)
            psb = ttk.Scrollbar(pf, orient="vertical", command=pt.yview)
            psb.pack(side="right", fill="y")
            pt.configure(yscrollcommand=psb.set)

            df_f = self.original_df[
                self.original_df["status"].astype(str).str.upper() == status_f
            ].copy()

            def load(term=""):
                for item in pt.get_children():
                    pt.delete(item)
                for _, r in df_f.iterrows():
                    rid = int(r.get("id", 0))
                    if rid in ids_atuais:
                        continue
                    vals = get_row_vals(r)
                    if term and term.lower() not in " ".join(str(v) for v in vals).lower():
                        continue
                    pt.insert("", "end", iid=str(rid), values=vals)

            load()
            srch_var.trace_add("write", lambda *a: load(srch_var.get()))

            def confirmar():
                for item in pt.selection():
                    rid = int(pt.item(item, "values")[0])
                    row_match = df_f[df_f["id"] == rid]
                    if row_match.empty: continue
                    row = row_match.iloc[0]
                    on_add(rid, row)
                pop.destroy()

            bf = tk.Frame(pop, padx=10, pady=8)
            bf.pack(fill="x")
            tk.Label(bf, text="Duplo-clique ou selecione e confirme",
                     fg="#64748b", font=("Arial", 8)).pack(side="left")
            ttk.Button(bf, text="Adicionar →",
                       command=confirmar).pack(side="right", padx=(6,0))
            ttk.Button(bf, text="Fechar",
                       command=pop.destroy).pack(side="right")
            pt.bind("<Double-1>", lambda e: confirmar())

        # ── Totais + nota + botão ──────────────────────────────────────────
        _recalc()
        totais_lbl.pack(fill="x", pady=(4, 6))

        nota_var = tk.StringVar(
            value=f"Conciliação manual: {len(rows_banco)} banco"
                  f" + {len(rows_erp)} ERP")
        tk.Label(body, text="Nota (gravada no registro):",
                 anchor="w", font=("Arial", 8)).pack(fill="x")
        ttk.Entry(body, textvariable=nota_var, width=80).pack(
            fill="x", pady=(2, 8))

        tk.Label(body,
                 text="Dica: duplo-clique em qualquer linha para removê-la.",
                 fg="#64748b", font=("Arial", 8), anchor="w").pack(fill="x")

        btn_f = tk.Frame(win, padx=12, pady=10)
        btn_f.pack(fill="x")
        status_lbl = tk.Label(btn_f, text="", fg="#475569", anchor="w")
        status_lbl.pack(side="left", fill="x", expand=True)

        def conciliar():
            all_ids = list(ids_banco) + list(ids_erp)
            if not all_ids:
                messagebox.showwarning("Aviso",
                    "Nenhum registro selecionado.", parent=win)
                return
            nota = nota_var.get().strip() or "Conciliação manual via Magical"

            import threading as _t
            btn_ok.config(state="disabled")
            status_lbl.config(text="Salvando...", fg="#475569")

            def worker():
                try:
                    ok = self.repo.bulk_update_reconciliation_results(
                        all_ids, "CONCILIADO", nota)
                except Exception as exc:
                    self.top.after(0, lambda: [
                        status_lbl.config(text=f"Erro: {exc}", fg="#b91c1c"),
                        btn_ok.config(state="normal")
                    ])
                    return

                try:
                    self.repo.log("INFO", "Conciliação manual",
                        f"run_id={self.run_id} | {len(ids_banco)} banco "
                        f"+ {len(ids_erp)} ERP → CONCILIADO | {nota}")
                except Exception:
                    pass

                def fim():
                    status_lbl.config(
                        text=f"✓ {ok} registro(s) marcados como CONCILIADO.",
                        fg="#166534")
                    btn_ok.config(state="normal")
                    self._reload_data()
                    messagebox.showinfo(
                        "Conciliação salva",
                        f"Conciliado com sucesso!\n\n"
                        f"Banco: {len(ids_banco)} linha(s)\n"
                        f"ERP: {len(ids_erp)} linha(s)\n"
                        f"Total: {ok} registro(s) → CONCILIADO\n\n"
                        f"Nota: {nota}",
                        parent=win)

                self.top.after(0, fim)

            _t.Thread(target=worker, daemon=True).start()

        btn_ok = ttk.Button(btn_f, text="✓ Conciliar localmente",
                             command=conciliar)
        btn_ok.pack(side="right", padx=(6, 0))
        ttk.Button(btn_f, text="Fechar",
                   command=win.destroy).pack(side="right")

    # ── Helpers de API ────────────────────────────────────────────────────

    def _api_post(self, url_base, token, payload):
        """Faz POST na API MeEventos. Retorna (id_api, erro_msg)."""
        try:
            import requests as _req
        except ImportError:
            return "", "requests não instalado: pip install requests"
        try:
            resp = _req.post(
                f"{url_base.rstrip('/')}/api/v1/financial",
                headers={"Authorization": token,
                         "Content-Type": "application/json",
                         "Accept": "application/json"},
                json=payload, timeout=15,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                id_api = ""
                if isinstance(data.get("data"), list) and data["data"]:
                    id_api = str(data["data"][0].get("idmovimentacao", ""))
                return id_api, ""
            return "", f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as exc:
            return "", str(exc)[:120]
        ids = self._get_selected_ids()
        if not ids:
            return

        rows_banco, rows_erp = [], []
        for result_id in ids:
            match = self.original_df[self.original_df["id"] == result_id]
            if match.empty:
                continue
            row    = match.iloc[0]
            status = str(row.get("status", "")).upper()
            if status == "SOMENTE_BANCO":
                rows_banco.append((result_id, row))
            elif status == "SOMENTE_ERP":
                rows_erp.append((result_id, row))
            else:
                messagebox.showwarning(
                    "Aviso",
                    f"Linha ID {result_id} tem status '{status}'.\n\n"
                    "Selecione apenas linhas SOMENTE_BANCO ou SOMENTE_ERP.",
                    parent=self.top
                )
                return

        if not rows_banco and not rows_erp:
            return

        from core.partner_rules import PARTNERS as _PARTNERS

        # ── Janela principal ───────────────────────────────────────────────
        win = tk.Toplevel(self.top)
        win.title("Conciliação Manual — Magical Conciliação")
        win.geometry("860x700")
        win.resizable(True, True)
        win.grab_set()

        hdr = tk.Frame(win, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Conciliação Manual",
                 fg="white", bg="#1e293b",
                 font=("Arial", 10, "bold")).pack(side="left", padx=12, pady=8)

        # ── Notebook com duas abas ─────────────────────────────────────────
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=(8, 0))

        # ══════════════════════════════════════════════════════════════════
        # ABA 1 — DESMEMBRAMENTO com engine de sugestão automática
        # ══════════════════════════════════════════════════════════════════
        tab_desm = tk.Frame(nb)
        nb.add(tab_desm, text=f"  Desmembrar ({len(rows_banco)} banco)  ")

        info_desm = tk.Frame(tab_desm, bg="#f0f9ff", padx=10, pady=8)
        info_desm.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(
            info_desm,
            text="O sistema busca automaticamente lançamentos do ERP que somam o valor do banco.\n"
                 "Aceite a sugestão ou edite manualmente.",
            bg="#f0f9ff", fg="#0369a1", justify="left"
        ).pack(anchor="w")

        desm_outer = tk.Frame(tab_desm)
        desm_outer.pack(fill="both", expand=True, padx=10, pady=8)

        desm_canvas = tk.Canvas(desm_outer, highlightthickness=0)
        desm_scroll = ttk.Scrollbar(desm_outer, orient="vertical",
                                     command=desm_canvas.yview)
        desm_canvas.configure(yscrollcommand=desm_scroll.set)
        desm_canvas.pack(side="left", fill="both", expand=True)
        desm_scroll.pack(side="right", fill="y")

        desm_frame = tk.Frame(desm_canvas)
        desm_canvas.create_window((0, 0), window=desm_frame, anchor="nw")
        desm_frame.bind("<Configure>",
                        lambda e: desm_canvas.configure(
                            scrollregion=desm_canvas.bbox("all")))

        desm_items = []  # lista de (result_id, row, sub_items)

        def fmt_brl(v):
            try:
                return f"{abs(float(v or 0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")
            except Exception:
                return "0,00"

        # ── Engine de sugestão automática ─────────────────────────────────
        def _score_similarity(text_a, text_b):
            """Score de similaridade simples entre dois textos (0-1)."""
            a = set(str(text_a).upper().split())
            b = set(str(text_b).upper().split())
            if not a or not b:
                return 0.0
            return len(a & b) / max(len(a), len(b))

        def _find_erp_suggestions(val_banco, favor_banco, desc_banco, data_banco):
            """
            Busca no SOMENTE_ERP candidatos que:
            1. Somam o valor exato (subset sum) dentro de janela de ±15 dias
            2. Têm nome/descrição similar ao favorecido do banco
            Retorna lista de (confiança, [(rid, row)]) ordenada por confiança.
            """
            try:
                import pandas as _pd
                dt_banco = _pd.to_datetime(data_banco, errors="coerce")
            except Exception:
                dt_banco = None

            df_erp = self.original_df[
                self.original_df["status"].astype(str).str.upper() == "SOMENTE_ERP"
            ].copy()

            if df_erp.empty:
                return []

            # Filtra por janela de data ±15 dias
            candidatos = []
            for _, r in df_erp.iterrows():
                try:
                    import pandas as _pd2
                    dt_erp = _pd2.to_datetime(r.get("data_erp"), errors="coerce")
                    if dt_banco is not None and not _pd2.isna(dt_erp):
                        diff_days = abs((dt_erp - dt_banco).days)
                        if diff_days > 15:
                            continue
                except Exception:
                    pass
                candidatos.append(r)

            if not candidatos:
                return []

            # Monta lista de depósitos candidatos
            deps = []
            for r in candidatos:
                try:
                    v = abs(float(r.get("valor_erp") or 0))
                except Exception:
                    v = 0.0
                deps.append({
                    "rid":   int(r.get("id", 0)),
                    "row":   r,
                    "value": v,
                    "desc":  str(r.get("descricao_erp") or ""),
                    "favor": str(r.get("favorecido_erp") or ""),
                })

            # Subset sum — encontra combinações que somam o valor do banco
            target  = round(val_banco, 2)
            results = []

            def backtrack(idx, remaining, chosen):
                if abs(remaining) < 0.02:
                    results.append(list(chosen))
                    return
                if idx >= len(deps) or remaining < -0.02:
                    return
                d = deps[idx]
                backtrack(idx + 1, round(remaining - d["value"], 2), chosen + [d])
                backtrack(idx + 1, remaining, chosen)

            backtrack(0, target, [])

            if not results:
                return []

            # Pontua cada combinação por similaridade de texto
            haystack = f"{favor_banco} {desc_banco}".upper()
            scored = []
            for combo in results:
                # Score de texto: média da similaridade de cada item
                text_scores = [
                    _score_similarity(haystack, f"{d['desc']} {d['favor']}")
                    for d in combo
                ]
                text_score = sum(text_scores) / len(text_scores) if text_scores else 0

                # Score de valor: 1.0 (já passou pelo subset sum = soma exata)
                # Score final ponderado
                confianca = round(0.5 + text_score * 0.5, 2)  # 50% base + 50% texto

                scored.append((confianca, [(d["rid"], d["row"]) for d in combo]))

            # Ordena pela maior confiança e menos itens (combinação mais simples primeiro)
            scored.sort(key=lambda x: (-x[0], len(x[1])))
            return scored[:3]  # top 3 sugestões

        # ── Renderiza cada linha SOMENTE_BANCO ─────────────────────────────
        grid_row = [0]

        for result_id, row in rows_banco:
            val_banco   = abs(float(row.get("valor_banco") or 0))
            desc_banco  = str(row.get("descricao_banco") or "").strip()
            favor_banco = str(row.get("favorecido_banco") or "").strip()
            data_banco  = str(row.get("data_banco") or "")[:10]

            sub_items = []  # (desc_var, valor_var) para envio

            # ── Cabeçalho da origem ───────────────────────────────────────
            orig_bg = "#1e293b"
            orig_f  = tk.Frame(desm_frame, bg=orig_bg)
            orig_f.grid(row=grid_row[0], column=0, columnspan=5,
                        sticky="ew", padx=2, pady=(10, 0))
            grid_row[0] += 1

            tk.Label(
                orig_f,
                text=f"  BANCO  ID {result_id} · {data_banco} · R${fmt_brl(val_banco)}",
                font=("Arial", 9, "bold"), bg=orig_bg, fg="white",
                anchor="w", padx=6, pady=4
            ).pack(side="left")

            fav_lbl = tk.Label(
                orig_f,
                text=f"{favor_banco or desc_banco}",
                font=("Arial", 9), bg=orig_bg, fg="#94a3b8",
                anchor="w", padx=4
            )
            fav_lbl.pack(side="left")

            soma_lbl = tk.Label(
                orig_f, text="",
                font=("Arial", 9, "bold"), bg=orig_bg,
                fg="#4ade80", anchor="e", padx=12
            )
            soma_lbl.pack(side="right")

            def make_recalc(si, sl, vb):
                def _recalc(*_):
                    total = 0.0
                    for dv, vv in si:
                        try: total += abs(float(vv.get().replace(",", ".")))
                        except Exception: pass
                    diff = round(total - vb, 2)
                    if abs(diff) < 0.02:
                        sl.config(text=f"✓ R${fmt_brl(vb)} fechado", fg="#4ade80")
                    elif total < vb:
                        sl.config(text=f"⚠ falta R${fmt_brl(abs(diff))}", fg="#fbbf24")
                    else:
                        sl.config(text=f"⚠ excede R${fmt_brl(abs(diff))}", fg="#f87171")
                return _recalc

            recalc = make_recalc(sub_items, soma_lbl, val_banco)

            # ── Sugestões automáticas ─────────────────────────────────────
            sugestoes = _find_erp_suggestions(
                val_banco, favor_banco, desc_banco, data_banco)

            if sugestoes:
                confianca, candidatos = sugestoes[0]
                conf_pct = int(confianca * 100)
                conf_cor = "#166534" if conf_pct >= 80 else "#92400e"

                sug_f = tk.Frame(desm_frame, bg="#f0fdf4",
                                  bd=1, relief="solid")
                sug_f.grid(row=grid_row[0], column=0, columnspan=5,
                           sticky="ew", padx=6, pady=(4, 0))
                grid_row[0] += 1

                hdr_sug = tk.Frame(sug_f, bg="#f0fdf4")
                hdr_sug.pack(fill="x", padx=8, pady=(6, 2))
                tk.Label(hdr_sug,
                         text=f"💡 Sugestão automática — confiança {conf_pct}%",
                         font=("Arial", 9, "bold"),
                         fg=conf_cor, bg="#f0fdf4").pack(side="left")

                # Lista dos candidatos sugeridos
                for crid, crow in candidatos:
                    cv = abs(float(crow.get("valor_erp") or 0))
                    cd = str(crow.get("descricao_erp") or "").strip()[:55]
                    item_f = tk.Frame(sug_f, bg="#f0fdf4")
                    item_f.pack(fill="x", padx=16, pady=1)
                    tk.Label(item_f,
                             text=f"ERP #{crid}  ·  R${fmt_brl(cv)}  ·  {cd}",
                             font=("Courier New", 8),
                             fg="#166534", bg="#f0fdf4", anchor="w"
                             ).pack(side="left")

                soma_sug = sum(abs(float(r.get("valor_erp") or 0))
                               for _, r in candidatos)
                tk.Label(sug_f,
                         text=f"  Soma: R${fmt_brl(soma_sug)}"
                              f"{'  ✓ fecha' if abs(soma_sug - val_banco) < 0.02 else ''}",
                         font=("Arial", 8, "bold"),
                         fg="#166534", bg="#f0fdf4"
                         ).pack(anchor="w", padx=16, pady=(2, 4))

                btn_sug_f = tk.Frame(sug_f, bg="#f0fdf4")
                btn_sug_f.pack(fill="x", padx=8, pady=(0, 6))

                # Área de sub-linhas (começa vazia, preenchida ao aceitar)
                sub_area_row = [grid_row[0]]

                def aceitar_sugestao(cands=candidatos, si=sub_items,
                                     sl=soma_lbl, rc=recalc, sf=sug_f,
                                     sar=sub_area_row):
                    # Limpa sub_items anteriores
                    si.clear()
                    # Remove widgets antigos desta seção
                    for w in desm_frame.grid_slaves():
                        try:
                            info = w.grid_info()
                            r = int(info.get("row", -1))
                            if sar[0] <= r < sar[0] + len(cands) + 2:
                                w.grid_remove()
                        except Exception:
                            pass

                    r = sar[0]
                    for crid, crow in cands:
                        cv   = abs(float(crow.get("valor_erp") or 0))
                        cd   = str(crow.get("descricao_erp") or "").strip()
                        dv   = tk.StringVar(value=cd)
                        vv   = tk.StringVar(value=f"{cv:.2f}".replace(".", ","))
                        vv.trace_add("write", rc)

                        tk.Label(desm_frame, text=f"ERP#{crid}",
                                 font=("Arial", 7), fg="#1e40af",
                                 width=7, anchor="e"
                                 ).grid(row=r, column=0, sticky="e", padx=2)
                        e1 = ttk.Entry(desm_frame, textvariable=dv, width=28)
                        e2 = ttk.Entry(desm_frame, textvariable=vv, width=11)
                        e1.grid(row=r, column=1, sticky="ew", padx=2, pady=1)
                        e2.grid(row=r, column=2, sticky="ew", padx=2, pady=1)

                        def rem_fn(dv_=dv, vv_=vv, e1_=e1, e2_=e2,
                                   si_=si, rc_=rc):
                            e1_.grid_remove(); e2_.grid_remove()
                            try: si_.remove((dv_, vv_))
                            except ValueError: pass
                            rc_()

                        ttk.Button(desm_frame, text="−", width=3,
                                   command=rem_fn
                                   ).grid(row=r, column=3, padx=2, pady=1)
                        si.append((dv, vv))
                        r += 1

                    # Botão adicionar manual
                    def add_manual(r_ref=[r], si_=si, rc_=rc):
                        dv = tk.StringVar()
                        vv = tk.StringVar(value="0,00")
                        vv.trace_add("write", rc_)
                        tk.Label(desm_frame, text="manual",
                                 font=("Arial", 7), fg="#94a3b8",
                                 width=7, anchor="e"
                                 ).grid(row=r_ref[0], column=0, sticky="e", padx=2)
                        e1 = ttk.Entry(desm_frame, textvariable=dv, width=28)
                        e2 = ttk.Entry(desm_frame, textvariable=vv, width=11)
                        e1.grid(row=r_ref[0], column=1, sticky="ew", padx=2, pady=1)
                        e2.grid(row=r_ref[0], column=2, sticky="ew", padx=2, pady=1)

                        def rem_fn(dv_=dv, vv_=vv, e1_=e1, e2_=e2,
                                   si_=si_, rc_=rc_):
                            e1_.grid_remove(); e2_.grid_remove()
                            try: si_.remove((dv_, vv_))
                            except ValueError: pass
                            rc_()

                        ttk.Button(desm_frame, text="−", width=3,
                                   command=rem_fn
                                   ).grid(row=r_ref[0], column=3,
                                          padx=2, pady=1)
                        si_.append((dv, vv))
                        r_ref[0] += 1
                        rc_()
                        desm_canvas.configure(
                            scrollregion=desm_canvas.bbox("all"))

                    ttk.Button(desm_frame, text="+ linha manual",
                               command=add_manual
                               ).grid(row=r, column=1, sticky="w",
                                      padx=2, pady=4)

                    sf.pack_forget()  # esconde o card de sugestão
                    rc()
                    desm_canvas.configure(
                        scrollregion=desm_canvas.bbox("all"))

                ttk.Button(btn_sug_f,
                           text="✓ Aceitar sugestão",
                           command=aceitar_sugestao,
                           style="Accent.TButton" if "Accent.TButton" in
                                  ttk.Style().theme_names() else "TButton"
                           ).pack(side="left", padx=(0, 8))

                def editar_manual(si=sub_items, rc=recalc,
                                  sf=sug_f, vb=val_banco,
                                  db=desc_banco, fb=favor_banco,
                                  sar=sub_area_row):
                    sf.pack_forget()
                    r = sar[0]
                    dv = tk.StringVar(
                        value=f"{db} | {fb}".strip(" |") if (db or fb) else "")
                    vv = tk.StringVar(value=f"{vb:.2f}".replace(".", ","))
                    vv.trace_add("write", rc)
                    tk.Label(desm_frame, text="manual",
                             font=("Arial", 7), fg="#94a3b8",
                             width=7, anchor="e"
                             ).grid(row=r, column=0, sticky="e", padx=2)
                    e1 = ttk.Entry(desm_frame, textvariable=dv, width=28)
                    e2 = ttk.Entry(desm_frame, textvariable=vv, width=11)
                    e1.grid(row=r, column=1, sticky="ew", padx=2, pady=1)
                    e2.grid(row=r, column=2, sticky="ew", padx=2, pady=1)

                    def rem_fn(dv_=dv, vv_=vv, e1_=e1, e2_=e2,
                               si_=si, rc_=rc):
                        e1_.grid_remove(); e2_.grid_remove()
                        try: si_.remove((dv_, vv_))
                        except ValueError: pass
                        rc_()

                    ttk.Button(desm_frame, text="−", width=3,
                               command=rem_fn
                               ).grid(row=r, column=3, padx=2, pady=1)
                    si.append((dv, vv))
                    rc()

                ttk.Button(btn_sug_f, text="Editar manualmente",
                           command=editar_manual).pack(side="left")

            else:
                # Sem sugestão — exibe linha manual direto
                no_sug = tk.Label(desm_frame,
                                  text="  Nenhuma sugestão automática — preencha manualmente:",
                                  font=("Arial", 8), fg="#92400e")
                no_sug.grid(row=grid_row[0], column=0, columnspan=5,
                            sticky="w", padx=6, pady=(4, 0))
                grid_row[0] += 1

                dv = tk.StringVar(
                    value=f"{desc_banco} | {favor_banco}".strip(" |"))
                vv = tk.StringVar(
                    value=f"{val_banco:.2f}".replace(".", ","))
                vv.trace_add("write", recalc)

                tk.Label(desm_frame, text="manual",
                         font=("Arial", 7), fg="#94a3b8",
                         width=7, anchor="e"
                         ).grid(row=grid_row[0], column=0,
                                sticky="e", padx=2)
                e1 = ttk.Entry(desm_frame, textvariable=dv, width=28)
                e2 = ttk.Entry(desm_frame, textvariable=vv, width=11)
                e1.grid(row=grid_row[0], column=1, sticky="ew", padx=2, pady=1)
                e2.grid(row=grid_row[0], column=2, sticky="ew", padx=2, pady=1)

                def rem_fn(dv_=dv, vv_=vv, e1_=e1, e2_=e2,
                           si_=sub_items, rc_=recalc):
                    e1_.grid_remove(); e2_.grid_remove()
                    try: si_.remove((dv_, vv_))
                    except ValueError: pass
                    rc_()

                ttk.Button(desm_frame, text="−", width=3,
                           command=rem_fn
                           ).grid(row=grid_row[0], column=3,
                                  padx=2, pady=1)
                sub_items.append((dv, vv))
                grid_row[0] += 1

                def add_manual_ns(si_=sub_items, rc_=recalc):
                    dv_ = tk.StringVar()
                    vv_ = tk.StringVar(value="0,00")
                    vv_.trace_add("write", rc_)
                    tk.Label(desm_frame, text="manual",
                             font=("Arial", 7), fg="#94a3b8",
                             width=7, anchor="e"
                             ).grid(row=grid_row[0], column=0,
                                    sticky="e", padx=2)
                    e1_ = ttk.Entry(desm_frame, textvariable=dv_, width=28)
                    e2_ = ttk.Entry(desm_frame, textvariable=vv_, width=11)
                    e1_.grid(row=grid_row[0], column=1, sticky="ew",
                             padx=2, pady=1)
                    e2_.grid(row=grid_row[0], column=2, sticky="ew",
                             padx=2, pady=1)

                    def rem2(dv__=dv_, vv__=vv_, e1__=e1_, e2__=e2_,
                             si__=si_, rc__=rc_):
                        e1__.grid_remove(); e2__.grid_remove()
                        try: si__.remove((dv__, vv__))
                        except ValueError: pass
                        rc__()

                    ttk.Button(desm_frame, text="−", width=3,
                               command=rem2
                               ).grid(row=grid_row[0], column=3,
                                      padx=2, pady=1)
                    si_.append((dv_, vv_))
                    grid_row[0] += 1
                    rc_()

                ttk.Button(desm_frame, text="+ linha manual",
                           command=add_manual_ns
                           ).grid(row=grid_row[0], column=1,
                                  sticky="w", padx=2, pady=4)
                grid_row[0] += 1

            desm_items.append((result_id, row, sub_items))

        # ══════════════════════════════════════════════════════════════════
        # ABA 2 — MESCLAGEM (SOMENTE_ERP + SOMENTE_BANCO → conciliado)
        # ══════════════════════════════════════════════════════════════════
        tab_mesc = tk.Frame(nb)
        nb.add(tab_mesc, text=f"  Mesclar ({len(rows_erp)} ERP + {len(rows_banco)} banco)  ")

        info_mesc = tk.Frame(tab_mesc, bg="#f0fdf4", padx=10, pady=8)
        info_mesc.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(
            info_mesc,
            text="Vincule lançamentos do ERP com pagamentos do banco.\n"
                 "Use os botões '+ Adicionar' para incluir outros registros da conciliação atual.",
            bg="#f0fdf4", fg="#166534", justify="left"
        ).pack(anchor="w")

        mesc_body = tk.Frame(tab_mesc, padx=10, pady=8)
        mesc_body.pack(fill="both", expand=True)

        # Sets de IDs incluídos (mutável para os botões de adicionar/remover)
        mesc_ids_erp   = {rid for rid, _ in rows_erp}
        mesc_ids_banco = {rid for rid, _ in rows_banco}

        # Label de totais — atualizada dinamicamente
        totais_var = tk.StringVar()
        totais_lbl = tk.Label(mesc_body, textvariable=totais_var,
                               font=("Arial", 9, "bold"), anchor="w")

        def _recalc_totais():
            t_erp = t_banco = 0
            for item in erp_tree.get_children():
                v = erp_tree.item(item, "values")
                try: t_erp += abs(float(str(v[3]).replace("R$","").replace(".","").replace(",",".").strip()))
                except Exception: pass
            for item in banco_tree.get_children():
                v = banco_tree.item(item, "values")
                try: t_banco += abs(float(str(v[4]).replace("R$","").replace(".","").replace(",",".").strip()))
                except Exception: pass
            diff = t_banco - t_erp
            if abs(diff) < 0.01:
                txt = "✓ Valores iguais"
                clr = "#166534"
            else:
                lado = "Banco maior" if diff > 0 else "ERP maior"
                dv   = f"R$ {abs(diff):,.2f}".replace(",","X").replace(".",",").replace("X",".")
                txt  = f"⚠ {lado} em {dv}"
                clr  = "#92400e"
            brl_erp   = f"R$ {t_erp:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            brl_banco = f"R$ {t_banco:,.2f}".replace(",","X").replace(".",",").replace("X",".")
            totais_var.set(f"ERP: {brl_erp}  |  Banco: {brl_banco}  |  {txt}")
            totais_lbl.config(fg=clr)

        # ── Tabela ERP ────────────────────────────────────────────────────
        erp_frame = tk.LabelFrame(mesc_body, text="Lançamentos SOMENTE_ERP",
                                   padx=8, pady=6)
        erp_frame.pack(fill="both", expand=True, pady=(0, 4))

        erp_cols = ("id", "data", "descricao", "valor", "remover")
        erp_tree = ttk.Treeview(erp_frame, columns=erp_cols,
                                 show="headings", height=4)
        for col, hd, w in [("id","ID",45),("data","Data ERP",90),
                             ("descricao","Descrição ERP",350),
                             ("valor","Valor ERP",100),("remover","",50)]:
            erp_tree.heading(col, text=hd)
            erp_tree.column(col, width=w, anchor="w")
        erp_tree.pack(side="left", fill="both", expand=True)
        erp_sb = ttk.Scrollbar(erp_frame, orient="vertical", command=erp_tree.yview)
        erp_sb.pack(side="right", fill="y")
        erp_tree.configure(yscrollcommand=erp_sb.set)
        erp_tree.tag_configure("erp", background="#fff3cd")

        def _erp_insert(rid, row):
            val = abs(float(row.get("valor_erp") or 0))
            erp_tree.insert("", "end", iid=str(rid), values=(
                rid,
                str(row.get("data_erp") or "")[:10],
                str(row.get("descricao_erp") or "")[:60],
                f"R$ {val:,.2f}".replace(",","X").replace(".",",").replace("X","."),
                "✕ remover"
            ), tags=("erp",))
            mesc_ids_erp.add(rid)
            _recalc_totais()

        for rid, row in rows_erp:
            _erp_insert(rid, row)

        def _remover_erp(event=None):
            sel = erp_tree.selection()
            for item in sel:
                try:
                    rid = int(erp_tree.item(item, "values")[0])
                    mesc_ids_erp.discard(rid)
                    erp_tree.delete(item)
                except Exception:
                    pass
            _recalc_totais()

        erp_tree.bind("<Double-1>", _remover_erp)

        # Botão adicionar ERP
        def _popup_adicionar_erp():
            _popup_adicionar(
                titulo="Adicionar registro SOMENTE_ERP",
                status_filtro="SOMENTE_ERP",
                cols=[("id","ID",45),("data","Data ERP",90),
                      ("descricao","Descrição ERP",320),("valor","Valor ERP",110)],
                col_val="valor_erp", col_data="data_erp",
                col_desc="descricao_erp", col_fav=None,
                ids_ja_adicionados=mesc_ids_erp,
                on_confirm=_erp_insert,
                tag="erp"
            )

        ttk.Button(erp_frame, text="+ Adicionar ERP",
                   command=_popup_adicionar_erp).pack(side="bottom", anchor="w", pady=(4,0))

        # ── Tabela Banco ──────────────────────────────────────────────────
        banco_frame = tk.LabelFrame(mesc_body, text="Lançamentos SOMENTE_BANCO",
                                     padx=8, pady=6)
        banco_frame.pack(fill="both", expand=True, pady=(0, 4))

        banco_cols = ("id", "data", "descricao", "favorecido", "valor", "remover")
        banco_tree = ttk.Treeview(banco_frame, columns=banco_cols,
                                   show="headings", height=4)
        for col, hd, w in [("id","ID",45),("data","Data Banco",90),
                             ("descricao","Descrição Banco",220),
                             ("favorecido","Favorecido",160),
                             ("valor","Valor Banco",100),("remover","",50)]:
            banco_tree.heading(col, text=hd)
            banco_tree.column(col, width=w, anchor="w")
        banco_tree.pack(side="left", fill="both", expand=True)
        banco_sb = ttk.Scrollbar(banco_frame, orient="vertical", command=banco_tree.yview)
        banco_sb.pack(side="right", fill="y")
        banco_tree.configure(yscrollcommand=banco_sb.set)
        banco_tree.tag_configure("banco", background="#f8d7da")

        def _banco_insert(rid, row):
            val = abs(float(row.get("valor_banco") or 0))
            banco_tree.insert("", "end", iid=str(rid), values=(
                rid,
                str(row.get("data_banco") or "")[:10],
                str(row.get("descricao_banco") or "")[:40],
                str(row.get("favorecido_banco") or "")[:25],
                f"R$ {val:,.2f}".replace(",","X").replace(".",",").replace("X","."),
                "✕ remover"
            ), tags=("banco",))
            mesc_ids_banco.add(rid)
            _recalc_totais()

        for rid, row in rows_banco:
            _banco_insert(rid, row)

        def _remover_banco(event=None):
            sel = banco_tree.selection()
            for item in sel:
                try:
                    rid = int(banco_tree.item(item, "values")[0])
                    mesc_ids_banco.discard(rid)
                    banco_tree.delete(item)
                except Exception:
                    pass
            _recalc_totais()

        banco_tree.bind("<Double-1>", _remover_banco)

        def _popup_adicionar_banco():
            _popup_adicionar(
                titulo="Adicionar registro SOMENTE_BANCO",
                status_filtro="SOMENTE_BANCO",
                cols=[("id","ID",45),("data","Data Banco",90),
                      ("descricao","Descrição Banco",220),
                      ("favorecido","Favorecido",160),("valor","Valor Banco",110)],
                col_val="valor_banco", col_data="data_banco",
                col_desc="descricao_banco", col_fav="favorecido_banco",
                ids_ja_adicionados=mesc_ids_banco,
                on_confirm=_banco_insert,
                tag="banco"
            )

        ttk.Button(banco_frame, text="+ Adicionar Banco",
                   command=_popup_adicionar_banco).pack(side="bottom", anchor="w", pady=(4,0))

        # ── Popup genérico de busca/adição ────────────────────────────────
        def _popup_adicionar(titulo, status_filtro, cols, col_val,
                              col_data, col_desc, col_fav,
                              ids_ja_adicionados, on_confirm, tag):
            """Popup de busca para adicionar registros à mesclagem."""
            pop = tk.Toplevel(win)
            pop.title(titulo)
            pop.geometry("760x420")
            pop.grab_set()

            tk.Label(pop, text="Pesquisar:", anchor="w").pack(
                fill="x", padx=10, pady=(8,0))
            srch_var = tk.StringVar()
            srch_entry = ttk.Entry(pop, textvariable=srch_var, width=50)
            srch_entry.pack(fill="x", padx=10, pady=(2,6))

            pop_tree = ttk.Treeview(pop, columns=[c[0] for c in cols],
                                     show="headings", height=12)
            for col, hd, w in cols:
                pop_tree.heading(col, text=hd)
                pop_tree.column(col, width=w, anchor="w")

            frm = tk.Frame(pop)
            frm.pack(fill="both", expand=True, padx=10)
            pop_tree.pack(side="left", fill="both", expand=True)
            pop_sb = ttk.Scrollbar(frm, orient="vertical", command=pop_tree.yview)
            pop_sb.pack(side="right", fill="y")
            pop_tree.configure(yscrollcommand=pop_sb.set)

            # Carrega registros disponíveis do original_df
            df_filtrado = self.original_df[
                self.original_df["status"].str.upper() == status_filtro
            ].copy()

            def _load(term=""):
                for item in pop_tree.get_children():
                    pop_tree.delete(item)
                for _, row in df_filtrado.iterrows():
                    rid = int(row.get("id", 0))
                    if rid in ids_ja_adicionados:
                        continue
                    desc = str(row.get(col_desc) or "").strip()
                    fav  = str(row.get(col_fav)  or "").strip() if col_fav else ""
                    data = str(row.get(col_data)  or "")[:10]
                    val  = abs(float(row.get(col_val) or 0))
                    val_fmt = f"R$ {val:,.2f}".replace(",","X").replace(".",",").replace("X",".")

                    if term and term.lower() not in f"{desc} {fav} {data} {rid}".lower():
                        continue

                    vals = [rid, data, desc[:50]]
                    if col_fav:
                        vals.append(fav[:25])
                    vals.append(val_fmt)

                    pop_tree.insert("", "end", iid=str(rid), values=vals)

            _load()
            srch_var.trace_add("write", lambda *a: _load(srch_var.get()))

            def confirmar():
                sel = pop_tree.selection()
                if not sel:
                    messagebox.showwarning("Aviso", "Selecione ao menos um registro.", parent=pop)
                    return
                for item in sel:
                    rid = int(pop_tree.item(item, "values")[0])
                    row_match2 = df_filtrado[df_filtrado["id"] == rid]
                    if row_match2.empty: continue
                    row = row_match2.iloc[0]
                    on_confirm(rid, row)
                pop.destroy()

            btn_row = tk.Frame(pop, padx=10, pady=8)
            btn_row.pack(fill="x")
            tk.Label(btn_row, text="Duplo-clique ou selecione e confirme",
                     fg="#64748b", font=("Arial", 8)).pack(side="left")
            ttk.Button(btn_row, text="Adicionar selecionados →",
                       command=confirmar).pack(side="right", padx=(6,0))
            ttk.Button(btn_row, text="Fechar",
                       command=pop.destroy).pack(side="right")

            pop_tree.bind("<Double-1>", lambda e: confirmar())
            srch_entry.focus()

        # Totais e nota
        _recalc_totais()
        totais_lbl.pack(fill="x", pady=(0, 4))

        nota_mesc_var = tk.StringVar(
            value=f"Mesclagem: {len(rows_erp)} ERP + {len(rows_banco)} banco — PIX agrupado")
        tk.Label(mesc_body, text="Nota:", anchor="w").pack(fill="x")
        ttk.Entry(mesc_body, textvariable=nota_mesc_var, width=70).pack(
            fill="x", pady=(2, 0))

        tk.Label(mesc_body, text="Dica: duplo-clique em qualquer linha para removê-la.",
                 fg="#64748b", font=("Arial", 8), anchor="w").pack(fill="x", pady=(4,0))

        # ══════════════════════════════════════════════════════════════════
        # PAINEL INFERIOR — nota + botões (sem API)
        # ══════════════════════════════════════════════════════════════════
        btn_frame  = tk.Frame(win, padx=10, pady=8)
        btn_frame.pack(fill="x")

        status_lbl = tk.Label(btn_frame, text="", fg="#475569", anchor="w")
        status_lbl.pack(side="left", fill="x", expand=True)

        def executar():
            aba = nb.index(nb.select())
            import threading as _threading

            btn_exec.config(state="disabled")
            status_lbl.config(text="Salvando...", fg="#475569")
            win.update()

            if aba == 0:
                # ── Aba Desmembrar ─────────────────────────────────────────
                # Coleta IDs do banco + IDs do ERP sugeridos/aceitos nas sub-linhas
                ids_banco_desm = [result_id for result_id, _, __ in desm_items]

                # IDs ERP: extrai dos labels "ERP#N" que foram aceitos
                ids_erp_desm = []
                for widget in desm_frame.grid_slaves():
                    txt = getattr(widget, 'cget', lambda x: "")(None)
                    try:
                        cfg = widget.grid_info()
                        col = int(cfg.get("column", -1))
                        if col == 0:
                            lbl_txt = widget.cget("text") if hasattr(widget, 'cget') else ""
                            if lbl_txt and lbl_txt.startswith("ERP#"):
                                try:
                                    eid = int(lbl_txt.replace("ERP#", ""))
                                    if eid not in ids_erp_desm:
                                        ids_erp_desm.append(eid)
                                except Exception:
                                    pass
                    except Exception:
                        pass

                all_ids = ids_banco_desm + ids_erp_desm
                nota = (f"Conciliação manual (desmembramento): "
                        f"{len(ids_banco_desm)} banco + {len(ids_erp_desm)} ERP")

                def worker_desm():
                    try:
                        ok = self.repo.bulk_conciliar_manual(
                            ids_banco=ids_banco_desm,
                            ids_erp=ids_erp_desm,
                            nota=nota)
                    except Exception as exc:
                        self.top.after(0, lambda: [
                            status_lbl.config(text=f"Erro: {exc}", fg="#b91c1c"),
                            btn_exec.config(state="normal")])
                        return
                    try:
                        self.repo.log("INFO", "Conciliação manual (desmembramento)",
                            f"run_id={self.run_id} | {nota}")
                    except Exception:
                        pass

                    def fim():
                        status_lbl.config(
                            text=f"✓ {ok} registro(s) conciliados.", fg="#166534")
                        btn_exec.config(state="normal")
                        self._reload_data()
                        messagebox.showinfo(
                            "Conciliado",
                            f"Conciliação salva!\n\n"
                            f"Banco: {len(ids_banco_desm)} linha(s)\n"
                            f"ERP: {len(ids_erp_desm)} linha(s)\n"
                            f"Total: {ok} → CONCILIADO\n\n"
                            f"Nota: {nota}", parent=win)

                    self.top.after(0, fim)

                _threading.Thread(target=worker_desm, daemon=True).start()

            else:
                # ── Aba Mesclar ────────────────────────────────────────────
                nota = nota_mesc_var.get().strip() or \
                       "Mesclagem manual ERP+Banco via Magical Conciliação"
                all_ids = list(mesc_ids_erp) + list(mesc_ids_banco)

                if not all_ids:
                    messagebox.showwarning("Aviso",
                        "Nenhum registro selecionado.", parent=win)
                    btn_exec.config(state="normal")
                    return

                def worker_mesc():
                    try:
                        ok = self.repo.bulk_conciliar_manual(
                            ids_banco=list(mesc_ids_banco),
                            ids_erp=list(mesc_ids_erp),
                            nota=nota)
                    except Exception as exc:
                        self.top.after(0, lambda: [
                            status_lbl.config(text=f"Erro: {exc}", fg="#b91c1c"),
                            btn_exec.config(state="normal")])
                        return
                    try:
                        self.repo.log("INFO", "Mesclagem ERP+Banco",
                            f"run_id={self.run_id} | "
                            f"{len(mesc_ids_erp)} ERP + {len(mesc_ids_banco)} banco "
                            f"→ CONCILIADO | {nota}")
                    except Exception:
                        pass

                    def fim():
                        status_lbl.config(
                            text=f"✓ {ok} linha(s) → CONCILIADO.", fg="#166534")
                        btn_exec.config(state="normal")
                        self._reload_data()
                        messagebox.showinfo(
                            "Mesclagem concluída",
                            f"Conciliado com sucesso!\n\n"
                            f"ERP: {len(mesc_ids_erp)} linha(s)\n"
                            f"Banco: {len(mesc_ids_banco)} linha(s)\n"
                            f"Total: {ok} → CONCILIADO\n\n"
                            f"Nota: {nota}", parent=win)

                    self.top.after(0, fim)

                _threading.Thread(target=worker_mesc, daemon=True).start()

        def _atualizar_btn_texto(event=None):
            aba = nb.index(nb.select())
            if aba == 0:
                btn_exec.config(text="✓ Conciliar localmente →")
            else:
                btn_exec.config(text="✓ Conciliar localmente →")

        btn_exec = ttk.Button(btn_frame, text="✓ Conciliar localmente →",
                               command=executar)
        btn_exec.pack(side="right", padx=(6, 0))
        nb.bind("<<NotebookTabChanged>>", _atualizar_btn_texto)
        ttk.Button(btn_frame, text="Fechar",
                   command=win.destroy).pack(side="right")

    # ── Helpers de API ────────────────────────────────────────────────────

    def _api_post(self, url_base, token, payload):
        """Faz POST na API MeEventos. Retorna (id_api, erro_msg)."""
        try:
            import requests as _req
        except ImportError:
            return "", "requests não instalado: pip install requests"
        try:
            resp = _req.post(
                f"{url_base.rstrip('/')}/api/v1/financial",
                headers={"Authorization": token,
                         "Content-Type": "application/json",
                         "Accept": "application/json"},
                json=payload, timeout=15,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                id_api = ""
                if isinstance(data.get("data"), list) and data["data"]:
                    id_api = str(data["data"][0].get("idmovimentacao", ""))
                return id_api, ""
            return "", f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as exc:
            return "", str(exc)[:120]

    # =========================
    # LANÇAR SOMENTE_BANCO NO ERP VIA API
    # =========================

    def _lancar_somente_banco_no_erp(self):
        """
        Lança lançamentos SOMENTE_BANCO diretamente na API do MeEventos.
        Usado quando não existe correspondente no ERP e o lançamento precisa
        ser criado lá. Após envio bem-sucedido, marca como TRATADO_MANUAL.
        """
        ids = self._get_selected_ids()
        if not ids:
            return

        rows = []
        for result_id in ids:
            match = self.original_df[self.original_df["id"] == result_id]
            if match.empty:
                continue
            row    = match.iloc[0]
            status = str(row.get("status", "")).upper()
            if status != "SOMENTE_BANCO":
                messagebox.showwarning(
                    "Aviso",
                    f"Linha ID {result_id} tem status '{status}'.\n\n"
                    "Use '↑ Lançar no ERP' apenas para registros SOMENTE_BANCO\n"
                    "que não têm correspondente no ERP e precisam ser criados lá.\n\n"
                    "Para vincular com um ERP existente, use '⇄ Conciliação manual'.",
                    parent=self.top)
                return
            rows.append((result_id, row))

        if not rows:
            return

        from core.partner_rules import PARTNERS as _PARTNERS

        # ── Janela de configuração ─────────────────────────────────────────
        win = tk.Toplevel(self.top)
        win.title("Lançar no ERP — MeEventos")
        win.geometry("620x480")
        win.resizable(False, False)
        win.grab_set()

        hdr = tk.Frame(win, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Lançar no ERP via API",
                 fg="white", bg="#1e293b",
                 font=("Arial", 10, "bold")).pack(side="left", padx=12, pady=8)
        tk.Label(hdr,
                 text="Cria o lançamento no MeEventos para registros sem correspondente.",
                 fg="#94a3b8", bg="#1e293b",
                 font=("Arial", 9)).pack(side="left", padx=4)

        body = tk.Frame(win, padx=16, pady=12)
        body.pack(fill="both", expand=True)

        # Resumo do que será lançado
        total_val = sum(abs(float(r.get("valor_banco") or 0)) for _, r in rows)
        def brl(v):
            return f"R$ {abs(float(v or 0)):,.2f}".replace(",","X").replace(".",",").replace("X",".")

        summary_f = tk.Frame(body, bg="#f8fafc", padx=12, pady=10)
        summary_f.pack(fill="x", pady=(0, 12))
        tk.Label(summary_f,
                 text=f"{len(rows)} lançamento(s) selecionado(s)  ·  Total: {brl(total_val)}",
                 font=("Arial", 10, "bold"), bg="#f8fafc", anchor="w").pack(fill="x")

        # Lista resumida dos lançamentos
        for rid, row in rows[:5]:
            data  = str(row.get("data_banco") or "")[:10]
            desc  = str(row.get("descricao_banco") or "")[:45]
            fav   = str(row.get("favorecido_banco") or "")[:25]
            val   = brl(row.get("valor_banco"))
            tk.Label(summary_f,
                     text=f"  {data}  ·  {fav or desc}  ·  {val}",
                     font=("Arial", 8), fg="#475569", bg="#f8fafc",
                     anchor="w").pack(fill="x")
        if len(rows) > 5:
            tk.Label(summary_f,
                     text=f"  ... e mais {len(rows)-5} lançamento(s)",
                     font=("Arial", 8), fg="#94a3b8", bg="#f8fafc",
                     anchor="w").pack(fill="x")

        # Tipo
        tk.Label(body, text="Tipo de lançamento:", anchor="w").pack(fill="x")
        tipo_var = tk.StringVar(value="2")
        tipo_f = tk.Frame(body)
        tipo_f.pack(fill="x", pady=(4, 12))
        ttk.Radiobutton(tipo_f, text="Despesa",  variable=tipo_var, value="2").pack(side="left", padx=(0,16))
        ttk.Radiobutton(tipo_f, text="Receita",  variable=tipo_var, value="1").pack(side="left")

        # Parceiro (token da API)
        tk.Label(body, text="Parceiro (token da API):", anchor="w").pack(fill="x")
        partner_names = [p["partner_name"] for p in _PARTNERS]
        partner_var   = tk.StringVar()
        partner_combo = ttk.Combobox(body, textvariable=partner_var,
                                      values=partner_names,
                                      state="readonly", width=35)
        partner_combo.pack(anchor="w", pady=(4, 4))

        api_lbl = tk.Label(body, text="", fg="#475569", font=("Arial", 9))
        api_lbl.pack(anchor="w", pady=(0, 12))

        def on_partner(event=None):
            nm   = partner_var.get()
            safe = nm.lower().replace(" ", "_")
            url  = self.repo.get_setting(f"erp_api_url_{safe}")   or ""
            tok  = self.repo.get_setting(f"erp_api_token_{safe}") or ""
            if url and tok:
                api_lbl.config(text=f"✓ API configurada — {url}", fg="#166534")
            elif url:
                api_lbl.config(text="⚠ URL configurada mas sem token.", fg="#92400e")
            else:
                api_lbl.config(
                    text="✗ Sem configuração. Acesse Configurações → API MeEventos.",
                    fg="#b91c1c")

        partner_combo.bind("<<ComboboxSelected>>", on_partner)

        # Restaura último parceiro usado
        try:
            last = self.repo.get_setting("erp_last_partner")
            if last:
                partner_var.set(last)
                on_partner()
        except Exception:
            pass

        # Simulação
        dry_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(body,
                        text="Simulação (não envia para a API — só valida)",
                        variable=dry_var).pack(anchor="w", pady=(0, 8))

        status_lbl = tk.Label(body, text="", fg="#475569", anchor="w",
                               font=("Arial", 9))
        status_lbl.pack(fill="x")

        # Botões
        btn_f = tk.Frame(win, padx=16, pady=10)
        btn_f.pack(fill="x")

        def lancar():
            partner = partner_var.get()
            if not partner:
                messagebox.showwarning("Aviso", "Selecione o parceiro.", parent=win)
                return

            safe  = partner.lower().replace(" ", "_")
            url   = self.repo.get_setting(f"erp_api_url_{safe}")   or ""
            token = self.repo.get_setting(f"erp_api_token_{safe}") or ""
            dry   = dry_var.get()
            tipo  = int(tipo_var.get())

            if not dry and not token:
                messagebox.showwarning(
                    "Aviso",
                    f"Token não configurado para '{partner}'.\n"
                    "Acesse Configurações → API MeEventos.",
                    parent=win)
                return

            btn_lancar.config(state="disabled")
            status_lbl.config(text="Enviando...", fg="#475569")
            win.update()

            try:
                self.repo.save_setting("erp_last_partner", partner)
            except Exception:
                pass

            import threading as _t
            _t.Thread(
                target=self._lancar_api_worker,
                args=(rows, url, token, tipo, partner, dry, win,
                      status_lbl, btn_lancar),
                daemon=True
            ).start()

        btn_lancar = ttk.Button(btn_f, text="↑ Lançar no ERP →", command=lancar)
        btn_lancar.pack(side="right", padx=(6, 0))
        ttk.Button(btn_f, text="Fechar", command=win.destroy).pack(side="right")

    def _lancar_api_worker(self, rows, url_base, token, tipocobranca,
                            partner_name, dry_run, win, status_lbl, btn_lancar):
        """Thread de lançamento via API — cria lançamentos no MeEventos."""
        try:
            batch_id = self.repo.save_erp_launch_batch(
                partner_name=partner_name,
                file_name=f"conciliacao_run_{self.run_id}",
                file_path="",
                total_rows=len(rows),
                total_enviado=0, total_simulado=0, total_erro=0,
                dry_run=dry_run,
            )
        except Exception:
            batch_id = None

        enviados = erros = 0

        for result_id, row in rows:
            try:
                import pandas as _pd
                data_fmt = _pd.to_datetime(
                    row.get("data_banco"), errors="coerce"
                ).strftime("%Y-%m-%d")
            except Exception:
                data_fmt = str(row.get("data_banco") or "")[:10]

            valor = abs(float(row.get("valor_banco") or 0))

            desc_parts = [
                str(row.get("descricao_banco") or "").strip(),
                str(row.get("favorecido_banco") or "").strip(),
            ]
            descricao = " | ".join(
                p for p in desc_parts if p and p != "nan"
            ) or "Lançamento via Magical Conciliação"

            payload = {
                "datapagamento": data_fmt,
                "valor":         round(valor, 2),
                "pago":          "sim",   # já saiu do banco
                "tipocobranca":  tipocobranca,
                "descricao":     descricao[:200],
            }

            if dry_run:
                api_status = "SIMULADO"
                id_api     = ""
                mensagem   = f"Simulado — R${valor:.2f} | {descricao[:60]}"
                enviados  += 1
            else:
                id_api, erro = self._api_post(url_base, token, payload)
                if not erro:
                    api_status = "LANCADO"
                    mensagem   = f"ID criado: {id_api}"
                    enviados  += 1
                else:
                    api_status = "ERRO_API"
                    mensagem   = erro
                    erros     += 1

            # Auditoria
            if batch_id:
                try:
                    self.repo.save_erp_launch_item(
                        batch_id=batch_id, linha_excel=result_id,
                        partner_name=partner_name, payload=payload,
                        status=api_status, id_api=id_api,
                        mensagem=mensagem, categoria="",
                    )
                except Exception:
                    pass

            # Marca como TRATADO_MANUAL se enviado/simulado com sucesso
            if api_status in ("LANCADO", "SIMULADO"):
                modo = "Simulado" if dry_run else "Enviado"
                nota = (f"{modo} ao ERP via Magical — ID: {id_api}"
                        if id_api else f"{modo} ao ERP via Magical")
                try:
                    self.repo.update_reconciliation_result_status(
                        result_id, "TRATADO_MANUAL", nota)
                except Exception:
                    pass

        def _fim():
            cor = "#166534" if erros == 0 else "#b91c1c"
            modo = "simulados" if dry_run else "lançados"
            status_lbl.config(
                text=f"Concluído — {enviados} {modo}, {erros} erro(s).",
                fg=cor)
            btn_lancar.config(state="normal")
            self._reload_data()
            messagebox.showinfo(
                "Resultado",
                f"{'Simulação' if dry_run else 'Lançamento'} concluído!\n\n"
                f"{'Simulados' if dry_run else 'Criados no ERP'}: {enviados}\n"
                f"Erros: {erros}"
                + ("\n\nNenhum dado enviado à API (modo simulação)." if dry_run else ""),
                parent=win)

        self.top.after(0, _fim)

    # =========================
    # ANALYTICS DE PARCEIRO
    # =========================

    def _maybe_show_partner_analytics(self, search_term: str, df_filtered):
        """
        Verifica se o termo de busca corresponde a um parceiro cadastrado.
        Se sim, abre o popup de analytics automaticamente.
        """
        from core.partner_rules import PARTNERS as _PARTNERS
        term_upper = search_term.upper()

        matched_partner = None
        for p in _PARTNERS:
            name = p["partner_name"].upper()
            aliases = [str(a).upper() for a in p.get("aliases", [])]
            if term_upper in name or name in term_upper:
                matched_partner = p["partner_name"]
                break
            for alias in aliases:
                if term_upper in alias or alias in term_upper:
                    matched_partner = p["partner_name"]
                    break
            if matched_partner:
                break

        if matched_partner:
            self._show_partner_analytics(matched_partner, df_filtered)

    def _show_partner_analytics(self, partner_name: str, df_filtered):
        """
        Popup de analytics financeiro do parceiro.
        Responde as perguntas que o gestor faria.
        """
        import numpy as np

        win = tk.Toplevel(self.top)
        win.title(f"Analytics — {partner_name}")
        win.geometry("720x620")
        win.resizable(True, True)

        # Header
        hdr = tk.Frame(win, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"Analytics — {partner_name}",
                 fg="white", bg="#1e293b",
                 font=("Arial", 11, "bold")).pack(side="left", padx=12, pady=10)
        tk.Label(hdr, text="Inteligência financeira do parceiro",
                 fg="#94a3b8", bg="#1e293b",
                 font=("Arial", 9)).pack(side="left", padx=4, pady=10)

        # Scroll
        canvas = tk.Canvas(win, highlightthickness=0)
        sb = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        body = tk.Frame(canvas, padx=16, pady=12)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            body_id, width=e.width))

        def section(title):
            f = tk.Frame(body)
            f.pack(fill="x", pady=(10, 4))
            tk.Label(f, text=title.upper(),
                     font=("Arial", 9, "bold"),
                     fg="#64748b").pack(side="left")
            tk.Frame(f, bg="#e2e8f0", height=1).pack(
                side="left", fill="x", expand=True, padx=(8, 0), pady=6)

        def metric_row(parent, label, value, color="#0f172a", sub=None):
            f = tk.Frame(parent, bg="#f8fafc",
                         padx=10, pady=8)
            f.pack(fill="x", pady=2)
            tk.Label(f, text=label, font=("Arial", 9),
                     fg="#475569", bg="#f8fafc", anchor="w").pack(fill="x")
            tk.Label(f, text=value, font=("Arial", 13, "bold"),
                     fg=color, bg="#f8fafc", anchor="w").pack(fill="x")
            if sub:
                tk.Label(f, text=sub, font=("Arial", 8),
                         fg="#94a3b8", bg="#f8fafc", anchor="w").pack(fill="x")

        def card_grid(parent, items):
            """items = list of (label, value, color, sub)"""
            cols = 3
            for i, (lbl, val, clr, sub) in enumerate(items):
                row = i // cols
                col = i % cols
                if col == 0:
                    fr = tk.Frame(parent)
                    fr.pack(fill="x", pady=2)
                f = tk.Frame(fr, bg="#f8fafc", padx=10, pady=8,
                             bd=0, relief="flat")
                f.pack(side="left", fill="x", expand=True,
                       padx=(0 if col == 0 else 4, 0))
                tk.Label(f, text=lbl, font=("Arial", 8),
                         fg="#475569", bg="#f8fafc", anchor="w").pack(fill="x")
                tk.Label(f, text=val, font=("Arial", 12, "bold"),
                         fg=clr, bg="#f8fafc", anchor="w").pack(fill="x")
                if sub:
                    tk.Label(f, text=sub, font=("Arial", 7),
                             fg="#94a3b8", bg="#f8fafc", anchor="w").pack(fill="x")

        def fmt(v):
            try:
                return f"R$ {abs(float(v)):,.2f}".replace(
                    ",","X").replace(".",",").replace("X",".")
            except Exception:
                return "—"

        # ── Dados da conciliação filtrada (df_filtered) ────────────────────
        df = df_filtered.copy()

        total_registros = len(df)
        conciliados     = (df["status"].astype(str).str.upper() == "CONCILIADO").sum()
        so_banco        = (df["status"].astype(str).str.upper() == "SOMENTE_BANCO").sum()
        so_erp          = (df["status"].astype(str).str.upper() == "SOMENTE_ERP").sum()
        tratados        = (df["status"].astype(str).str.upper() == "TRATADO_MANUAL").sum()

        pct_concil = int(conciliados / total_registros * 100) if total_registros > 0 else 0

        val_banco = df["valor_banco"].apply(
            lambda x: abs(float(x)) if str(x) not in ("nan","NaN","") else 0
        ).sum()
        val_erp = df["valor_erp"].apply(
            lambda x: abs(float(x)) if str(x) not in ("nan","NaN","") else 0
        ).sum()
        val_sb = df[df["status"].astype(str).str.upper() == "SOMENTE_BANCO"]["valor_banco"].apply(
            lambda x: abs(float(x)) if str(x) not in ("nan","NaN","") else 0
        ).sum()
        val_se = df[df["status"].astype(str).str.upper() == "SOMENTE_ERP"]["valor_erp"].apply(
            lambda x: abs(float(x)) if str(x) not in ("nan","NaN","") else 0
        ).sum()

        # ── Dados históricos de regras mensais ─────────────────────────────
        all_rules = self.repo.list_partner_month_rules()
        partner_rules = [r for r in all_rules
                        if r["partner_name"].upper() == partner_name.upper()]
        partner_rules.sort(key=lambda r: r["reference_month"], reverse=True)

        meses_com_regra = len(partner_rules)
        total_esperado_acum = sum(float(r.get("total_expected") or 0)
                                   for r in partner_rules)
        subtotal_medio = (
            sum(float(r.get("subtotal") or 0) for r in partner_rules) /
            meses_com_regra if meses_com_regra > 0 else 0
        )
        taxa_fixa = float(partner_rules[0].get("marketing_fee") or 0) \
            if partner_rules else 0

        # Último mês
        ultimo_mes = partner_rules[0] if partner_rules else None

        # ── Lançamentos enviados ao ERP ────────────────────────────────────
        try:
            batches = self.repo.list_erp_launch_batches(limit=200)
            erp_batches = [b for b in batches
                           if partner_name.upper() in b.get("partner_name","").upper()]
            total_erp_lancamentos = sum(b.get("total_enviado",0) or 0
                                        for b in erp_batches)
            total_erp_simulados   = sum(b.get("total_simulado",0) or 0
                                        for b in erp_batches)
        except Exception:
            total_erp_lancamentos = 0
            total_erp_simulados   = 0

        # ══════════════════════════════════════════════════════════════════
        # RENDERIZAÇÃO
        # ══════════════════════════════════════════════════════════════════

        # ── 1. Visão desta conciliação ─────────────────────────────────────
        section("Esta conciliação")
        card_grid(body, [
            ("Registros filtrados",  str(total_registros),     "#0f172a", None),
            ("Taxa de conciliação",  f"{pct_concil}%",
             "#166534" if pct_concil >= 90 else "#92400e" if pct_concil >= 70 else "#991b1b",
             f"{conciliados} conciliados"),
            ("Tratados manualmente", str(tratados),            "#1e40af", None),
            ("Só no banco",          str(so_banco),
             "#b91c1c" if so_banco > 0 else "#166534",
             fmt(val_sb) if so_banco > 0 else "—"),
            ("Só no ERP",            str(so_erp),
             "#92400e" if so_erp > 0 else "#166534",
             fmt(val_se) if so_erp > 0 else "—"),
            ("Volume banco vs ERP",
             f"{fmt(val_banco)} / {fmt(val_erp)}",
             "#0f172a", "banco / ERP"),
        ])

        # ── 2. Situação financeira atual ───────────────────────────────────
        if ultimo_mes:
            section("Situação financeira — último mês cadastrado")
            mes = ultimo_mes["reference_month"]
            esp = float(ultimo_mes.get("total_expected") or 0)
            sub = float(ultimo_mes.get("subtotal") or 0)
            taxa = float(ultimo_mes.get("marketing_fee") or 0)

            card_grid(body, [
                ("Mês de referência",   mes,        "#0f172a", None),
                ("Fatura (subtotal)",   fmt(sub),   "#0f172a", "base de cálculo"),
                ("Taxa de gestão",      fmt(taxa),  "#0f172a", "estrutura + marketing"),
                ("Total a receber",     fmt(esp),   "#166534", "subtotal + taxa"),
                ("Saldo pendente banco",fmt(val_sb),"#b91c1c" if val_sb > 0 else "#166534",
                 "SOMENTE_BANCO nesta conciliação"),
                ("Saldo pendente ERP",  fmt(val_se),"#92400e" if val_se > 0 else "#166534",
                 "SOMENTE_ERP nesta conciliação"),
            ])

        # ── 3. Histórico de recebimentos ───────────────────────────────────
        if partner_rules:
            section(f"Histórico — {meses_com_regra} meses cadastrados")

            hist_frame = tk.Frame(body)
            hist_frame.pack(fill="x", pady=4)

            # Header da tabela histórica
            hdr_cols = [("Mês", 80), ("Subtotal", 110),
                        ("Taxa", 90), ("Total esperado", 120),
                        ("Observação", 200)]
            for col, w in hdr_cols:
                tk.Label(hist_frame, text=col, font=("Arial", 8, "bold"),
                         fg="#475569", bg="#e2e8f0",
                         width=w//8, anchor="w", padx=4, pady=3
                         ).pack(side="left")

            for rule in partner_rules[:6]:  # últimos 6 meses
                row_f = tk.Frame(body,
                                 bg="#f8fafc" if partner_rules.index(rule) % 2 == 0
                                 else "#ffffff")
                row_f.pack(fill="x")
                vals = [
                    rule["reference_month"],
                    fmt(rule.get("subtotal")),
                    fmt(rule.get("marketing_fee")),
                    fmt(rule.get("total_expected")),
                    rule.get("notes") or "—",
                ]
                for i, (v, (_, w)) in enumerate(zip(vals, hdr_cols)):
                    tk.Label(row_f, text=v, font=("Arial", 8),
                             fg="#0f172a", bg=row_f["bg"],
                             width=w//8, anchor="w", padx=4, pady=3
                             ).pack(side="left")

            # Estatísticas do histórico
            if meses_com_regra >= 2:
                subtotais = [float(r.get("subtotal") or 0) for r in partner_rules]
                st_max    = max(subtotais)
                st_min    = min(subtotais)
                st_med    = sum(subtotais) / len(subtotais)
                variacao  = ((st_max - st_min) / st_med * 100) if st_med > 0 else 0

                section("Estatísticas do histórico")
                card_grid(body, [
                    ("Maior fatura",       fmt(st_max), "#0f172a",
                     partner_rules[subtotais.index(st_max)]["reference_month"]),
                    ("Menor fatura",       fmt(st_min), "#0f172a",
                     partner_rules[subtotais.index(st_min)]["reference_month"]),
                    ("Média mensal",       fmt(st_med), "#0f172a", f"{meses_com_regra} meses"),
                    ("Variação histórica", f"{variacao:.1f}%",
                     "#166534" if variacao < 20 else "#92400e" if variacao < 40 else "#b91c1c",
                     "max - min / média"),
                    ("Taxa fixa mensal",   fmt(taxa_fixa), "#0f172a",
                     "gestão + marketing"),
                    ("Total acumulado",    fmt(total_esperado_acum), "#0f172a",
                     f"{meses_com_regra} meses"),
                ])

        # ── 4. Atividade no ERP via API ────────────────────────────────────
        if total_erp_lancamentos > 0 or total_erp_simulados > 0:
            section("Lançamentos via API")
            card_grid(body, [
                ("Enviados ao ERP",   str(total_erp_lancamentos), "#166534", None),
                ("Simulações",        str(total_erp_simulados),   "#1e40af", None),
                ("Batches no histórico", str(len(erp_batches)),   "#0f172a", None),
            ])

        # ── 5. Diagnóstico para o gestor ───────────────────────────────────
        section("Diagnóstico")
        diag_frame = tk.Frame(body, bg="#f0f9ff",
                               bd=0, padx=12, pady=10)
        diag_frame.pack(fill="x", pady=(0, 12))

        diagnosticos = []

        if pct_concil >= 95:
            diagnosticos.append(("✓", "#166534",
                f"Conciliação saudável — {pct_concil}% dos registros conciliados."))
        elif pct_concil >= 80:
            diagnosticos.append(("⚠", "#92400e",
                f"Conciliação parcial — {pct_concil}% conciliados. "
                f"Verifique {so_banco + so_erp} pendências."))
        else:
            diagnosticos.append(("✗", "#b91c1c",
                f"Conciliação crítica — apenas {pct_concil}% conciliados. "
                f"Atenção imediata necessária."))

        if val_sb > 0:
            diagnosticos.append(("⚠", "#92400e",
                f"{so_banco} lançamento(s) no banco sem correspondência no ERP "
                f"({fmt(val_sb)}). Verificar se foram lançados."))

        if val_se > 0:
            diagnosticos.append(("⚠", "#92400e",
                f"{so_erp} lançamento(s) no ERP sem correspondência no banco "
                f"({fmt(val_se)}). Verificar se foram pagos/recebidos."))

        if meses_com_regra >= 2:
            subtotais = [float(r.get("subtotal") or 0) for r in partner_rules]
            ultimo_sub = subtotais[0]
            penultimo  = subtotais[1] if len(subtotais) > 1 else ultimo_sub
            if penultimo > 0:
                var_mes = (ultimo_sub - penultimo) / penultimo * 100
                if abs(var_mes) > 15:
                    sinal = "alta" if var_mes > 0 else "queda"
                    diagnosticos.append(("⚠", "#92400e" if var_mes < 0 else "#1e40af",
                        f"Variação de fatura: {sinal} de {abs(var_mes):.1f}% "
                        f"em relação ao mês anterior "
                        f"({fmt(penultimo)} → {fmt(ultimo_sub)})."))

        if not diagnosticos:
            diagnosticos.append(("✓", "#166534",
                "Nenhuma inconsistência detectada para este parceiro."))

        for icon, color, msg in diagnosticos:
            df_row = tk.Frame(diag_frame, bg="#f0f9ff")
            df_row.pack(fill="x", pady=2)
            tk.Label(df_row, text=icon, font=("Arial", 11, "bold"),
                     fg=color, bg="#f0f9ff", width=2).pack(side="left")
            tk.Label(df_row, text=msg, font=("Arial", 9),
                     fg="#0f172a", bg="#f0f9ff", anchor="w",
                     wraplength=620, justify="left").pack(side="left", fill="x")

        # Botão fechar
        tk.Button(win, text="Fechar",
                  command=win.destroy,
                  font=("Arial", 9),
                  relief="flat", bg="#1e293b", fg="white",
                  padx=20, pady=6).pack(pady=(0, 12))

    # =========================
    # HELPERS DE FORMATAÇÃO
    # =========================
    @staticmethod
    def _safe_str(value):
        if value is None:
            return ""
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""
        return text

    @staticmethod
    def _fmt_date(value):
        try:
            dt = pd.to_datetime(value, errors="coerce")
            if pd.isna(dt):
                return ""
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return ""

    @staticmethod
    def _fmt_money_excel(value):
        try:
            v = float(value)
        except Exception:
            return ""
        sinal = "- " if v < 0 else ""
        v = abs(v)
        return f"{sinal}R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")