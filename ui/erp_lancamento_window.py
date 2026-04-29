import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import warnings
import pandas as pd

# Suprime aviso do openpyxl sobre Data Validation (dropdowns do Excel)
# que não é suportado mas não afeta a leitura dos dados
warnings.filterwarnings(
    "ignore",
    message="Data Validation extension is not supported and will be removed",
    category=UserWarning,
    module="openpyxl"
)
import numpy as np
import json
from datetime import datetime
from pathlib import Path

from utils.paths import app_path, user_data_path
from database.repository import SystemRepository


# =============================================================================
# MAPEAMENTO DE CAMPOS
# Planilha → API MeEventos
# Campos enviados: valor, descricao, idcategoria, mododepagamento, idevento
# =============================================================================

# Mapa: valor da coluna "TIPO DESPESA MeEventos" → tipocobranca da API
# tipocobranca: 1=Receita, 2=Despesa (todos os tipos da planilha são despesas)
TIPO_DESPESA_MAP = {
    "CMV":                  2,
    "DespesasPrestadores":  2,
    "DespesasGerais":       2,
    "DespesasOcupacional":  2,
    "OutrasDespesas":       2,
}

# Mapa: FORMA PGTO (planilha) → mododepagamento ID (API MeEventos)
# Confirme os IDs em Configurações → Modos de Pagamento no MeEventos
FORMA_PGTO_MAP = {
    "PIX":      3,
    "TED":      2,
    "BOLETO":   4,
    "DINHEIRO": 1,
}
FORMA_PGTO_DEFAULT = 1   # usado quando a forma não está no mapa acima

# Mapa: CATEGORIA MeEventos (planilha) → idcategoria ID (API MeEventos)
# Preencha com os IDs do seu cadastro em Configurações → Categorias no MeEventos
# Deixe None para categorias que devem usar o valor padrão abaixo
CATEGORIA_MAP = {
    "Decoração":                    None,   # preencher com ID real
    "Decorador":                    None,
    "Bolo":                         None,
    "Doce":                         None,
    "Bebidas":                      None,
    "Buffet":                       None,
    "Som & Imagem":                 None,
    "Brigadista":                   None,
    "Recepcionista":                None,
    "Manobrista":                   None,
    "Eletricista":                  None,
    "Gerente de Evento":            None,
    "Mão de Obra Especializada":    None,
    "Prestação de Serviços - T":    None,
    "Despesa com Alimentação":      None,
    "Produtos Alimentícios - Outros": None,
    "Manutenção & Conservação":     None,
    "Telefonia & Internet":         None,
    "Móveis & Utensílios":          None,
    "Alarmes":                      None,
}
CATEGORIA_DEFAULT = 1    # ID usado quando categoria não está no mapa


class ErpLancamentoWindow:
    """
    Módulo de lançamento de despesas no ERP MeEventos via API.

    Fluxo:
      1. Usuário informa a URL base e token da API
      2. Seleciona planilha de despesas (.xlsx)
      3. Sistema lê e valida as linhas
      4. Preview com status de cada linha (pronta / atenção / bloqueada)
      5. Usuário confirma → lança via API em thread separada
      6. Resultado linha a linha com status de sucesso/erro
    """

    # Colunas da planilha (row index 3 = cabeçalho)
    COL_DATA          = "DATA"
    COL_TIPO          = "TIPO DESPESA\nMeEventos"
    COL_ID_EVENTO     = "ID\nMeEventos"
    COL_CATEGORIA     = "CATEGORIA\nMeEventos"
    COL_DETALHE       = "DETALHE PAGAMENTO"
    COL_VALOR         = "VALOR"
    COL_FORNECEDOR    = "FORNECEDOR"
    COL_FAVORECIDO    = "FAVORECIDO"
    COL_FORMA_PGTO    = "FORMA\nPGTO"
    COL_LANCAMENTO    = "PARA LANÇAMENTO DO FINANCEIRO NO Me Eventos"

    STATUS_OK       = "✓ Pronto"
    STATUS_ATENCAO  = "⚠ Atenção"
    STATUS_BLOQUEIO = "✗ Bloqueado"

    def __init__(self, master):
        self.top = tk.Toplevel(master)
        self.top.title("Lançamento no ERP — MeEventos")
        self.top.geometry("1300x780")
        self.top.minsize(1100, 600)

        try:
            icon_path = app_path("assets", "icon.ico")
            if icon_path.exists():
                self.top.iconbitmap(str(icon_path))
        except Exception:
            pass

        self.repo = SystemRepository(str(user_data_path("data", "conciliacao.db")))

        self.df_raw      = None
        self.df_preview  = None
        self.file_path   = None

        self._build_layout()
        self._load_api_settings()

        # Salva URL e token ao fechar a janela
        self.top.protocol("WM_DELETE_WINDOW", self._on_close)

    # =========================================================================
    # LAYOUT
    # =========================================================================

    def _build_layout(self):
        header = tk.Frame(self.top, bg="#1e293b", height=48)
        header.pack(fill="x")
        tk.Label(
            header, text="Lançamento de Despesas — ERP MeEventos",
            fg="white", bg="#1e293b", font=("Arial", 12, "bold")
        ).pack(side="left", padx=12, pady=10)

        # ── Parceiro + modo ───────────────────────────────────────────────────
        api_frame = tk.LabelFrame(self.top, text="Parceiro e modo", padx=10, pady=8)
        api_frame.pack(fill="x", padx=12, pady=(10, 0))

        tk.Label(api_frame, text="Parceiro:").grid(row=0, column=0, sticky="w", pady=4)

        from core.partner_rules import PARTNERS as _PARTNERS
        partner_names = [p["partner_name"] for p in _PARTNERS]

        self.partner_var = tk.StringVar()
        self.partner_combo = ttk.Combobox(
            api_frame, textvariable=self.partner_var,
            values=partner_names, state="readonly", width=28
        )
        self.partner_combo.grid(row=0, column=1, sticky="w", padx=8, pady=4)
        self.partner_combo.bind("<<ComboboxSelected>>", self._on_partner_selected)

        self.api_status_label = tk.Label(
            api_frame, text="Selecione o parceiro para carregar a configuração da API.",
            fg="#475569", anchor="w"
        )
        self.api_status_label.grid(row=0, column=2, columnspan=2, sticky="w", padx=(12, 0))

        tk.Label(api_frame, text="Modo:").grid(row=1, column=0, sticky="w", pady=4)
        self.dry_run_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            api_frame,
            text="Simulação (não envia para a API — só valida)",
            variable=self.dry_run_var
        ).grid(row=1, column=1, columnspan=3, sticky="w", padx=8)

        # Armazena URL e token carregados das configurações
        self._current_url   = ""
        self._current_token = ""

        # ── Arquivo ──────────────────────────────────────────────────────────
        file_frame = tk.LabelFrame(self.top, text="Planilha de despesas", padx=10, pady=8)
        file_frame.pack(fill="x", padx=12, pady=(8, 0))

        self.file_label = tk.Label(file_frame, text="Nenhuma planilha selecionada", fg="#64748b", anchor="w")
        self.file_label.pack(side="left", fill="x", expand=True)

        ttk.Button(file_frame, text="Selecionar planilha", command=self._select_file).pack(side="left", padx=6)
        ttk.Button(file_frame, text="↺ Revalidar", command=self._load_and_validate).pack(side="left")

        # ── Filtros de preview ────────────────────────────────────────────────
        filter_frame = tk.Frame(self.top)
        filter_frame.pack(fill="x", padx=12, pady=(8, 0))

        tk.Label(filter_frame, text="Exibir:").pack(side="left")
        self.filter_status_var = tk.StringVar(value="TODOS")
        ttk.Combobox(
            filter_frame,
            textvariable=self.filter_status_var,
            values=["TODOS", self.STATUS_OK, self.STATUS_ATENCAO, self.STATUS_BLOQUEIO],
            state="readonly", width=20
        ).pack(side="left", padx=6)
        self.filter_status_var.trace_add("write", lambda *a: self._refresh_preview())

        self.summary_label = tk.Label(filter_frame, text="", font=("Arial", 9, "bold"))
        self.summary_label.pack(side="left", padx=12)

        # ── Tabela de preview ─────────────────────────────────────────────────
        table_frame = tk.Frame(self.top)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(6, 0))

        cols = ("status", "linha", "data", "id_evento", "categoria",
                "descricao", "valor", "forma_pgto", "aviso")

        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        self.tree.pack(side="left", fill="both", expand=True)

        sy = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        sy.pack(side="right", fill="y")
        sx = ttk.Scrollbar(self.top, orient="horizontal", command=self.tree.xview)
        sx.pack(fill="x", padx=12)
        self.tree.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)

        headings = {
            "status":    "Status",
            "linha":     "Linha",
            "data":      "Data",
            "id_evento": "ID Evento",
            "categoria": "Categoria [ID]",
            "descricao": "Descrição (enviada à API)",
            "valor":     "Valor",
            "forma_pgto":"Modo Pgto",
            "aviso":     "Aviso / Observação",
        }
        widths = {
            "status": 100, "linha": 55, "data": 95,
            "id_evento": 80, "categoria": 180, "descricao": 280,
            "valor": 100, "forma_pgto": 80, "aviso": 300,
        }
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="w")

        self.tree.tag_configure(self.STATUS_OK,       background="#dff3e3")
        self.tree.tag_configure(self.STATUS_ATENCAO,  background="#fff3cd")
        self.tree.tag_configure(self.STATUS_BLOQUEIO, background="#f8d7da")
        self.tree.tag_configure("LANCADO",            background="#dbeafe")
        self.tree.tag_configure("ERRO_API",           background="#f8d7da")

        self.tree.bind("<Double-1>", self._on_row_double_click)

        # ── Rodapé ───────────────────────────────────────────────────────────
        footer = tk.Frame(self.top, bd=1, relief="solid", padx=10, pady=8)
        footer.pack(fill="x", padx=12, pady=(6, 12))

        self.btn_lancar = ttk.Button(
            footer, text="Lançar no ERP →", command=self._confirm_and_launch,
            state="disabled"
        )
        self.btn_lancar.pack(side="right", padx=6)

        ttk.Button(footer, text="Fechar", command=self.top.destroy).pack(side="right")

        ttk.Separator(footer, orient="vertical").pack(side="right", fill="y", padx=8)

        def _open_history():
            try:
                from ui.erp_history_window import ErpHistoryWindow
                ErpHistoryWindow(self.top, self.repo)
            except Exception as exc:
                from tkinter import messagebox
                messagebox.showerror("Erro", str(exc), parent=self.top)

        ttk.Button(footer, text="📋 Histórico",
                   command=_open_history).pack(side="right")

        self.progress = ttk.Progressbar(footer, orient="horizontal", length=200, mode="determinate")
        self.progress.pack(side="left", padx=(0, 10))

        self.status_label = tk.Label(footer, text="Selecione uma planilha para começar.", fg="#475569")
        self.status_label.pack(side="left")

        # Total de valor — alinhado à direita no rodapé
        self.total_valor_label = tk.Label(
            footer, text="", font=("Arial", 10, "bold"), fg="#1e293b")
        self.total_valor_label.pack(side="right", padx=(10, 0))

    # =========================================================================
    # HELPERS DE UI
    # =========================================================================

    def _on_partner_selected(self, event=None):
        """Carrega URL e token do parceiro selecionado a partir das Configurações."""
        name = self.partner_var.get()
        if not name:
            return
        safe = name.lower().replace(" ", "_")
        url   = self.repo.get_setting(f"erp_api_url_{safe}")   or ""
        token = self.repo.get_setting(f"erp_api_token_{safe}") or ""
        self._current_url   = url
        self._current_token = token

        if url and token:
            self.api_status_label.config(
                text=f"API configurada ✓  ({url})", fg="#166534")
        elif url:
            self.api_status_label.config(
                text="URL carregada, mas token não configurado.", fg="#92400e")
        else:
            self.api_status_label.config(
                text="Parceiro sem configuração de API. Acesse Configurações → API MeEventos.",
                fg="#b91c1c")

    def _load_api_settings(self):
        """Restaura o último parceiro selecionado."""
        try:
            last = self.repo.get_setting("erp_last_partner")
            if last and last in [p["partner_name"] for p in __import__(
                    "core.partner_rules", fromlist=["PARTNERS"]).PARTNERS]:
                self.partner_var.set(last)
                self._on_partner_selected()
        except Exception:
            pass

    def _save_api_settings(self):
        """Salva o último parceiro usado."""
        try:
            self.repo.save_setting("erp_last_partner", self.partner_var.get())
        except Exception:
            pass

    def _on_close(self):
        """Salva estado e fecha a janela."""
        self._save_api_settings()
        self.top.destroy()

    def _set_status(self, text, color="#475569"):
        self.status_label.config(text=text, fg=color)

    def _on_row_double_click(self, event):
        """Abre popup com o payload JSON completo da linha clicada."""
        item = self.tree.identify_row(event.y)
        if not item:
            return

        # Descobre o índice original pelo número da linha Excel (coluna 1)
        vals = self.tree.item(item, "values")
        if not vals:
            return

        try:
            linha_excel = int(vals[1])
            idx_original = linha_excel - 5   # header=4, dados=5+
        except (ValueError, IndexError):
            return

        if self.df_preview is None or self.df_preview.empty:
            return

        matches = self.df_preview[self.df_preview["_idx"] == idx_original]
        if matches.empty:
            return

        try:
            row = matches.iloc[0]
        except (IndexError, KeyError):
            return
        payload = row.get("_payload", {})
        status  = row.get("_status", "")
        aviso   = row.get("_aviso", "")

        # ── Monta o popup ────────────────────────────────────────────────────
        win = tk.Toplevel(self.top)
        win.title(f"Payload — Linha {linha_excel}")
        win.geometry("560x460")
        win.resizable(True, True)
        win.grab_set()

        # Cabeçalho colorido conforme status
        bg_colors = {
            self.STATUS_OK:       "#166534",
            self.STATUS_ATENCAO:  "#92400e",
            self.STATUS_BLOQUEIO: "#991b1b",
            "✓ Lançado":          "#1e40af",
            "✗ Erro API":         "#991b1b",
        }
        bg = bg_colors.get(status, "#1e293b")
        hdr = tk.Frame(win, bg=bg)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"Linha {linha_excel} — {status}",
                 fg="white", bg=bg, font=("Arial", 10, "bold")).pack(
            side="left", padx=12, pady=8)

        # Aviso (se houver)
        if aviso:
            tk.Label(win, text=f"⚠  {aviso}", fg="#92400e", anchor="w",
                     font=("Arial", 9), wraplength=520).pack(
                fill="x", padx=12, pady=(8, 0))

        # JSON formatado
        import json as _json
        payload_txt = _json.dumps(payload, ensure_ascii=False, indent=2)

        frame_txt = tk.Frame(win)
        frame_txt.pack(fill="both", expand=True, padx=12, pady=8)

        txt = tk.Text(frame_txt, wrap="word", font=("Courier New", 10),
                      bg="#f8fafc", relief="flat", bd=0)
        txt.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(frame_txt, orient="vertical", command=txt.yview)
        sb.pack(side="right", fill="y")
        txt.configure(yscrollcommand=sb.set)

        # Coloração básica das chaves JSON
        txt.insert("1.0", payload_txt)
        txt.config(state="disabled")

        # Rodapé
        btn_frame = tk.Frame(win, padx=12, pady=8)
        btn_frame.pack(fill="x")

        def copiar():
            win.clipboard_clear()
            win.clipboard_append(payload_txt)
            btn_copy.config(text="✓ Copiado!")
            win.after(1500, lambda: btn_copy.config(text="Copiar JSON"))

        btn_copy = ttk.Button(btn_frame, text="Copiar JSON", command=copiar)
        btn_copy.pack(side="left")
        ttk.Button(btn_frame, text="Fechar", command=win.destroy).pack(side="right")

    # =========================================================================
    # SELEÇÃO E LEITURA DA PLANILHA
    # =========================================================================

    def _select_file(self):
        path = filedialog.askopenfilename(
            title="Selecionar planilha de despesas",
            filetypes=[("Excel", "*.xlsx"), ("Todos", "*.*")]
        )
        if path:
            self.file_path = path
            self.file_label.config(text=Path(path).name, fg="#166534")
            self._load_and_validate()

    def _load_and_validate(self):
        if not self.file_path:
            messagebox.showwarning("Aviso", "Selecione uma planilha primeiro.")
            return

        self._set_status("Lendo planilha...")
        self.btn_lancar.config(state="disabled")

        threading.Thread(target=self._load_worker, daemon=True).start()

    def _find_header_row(self, df: pd.DataFrame) -> int:
        """
        Detecta a linha do cabeçalho buscando a célula 'DATA' nas primeiras 10 linhas.
        Funciona independente do número de linhas de instrução acima do cabeçalho.
        """
        for i in range(min(10, len(df))):
            row_vals = [str(v).strip() for v in df.iloc[i].tolist()]
            if "DATA" in row_vals:
                return i
        raise ValueError(
            "Cabeçalho 'DATA' não encontrado nas primeiras 10 linhas da aba 'Despesas'.\n"
            "Verifique se o arquivo selecionado é a planilha de despesas correta."
        )

    def _build_clean_headers(self, raw_headers: list) -> list:
        """
        Constrói nomes de colunas limpos a partir dos headers brutos,
        tratando células vazias/NaN e nomes duplicados.
        """
        clean = []
        seen = {}
        for i, h in enumerate(raw_headers):
            key = str(h).strip() if h is not None and str(h).strip() not in ("nan", "") else ""
            if not key:
                key = f"_col_{i}"
            if key in seen:
                seen[key] += 1
                key = f"{key}.{seen[key]}"
            else:
                seen[key] = 0
            clean.append(key)
        return clean

    def _load_worker(self):
        try:
            df_raw = pd.read_excel(self.file_path, sheet_name="Despesas", header=None)

            # Detecta o cabeçalho dinamicamente — funciona com qualquer versão da planilha
            header_row_idx = self._find_header_row(df_raw)
            headers = self._build_clean_headers(df_raw.iloc[header_row_idx].tolist())

            data = df_raw.iloc[header_row_idx + 1:].reset_index(drop=True)
            data.columns = headers

            # Seleciona apenas as colunas relevantes que existem
            keep = [
                self.COL_DATA, self.COL_TIPO, self.COL_ID_EVENTO,
                self.COL_CATEGORIA, self.COL_DETALHE, self.COL_VALOR,
                self.COL_FORNECEDOR, self.COL_FAVORECIDO, self.COL_FORMA_PGTO,
                self.COL_LANCAMENTO,
            ]
            missing = [c for c in keep if c not in data.columns]
            if missing:
                raise ValueError(
                    f"Coluna(s) não encontrada(s) na planilha: {missing}\n"
                    f"Colunas disponíveis: {[c for c in data.columns if not c.startswith('_col_')]}"
                )
            data = data[keep].copy()

            # Filtra linhas com data e valor válidos
            data = data[data[self.COL_DATA].notna()].copy()
            data = data[data[self.COL_VALOR].notna()].copy()
            data = data[data[self.COL_DATA].apply(
                lambda x: not isinstance(x, str) or x.strip() == ""
            )].copy()
            data = data[data[self.COL_VALOR].apply(
                lambda x: isinstance(x, (int, float)) and not np.isnan(float(x))
            )].copy()

            data = data.reset_index(drop=True)
            self.df_raw = data

            # Valida cada linha
            self.df_preview = self._validate_all(data)

            self.top.after(0, self._on_load_done)

        except Exception as exc:
            self.top.after(0, lambda m=str(exc): self._set_status(f"Erro ao ler planilha: {m}", "#b91c1c"))

    def _on_load_done(self):
        self._refresh_preview()
        total = len(self.df_preview)
        ok    = (self.df_preview["_status"] == self.STATUS_OK).sum()
        atenc = (self.df_preview["_status"] == self.STATUS_ATENCAO).sum()
        bloq  = (self.df_preview["_status"] == self.STATUS_BLOQUEIO).sum()

        # Calcula total de valor das linhas não bloqueadas
        total_val = self.df_preview[
            self.df_preview["_status"] != self.STATUS_BLOQUEIO
        ]["_valor"].sum()
        total_val_fmt = (f"R$ {total_val:,.2f}"
                         .replace(",","X").replace(".",",").replace("X","."))

        self.summary_label.config(
            text=f"Total: {total}  |  ✓ {ok}  ⚠ {atenc}  ✗ {bloq}"
        )
        self.total_valor_label.config(
            text=f"Total a lançar: {total_val_fmt}"
        )
        self._set_status(f"{total} despesas carregadas. Revise e clique em 'Lançar no ERP'.")
        if ok + atenc > 0:
            self.btn_lancar.config(state="normal")

    # =========================================================================
    # VALIDAÇÃO
    # =========================================================================

    def _validate_all(self, data: pd.DataFrame) -> pd.DataFrame:
        # ── Detecção de duplicatas (Tipo 1: data + descrição + valor idênticos) ──
        # Chave: data + coluna PARA LANÇAMENTO (descrição) + valor
        dup_indices = set()
        seen = {}

        for i, row in data.iterrows():
            try:
                data_val = pd.to_datetime(row.get(self.COL_DATA)).strftime("%Y-%m-%d")
            except Exception:
                data_val = str(row.get(self.COL_DATA) or "")

            descricao = str(row.get(self.COL_LANCAMENTO) or "").strip()
            if not descricao or descricao in ("nan", "#REF!"):
                descricao = str(row.get(self.COL_DETALHE) or "").strip()

            try:
                valor = round(abs(float(row.get(self.COL_VALOR) or 0)), 2)
            except Exception:
                valor = 0.0

            chave = (data_val, descricao, valor)

            if chave in seen:
                # Marca tanto a primeira ocorrência quanto esta como duplicata
                dup_indices.add(seen[chave])
                dup_indices.add(i)
            else:
                seen[chave] = i

        # Valida cada linha passando a informação de duplicata
        rows = []
        for i, row in data.iterrows():
            validated = self._validate_row(i, row, is_duplicate=(i in dup_indices))
            rows.append(validated)
        return pd.DataFrame(rows)

    def _validate_row(self, idx, row, is_duplicate=False) -> dict:
        avisos = []
        status = self.STATUS_OK

        # ── DUPLICATA ─────────────────────────────────────────────────────────
        if is_duplicate:
            avisos.append("Linha duplicada — mesma data, descrição e valor")
            status = self.STATUS_BLOQUEIO

        # ── DATA ──────────────────────────────────────────────────────────────
        data_val = row.get(self.COL_DATA)
        try:
            data_fmt = pd.to_datetime(data_val).strftime("%Y-%m-%d")
        except Exception:
            data_fmt = str(data_val)
            avisos.append("Data inválida")
            status = self.STATUS_BLOQUEIO

        # ── TIPO DESPESA (interno — todos são despesa=2) ───────────────────────
        tipo_raw = str(row.get(self.COL_TIPO, "") or "").strip()
        tipocobranca = TIPO_DESPESA_MAP.get(tipo_raw, 2)

        # ── ID EVENTO ─────────────────────────────────────────────────────────
        id_evento_raw = row.get(self.COL_ID_EVENTO)
        id_evento = None
        id_evento_display = ""

        if isinstance(id_evento_raw, (int, float)) and not np.isnan(float(id_evento_raw)):
            id_evento = int(id_evento_raw)
            id_evento_display = str(id_evento)
        elif isinstance(id_evento_raw, datetime):
            # Excel armazena o ID como serial numérico (ex: 46132 = 20/04/2026)
            # pandas converte para datetime — revertemos para o serial original
            from datetime import date as _date
            id_evento = (id_evento_raw.date() - _date(1899, 12, 30)).days
            id_evento_display = str(id_evento)
        elif str(id_evento_raw or "").strip().lower() in ("sem id", "preencher id", "nan", ""):
            id_evento_display = "Sem ID"
            avisos.append("Sem ID de evento — lançará sem vínculo com evento")
            status = max(status, self.STATUS_ATENCAO, key=self._status_weight)
        else:
            id_evento_display = str(id_evento_raw)
            avisos.append(f"ID pendente: '{id_evento_raw}' — lançará sem vínculo")
            status = max(status, self.STATUS_ATENCAO, key=self._status_weight)

        # ── VALOR ─────────────────────────────────────────────────────────────
        try:
            valor = abs(float(row.get(self.COL_VALOR, 0)))
            if valor <= 0:
                avisos.append("Valor zerado")
                status = self.STATUS_BLOQUEIO
        except Exception:
            valor = 0
            avisos.append("Valor inválido")
            status = self.STATUS_BLOQUEIO

        # ── DESCRIÇÃO — coluna "PARA LANÇAMENTO DO FINANCEIRO NO Me Eventos" ──
        # Esta é a descrição exata que o usuário já preparou para a tela do ERP.
        # Fallback: DETALHE | FAVORECIDO quando a coluna estiver vazia ou com erro.
        lancamento = str(row.get(self.COL_LANCAMENTO, "") or "").strip()
        detalhe    = str(row.get(self.COL_DETALHE, "")    or "").strip()
        favorecido = str(row.get(self.COL_FAVORECIDO, "") or "").strip()

        if lancamento and lancamento not in ("nan",) and "#REF!" not in lancamento:
            # Remove " | " inicial quando aparece por detalhe vazio (ex: " | FORNECEDOR")
            descricao = lancamento.lstrip(" |").strip()
        else:
            parts = [p for p in [detalhe, favorecido] if p and p not in ("nan",)]
            descricao = " | ".join(parts) if parts else tipo_raw

        # ── CATEGORIA → idcategoria ────────────────────────────────────────────
        categoria_raw = str(row.get(self.COL_CATEGORIA, "") or "").strip()
        id_categoria  = CATEGORIA_MAP.get(categoria_raw)

        if id_categoria is None:
            id_categoria = CATEGORIA_DEFAULT
            if categoria_raw and categoria_raw not in ("nan",):
                avisos.append(f"Categoria '{categoria_raw}' sem ID mapeado — usando padrão")
                status = max(status, self.STATUS_ATENCAO, key=self._status_weight)

        # ── MODO DE PAGAMENTO → mododepagamento ───────────────────────────────
        forma_raw = str(row.get(self.COL_FORMA_PGTO, "") or "").strip().upper()
        modo_pgto = FORMA_PGTO_MAP.get(forma_raw, FORMA_PGTO_DEFAULT)
        if forma_raw and forma_raw not in FORMA_PGTO_MAP:
            avisos.append(f"Forma '{forma_raw}' sem mapeamento — usando padrão")
            status = max(status, self.STATUS_ATENCAO, key=self._status_weight)

        # ── PAYLOAD — apenas os campos que o usuário preenche na tela do ERP ──
        # Campos: Valor, Descrição, Categoria, Modo de Pagamento, Evento
        payload = {
            "datapagamento":   data_fmt,
            "valor":           round(valor, 2),
            "pago":            "nao",        # padrão "Pendente" — igual à tela do ERP
            "tipocobranca":    tipocobranca,
            "descricao":       descricao[:200],
            "idcategoria":     id_categoria,
            "mododepagamento": modo_pgto,
        }
        if id_evento:
            payload["idevento"] = id_evento

        return {
            "_idx":               idx,
            "_status":            status,
            "_aviso":             " | ".join(avisos) if avisos else "",
            "_payload":           payload,
            "_data_fmt":          data_fmt,
            "_tipo_raw":          tipo_raw,
            "_id_evento_display": id_evento_display,
            "_categoria":         categoria_raw,
            "_id_categoria":      id_categoria,
            "_detalhe":           detalhe,
            "_valor":             valor,
            "_favorecido":        favorecido,
            "_forma_raw":         forma_raw,
            "_descricao":         descricao,
        }

    @staticmethod
    def _status_weight(s):
        return {ErpLancamentoWindow.STATUS_OK: 0,
                ErpLancamentoWindow.STATUS_ATENCAO: 1,
                ErpLancamentoWindow.STATUS_BLOQUEIO: 2}.get(s, 0)

    # =========================================================================
    # PREVIEW
    # =========================================================================

    def _refresh_preview(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.df_preview is None or self.df_preview.empty:
            return

        filtro = self.filter_status_var.get()
        df = self.df_preview
        if filtro != "TODOS":
            df = df[df["_status"] == filtro]

        for _, row in df.iterrows():
            # Categoria: mostra nome + ID mapeado (ou "sem ID" se padrão)
            cat_display = row["_categoria"][:22]
            id_cat = row.get("_id_categoria", 1)
            cat_display += f" [{id_cat}]" if id_cat != 1 else " [?]"

            # Descrição final que será enviada
            desc_display = row.get("_descricao", row["_detalhe"])[:45]

            self.tree.insert(
                "", "end",
                values=(
                    row["_status"],
                    row["_idx"] + 5,
                    row["_data_fmt"],
                    row["_id_evento_display"],
                    cat_display,
                    desc_display,
                    f"R$ {row['_valor']:,.2f}".replace(",","X").replace(".",",").replace("X","."),
                    row["_forma_raw"],
                    row["_aviso"][:90],
                ),
                tags=(row["_status"],)
            )

    # =========================================================================
    # LANÇAMENTO
    # =========================================================================

    def _confirm_and_launch(self):
        if self.df_preview is None or self.df_preview.empty:
            return

        dry      = self.dry_run_var.get()
        partner  = self.partner_var.get().strip()
        token    = self._current_token
        url_base = self._current_url.rstrip("/")

        if not partner:
            messagebox.showwarning("Aviso", "Selecione o parceiro antes de lançar.")
            return

        if not dry and not token:
            messagebox.showwarning(
                "Aviso",
                f"Token da API não configurado para '{partner}'.\n\n"
                "Acesse Configurações → API MeEventos para cadastrar."
            )
            return

        if not dry and not url_base:
            messagebox.showwarning(
                "Aviso",
                f"URL da API não configurada para '{partner}'.\n\n"
                "Acesse Configurações → API MeEventos para cadastrar."
            )
            return

        # Conta o que vai ser lançado (OK + ATENÇÃO, excluindo BLOQUEADO)
        df_to_send = self.df_preview[
            self.df_preview["_status"].isin([self.STATUS_OK, self.STATUS_ATENCAO])
        ]
        n = len(df_to_send)
        bloq = (self.df_preview["_status"] == self.STATUS_BLOQUEIO).sum()

        modo_txt = "SIMULAÇÃO" if dry else "REAL"
        msg = (
            f"Modo: {modo_txt}\n\n"
            f"Serão enviadas: {n} despesas\n"
            f"Bloqueadas (ignoradas): {bloq}\n\n"
            f"{'[SIMULAÇÃO — nenhum dado será enviado para a API]' if dry else 'Os dados serão ENVIADOS para a API do MeEventos.'}\n\n"
            f"Confirma?"
        )
        if not messagebox.askyesno("Confirmar lançamento", msg):
            return

        self.btn_lancar.config(state="disabled")
        self.progress["value"] = 0
        self._set_status("Iniciando lançamento...")

        # Registra o lote no banco para auditoria/rastreabilidade
        file_name = Path(self.file_path).name if self.file_path else "desconhecido"
        batch_id = self.repo.save_erp_launch_batch(
            partner_name  = partner,
            file_name     = file_name,
            file_path     = self.file_path or "",
            total_rows    = len(self.df_preview),
            total_enviado = 0,   # atualizado ao final
            total_simulado= 0,
            total_erro    = 0,
            dry_run       = dry,
        )

        threading.Thread(
            target=self._launch_worker,
            args=(df_to_send, url_base, token, dry, partner, batch_id),
            daemon=True
        ).start()

    def _launch_worker(self, df_to_send, url_base, token, dry_run, partner_name, batch_id):
        total   = len(df_to_send)
        results = []

        for i, (_, row) in enumerate(df_to_send.iterrows()):
            payload = row["_payload"]
            idx     = row["_idx"]

            if dry_run:
                result = {
                    "idx":     idx,
                    "status":  "SIMULADO",
                    "message": f"Payload validado: valor={payload.get('valor')} cat={payload.get('idcategoria')}",
                }
            else:
                result = self._post_to_api(url_base, token, payload, idx)

            # Grava item no banco para auditoria
            try:
                self.repo.save_erp_launch_item(
                    batch_id    = batch_id,
                    linha_excel = idx + 5,
                    partner_name= partner_name,
                    payload     = payload,
                    status      = result["status"],
                    id_api      = result.get("id_api", ""),
                    mensagem    = result.get("message", ""),
                    categoria   = row.get("_categoria", ""),
                )
            except Exception:
                pass   # auditoria não deve interromper o lançamento

            results.append(result)
            progress = int((i + 1) / total * 100)
            self.top.after(0, lambda p=progress, r=result, ri=row: self._on_row_launched(p, r, ri))

        self.top.after(0, lambda: self._on_launch_done(results, dry_run, batch_id))

    def _post_to_api(self, url_base, token, payload, idx) -> dict:
        try:
            import requests as _requests
        except ImportError:
            return {
                "idx": idx, "status": "ERRO_API",
                "message": "Pacote 'requests' não instalado. Execute: pip install requests"
            }

        try:
            resp = _requests.post(
                f"{url_base}/api/v1/financial",
                headers={
                    "Authorization": token,
                    "Content-Type":  "application/json",
                    "Accept":        "application/json",
                },
                json=payload,
                timeout=15,
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                id_criado = ""
                if isinstance(data.get("data"), list) and data["data"]:
                    id_criado = data["data"][0].get("idmovimentacao", "")
                return {
                    "idx":    idx,
                    "status": "LANCADO",
                    "message": f"ID criado: {id_criado}",
                    "id_api": id_criado,
                }
            else:
                return {
                    "idx":     idx,
                    "status":  "ERRO_API",
                    "message": f"HTTP {resp.status_code}: {resp.text[:120]}",
                }
        except _requests.exceptions.ConnectionError:
            return {"idx": idx, "status": "ERRO_API",
                    "message": "Sem conexão com a API. Verifique a URL e sua rede."}
        except _requests.exceptions.Timeout:
            return {"idx": idx, "status": "ERRO_API",
                    "message": "Tempo de resposta esgotado (timeout 15s). Tente novamente."}
        except Exception as exc:
            return {"idx": idx, "status": "ERRO_API", "message": str(exc)[:120]}

    def _on_row_launched(self, progress, result, row_series):
        self.progress["value"] = progress
        self._set_status(f"Lançando... {progress}%")

        # Atualiza a linha na treeview
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            linha_excel = row_series["_idx"] + 5
            if vals and str(vals[1]) == str(linha_excel):
                st = result.get("status", "")
                msg = result.get("message", "")
                novo_status = ("✓ Lançado" if st == "LANCADO"
                               else "✓ Simulado" if st == "SIMULADO"
                               else "✗ Erro API")
                tag = "LANCADO" if st in ("LANCADO", "SIMULADO") else "ERRO_API"
                new_vals = list(vals)
                new_vals[0] = novo_status
                new_vals[8] = msg[:80] if msg else ""
                self.tree.item(item, values=new_vals, tags=(tag,))
                break

    def _on_launch_done(self, results, dry_run, batch_id=None):
        self.progress["value"] = 100
        lancados = sum(1 for r in results if r.get("status") in ("LANCADO", "SIMULADO"))
        erros    = sum(1 for r in results if r.get("status") == "ERRO_API")

        modo = "simuladas" if dry_run else "lançadas"
        self._set_status(
            f"Concluído — {lancados} {modo}, {erros} com erro.",
            "#166534" if erros == 0 else "#b91c1c"
        )
        self.btn_lancar.config(state="normal")

        # Registra resumo no log de auditoria
        try:
            modo_log = "SIMULAÇÃO" if dry_run else "REAL"
            self.repo.log(
                "INFO",
                f"Lançamento ERP {modo_log} concluído",
                f"batch_id={batch_id} | {lancados} {modo} | {erros} erro(s)"
            )
        except Exception:
            pass

        msg = (
            f"Processo concluído!\n\n"
            f"{'Simuladas' if dry_run else 'Lançadas'}: {lancados}\n"
            f"Erros: {erros}\n"
        )
        if dry_run:
            msg += "\nNenhum dado foi enviado para a API (modo simulação)."

        messagebox.showinfo("Resultado", msg)