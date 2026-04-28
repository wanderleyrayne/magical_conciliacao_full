import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd

from database.repository import SystemRepository
from ui.reconciliation_detail_window import ReconciliationDetailWindow
from ui.partner_receipts_dialog import PartnerReceiptsDialog
from core.loader import load_tabular_file
from core.normalizer import Normalizer
from core.reconciler import Reconciler
from core.revenue_partner_matcher import RevenuePartnerMatcher
from utils.paths import app_path, user_data_path


class HistoryWindow:
    def __init__(self, master, db_path=None):
        self.top = tk.Toplevel(master)
        self.top.title("Histórico de Conciliações")
        self.top.geometry("1320x660")
        self.top.minsize(1080, 540)

        try:
            icon_path = app_path("assets", "icon.ico")
            if icon_path.exists():
                self.top.iconbitmap(str(icon_path))
        except Exception:
            pass

        if db_path is None:
            db_path = str(user_data_path("data", "conciliacao.db"))

        self.repo = SystemRepository(db_path)
        self._build_layout()
        self._load_runs()

    def _build_layout(self):
        header = tk.Frame(self.top, bg="#1e293b", height=48)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Histórico de Conciliações",
            fg="white",
            bg="#1e293b",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=12, pady=10)

        actions = tk.Frame(self.top)
        actions.pack(fill="x", padx=12, pady=10)

        ttk.Button(actions, text="Atualizar", command=self._load_runs).pack(side="left")
        ttk.Button(actions, text="Abrir execução", command=self._open_selected_run).pack(side="left", padx=8)
        ttk.Button(actions, text="Ver resumo dos parceiros", command=self._open_partner_summary).pack(side="left", padx=8)
        ttk.Button(actions, text="Reprocessar com novo ERP", command=self._reprocess_selected_run).pack(side="left", padx=8)

        self.info_label = tk.Label(actions, text="", anchor="e")
        self.info_label.pack(side="right")

        table_frame = tk.Frame(self.top)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        columns = [
            "id",
            "parent_run_id",
            "run_group",
            "run_version",
            "executed_at",
            "total_records",
            "total_conciliado",
            "total_somente_banco",
            "total_somente_erp",
            "total_despesas",
            "total_receitas",
        ]

        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.pack(side="left", fill="both", expand=True)

        scrollbar_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scrollbar_y.pack(side="right", fill="y")

        self.tree.configure(yscrollcommand=scrollbar_y.set)

        headings = {
            "id": "ID",
            "parent_run_id": "Base",
            "run_group": "Grupo",
            "run_version": "Versão",
            "executed_at": "Executado em",
            "total_records": "Registros",
            "total_conciliado": "Conciliados",
            "total_somente_banco": "Só Banco",
            "total_somente_erp": "Só ERP",
            "total_despesas": "Total Despesas",
            "total_receitas": "Total Receitas",
        }

        widths = {
            "id": 70,
            "parent_run_id": 70,
            "run_group": 160,
            "run_version": 70,
            "executed_at": 170,
            "total_records": 90,
            "total_conciliado": 95,
            "total_somente_banco": 95,
            "total_somente_erp": 95,
            "total_despesas": 140,
            "total_receitas": 140,
        }

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center")

        self.tree.bind("<Double-1>", lambda e: self._open_selected_run())


    def _open_partner_summary(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione uma execução.")
            return

        values = self.tree.item(selected[0], "values")
        if not values:
            messagebox.showwarning("Aviso", "Execução inválida.")
            return

        try:
            run_id = int(values[0])
        except Exception:
            messagebox.showerror("Erro", "ID da execução inválido.")
            return

        try:
            df_prev = self.repo.get_reconciliation_results_df(run_id)
            if df_prev.empty:
                messagebox.showwarning("Aviso", "A execução não possui resultados.")
                return

            banco_rows = []

            for _, row in df_prev.iterrows():
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
                        "attributed_partner": row.get("attributed_partner", ""),
                    })

            df_banco = pd.DataFrame(banco_rows).drop_duplicates()

            if df_banco.empty:
                messagebox.showwarning("Aviso", "Não foi possível reconstruir os recebimentos da execução.")
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


    def _load_runs(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            runs = self.repo.list_reconciliation_runs(limit=300)

            for run in runs:
                parent_run_id = run.get("parent_run_id")
                parent_run_id = parent_run_id if parent_run_id is not None else "-"

                run_group = run.get("run_group", "") or "-"
                run_version = run.get("run_version", 1) or 1

                self.tree.insert(
                    "",
                    "end",
                    values=(
                        run.get("id", ""),
                        parent_run_id,
                        run_group,
                        run_version,
                        run.get("executed_at", ""),
                        run.get("total_records", 0),
                        run.get("total_conciliado", 0),
                        run.get("total_somente_banco", 0),
                        run.get("total_somente_erp", 0),
                        self._fmt_money(run.get("total_despesas", 0)),
                        self._fmt_money(run.get("total_receitas", 0)),
                    )
                )

            self.info_label.config(text=f"Execuções carregadas: {len(runs)}")
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível carregar o histórico.\n\nDetalhes: {exc}")

    def _open_selected_run(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione uma execução para abrir.")
            return

        values = self.tree.item(selected[0], "values")
        if not values:
            messagebox.showwarning("Aviso", "Não foi possível identificar a execução selecionada.")
            return

        try:
            run_id = int(values[0])
        except Exception:
            messagebox.showerror("Erro", "ID da execução inválido.")
            return

        try:
            ReconciliationDetailWindow(
                self.top,
                run_id=run_id,
                db_path=str(self.repo.db.db_path)
            )
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível abrir a execução.\n\nDetalhes: {exc}")

    def _reprocess_selected_run(self):
        # ── Validações e seleção de arquivo ficam na thread principal ──────────
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecione uma execução para reprocessar.")
            return

        values = self.tree.item(selected[0], "values")
        if not values:
            messagebox.showwarning("Aviso", "Execução inválida.")
            return

        try:
            base_run_id = int(values[0])
        except Exception:
            messagebox.showerror("Erro", "ID da execução inválido.")
            return

        file_path = filedialog.askopenfilename(
            title="Selecionar novo ERP consolidado",
            filetypes=[
                ("Arquivos suportados", "*.xlsx *.csv *.txt"),
                ("Excel", "*.xlsx"),
                ("CSV", "*.csv"),
                ("Texto", "*.txt"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if not file_path:
            return

        # Carrega resultados anteriores ainda na thread principal (rápido — só leitura)
        df_prev = self.repo.get_reconciliation_results_df(base_run_id)
        if df_prev.empty:
            messagebox.showwarning("Aviso", "A execução selecionada não possui resultados para servir de base.")
            return

        banco_rows = []
        for _, row in df_prev.iterrows():
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
                    "attributed_partner": row.get("attributed_partner", ""),
                })

        df_banco = pd.DataFrame(banco_rows).drop_duplicates()
        if df_banco.empty:
            messagebox.showwarning("Aviso", "Não foi possível reaproveitar o extrato da execução selecionada.")
            return

        # Bloqueia o botão para evitar cliques duplos durante o processamento
        self._set_reprocess_button_state("disabled")
        self.info_label.config(text="Reprocessando — aguarde...")

        import threading
        thread = threading.Thread(
            target=self._reprocess_worker,
            args=(base_run_id, file_path, df_banco),
            daemon=True,
        )
        thread.start()

    def _reprocess_worker(self, base_run_id: int, file_path: str, df_banco):
        """Executa o reprocessamento pesado fora da thread principal."""
        try:
            raw_df    = load_tabular_file(file_path)
            df_erp    = Normalizer.normalizar_erp_consolidado(raw_df)
            df_entidades = self.repo.load_entities_master_df()

            df_despesas = df_erp[df_erp["tipo"] == "SAIDA"].copy()
            df_receitas = df_erp[df_erp["tipo"] == "ENTRADA"].copy()

            df_result_desp = None
            df_result_rec  = None

            if not df_despesas.empty:
                df_result_desp = Reconciler.conciliar_despesas(df_banco, df_despesas, df_entidades)

            if not df_receitas.empty:
                df_result_rec = Reconciler.conciliar_receitas(df_banco, df_receitas, df_entidades)

            df_final = Reconciler.consolidar_resultados(df_result_desp, df_result_rec)

            version_info = self.repo.get_next_run_version_info(base_run_id)
            if not version_info:
                self.top.after(0, lambda: self._on_reprocess_error("Não foi possível calcular a próxima versão."))
                return

            new_run_id = self.repo.save_reconciliation_run_versioned(
                df_resultado=df_final,
                parent_run_id=version_info["parent_run_id"],
                run_group=version_info["run_group"],
                run_version=version_info["next_version"],
            )
            self.repo.save_reconciliation_results(new_run_id, df_final)

            partner_receipts_summary = RevenuePartnerMatcher.build_partner_receipts_summary(
                df_banco=df_banco,
                repo=self.repo,
            )

            self.repo.log(
                "INFO",
                "Reprocessamento com novo ERP executado",
                f"base_run_id={base_run_id} | new_run_id={new_run_id} | version={version_info['next_version']}",
            )

            self.top.after(
                0,
                lambda: self._on_reprocess_done(
                    base_run_id, new_run_id, version_info["next_version"], partner_receipts_summary
                ),
            )

        except Exception as exc:
            msg = f"Não foi possível reprocessar com o novo ERP.\n\nDetalhes: {exc}"
            self.top.after(0, lambda m=msg: self._on_reprocess_error(m))

    def _on_reprocess_done(self, base_run_id, new_run_id, version, partner_receipts_summary):
        """Callback chamado na thread principal após reprocessamento bem-sucedido."""
        self._set_reprocess_button_state("normal")
        self._load_runs()
        self.info_label.config(text=f"Execuções carregadas: {len(self.tree.get_children())}")

        messagebox.showinfo(
            "Sucesso",
            f"Nova versão criada com sucesso.\n\nExecução base: #{base_run_id}\nNova execução: #{new_run_id}\nVersão: {version}",
        )

        ReconciliationDetailWindow(
            self.top,
            run_id=new_run_id,
            db_path=str(self.repo.db.db_path),
        )

        if partner_receipts_summary:
            PartnerReceiptsDialog(self.top, partner_receipts_summary)

    def _on_reprocess_error(self, msg: str):
        """Callback chamado na thread principal em caso de erro."""
        self._set_reprocess_button_state("normal")
        self.info_label.config(text="Erro no reprocessamento.")
        messagebox.showerror("Erro", msg)

    def _set_reprocess_button_state(self, state: str):
        """Habilita ou desabilita o botão de reprocessar para evitar cliques duplos."""
        try:
            for widget in self.top.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Button) and "Reprocessar" in str(child.cget("text")):
                        child.config(state=state)
                        return
        except Exception:
            pass

    @staticmethod
    def _fmt_money(value):
        try:
            v = float(value or 0)
            return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"