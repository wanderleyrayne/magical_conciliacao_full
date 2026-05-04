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
    # ── Custo de Mão de Obra ──────────────────────────────────────────
    "Brigadista":                    "16599",
    "Cerimonialista":                "16799",
    "Chef":                          "15699",
    "Decorador":                     "15599",
    "Eletricista":                   "16699",
    "Gerente de Evento":             "15999",
    "Mão de Obra Especializada":     "16999",
    "Recepcionista":                 "15799",
    "Segurança e Manobrista":        "16899",
    "Manobrista":                    "16899",

    # ── Custo Produtos Alimentícios ───────────────────────────────────
    "Bar":                           "17699",
    "Bebidas":                       "17099",
    "Bolo":                          "17199",
    "Buffet":                        "17299",
    "Doce":                          "17399",
    "Produtos Alimentícios - Outros":"17499",
    "Degustação":                    "17599",

    # ── Serviços Terceiros ────────────────────────────────────────────
    "Decoração":                     "17899",
    "Limpeza":                       "18299",

    # ── Som & Imagem / Iluminação ─────────────────────────────────────
    "Som & Imagem":                  "18099",
    "Iluminação":                    "18199",

    # ── Custo Logística & Transporte ──────────────────────────────────
    "Combustível":                   "14099",
    "Frete":                         "17799",
    "Translado":                     "15299",
    "Transporte Cargas":             "2082717",

    # ── Custo de Materiais & Mobiliários ─────────────────────────────
    "Aluguel Mobiliário":            "17999",

    # ── Despesas Prestadores ──────────────────────────────────────────
    "Prestação de Serviços":         "2082704",
    "Prestação de Serviços - T":     "15499",
    "Prestação de Serviços - A":     "15399",
    "Prestação de Serviços - CB":    "21299",
    "Repasse":                       "14199",
    "Repasse - P":                   "2082708",
    "Repasse - SG":                  "21199",
    "Salário":                       "2082716",
    "Remuneração - Vendedores":      "20899",
    "Remuneração - Planejadoras":    "20999",
    "Remuneração - SDR":             "21099",
    "Férias":                        "21499",
    "Rescisões Trabalhistas":        "15099",
    "Pró-Labore Sócios":             "20699",

    # ── Despesas Gerais ───────────────────────────────────────────────
    "Assistência Contábil & BPO":    "14299",
    "Assistência Jurídica":          "19599",
    "Cartório":                      "13999",
    "Copa & Cozinha":                "19699",
    "Estornos - Lançamentos Indevidos": "2082706",
    "Instalações Comerciais":        "19999",
    "Locação de Equipamentos":       "19799",
    "Manutenção & Conservação":      "14799",
    "Material de Escritório":        "20099",
    "Materiais de Limpeza & Higiene":"14699",
    "Móveis & Utensílios":           "19899",
    "Obras & Reformas":              "19499",
    "Passagem aéreas":               "14899",
    "Serviços Gerais":               "20599",
    "Tecnologia da Informação":      "20199",
    "Telefonia & Internet":          "20299",

    # ── Despesas Marketing & Publicidade ─────────────────────────────
    "Elaboração Conteúdo":           "14999",
    "Estrutura de Marketing":        "16299",
    "Marketing & Publicidade":       "2082699",
    "Tráfego Pago":                  "2081799",

    # ── Despesas Ocupacional ──────────────────────────────────────────
    "Água e esgoto":                 "13599",
    "Alarmes":                       "19399",
    "Aluguel":                       "13699",
    "Aquisição de Equipamentos":     "13799",
    "Condomínio":                    "18699",
    "Energia Elétrica":              "18999",
    "Gás":                           "19099",
    "Gerador":                       "19199",
    "IPTU":                          "2080799",
    "Seguros":                       "19299",
    "Taxas":                         "18899",

    # ── Impostos ─────────────────────────────────────────────────────
    "COFINS":                        "2082720",
    "CSLL":                          "2080699",
    "CSLL & IRPJ":                   "2082718",
    "FGTS":                          "2080299",
    "ICMS":                          "2080399",
    "IMPOSTO":                       "2081399",
    "INSS":                          "2080499",
    "IOF":                           "15899",
    "IRPJ":                          "2082723",
    "ISS":                           "2081199",
    "PIS":                           "2082724",
    "PIS & COFINS":                  "2082719",
    "SIMPLES NACIONAL":              "2082721",

    # ── Tarifas Bancárias ─────────────────────────────────────────────
    "Tarifa Boleto":                 "18499",
    "Tarifa Cartão Crédito":         "2082499",
    "Tarifa Cartão Débito":          "2082399",
    "Tarifa PIX":                    "18599",
    "Tarifas Bancárias":             "15199",

    # ── Outras ────────────────────────────────────────────────────────
    "Antecipação - Degustação":      "2082712",
    "Antecipações & Retiradas Sócios":"20499",
    "Arrendamento":                  "13899",
    "Comissão Magical":              "2081499",
    "Despesas com Sócios":           "20399",
    "Devoluções de Vendas":          "13499",
    "Empréstimos":                   "14399",
    "Investimentos":                 "14499",
    "Juros":                         "14599",
    "Participação Sócios":           "2082599",

    # ── Receitas ─────────────────────────────────────────────────────
    "Receita - Sinal":               "13099",
    "Receita - Recorrentes":         "13199",
    "Receita - Integralização":      "13399",
    "Receita - Aplicações":          "13299",
    "Receita - Financeiras":         "16099",
    "Receita - Quitação":            "16099",
    "Receita - Serviços":            "2081599",
    "Receita - Opcional Pós Venda":  "2082709",
    "Estrutura de Marketing (R)":    "2082299",
    "Crédito Indevido":              "2082707",
}
CATEGORIA_DEFAULT = "2082704"   # Prestação de Serviços — fallback genérico


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
    COL_CATEGORIA_ALT = "CATEGORIA MeEventos"
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
        self._categoria_map_local = {}   # categorias dinâmicas do parceiro atual

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
        ttk.Button(file_frame, text="↺ Revalidar", command=self._revalidate).pack(side="left")

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
            "descricao": "Descrição ",
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
        """Carrega URL e token do parceiro selecionado e busca categorias da API."""
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
            # Carrega categorias em background
            import threading as _t
            _t.Thread(target=self._load_categories,
                      args=(url, token, safe), daemon=True).start()
        elif url:
            self.api_status_label.config(
                text="URL carregada, mas token não configurado.", fg="#92400e")
        else:
            self.api_status_label.config(
                text="Parceiro sem configuração de API. Acesse Configurações → API MeEventos.",
                fg="#b91c1c")

    def _load_categories(self, url_base: str, token: str, safe_name: str):
        """
        Busca categorias da API do MeEventos para o parceiro atual.
        Cache de 7 dias no banco — silencioso, sem feedback na UI.
        """
        import json as _json
        from datetime import datetime, timedelta

        cache_key    = f"erp_categories_{safe_name}"
        cache_ts_key = f"erp_categories_ts_{safe_name}"

        # Verifica cache — usa se tiver menos de 7 dias
        try:
            cached    = self.repo.get_setting(cache_key)
            cached_ts = self.repo.get_setting(cache_ts_key)
            if cached and cached_ts:
                ts = datetime.fromisoformat(cached_ts)
                if datetime.now() - ts < timedelta(days=7):
                    self._categoria_map_local = _json.loads(cached)
                    return  # cache válido — não chama a API
        except Exception:
            pass

        # Cache expirado ou inexistente — busca da API
        try:
            import requests as _req
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
                "Accept":        "application/json",
            }
            categoria_map = {}

            for tipo in ("despesas", "receitas"):
                page = 1
                while True:
                    resp = _req.get(
                        f"{url_base.rstrip('/')}/api/v1/financial-categories",
                        params={"tipo": tipo, "page": page, "page_size": 100},
                        headers=headers, timeout=10
                    )
                    if resp.status_code != 200:
                        break
                    data = resp.json()
                    for cat in data.get("data", []):
                        nome = str(cat.get("nome") or "").strip()
                        cid  = str(cat.get("id")   or "").strip()
                        if nome and cid:
                            categoria_map[nome] = cid
                    pagination = data.get("pagination", {})
                    if page >= pagination.get("total_page", 1):
                        break
                    page += 1

            if categoria_map:
                self._categoria_map_local = categoria_map
                self.repo.save_setting(cache_key, _json.dumps(categoria_map))
                self.repo.save_setting(cache_ts_key, datetime.now().isoformat())

        except Exception:
            pass  # falha silenciosa — usa mapa estático como fallback

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

    def _parse_date_str(self, text: str) -> str | None:
        """
        Tenta converter texto para data no formato YYYY-MM-DD.
        Aceita: 23/04/2026, 2026-04-23, 23-04-2026, 2304/2026, 2304/26.
        Retorna None se não conseguir parsear.
        """
        import re as _re
        text = text.strip()

        # DD/MM/YYYY
        m = _re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', text)
        if m:
            return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

        # YYYY-MM-DD
        m = _re.match(r'^(\d{4})-(\d{2})-(\d{2})$', text)
        if m:
            return text

        # DD-MM-YYYY
        m = _re.match(r'^(\d{1,2})-(\d{1,2})-(\d{4})$', text)
        if m:
            return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"

        # DDMM/YYYY — ex: "2304/2026" (Excel remove o zero do dia)
        m = _re.match(r'^(\d{2})(\d{2})/(\d{4})$', text)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"

        # DDMM/YY — ex: "2304/26"
        m = _re.match(r'^(\d{2})(\d{2})/(\d{2})$', text)
        if m:
            return f"20{m.group(3)}-{m.group(2)}-{m.group(1)}"

        # Tenta pandas como último recurso
        try:
            import pandas as _pd
            dt = _pd.to_datetime(text, dayfirst=True, errors="coerce")
            if not _pd.isna(dt):
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

        return None

    def _resolve_event_by_date(self, data_fmt: str,
                                avisos: list) -> tuple:
        """
        Busca o ID do evento pela data via API do MeEventos.
        Usa cache em memória para evitar chamadas repetidas.
        Retorna (id_evento, id_evento_display) ou (None, "").
        """
        if not hasattr(self, "_event_date_cache"):
            self._event_date_cache = {}

        if data_fmt in self._event_date_cache:
            cached = self._event_date_cache[data_fmt]
            if cached:
                return cached, f"{cached} ({data_fmt})"
            return None, ""

        url_base = getattr(self, "_current_url", "").rstrip("/")
        token    = getattr(self, "_current_token", "")

        if not url_base or not token:
            self._event_date_cache[data_fmt] = None
            return None, ""

        try:
            import requests as _req
            resp = _req.get(
                f"{url_base}/api/v1/events",
                params={"start": data_fmt, "end": data_fmt},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    evento_id = str(data[0].get("id", ""))
                    nome      = str(data[0].get("nomeevento", "")).strip()[:40]
                    if len(data) > 1:
                        avisos.append(
                            f"{len(data)} eventos em {data_fmt} — vinculado ao primeiro: {nome}")
                    self._event_date_cache[data_fmt] = evento_id
                    return evento_id, f"{evento_id} ({nome})"
                else:
                    self._event_date_cache[data_fmt] = None
                    return None, ""
            else:
                self._event_date_cache[data_fmt] = None
                return None, ""
        except Exception:
            pass

        self._event_date_cache[data_fmt] = None
        return None, ""

    def _revalidate(self):
        """Limpa cache de eventos e revalida a planilha com o parceiro atual."""
        self._event_date_cache = {}
        self._load_and_validate()

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

            # Normaliza coluna CATEGORIA — aceita com ou sem quebra de linha
            if self.COL_CATEGORIA not in data.columns and self.COL_CATEGORIA_ALT in data.columns:
                data = data.rename(columns={self.COL_CATEGORIA_ALT: self.COL_CATEGORIA})

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
        # ── Detecção de duplicatas ────────────────────────────────────────────
        # Chave: data + descrição + valor + ID evento
        # Se o ID evento é diferente → mesmo manobrista em eventos diferentes → NÃO é duplicata
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

            # ID evento faz parte da chave — mesmo manobrista em eventos distintos não é duplicata
            id_evento_raw = str(row.get(self.COL_ID_EVENTO) or "").strip()
            id_evento_key = id_evento_raw if id_evento_raw not in ("nan", "", "Sem ID") else "__sem_id__"

            chave = (data_val, descricao, valor, id_evento_key)

            if chave in seen:
                dup_indices.add(seen[chave])
                dup_indices.add(i)
            else:
                seen[chave] = i

        # Valida cada linha
        rows = []
        for i, row in data.iterrows():
            validated = self._validate_row(i, row, is_duplicate=(i in dup_indices))
            rows.append(validated)
        return pd.DataFrame(rows)

    def _validate_row(self, idx, row, is_duplicate=False) -> dict:
        avisos = []
        status = self.STATUS_OK

        # ── JÁ LANÇADO ANTERIORMENTE ──────────────────────────────────────────
        if not is_duplicate:
            try:
                partner = self.partner_var.get() if hasattr(self, 'partner_var') else ""
                file_name = Path(self.file_path).name if self.file_path else ""
                linha_num = idx + 5  # offset do header

                ja_lancado = self.repo.check_already_launched(
                    partner_name=partner,
                    file_name=file_name,
                    linha=linha_num,
                    descricao=str(row.get(self.COL_LANCAMENTO) or ""),
                    valor=abs(float(row.get(self.COL_VALOR) or 0)),
                )
                if ja_lancado and not self._dry_run_var.get():
                    avisos.append(
                        f"Já lançado em {str(ja_lancado.get('created_at',''))[:16]}"
                        f" | ID API: {ja_lancado.get('id_api','—')}"
                        f" — linha ignorada no relançamento"
                    )
                    status = self.STATUS_BLOQUEIO
            except Exception:
                pass
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
            # Número direto → usa como ID
            id_evento = int(id_evento_raw)
            id_evento_display = str(id_evento)
        elif isinstance(id_evento_raw, datetime):
            # Excel pode converter data para datetime — tenta buscar evento por data
            data_evento = id_evento_raw.strftime("%Y-%m-%d")
            id_evento, id_evento_display = self._resolve_event_by_date(data_evento, avisos)
            if not id_evento:
                id_evento_display = id_evento_raw.strftime("%d/%m/%Y")
                avisos.append(f"Data '{id_evento_display}' — nenhum evento encontrado")
                status = max(status, self.STATUS_ATENCAO, key=self._status_weight)
        elif str(id_evento_raw or "").strip().lower() in ("sem id", "preencher id", "nan", ""):
            id_evento_display = "Sem ID"
            avisos.append("Sem ID de evento — lançará sem vínculo com evento")
            status = max(status, self.STATUS_ATENCAO, key=self._status_weight)
        else:
            # Pode ser uma data no formato texto (ex: "23/04/2026")
            raw_str = str(id_evento_raw).strip()
            data_fmt = self._parse_date_str(raw_str)
            if data_fmt:
                id_evento, id_evento_display = self._resolve_event_by_date(data_fmt, avisos)
                if not id_evento:
                    id_evento_display = raw_str
                    avisos.append(f"Data '{raw_str}' — nenhum evento encontrado")
                    status = max(status, self.STATUS_ATENCAO, key=self._status_weight)
            else:
                # Tenta usar como ID diretamente
                try:
                    id_evento = int(float(raw_str))
                    id_evento_display = str(id_evento)
                except Exception:
                    id_evento_display = raw_str
                    avisos.append(f"ID pendente: '{raw_str}' — lançará sem vínculo")
                    status = max(status, self.STATUS_ATENCAO, key=self._status_weight)

        # ── VALOR ─────────────────────────────────────────────────────────────
        # Aceita todos os formatos: Número, Moeda, Contábil (pandas já lê como float),
        # texto BR "238,00" / "2.230,03", texto EN "238.00"
        valor_raw = row.get(self.COL_VALOR, 0)
        valor = 0.0

        def _parse_valor(v) -> float | None:
            import re as _re
            # 1. Já é numérico (Número/Moeda/Contábil do Excel → pandas float)
            if isinstance(v, (int, float)):
                try:
                    f = float(v)
                    return abs(f) if f != float('nan') else None
                except Exception:
                    return None
            s = str(v or "").strip()
            # Remove símbolos de moeda e espaços
            s = _re.sub(r'[R\$\s]', '', s)
            if not s or s in ("nan", "None", ""):
                return None
            # Formato BR: vírgula como decimal (238,00 / 2.230,03)
            if ',' in s:
                try:
                    return abs(float(s.replace(".", "").replace(",", ".")))
                except Exception:
                    pass
            # Formato EN ou número puro: ponto como decimal ou sem decimal
            try:
                return abs(float(s.replace(",", "")))
            except Exception:
                pass
            return None

        resultado = _parse_valor(valor_raw)

        if resultado and resultado > 0:
            valor = resultado
        elif resultado == 0.0 or resultado is None:
            avisos.append(f"Valor inválido ou zerado: '{valor_raw}'")
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
        # Aceita dois formatos de cabeçalho: "CATEGORIA\nMeEventos" ou "CATEGORIA MeEventos"
        categoria_raw = str(
            row.get(self.COL_CATEGORIA) or
            row.get(self.COL_CATEGORIA_ALT) or ""
        ).strip()

        # 1. Mapa dinâmico do parceiro (buscado da API) — tem prioridade
        # 2. Mapa estático hardcoded (fallback)
        id_categoria = (
            self._categoria_map_local.get(categoria_raw) or
            CATEGORIA_MAP.get(categoria_raw)
        )

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
        payload = {
            "datapagamento":   data_fmt,
            "valor":           round(valor, 2),
            "pago":            "nao",
            "tipocobranca":    tipocobranca,
            "descricao":       descricao[:200],
            "idcategoria":     id_categoria,
        }
        # mododepagamento opcional — só inclui se mapeado explicitamente
        if forma_raw in FORMA_PGTO_MAP:
            payload["mododepagamento"] = modo_pgto
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
        from logger import log as _log
        total   = len(df_to_send)
        results = []
        file_name = Path(self.file_path).name if self.file_path else "desconhecido"

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

            # Log de cada item
            _log.lancamento_item(
                parceiro  = partner_name,
                linha     = idx + 5,
                status    = result["status"],
                id_api    = result.get("id_api", ""),
                payload   = payload if result["status"] == "ERRO_API" else None,
                mensagem  = result.get("message", ""),
            )

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
                pass

            results.append(result)
            progress = int((i + 1) / total * 100)
            self.top.after(0, lambda p=progress, r=result, ri=row: self._on_row_launched(p, r, ri))

        # Log de resumo do lote
        ok   = sum(1 for r in results if r["status"] == "LANCADO")
        erros= sum(1 for r in results if r["status"] == "ERRO_API")
        sim  = sum(1 for r in results if r["status"] == "SIMULADO")
        valor_total = sum(
            abs(float(row["_payload"].get("valor") or 0))
            for _, row in df_to_send.iterrows()
            if row["_payload"].get("valor")
        )
        _log.lancamento(
            parceiro    = partner_name,
            planilha    = file_name,
            caminho     = self.file_path or "",
            ok          = ok if not dry_run else sim,
            erros       = erros,
            simulado    = dry_run,
            valor_total = valor_total,
        )

        self.top.after(0, lambda: self._on_launch_done(results, dry_run, batch_id))

    def _post_to_api(self, url_base, token, payload, idx) -> dict:
        from logger import log as _log
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
            _log.api(
                endpoint = "POST /api/v1/financial",
                status   = resp.status_code,
                payload  = payload if resp.status_code not in (200, 201) else None,
                resposta = resp.json() if resp.status_code not in (200, 201) else None,
                parceiro = "",
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
            _log.erro("Exceção em _post_to_api", exc=exc)
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