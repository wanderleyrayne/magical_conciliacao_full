import tkinter as tk
from tkinter import ttk, filedialog
from pathlib import Path
import threading

from database.repository import SystemRepository
from version import APP_NAME, APP_VERSION, APP_AUTHOR
from ui.status_bar import StatusBar
from ui.dialogs import erro, aviso
from ui.results_window import ResultsWindow
from ui.history_window import HistoryWindow
from ui.erp_lancamento_window import ErpLancamentoWindow
from ui.settings_window import SettingsWindow
from core.loader import load_tabular_file, summarize_dataframe
from core.normalizer import Normalizer
from core.reconciler import Reconciler
from utils.paths import app_path, user_data_path
from core.revenue_partner_matcher import RevenuePartnerMatcher
from core.settings_manager import SettingsManager
from ui.partner_receipts_dialog import PartnerReceiptsDialog

class MainWindow:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1200x720")
        self.root.minsize(1000, 650)

        self.repo = SystemRepository(str(user_data_path("data", "conciliacao.db")))
        self.erp_mode = tk.StringVar(value="consolidado")

        try:
            icon_path = app_path("assets", "icon.ico")
            self.root.iconbitmap(str(icon_path))
        except Exception:
            pass

        self.files = {
            "Extrato bancário": {"path": None, "raw_df": None, "normalized_df": None, "summary": None},
            "ERP despesas": {"path": None, "raw_df": None, "normalized_df": None, "summary": None},
            "ERP receitas": {"path": None, "raw_df": None, "normalized_df": None, "summary": None},
            "ERP consolidado": {"path": None, "raw_df": None, "normalized_df": None, "summary": None},
        }

        self.file_labels = {}
        self.file_cards = {}

        self._build_layout()

    def open_history_window(self):
        HistoryWindow(self.root, db_path=str(self.repo.db.db_path))

    def open_erp_lancamento(self):
        ErpLancamentoWindow(self.root)

    def open_settings_window(self):
        SettingsWindow(
            self.root,
            db_path=str(self.repo.db.db_path),
            on_save_callback=lambda: self.status_bar.set_text(
                f"Configurações atualizadas | Entidades em base: {self.repo.count_entities_master()}"
            )
        )

    def _build_layout(self):
        header = tk.Frame(self.root, bg="#1e293b", height=54)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"{APP_NAME} | v{APP_VERSION}",
            fg="white",
            bg="#1e293b",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=12, pady=12)

        tk.Label(
            header,
            text=APP_AUTHOR,
            fg="white",
            bg="#1e293b"
        ).pack(side="right", padx=12)

        body = tk.Frame(self.root, bg="#f8fafc")
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg="#f8fafc", width=360)
        left.pack(side="left", fill="y", padx=16, pady=16)
        left.pack_propagate(False)

        right = tk.Frame(body, bg="white", bd=1, relief="solid")
        right.pack(side="right", fill="both", expand=True, padx=(0, 16), pady=16)

        title = tk.Label(
            left,
            text="Upload de arquivos",
            font=("Arial", 16, "bold"),
            bg="#f8fafc"
        )
        title.pack(anchor="w", pady=(0, 10))

        subtitle = tk.Label(
            left,
            text="Selecione os arquivos para leitura, padronização e conciliação.",
            justify="left",
            bg="#f8fafc",
            fg="#475569",
            wraplength=320
        )
        subtitle.pack(anchor="w", pady=(0, 15))

        uploads_container = tk.Frame(left, bg="#f8fafc")
        uploads_container.pack(fill="x", anchor="n")

        mode_box = tk.LabelFrame(uploads_container, text="Modo ERP", bg="#f8fafc", padx=10, pady=8)
        mode_box.pack(fill="x", pady=5)

        ttk.Radiobutton(
            mode_box,
            text="ERP consolidado",
            value="consolidado",
            variable=self.erp_mode,
            command=self._refresh_upload_cards
        ).pack(anchor="w")

        ttk.Radiobutton(
            mode_box,
            text="ERP separado (despesas + receitas)",
            value="separado",
            variable=self.erp_mode,
            command=self._refresh_upload_cards
        ).pack(anchor="w", pady=(4, 0))

        for label in self.files.keys():
            card = tk.LabelFrame(uploads_container, text=label, bg="#f8fafc", padx=10, pady=8)

            status_lbl = tk.Label(
                card,
                text="Nenhum arquivo selecionado",
                bg="#f8fafc",
                fg="#64748b",
                wraplength=280,
                justify="left",
                anchor="w",
                height=2
            )
            status_lbl.pack(anchor="w", pady=(0, 6))
            self.file_labels[label] = status_lbl

            btn = ttk.Button(
                card,
                text="Selecionar arquivo",
                command=lambda name=label: self.select_file(name)
            )
            btn.pack(anchor="w")

            self.file_cards[label] = card

        self._refresh_upload_cards()

        spacer = tk.Frame(left, bg="#f8fafc")
        spacer.pack(fill="both", expand=True)

        self.bottom_container = tk.Frame(left, bg="#f8fafc")
        self.bottom_container.pack(fill="x", side="bottom")

        # Linha 1: ações principais
        actions_row1 = tk.Frame(self.bottom_container, bg="#f8fafc")
        actions_row1.pack(fill="x", pady=(10, 4))

        ttk.Button(actions_row1, text="Limpar", command=self.clear_uploads).pack(side="left", padx=(0, 6))
        ttk.Button(actions_row1, text="Executar conciliação", command=self.run_reconciliation).pack(side="left", padx=(0, 6))
        ttk.Button(actions_row1, text="Histórico", command=self.open_history_window).pack(side="left", padx=(0, 6))
        ttk.Button(actions_row1, text="⚙ Configurações", command=self.open_settings_window).pack(side="right")

        # Linha 2: ações secundárias
        actions_row2 = tk.Frame(self.bottom_container, bg="#f8fafc")
        actions_row2.pack(fill="x", pady=(0, 8))

        ttk.Button(actions_row2, text="↑ Lançar no ERP", command=self.open_erp_lancamento).pack(side="left", padx=(0, 6))

        progress_box = tk.LabelFrame(self.bottom_container, text="Processamento", bg="#f8fafc", padx=10, pady=10)
        progress_box.pack(fill="x", pady=(0, 0))

        self.progress = ttk.Progressbar(progress_box, orient="horizontal", length=280, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))

        self.progress_text = tk.Label(
            progress_box,
            text="Aguardando arquivos...",
            bg="#f8fafc",
            fg="#475569"
        )
        self.progress_text.pack(anchor="w")

        preview_header = tk.Frame(right, bg="white")
        preview_header.pack(fill="x", padx=12, pady=12)

        tk.Label(
            preview_header,
            text="Resumo do arquivo carregado",
            bg="white",
            font=("Arial", 14, "bold")
        ).pack(anchor="w")

        tk.Label(
            preview_header,
            text="Visualização da estrutura original e da estrutura normalizada.",
            bg="white",
            fg="#475569"
        ).pack(anchor="w", pady=(4, 0))

        self.preview = tk.Text(right, wrap="word", height=30, bg="white", fg="#0f172a")
        self.preview.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.preview.insert("1.0", "Nenhum arquivo carregado.")
        self.preview.config(state="disabled")

        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(fill="x")
        total_entidades = self.repo.count_entities_master()
        self.status_bar.set_text(f"Sistema pronto | Entidades em base: {total_entidades}")

    def _refresh_upload_cards(self):
        for card in self.file_cards.values():
            card.pack_forget()

        visible = ["Extrato bancário"]

        if self.erp_mode.get() == "consolidado":
            visible.append("ERP consolidado")
        else:
            visible.extend(["ERP despesas", "ERP receitas"])

        for label in visible:
            self.file_cards[label].pack(fill="x", pady=5)

    def select_file(self, file_type: str):
        file_path = filedialog.askopenfilename(
            title=f"Selecionar {file_type}",
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

        self.progress["value"] = 0
        self.progress_text.config(text=f"Lendo {file_type}...")
        self.status_bar.set_text(f"Carregando {file_type}")
        self._update_preview("Processando arquivo...")

        thread = threading.Thread(
            target=self._load_file_worker,
            args=(file_type, file_path),
            daemon=True
        )
        thread.start()

    def _load_file_worker(self, file_type: str, file_path: str):
        try:
            self._set_progress(10, "Abrindo arquivo...")
            raw_df = load_tabular_file(file_path)

            self._set_progress(35, "Lendo estrutura...")
            summary = summarize_dataframe(raw_df)

            self._set_progress(60, "Padronizando dados...")
            normalized_df = self._normalize_by_type(file_type, raw_df)

            self._set_progress(85, "Montando resumo...")
            preview_text = self._build_preview_text(file_path, summary, normalized_df)

            self.files[file_type]["path"] = file_path
            self.files[file_type]["raw_df"] = raw_df
            self.files[file_type]["normalized_df"] = normalized_df
            self.files[file_type]["summary"] = summary

            imported_file_id = self.repo.save_imported_file(
                file_type=file_type,
                file_name=Path(file_path).name,
                file_path=file_path,
                total_rows=summary["linhas"],
                total_columns=summary["colunas"]
            )

            self.repo.save_normalized_dataframe(
                imported_file_id=imported_file_id,
                source_type=file_type,
                df=normalized_df
            )

            self.repo.log(
                "INFO",
                f"Arquivo carregado: {file_type}",
                f"{Path(file_path).name} | linhas={summary['linhas']} | colunas={summary['colunas']}"
            )

            short_name = Path(file_path).name
            if len(short_name) > 32:
                short_name = short_name[:32] + "..."

            self.root.after(
                0,
                lambda: self.file_labels[file_type].config(
                    text=(
                        f"{short_name}\n"
                        f"{summary['linhas']} linhas | {summary['colunas']} colunas | {len(normalized_df)} regs"
                    ),
                    fg="#166534"
                )
            )

            self.root.after(0, lambda: self._update_preview(preview_text))
            self.root.after(0, lambda: self.progress.config(value=100))
            self.root.after(0, lambda: self.progress_text.config(text="Arquivo carregado e normalizado com sucesso"))
            self.root.after(0, lambda: self.status_bar.set_text(
                f"{file_type} carregado | Entidades em base: {self.repo.count_entities_master()}"
            ))

        except Exception as exc:
            self.repo.log(
                "ERROR",
                f"Erro ao carregar arquivo: {file_type}",
                str(exc)
            )
            erro_msg = f"Não foi possível carregar o arquivo de {file_type}.\n\nDetalhes: {str(exc)}"

            self.root.after(0, lambda: self.progress.config(value=0))
            self.root.after(0, lambda: self.progress_text.config(text="Falha ao carregar arquivo"))
            self.root.after(0, lambda: self.status_bar.set_text("Erro no carregamento"))
            self.root.after(0, lambda msg=erro_msg: erro(msg))

    def _normalize_by_type(self, file_type: str, df):
        if file_type == "Extrato bancário":
            return Normalizer.normalizar_extrato(df)

        if file_type == "ERP despesas":
            return Normalizer.normalizar_erp_despesas(df)

        if file_type == "ERP receitas":
            return Normalizer.normalizar_erp_receitas(df)

        if file_type == "ERP consolidado":
            return Normalizer.normalizar_erp_consolidado(df)

        return df.copy()

    def _build_preview_text(self, file_path: str, summary: dict, normalized_df) -> str:
        lines = [
            f"Arquivo: {Path(file_path).name}",
            f"Caminho: {file_path}",
            "",
            "ESTRUTURA ORIGINAL",
            f"Linhas: {summary['linhas']}",
            f"Colunas: {summary['colunas']}",
            "",
            "Cabeçalhos detectados:"
        ]

        for col in summary["nomes_colunas"][:50]:
            lines.append(f"- {col}")

        lines.extend([
            "",
            "ESTRUTURA NORMALIZADA",
            f"Linhas normalizadas: {len(normalized_df)}",
            f"Colunas normalizadas: {len(normalized_df.columns)}",
            "",
            "Campos:"
        ])

        for col in normalized_df.columns:
            lines.append(f"- {col}")

        if "tipo" in normalized_df.columns:
            entradas = 0
            saidas = 0
            try:
                entradas = int((normalized_df["tipo"] == "ENTRADA").sum())
                saidas = int((normalized_df["tipo"] == "SAIDA").sum())
            except Exception:
                pass

            lines.extend([
                "",
                "Resumo por tipo:",
                f"- Entradas: {entradas}",
                f"- Saídas: {saidas}",
            ])

        try:
            lines.extend([
                "",
                "Prévia dos 5 primeiros registros:",
                normalized_df.head(5).to_string(index=False)
            ])
        except Exception:
            pass

        return "\n".join(lines)

    def _set_progress(self, value: int, text: str):
        self.root.after(0, lambda: self.progress.config(value=value))
        self.root.after(0, lambda: self.progress_text.config(text=text))

    def _update_preview(self, text: str):
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.config(state="disabled")

    def clear_uploads(self):
        for name in self.files.keys():
            self.files[name] = {
                "path": None,
                "raw_df": None,
                "normalized_df": None,
                "summary": None
            }
            if name in self.file_labels:
                self.file_labels[name].config(
                    text="Nenhum arquivo selecionado",
                    fg="#64748b"
                )

        self.progress["value"] = 0
        self.progress_text.config(text="Aguardando arquivos...")
        self._update_preview("Nenhum arquivo carregado.")
        self.status_bar.set_text(f"Uploads limpos | Entidades em base: {self.repo.count_entities_master()}")

    def run_reconciliation(self):
        df_banco     = self.files["Extrato bancário"]["normalized_df"]
        df_entidades = self.repo.load_entities_master_df()

        if df_banco is None:
            aviso("Carregue o extrato bancário antes de executar a conciliação.")
            return

        df_despesas = None
        df_receitas = None

        if self.erp_mode.get() == "consolidado":
            df_erp_consolidado = self.files["ERP consolidado"]["normalized_df"]
            if df_erp_consolidado is None or df_erp_consolidado.empty:
                aviso("Carregue o arquivo ERP consolidado.")
                return
            df_despesas = df_erp_consolidado[df_erp_consolidado["tipo"] == "SAIDA"].copy()
            df_receitas = df_erp_consolidado[df_erp_consolidado["tipo"] == "ENTRADA"].copy()
        else:
            df_despesas = self.files["ERP despesas"]["normalized_df"]
            df_receitas = self.files["ERP receitas"]["normalized_df"]
            if df_despesas is None and df_receitas is None:
                aviso("Carregue ao menos um arquivo de ERP: despesas ou receitas.")
                return

        # Lê a tolerância de data configurada pelo usuário
        settings    = SettingsManager(str(self.repo.db.db_path))
        date_tolerance = settings.get_date_tolerance()

        self.progress["value"] = 0
        self.progress_text.config(text="Iniciando conciliação...")
        self.status_bar.set_text(f"Executando conciliação (tolerância: {date_tolerance} dias)")

        # Roda em thread separada para não travar a UI
        import threading
        thread = threading.Thread(
            target=self._run_reconciliation_worker,
            args=(df_banco, df_despesas, df_receitas, df_entidades, date_tolerance),
            daemon=True,
        )
        thread.start()

    def _run_reconciliation_worker(self, df_banco, df_despesas, df_receitas, df_entidades, date_tolerance):
        try:
            df_result_desp = None
            df_result_rec  = None

            if df_despesas is not None and not df_despesas.empty:
                self._set_progress(30, "Conciliando despesas...")
                df_result_desp = Reconciler.conciliar_despesas(
                    df_banco, df_despesas, df_entidades, date_tolerance=date_tolerance
                )

            if df_receitas is not None and not df_receitas.empty:
                self._set_progress(65, "Conciliando receitas...")
                df_result_rec = Reconciler.conciliar_receitas(
                    df_banco, df_receitas, df_entidades, date_tolerance=date_tolerance
                )

            self._set_progress(85, "Consolidando resultados...")
            df_final = Reconciler.consolidar_resultados(df_result_desp, df_result_rec)

            self._set_progress(92, "Salvando no banco...")
            partner_receipts_summary = RevenuePartnerMatcher.build_partner_receipts_summary(
                df_banco=df_banco,
                repo=self.repo,
            )

            run_id = self.repo.save_reconciliation_run(df_final)
            self.repo.save_reconciliation_results(run_id, df_final)
            self.repo.log(
                "INFO",
                "Conciliação executada",
                f"run_id={run_id} | registros={len(df_final)} | tolerancia={date_tolerance}d"
            )

            # Toda interação com a UI deve vir via root.after
            self.root.after(0, lambda: self._on_reconciliation_done(df_final, partner_receipts_summary))

        except Exception as exc:
            self.repo.log("ERROR", "Erro ao executar conciliação", str(exc))
            msg = f"Erro ao executar conciliação.\n\nDetalhes: {str(exc)}"
            self.root.after(0, lambda m=msg: self._on_reconciliation_error(m))

    def _on_reconciliation_done(self, df_final, partner_receipts_summary):
        self.progress["value"] = 100
        self.progress_text.config(text="Conciliação concluída")
        self.status_bar.set_text("Conciliação concluída")

        if df_final.empty:
            aviso("A conciliação foi executada, mas nenhum resultado foi gerado.")
            return

        ResultsWindow(self.root, df_final, self.repo)

        # Resumo de parceiros removido da abertura automática
        # Agora acessível pelo botão "Resumo parceiros" na tela de resultado

    def _on_reconciliation_error(self, msg):
        erro(msg)
        self.status_bar.set_text("Erro na conciliação")
        self.progress["value"] = 0
        self.progress_text.config(text="Falha na conciliação")