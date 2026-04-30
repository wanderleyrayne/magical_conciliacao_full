import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime

from core.settings_manager import SettingsManager, DEFAULT_VISIBLE_COLUMNS
from database.repository import SystemRepository
from core.loader import load_tabular_file, summarize_dataframe
from core.normalizer import Normalizer
from core.partner_rules import PARTNERS


class SettingsWindow:
    ALL_COLUMNS = [
        ("tipo_conciliacao", "Tipo"),
        ("status", "Status"),
        ("diferenca_dias", "Dif. Dias"),
        ("data_erp", "Data ERP"),
        ("data_banco", "Data Banco"),
        ("descricao_erp", "Descrição ERP"),
        ("descricao_banco", "Descrição Banco"),
        ("favorecido_banco", "Favorecido Banco"),
        ("documento_banco", "Documento Banco"),
        ("entidade_encontrada", "Entidade Encontrada"),
        ("categoria_entidade", "Categoria Entidade"),
        ("valor_erp", "Valor ERP"),
        ("valor_banco", "Valor Banco"),
        ("manual_note", "Observação"),
    ]

    def __init__(self, master, db_path="data/conciliacao.db", on_save_callback=None):
        self.top = tk.Toplevel(master)
        self.top.title("Configurações")
        self.top.geometry("760x700")
        self.top.minsize(620, 560)

        self.on_save_callback = on_save_callback
        self.db_path = db_path
        self.settings = SettingsManager(db_path)
        self.repo = SystemRepository(db_path)
        self.visible_columns = set(self.settings.get_visible_columns())
        self.vars = {}

        self.selected_entities_path = None

        self._build_layout()
        self._load_entities_info()
        self._load_monthly_rules()

    def _build_layout(self):
        header = tk.Frame(self.top, bg="#1e293b", height=48)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Configurações",
            fg="white",
            bg="#1e293b",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=12, pady=10)

        body = tk.Frame(self.top)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True)

        # =========================
        # ABA COLUNAS
        # =========================
        tab_columns = tk.Frame(notebook)
        notebook.add(tab_columns, text="Colunas")

        tk.Label(
            tab_columns,
            text="Escolha quais colunas devem aparecer nas telas de resultado e histórico.",
            anchor="w",
            justify="left"
        ).pack(fill="x", pady=(10, 10), padx=10)

        canvas = tk.Canvas(tab_columns, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab_columns, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=(0, 10))
        scrollbar.pack(side="right", fill="y", padx=(0, 10), pady=(0, 10))

        for key, label in self.ALL_COLUMNS:
            var = tk.BooleanVar(value=(key in self.visible_columns))
            self.vars[key] = var
            cb = ttk.Checkbutton(scrollable_frame, text=label, variable=var)
            cb.pack(anchor="w", pady=4, padx=4)

        actions = tk.Frame(tab_columns)
        actions.pack(fill="x", pady=(0, 10), padx=10)

        ttk.Button(actions, text="Marcar todas", command=self._check_all).pack(side="left")
        ttk.Button(actions, text="Desmarcar todas", command=self._uncheck_all).pack(side="left", padx=6)
        ttk.Button(actions, text="Restaurar padrão", command=self._restore_default).pack(side="left", padx=6)

        # =========================
        # ABA BASE DE ENTIDADES
        # =========================
        tab_entities = tk.Frame(notebook)
        notebook.add(tab_entities, text="Base de entidades")

        info_frame = tk.LabelFrame(tab_entities, text="Informações da base", padx=12, pady=12)
        info_frame.pack(fill="x", padx=10, pady=(10, 10))

        self.entities_total_label = tk.Label(info_frame, text="Entidades em base: 0", anchor="w")
        self.entities_total_label.pack(fill="x", pady=(0, 6))

        self.entities_updated_label = tk.Label(info_frame, text="Última atualização: -", anchor="w")
        self.entities_updated_label.pack(fill="x")

        import_frame = tk.LabelFrame(tab_entities, text="Atualização por arquivo", padx=12, pady=12)
        import_frame.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(
            import_frame,
            text="Importe um arquivo de entidades para atualizar a base persistida do sistema.",
            anchor="w",
            justify="left"
        ).pack(fill="x", pady=(0, 10))

        self.entities_file_label = tk.Label(import_frame, text="Nenhum arquivo selecionado", fg="#64748b", anchor="w")
        self.entities_file_label.pack(fill="x", pady=(0, 8))

        buttons_frame = tk.Frame(import_frame)
        buttons_frame.pack(fill="x")

        ttk.Button(buttons_frame, text="Selecionar arquivo", command=self._select_entities_file).pack(side="left")
        ttk.Button(buttons_frame, text="Atualizar base", command=self._import_entities_file).pack(side="left", padx=8)

        ttk.Separator(buttons_frame, orient="vertical").pack(side="left", fill="y", padx=12)

        ttk.Button(
            buttons_frame,
            text="⬆ Importar base_entidades.xlsx",
            command=self._import_base_entidades
        ).pack(side="left")

        # =========================
        # ABA REGRAS MENSAIS
        # =========================
        tab_rules = tk.Frame(notebook)
        notebook.add(tab_rules, text="Regras mensais")

        form_frame = tk.LabelFrame(tab_rules, text="Cadastro de regra mensal", padx=12, pady=12)
        form_frame.pack(fill="x", padx=10, pady=(10, 10))

        tk.Label(form_frame, text="Mês de referência:").grid(row=0, column=0, sticky="w", pady=4)
        self.rule_month_var = tk.StringVar(value=datetime.now().strftime("%Y-%m"))
        ttk.Entry(form_frame, textvariable=self.rule_month_var, width=18).grid(row=0, column=1, sticky="w", pady=4, padx=8)

        tk.Label(form_frame, text="Formato: YYYY-MM (ex.: 2026-03)").grid(
            row=0, column=2, sticky="w", pady=4
        )

        tk.Label(form_frame, text="Parceiro:").grid(row=1, column=0, sticky="w", pady=4)
        self.rule_partner_var = tk.StringVar()
        partner_names = [p["partner_name"] for p in PARTNERS if not p["is_hub"]]
        self.rule_partner_combo = ttk.Combobox(
            form_frame,
            textvariable=self.rule_partner_var,
            values=partner_names,
            state="readonly",
            width=30
        )
        self.rule_partner_combo.grid(row=1, column=1, sticky="w", pady=4, padx=8)

        tk.Label(form_frame, text="Subtotal (fatura):").grid(row=2, column=0, sticky="w", pady=4)
        self.rule_subtotal_var = tk.StringVar()
        self.rule_subtotal_entry = ttk.Entry(form_frame, textvariable=self.rule_subtotal_var, width=18)
        self.rule_subtotal_entry.grid(row=2, column=1, sticky="w", pady=4, padx=8)

        tk.Label(form_frame, text="Taxa estrutura/marketing:").grid(row=3, column=0, sticky="w", pady=4)
        self.rule_fee_var = tk.StringVar()
        self.rule_fee_entry = ttk.Entry(form_frame, textvariable=self.rule_fee_var, width=18)
        self.rule_fee_entry.grid(row=3, column=1, sticky="w", pady=4, padx=8)

        tk.Label(form_frame, text="Total a pagar:").grid(row=4, column=0, sticky="w", pady=4)
        self.rule_total_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.rule_total_var, width=18, state="readonly").grid(
            row=4, column=1, sticky="w", pady=4, padx=8
        )

        tk.Label(form_frame, text="Observação:").grid(row=5, column=0, sticky="w", pady=4)
        self.rule_notes_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.rule_notes_var, width=45).grid(
            row=5, column=1, columnspan=2, sticky="w", pady=4, padx=8
        )

        self.rule_subtotal_var.trace_add("write", lambda *args: self._recalculate_rule_total())
        self.rule_fee_var.trace_add("write", lambda *args: self._recalculate_rule_total())

        self.rule_subtotal_entry.bind("<FocusOut>", lambda e: self._format_money_field(self.rule_subtotal_var))
        self.rule_fee_entry.bind("<FocusOut>", lambda e: self._format_money_field(self.rule_fee_var))

        buttons_rules = tk.Frame(form_frame)
        buttons_rules.grid(row=6, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Button(buttons_rules, text="Salvar regra", command=self._save_monthly_rule).pack(side="left")
        ttk.Button(buttons_rules, text="Limpar campos", command=self._clear_rule_form).pack(side="left", padx=8)
        ttk.Button(buttons_rules, text="Atualizar lista", command=self._load_monthly_rules).pack(side="left", padx=8)

        ttk.Separator(buttons_rules, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Button(
            buttons_rules, text="⬆ Importar arquivo (CSV/Excel/TXT)",
            command=self._import_rules_from_file
        ).pack(side="left")

        # =========================
        # ABA CONCILIAÇÃO
        # =========================
        tab_concil = tk.Frame(notebook)
        notebook.add(tab_concil, text="Conciliação")

        concil_frame = tk.LabelFrame(tab_concil, text="Tolerância de data", padx=12, pady=12)
        concil_frame.pack(fill="x", padx=10, pady=(10, 10))

        tk.Label(
            concil_frame,
            text=(
                "Número máximo de dias de diferença entre a data do ERP e a data do banco\n"
                "para que dois lançamentos sejam considerados o mesmo. Valores maiores aumentam\n"
                "o número de conciliações automáticas, mas podem gerar falsos positivos."
            ),
            anchor="w",
            justify="left",
            fg="#475569",
        ).pack(fill="x", pady=(0, 12))

        tolerance_row = tk.Frame(concil_frame)
        tolerance_row.pack(fill="x")

        tk.Label(tolerance_row, text="Tolerância:", width=14, anchor="w").pack(side="left")

        self.tolerance_var = tk.IntVar(value=self.settings.get_date_tolerance())
        self.tolerance_label = tk.Label(
            tolerance_row,
            text=f"{self.tolerance_var.get()} dias",
            width=8,
            anchor="w",
            font=("Arial", 10, "bold"),
        )
        self.tolerance_label.pack(side="left")

        scale = ttk.Scale(
            concil_frame,
            from_=0,
            to=10,
            orient="horizontal",
            variable=self.tolerance_var,
            command=self._on_tolerance_change,
        )
        scale.pack(fill="x", pady=(8, 0))

        ticks = tk.Frame(concil_frame)
        ticks.pack(fill="x")
        for i in range(11):
            tk.Label(ticks, text=str(i), font=("Arial", 8), fg="#94a3b8").pack(side="left", expand=True)

        hint_frame = tk.Frame(concil_frame)
        hint_frame.pack(fill="x", pady=(12, 0))
        self.tolerance_hint = tk.Label(
            hint_frame,
            text=self._tolerance_hint(self.tolerance_var.get()),
            anchor="w",
            fg="#475569",
            font=("Arial", 9, "italic"),
        )
        self.tolerance_hint.pack(fill="x")

        ttk.Button(
            concil_frame,
            text="Restaurar padrão (3 dias)",
            command=lambda: self._set_tolerance(3),
        ).pack(anchor="w", pady=(12, 0))

        # =========================
        # ABA API MEEVENTOS
        # =========================
        tab_api = tk.Frame(notebook)
        notebook.add(tab_api, text="API MeEventos")

        tk.Label(
            tab_api,
            text="Configure a URL e o Token de acesso à API para cada parceiro.",
            anchor="w", fg="#475569"
        ).pack(fill="x", padx=10, pady=(10, 6))

        # Tabela de configuração por parceiro
        api_table_frame = tk.Frame(tab_api)
        api_table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        api_cols = ("partner", "url", "token")
        self.api_tree = ttk.Treeview(
            api_table_frame, columns=api_cols, show="headings", height=12,
            selectmode="browse"
        )
        self.api_tree.pack(side="left", fill="both", expand=True)

        api_scroll = ttk.Scrollbar(api_table_frame, orient="vertical", command=self.api_tree.yview)
        api_scroll.pack(side="right", fill="y")
        self.api_tree.configure(yscrollcommand=api_scroll.set)

        self.api_tree.heading("partner", text="Parceiro")
        self.api_tree.heading("url",     text="URL base")
        self.api_tree.heading("token",   text="Token (oculto)")
        self.api_tree.column("partner", width=140, anchor="w")
        self.api_tree.column("url",     width=340, anchor="w")
        self.api_tree.column("token",   width=180, anchor="w")

        self.api_tree.bind("<<TreeviewSelect>>", self._on_api_row_select)

        # Formulário de edição
        api_form = tk.LabelFrame(tab_api, text="Editar configuração do parceiro selecionado",
                                  padx=12, pady=10)
        api_form.pack(fill="x", padx=10, pady=(0, 10))

        tk.Label(api_form, text="Parceiro:", width=10, anchor="w").grid(
            row=0, column=0, sticky="w", pady=4)
        self.api_partner_label = tk.Label(api_form, text="—", anchor="w", fg="#334155",
                                           font=("Arial", 10, "bold"))
        self.api_partner_label.grid(row=0, column=1, columnspan=3, sticky="w", pady=4)

        tk.Label(api_form, text="URL base:", width=10, anchor="w").grid(
            row=1, column=0, sticky="w", pady=4)
        self.api_url_var = tk.StringVar()
        ttk.Entry(api_form, textvariable=self.api_url_var, width=55).grid(
            row=1, column=1, columnspan=3, sticky="w", padx=(8, 0), pady=4)

        tk.Label(api_form, text="Token:", width=10, anchor="w").grid(
            row=2, column=0, sticky="w", pady=4)
        self.api_token_var = tk.StringVar()
        self._api_token_entry = ttk.Entry(
            api_form, textvariable=self.api_token_var, width=55, show="*")
        self._api_token_entry.grid(row=2, column=1, columnspan=2, sticky="w",
                                    padx=(8, 4), pady=4)

        self._api_show_token_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            api_form, text="Mostrar",
            variable=self._api_show_token_var,
            command=lambda: self._api_token_entry.config(
                show="" if self._api_show_token_var.get() else "*")
        ).grid(row=2, column=3, sticky="w", pady=4)

        api_btn_frame = tk.Frame(api_form)
        api_btn_frame.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))

        ttk.Button(api_btn_frame, text="Salvar este parceiro",
                   command=self._save_api_partner).pack(side="left")
        ttk.Button(api_btn_frame, text="Limpar",
                   command=self._clear_api_form).pack(side="left", padx=8)

        # Carrega os dados na tabela
        self._load_api_table()

        list_frame = tk.LabelFrame(tab_rules, text="Regras cadastradas", padx=12, pady=12)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("reference_month", "partner_name", "subtotal", "marketing_fee", "total_expected")
        self.rules_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=10)
        self.rules_tree.pack(side="left", fill="both", expand=True)

        rules_scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.rules_tree.yview)
        rules_scroll.pack(side="right", fill="y")
        self.rules_tree.configure(yscrollcommand=rules_scroll.set)

        headings = {
            "reference_month": "Mês",
            "partner_name": "Parceiro",
            "subtotal": "Subtotal",
            "marketing_fee": "Taxa",
            "total_expected": "Total a pagar",
        }

        widths = {
            "reference_month": 100,
            "partner_name": 180,
            "subtotal": 120,
            "marketing_fee": 120,
            "total_expected": 130,
        }

        for col in cols:
            self.rules_tree.heading(col, text=headings[col])
            self.rules_tree.column(col, width=widths[col], anchor="center")

        # =========================
        # ABA BACKUP
        # =========================
        tab_backup = tk.Frame(notebook)
        notebook.add(tab_backup, text="Backup")

        tk.Label(
            tab_backup,
            text="Backups do banco de dados (conciliacao.db).\n"
                 "O sistema faz backup automático diário. Aqui você pode fazer manualmente e restaurar.",
            anchor="w", fg="#475569", justify="left"
        ).pack(fill="x", padx=10, pady=(10, 6))

        # Botões de ação
        backup_btn_f = tk.Frame(tab_backup)
        backup_btn_f.pack(fill="x", padx=10, pady=(0, 8))

        def _fazer_backup():
            try:
                from backup import make_backup
                dest = make_backup(label="manual")
                if dest:
                    messagebox.showinfo(
                        "Backup criado",
                        f"Backup salvo com sucesso!\n\n{dest.name}",
                        parent=self.top)
                    _load_backups()
                else:
                    messagebox.showerror("Erro", "Banco não encontrado.", parent=self.top)
            except Exception as exc:
                messagebox.showerror("Erro", str(exc), parent=self.top)

        def _abrir_pasta():
            try:
                from backup import _backup_dir
                import subprocess
                subprocess.Popen(f'explorer "{_backup_dir()}"')
            except Exception:
                pass

        ttk.Button(backup_btn_f, text="💾 Fazer backup agora",
                   command=_fazer_backup).pack(side="left", padx=(0, 8))
        ttk.Button(backup_btn_f, text="📁 Abrir pasta de backups",
                   command=_abrir_pasta).pack(side="left")

        # Tabela de backups existentes
        backup_list_f = tk.LabelFrame(tab_backup, text="Backups disponíveis",
                                       padx=8, pady=8)
        backup_list_f.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        bk_cols = ("datetime", "name", "size", "label")
        self.backup_tree = ttk.Treeview(backup_list_f, columns=bk_cols,
                                         show="headings", height=10)
        for col, hd, w in [
            ("datetime", "Data/Hora",    130),
            ("name",     "Arquivo",      260),
            ("size",     "Tamanho",       80),
            ("label",    "Tipo",         100),
        ]:
            self.backup_tree.heading(col, text=hd)
            self.backup_tree.column(col, width=w, anchor="w")

        bk_sb = ttk.Scrollbar(backup_list_f, orient="vertical",
                               command=self.backup_tree.yview)
        self.backup_tree.configure(yscrollcommand=bk_sb.set)
        self.backup_tree.pack(side="left", fill="both", expand=True)
        bk_sb.pack(side="right", fill="y")

        # Botões de restauração
        restore_btn_f = tk.Frame(tab_backup)
        restore_btn_f.pack(fill="x", padx=10, pady=(0, 6))

        def _restaurar():
            sel = self.backup_tree.selection()
            if not sel:
                messagebox.showwarning("Aviso", "Selecione um backup para restaurar.", parent=self.top)
                return
            nome = self.backup_tree.item(sel[0], "values")[1]
            if not messagebox.askyesno(
                "Confirmar restauração",
                f"Restaurar o backup:\n{nome}\n\n"
                "O banco atual será substituído.\n"
                "Um backup de segurança será criado automaticamente antes.\n\n"
                "Confirma?",
                parent=self.top
            ):
                return
            try:
                from backup import restore_backup, _backup_dir
                backup_path = _backup_dir() / nome
                ok = restore_backup(backup_path)
                if ok:
                    messagebox.showinfo(
                        "Restauração concluída",
                        "Banco restaurado com sucesso!\n\n"
                        "Reinicie o sistema para aplicar.",
                        parent=self.top)
                else:
                    messagebox.showerror("Erro", "Falha ao restaurar o backup.", parent=self.top)
            except Exception as exc:
                messagebox.showerror("Erro", str(exc), parent=self.top)

        ttk.Button(restore_btn_f, text="↩ Restaurar selecionado",
                   command=_restaurar).pack(side="left")

        def _load_backups():
            for item in self.backup_tree.get_children():
                self.backup_tree.delete(item)
            try:
                from backup import list_backups_info
                for b in list_backups_info():
                    self.backup_tree.insert("", "end", values=(
                        b["datetime"],
                        b["name"],
                        f"{b['size_kb']:.0f} KB",
                        b["label"],
                    ))
            except Exception:
                pass

        _load_backups()

        footer = tk.Frame(self.top, bd=1, relief="solid")
        footer.pack(fill="x", side="bottom")

        footer_inner = tk.Frame(footer)
        footer_inner.pack(fill="x", padx=12, pady=10)

        ttk.Button(footer_inner, text="Fechar", command=self.top.destroy).pack(side="right")
        ttk.Button(footer_inner, text="Salvar", command=self._save).pack(side="right", padx=8)

        # Botão verificar atualizações — lado esquerdo
        def _check_updates():
            try:
                from updater import check_for_updates
                check_for_updates(self.top, silent=False)
            except Exception as exc:
                from tkinter import messagebox
                messagebox.showerror("Erro", f"Updater indisponível:\n{exc}",
                                     parent=self.top)

        ttk.Button(footer_inner, text="🔄 Verificar atualizações",
                   command=_check_updates).pack(side="left")

        def _open_logs():
            try:
                from logger import log as _log
                import subprocess
                subprocess.Popen(f'explorer "{_log.log_dir()}"')
            except Exception:
                pass

        ttk.Button(footer_inner, text="📋 Ver logs",
                   command=_open_logs).pack(side="left", padx=(8, 0))

    # =========================
    # API MEEVENTOS
    # =========================
    def _api_key(self, partner_name: str) -> tuple:
        """Retorna as chaves de banco para URL e token de um parceiro."""
        safe = partner_name.lower().replace(" ", "_")
        return f"erp_api_url_{safe}", f"erp_api_token_{safe}"

    def _load_api_table(self):
        """Popula a tabela com todos os parceiros e suas configurações salvas."""
        for item in self.api_tree.get_children():
            self.api_tree.delete(item)

        for partner in PARTNERS:
            name = partner["partner_name"]
            key_url, key_token = self._api_key(name)
            url   = self.repo.get_setting(key_url)   or ""
            token = self.repo.get_setting(key_token) or ""
            token_display = ("*" * 8 + token[-4:]) if len(token) > 4 else ("*" * len(token) if token else "—")
            url_display   = url if url else "— não configurada"
            self.api_tree.insert("", "end", iid=name, values=(name, url_display, token_display))

    def _on_api_row_select(self, event=None):
        """Preenche o formulário com os dados do parceiro selecionado."""
        selected = self.api_tree.selection()
        if not selected:
            return
        name = selected[0]
        key_url, key_token = self._api_key(name)
        self.api_partner_label.config(text=name)
        self.api_url_var.set(self.repo.get_setting(key_url)   or "https://app7.meeventos.com.br/magicalrealitiesnetwork")
        self.api_token_var.set(self.repo.get_setting(key_token) or "")

    def _save_api_partner(self):
        """Salva URL e token do parceiro selecionado no banco."""
        name = self.api_partner_label.cget("text")
        if name == "—":
            messagebox.showwarning("Aviso", "Selecione um parceiro na tabela.", parent=self.top)
            return
        url   = self.api_url_var.get().strip().rstrip("/")
        token = self.api_token_var.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Informe a URL base.", parent=self.top)
            return
        key_url, key_token = self._api_key(name)
        self.repo.save_setting(key_url,   url)
        self.repo.save_setting(key_token, token)
        self._load_api_table()
        # Mantém a linha selecionada
        try:
            self.api_tree.selection_set(name)
        except Exception:
            pass
        messagebox.showinfo("Sucesso", f"Configuração de '{name}' salva.", parent=self.top)

    def _clear_api_form(self):
        self.api_partner_label.config(text="—")
        self.api_url_var.set("")
        self.api_token_var.set("")

    # =========================
    # TOLERÂNCIA DE DATA
    # =========================
    @staticmethod
    def _tolerance_hint(days: int) -> str:
        if days == 0:
            return "Apenas lançamentos com a mesma data exata serão conciliados."
        if days <= 2:
            return f"Conservador: aceita até {days} dia(s) de diferença."
        if days <= 5:
            return f"Recomendado: aceita até {days} dia(s) — cobre a maioria dos bancos."
        return f"Permissivo: aceita até {days} dia(s) — pode gerar falsos positivos."

    def _on_tolerance_change(self, value):
        days = int(float(value))
        self.tolerance_var.set(days)
        self.tolerance_label.config(text=f"{days} dias")
        self.tolerance_hint.config(text=self._tolerance_hint(days))

    def _set_tolerance(self, days: int):
        self.tolerance_var.set(days)
        self.tolerance_label.config(text=f"{days} dias")
        self.tolerance_hint.config(text=self._tolerance_hint(days))

    def _check_all(self):
        for var in self.vars.values():
            var.set(True)

    def _uncheck_all(self):
        for var in self.vars.values():
            var.set(False)

    def _restore_default(self):
        defaults = set(DEFAULT_VISIBLE_COLUMNS)
        for key, var in self.vars.items():
            var.set(key in defaults)

    def _save(self):
        selected = [key for key, var in self.vars.items() if var.get()]

        if not selected:
            messagebox.showwarning("Aviso", "Selecione ao menos uma coluna.")
            return

        self.settings.save_visible_columns(selected)
        self.settings.save_date_tolerance(int(self.tolerance_var.get()))

        if self.on_save_callback:
            try:
                self.on_save_callback()
            except Exception:
                pass

        messagebox.showinfo("Sucesso", "Configurações salvas com sucesso.")
        self.top.destroy()

    # =========================
    # BASE DE ENTIDADES
    # =========================
    def _load_entities_info(self):
        info = self.repo.get_entities_master_info()
        self.entities_total_label.config(text=f"Entidades em base: {info['total']}")

        ultima = info.get("ultima_atualizacao")
        if ultima:
            self.entities_updated_label.config(text=f"Última atualização: {ultima}")
        else:
            self.entities_updated_label.config(text="Última atualização: -")

    def _select_entities_file(self):
        path = filedialog.askopenfilename(
            title="Selecionar base de entidades",
            filetypes=[
                ("Arquivos suportados", "*.xlsx *.csv *.txt"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
                ("Texto", "*.txt"),
                ("Todos os arquivos", "*.*"),
            ],
        )

        if not path:
            return

        self.selected_entities_path = path
        self.entities_file_label.config(text=Path(path).name, fg="#166534")

    def _import_base_entidades(self):
        """
        Importa a planilha base_entidades.xlsx com CPF/CNPJ, razão social e cargo/ocupação.
        Usa o método import_base_entidades do repositório que faz o mapeamento automático
        de colunas e deriva categorias do campo CARGO OCUPAÇÃO.
        """
        path = filedialog.askopenfilename(
            title="Selecionar base_entidades.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")],
            parent=self.top
        )
        if not path:
            return

        try:
            total, _, erros = self.repo.import_base_entidades(path)
            if erros:
                messagebox.showerror(
                    "Erro na importação",
                    f"Erro ao processar o arquivo:\n{erros[0]}",
                    parent=self.top
                )
                return
            # Atualiza o contador de entidades
            count = self.repo.count_entities_master()
            try:
                self.status_callback(
                    f"Base de entidades atualizada | Entidades em base: {count}"
                )
            except Exception:
                pass  # status_callback opcional
            messagebox.showinfo(
                "Importação concluída",
                f"Base de entidades importada com sucesso!\n\n"
                f"Registros processados: {total}\n"
                f"Total na base: {count}\n\n"
                f"O sistema agora usará CPF/CNPJ e cargo/ocupação\n"
                f"para identificar e correlacionar lançamentos.",
                parent=self.top
            )
        except Exception as exc:
            messagebox.showerror(
                "Erro",
                f"Erro inesperado:\n{exc}",
                parent=self.top
            )

    def _import_entities_file(self):
        if not self.selected_entities_path:
            messagebox.showwarning("Aviso", "Selecione um arquivo antes de atualizar a base.")
            return

        try:
            raw_df = load_tabular_file(self.selected_entities_path)
            summary = summarize_dataframe(raw_df)
            normalized_df = Normalizer.normalizar_base_entidades(raw_df)

            imported_file_id = self.repo.save_imported_file(
                file_type="Base de entidades",
                file_name=Path(self.selected_entities_path).name,
                file_path=self.selected_entities_path,
                total_rows=summary["linhas"],
                total_columns=summary["colunas"]
            )

            self.repo.save_normalized_dataframe(
                imported_file_id=imported_file_id,
                source_type="Base de entidades",
                df=normalized_df
            )

            total_entidades = self.repo.upsert_entities_master(
                normalized_df,
                source_file_name=Path(self.selected_entities_path).name
            )

            self.repo.log(
                "INFO",
                "Base de entidades atualizada via configurações",
                f"arquivo={Path(self.selected_entities_path).name} | registros_processados={total_entidades}"
            )

            self._load_entities_info()

            if self.on_save_callback:
                try:
                    self.on_save_callback()
                except Exception:
                    pass

            messagebox.showinfo(
                "Sucesso",
                f"Base de entidades atualizada com sucesso.\n\nRegistros processados: {total_entidades}"
            )

        except Exception as exc:
            messagebox.showerror(
                "Erro",
                f"Não foi possível atualizar a base de entidades.\n\nDetalhes: {exc}"
            )

    # =========================
    # REGRAS MENSAIS
    # =========================
    def _parse_money(self, value: str) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0

        text = text.replace("R$", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")

        try:
            return float(text)
        except Exception:
            return 0.0

    def _format_money(self, value) -> str:
        try:
            v = float(value or 0)
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    def _format_money_field(self, var: tk.StringVar):
        value = self._parse_money(var.get())
        var.set(self._format_money(value))

    def _validate_reference_month(self, value: str) -> bool:
        try:
            datetime.strptime(value, "%Y-%m")
            return True
        except Exception:
            return False

    def _import_rules_from_file(self):
        """
        Importa regras mensais de arquivo CSV, Excel ou TXT.
        Colunas esperadas (flexível): mes, parceiro, subtotal, taxa, total
        Usa upsert — sobrescreve se (mes, parceiro) já existe.
        """
        path = filedialog.askopenfilename(
            title="Selecionar arquivo de regras mensais",
            filetypes=[
                ("Todos suportados", "*.csv *.xlsx *.xls *.txt"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xls"),
                ("TXT", "*.txt"),
            ],
            parent=self.top
        )
        if not path:
            return

        import pandas as pd
        import os

        ext = os.path.splitext(path)[1].lower()

        try:
            # ── Leitura ───────────────────────────────────────────────────
            if ext in (".xlsx", ".xls"):
                df = pd.read_excel(path, dtype=str)
            elif ext in (".csv", ".txt"):
                # Tenta detectar separador automaticamente
                df = pd.read_csv(path, sep=None, engine="python", dtype=str)
            else:
                messagebox.showerror("Erro", f"Formato não suportado: {ext}", parent=self.top)
                return

            df.columns = [c.strip().lower() for c in df.columns]

            # ── Mapeamento de colunas (aceita variações de nome) ─────────
            col_map = {
                "mes":      ["mes", "mês", "month", "referencia", "referência",
                             "mes_referencia", "mês_referência", "periodo", "período"],
                "parceiro": ["parceiro", "partner", "nome", "name", "casa", "unidade"],
                "subtotal": ["subtotal", "fatura", "valor_fatura", "bruto", "gross"],
                "taxa":     ["taxa", "fee", "marketing", "taxa_marketing",
                             "estrutura", "taxa_estrutura", "marketing_fee"],
                "total":    ["total", "total_pagar", "total_a_pagar", "net",
                             "liquido", "líquido", "valor_total"],
            }

            resolved = {}
            for field, aliases in col_map.items():
                for alias in aliases:
                    if alias in df.columns:
                        resolved[field] = alias
                        break

            missing = [f for f in ["mes", "parceiro", "subtotal"] if f not in resolved]
            if missing:
                messagebox.showerror(
                    "Colunas não encontradas",
                    f"Não foi possível identificar: {', '.join(missing)}\n\n"
                    f"Colunas encontradas no arquivo:\n{', '.join(df.columns)}\n\n"
                    f"Renomeie as colunas para: mes, parceiro, subtotal, taxa, total",
                    parent=self.top
                )
                return

            # ── Preview antes de confirmar ────────────────────────────────
            preview_win = tk.Toplevel(self.top)
            preview_win.title("Prévia da importação")
            preview_win.geometry("780x480")
            preview_win.grab_set()

            hdr = tk.Frame(preview_win, bg="#1e293b")
            hdr.pack(fill="x")
            tk.Label(hdr, text="Prévia — confirme antes de importar",
                     fg="white", bg="#1e293b",
                     font=("Arial", 10, "bold")).pack(side="left", padx=12, pady=8)

            # Tabela de prévia
            tree_frame = tk.Frame(preview_win)
            tree_frame.pack(fill="both", expand=True, padx=10, pady=8)

            preview_cols = ("mes", "parceiro", "subtotal", "taxa", "total", "status")
            tree = ttk.Treeview(tree_frame, columns=preview_cols,
                                show="headings", height=14)
            tree.pack(side="left", fill="both", expand=True)
            sb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            sb.pack(side="right", fill="y")
            tree.configure(yscrollcommand=sb.set)

            for col, head, w in [
                ("mes",      "Mês",          90),
                ("parceiro", "Parceiro",     160),
                ("subtotal", "Subtotal",     110),
                ("taxa",     "Taxa",         100),
                ("total",    "Total a pagar",120),
                ("status",   "Status",       140),
            ]:
                tree.heading(col, text=head)
                tree.column(col, width=w, anchor="w")

            tree.tag_configure("ok",    background="#dff3e3")
            tree.tag_configure("aviso", background="#fff3cd")
            tree.tag_configure("erro",  background="#f8d7da")

            partner_names_upper = {p["partner_name"].upper() for p in PARTNERS}

            def fmt_val(v):
                """Converte string de valor para float, limpando R$, pontos, vírgulas."""
                if not v or str(v).strip() in ("nan", ""):
                    return 0.0
                s = str(v).strip()
                s = s.replace("R$", "").replace(" ", "")
                # Detecta formato BR (1.234,56) ou US (1,234.56)
                if "," in s and "." in s:
                    if s.rfind(",") > s.rfind("."):
                        s = s.replace(".", "").replace(",", ".")
                    else:
                        s = s.replace(",", "")
                elif "," in s:
                    s = s.replace(",", ".")
                try:
                    return float(s)
                except ValueError:
                    return None

            rows_valid = []
            erros_count = 0

            for _, row in df.iterrows():
                mes      = str(row.get(resolved["mes"], "") or "").strip()
                parceiro = str(row.get(resolved["parceiro"], "") or "").strip()
                sub_raw  = row.get(resolved.get("subtotal", ""), "")
                taxa_raw = row.get(resolved.get("taxa", ""),     "")  if "taxa"  in resolved else ""
                tot_raw  = row.get(resolved.get("total", ""),    "")  if "total" in resolved else ""

                subtotal = fmt_val(sub_raw)
                taxa     = fmt_val(taxa_raw) if taxa_raw != "" else 0.0
                total    = fmt_val(tot_raw)  if tot_raw  != "" else None

                # Calcula total se não informado
                if total is None:
                    total = (subtotal or 0) + (taxa or 0)

                # Valida
                avisos = []
                tag    = "ok"

                if not mes or len(mes) < 7:
                    avisos.append("mês inválido")
                    tag = "erro"
                if not parceiro:
                    avisos.append("parceiro vazio")
                    tag = "erro"
                elif parceiro.upper() not in partner_names_upper:
                    avisos.append("parceiro não cadastrado")
                    tag = "aviso"
                if subtotal is None:
                    avisos.append("subtotal inválido")
                    tag = "erro"

                status_txt = "✓ OK" if not avisos else ("⚠ " if tag == "aviso" else "✗ ") + " | ".join(avisos)

                def fmt_brl(v):
                    if v is None: return "—"
                    return f"R$ {v:,.2f}".replace(",","X").replace(".",",").replace("X",".")

                tree.insert("", "end", values=(
                    mes, parceiro,
                    fmt_brl(subtotal), fmt_brl(taxa), fmt_brl(total),
                    status_txt
                ), tags=(tag,))

                if tag != "erro":
                    rows_valid.append({
                        "mes":      mes,
                        "parceiro": parceiro,
                        "subtotal": subtotal or 0,
                        "taxa":     taxa or 0,
                        "total":    total or 0,
                    })
                else:
                    erros_count += 1

            # Rodapé
            footer = tk.Frame(preview_win, padx=10, pady=8)
            footer.pack(fill="x")

            total_lbl = tk.Label(
                footer,
                text=f"{len(rows_valid)} linha(s) válidas para importar"
                     + (f" | {erros_count} com erro (serão ignoradas)" if erros_count else ""),
                anchor="w", fg="#475569"
            )
            total_lbl.pack(side="left")

            def confirmar_import():
                if not rows_valid:
                    messagebox.showwarning("Aviso", "Nenhuma linha válida para importar.",
                                           parent=preview_win)
                    return

                importados = 0
                falhas     = []

                for r in rows_valid:
                    try:
                        # Resolve o partner_name exato (case-insensitive)
                        partner_exact = next(
                            (p["partner_name"] for p in PARTNERS
                             if p["partner_name"].upper() == r["parceiro"].upper()),
                            r["parceiro"]
                        )
                        partner_cnpj = next(
                            (p["cnpj"] for p in PARTNERS
                             if p["partner_name"].upper() == r["parceiro"].upper()),
                            ""
                        )
                        self.repo.save_partner_month_rule(
                            reference_month = r["mes"],
                            partner_name    = partner_exact,
                            partner_cnpj    = partner_cnpj,
                            subtotal        = r["subtotal"],
                            marketing_fee   = r["taxa"],
                            total_expected  = r["total"],
                        )
                        importados += 1
                    except Exception as exc:
                        falhas.append(f"{r['parceiro']}/{r['mes']}: {exc}")

                preview_win.destroy()
                self._load_monthly_rules()

                msg = f"{importados} regra(s) importada(s) com sucesso."
                if falhas:
                    msg += f"\n\n{len(falhas)} erro(s):\n" + "\n".join(falhas[:5])
                messagebox.showinfo("Importação concluída", msg, parent=self.top)

            ttk.Button(footer, text="Importar agora",
                       command=confirmar_import).pack(side="right", padx=(6, 0))
            ttk.Button(footer, text="Cancelar",
                       command=preview_win.destroy).pack(side="right")

        except Exception as exc:
            messagebox.showerror(
                "Erro ao ler arquivo",
                f"Não foi possível processar o arquivo:\n{exc}",
                parent=self.top
            )

    def _recalculate_rule_total(self):
        subtotal = self._parse_money(self.rule_subtotal_var.get())
        fee = self._parse_money(self.rule_fee_var.get())
        total = subtotal + fee
        self.rule_total_var.set(self._format_money(total))

    def _clear_rule_form(self):
        self.rule_partner_var.set("")
        self.rule_subtotal_var.set("")
        self.rule_fee_var.set("")
        self.rule_total_var.set("")
        self.rule_notes_var.set("")

    def _load_monthly_rules(self):
        for item in self.rules_tree.get_children():
            self.rules_tree.delete(item)

        rules = self.repo.list_partner_month_rules()

        for rule in rules:
            self.rules_tree.insert(
                "",
                "end",
                values=(
                    rule["reference_month"],
                    rule["partner_name"],
                    self._format_money(rule["subtotal"]),
                    self._format_money(rule["marketing_fee"]),
                    self._format_money(rule["total_expected"]),
                )
            )

    def _save_monthly_rule(self):
        reference_month = self.rule_month_var.get().strip()
        partner_name = self.rule_partner_var.get().strip()
        subtotal = self._parse_money(self.rule_subtotal_var.get())
        fee = self._parse_money(self.rule_fee_var.get())
        total = subtotal + fee
        notes = self.rule_notes_var.get().strip()

        if not self._validate_reference_month(reference_month):
            messagebox.showwarning("Aviso", "Informe o mês no formato YYYY-MM. Exemplo: 2026-03")
            return

        if not partner_name:
            messagebox.showwarning("Aviso", "Selecione o parceiro.")
            return

        partner = next((p for p in PARTNERS if p["partner_name"] == partner_name), None)
        partner_cnpj = partner["cnpj"] if partner else ""

        self.repo.save_partner_month_rule(
            reference_month=reference_month,
            partner_name=partner_name,
            partner_cnpj=partner_cnpj,
            subtotal=subtotal,
            marketing_fee=fee,
            total_expected=total,
            notes=notes
        )

        self.repo.log(
            "INFO",
            "Regra mensal salva",
            f"mes={reference_month} | parceiro={partner_name} | subtotal={subtotal} | taxa={fee} | total={total}"
        )

        self._format_money_field(self.rule_subtotal_var)
        self._format_money_field(self.rule_fee_var)
        self.rule_total_var.set(self._format_money(total))

        self._load_monthly_rules()
        messagebox.showinfo("Sucesso", "Regra mensal salva com sucesso.")