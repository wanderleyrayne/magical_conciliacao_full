"""
pendencias_window.py — Tela de Pendências do fluxo colaborativo.

Mostra planilhas aguardando lançamento no ERP, geração de CNAB
e aprovação do Diretor. Integrado com PocketBase (cloud_sync).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import threading
from datetime import datetime


class PendenciasWindow:
    """Tela de Pendências — mostra fluxo colaborativo em tempo real."""

    POLL_INTERVAL = 60_000  # 60 segundos

    STATUS_CORES = {
        "recebido":      "#fef3c7",  # amarelo
        "em_lancamento": "#dbeafe",  # azul
        "lancado":       "#d1fae5",  # verde claro
        "cnab_gerado":   "#a7f3d0",  # verde
        "cnab_enviado":  "#6ee7b7",  # verde escuro
        "aprovado":      "#bbf7d0",  # verde aprovado
        "reprovado":     "#fecaca",  # vermelho
    }

    STATUS_LABEL = {
        "recebido":      "⏳ Aguardando lançamento ERP",
        "em_lancamento": "🔄 Em lançamento...",
        "lancado":       "✅ ERP lançado — aguarda CNAB",
        "cnab_gerado":   "📄 CNAB gerado — aguarda envio",
        "cnab_enviado":  "🏦 Enviado ao Itaú — aguarda aprovação",
        "aprovado":      "✅ Aprovado pelo Diretor",
        "reprovado":     "❌ Reprovado",
    }

    def __init__(self, master, db_path: str = None):
        # Resolve db_path automaticamente se não fornecido
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

        self.win = tk.Toplevel(master)
        self.win.title("Pendências — Fluxo Colaborativo")
        self.win.geometry("1100x600")
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._init_cloud()
        self._load()

    def _get_cfg(self, chave: str, default: str = "") -> str:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS nuvem_config "
                    "(chave TEXT PRIMARY KEY, valor TEXT)"
                )
                row = conn.execute(
                    "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1",
                    (chave,)
                ).fetchone()
                return row[0] if row and row[0] else default
        except Exception:
            return default

    def _init_cloud(self):
        try:
            pb_url   = self._get_cfg("pb_url")
            pb_email = self._get_cfg("pb_email")
            pb_senha = self._get_cfg("pb_senha")
            print(f"[PENDENCIAS] db_path={self.db_path}")
            print(f"[PENDENCIAS] pb_url={pb_url}")
            if pb_url and pb_email and pb_senha:
                from cloud_sync import CloudSync
                self.cloud = CloudSync(pb_url, pb_email, pb_senha)
                print("[PENDENCIAS] CloudSync inicializado OK")
            else:
                print("[PENDENCIAS] configs vazias — cloud nao inicializado")
        except Exception as e:
            print(f"[PENDENCIAS] erro init_cloud: {e}")
            self.cloud = None

    def _build_ui(self):
        # Cabeçalho
        hdr = tk.Frame(self.win, bg="#1e293b", pady=12)
        hdr.pack(fill="x")
        tk.Label(hdr, text="📋  Pendências — Fluxo Colaborativo",
                 bg="#1e293b", fg="white",
                 font=("Arial", 14, "bold")).pack(side="left", padx=16)

        # Filtros
        fil = tk.Frame(self.win)
        fil.pack(fill="x", padx=10, pady=(8, 0))

        tk.Label(fil, text="Filtro:").pack(side="left")
        self.filtro_var = tk.StringVar(value="TODOS")
        cb = ttk.Combobox(fil, textvariable=self.filtro_var, width=25,
                          state="readonly", values=[
                              "TODOS", "Aguardando ERP", "Aguardando CNAB",
                              "Aguardando Aprovação", "Aprovadas", "Reprovadas"
                          ])
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._load())

        ttk.Button(fil, text="↺ Atualizar", command=self._load).pack(side="left", padx=6)

        self.lbl_status = tk.Label(fil, text="", fg="#64748b", font=("Arial", 9))
        self.lbl_status.pack(side="right", padx=10)

        # Tabela principal
        # Frame da tabela — criado antes do Treeview
        frame_tree = tk.Frame(self.win)
        frame_tree.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        cols = ("casa", "planilha", "status", "valor", "itens",
                "lancado_por", "gerado_por", "criado_em")
        self.tree = ttk.Treeview(frame_tree, columns=cols, show="headings", height=18)

        for col, hd, w in [
            ("casa",       "Casa",          120),
            ("planilha",   "Planilha",      200),
            ("status",     "Status",        230),
            ("valor",      "Valor Total",   100),
            ("itens",      "Itens",          60),
            ("lancado_por","Lançado por",   110),
            ("gerado_por", "CNAB por",      110),
            ("criado_em",  "Recebido em",   140),
        ]:
            self.tree.heading(col, text=hd)
            self.tree.column(col, width=w, anchor="w")

        sb = ttk.Scrollbar(frame_tree, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill="both", expand=True, side="left")
        sb.pack(side="right", fill="y")

        # Configura cores por status
        for status, cor in self.STATUS_CORES.items():
            self.tree.tag_configure(status, background=cor)

        self.tree.bind("<Double-1>", self._on_double_click)

        # Rodapé com ações — pack antes da tabela para garantir visibilidade
        rod = tk.Frame(self.win, bg="#f1f5f9", pady=8, relief="ridge", bd=1)
        rod.pack(fill="x", side="bottom")

        rf = tk.Frame(rod, bg="#f1f5f9")
        rf.pack(pady=4)

        ttk.Button(rf, text="✅ Assumir lançamento ERP",
                   command=self._assumir_lancamento).pack(side="left", padx=6)
        ttk.Button(rf, text="📄 Marcar CNAB gerado",
                   command=self._marcar_cnab_gerado).pack(side="left", padx=6)
        ttk.Button(rf, text="🏦 Confirmar envio Itaú",
                   command=self._confirmar_envio).pack(side="left", padx=6)
        ttk.Separator(rf, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Button(rf, text="Fechar",
                   command=self._on_close).pack(side="left", padx=6)



    def _brl(self, v) -> str:
        try:
            return f"R$ {float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "—"

    def _load(self):
        """Carrega pendências do PocketBase."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        if not self.cloud:
            self.lbl_status.config(
                text="⚠ PocketBase não configurado — vá em Configurações → Nuvem",
                fg="#b45309"
            )
            return

        def _fetch():
            try:
                todas = self.cloud.listar_todas(limit=100)
                self.win.after(0, lambda: self._populate(todas))
            except Exception as e:
                self.win.after(0, lambda: self.lbl_status.config(
                    text=f"Erro ao carregar: {e}", fg="#dc2626"))

        threading.Thread(target=_fetch, daemon=True).start()

        # Agenda próximo polling
        if self._poll_id:
            self.win.after_cancel(self._poll_id)
        self._poll_id = self.win.after(self.POLL_INTERVAL, self._load)

    def _populate(self, pendencias: list):
        filtro = self.filtro_var.get()

        STATUS_CONCLUIDOS = {"aprovado", "reprovado"}

        filtro_map = {
            "Aguardando ERP":       ["recebido", "em_lancamento"],
            "Aguardando CNAB":      ["lancado"],
            "Aguardando Aprovação": ["cnab_gerado", "cnab_enviado"],
            "Aprovadas":            ["aprovado"],
            "Reprovadas":           ["reprovado"],
        }

        if filtro == "TODOS":
            # TODOS = só pendentes (exclui aprovado/reprovado)
            pendencias = [p for p in pendencias
                          if p.get("status") not in STATUS_CONCLUIDOS]
        else:
            status_filtro = filtro_map.get(filtro, [])
            pendencias = [p for p in pendencias
                          if p.get("status") in status_filtro]

        for p in pendencias:
            status   = p.get("status", "")
            label    = self.STATUS_LABEL.get(status, status)
            criado = str(p.get("recebido_em") or "—")

            self.tree.insert("", "end", iid=p["id"], values=(
                p.get("casa", ""),
                p.get("nome_arquivo", ""),
                label,
                self._brl(p.get("total_valor", 0)),
                p.get("total_itens", 0),
                p.get("lancado_por", ""),
                p.get("cnab_gerado_por", ""),
                criado,
            ), tags=(status,))

        qtd = len(pendencias)
        now = datetime.now().strftime("%H:%M:%S")
        self.lbl_status.config(
            text=f"{qtd} registro(s) · Atualizado às {now}",
            fg="#64748b"
        )

    def _sel_planilha(self) -> tuple:
        """Retorna (id, casa, status) da linha selecionada ou None."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Pendências",
                "Selecione uma planilha na lista.", parent=self.win)
            return None, None, None
        iid   = sel[0]
        vals  = self.tree.item(iid, "values")
        casa  = vals[0] if vals else ""
        tags  = self.tree.item(iid, "tags")
        status = tags[0] if tags else ""
        return iid, casa, status

    def _assumir_lancamento(self):
        pid, casa, status = self._sel_planilha()
        if not pid:
            return
        if status not in ("recebido",):
            messagebox.showwarning("Pendências",
                f"Esta planilha está com status '{status}' — não pode assumir.",
                parent=self.win)
            return

        meu_nome = self._get_cfg("meu_nome", "Usuário")
        if not messagebox.askyesno("Assumir lançamento",
            f"Assumir lançamento da planilha de '{casa}'?\n\n"
            f"O arquivo será baixado e aberto no Lançamento ERP.",
            parent=self.win):
            return

        self.lbl_status.config(text="Baixando arquivo...", fg="#2563eb")

        def _do():
            try:
                # 1. Marca como em lançamento
                self.cloud.iniciar_lancamento(pid, meu_nome)

                # 2. Baixa o arquivo do PocketBase
                import tempfile, os
                destino = os.path.join(tempfile.gettempdir(), "magical_pendencias")
                caminho = self.cloud.download_arquivo(pid, destino)

                self.win.after(0, lambda: self._abrir_erp(pid, casa, caminho))
            except Exception as e:
                self.win.after(0, lambda: messagebox.showerror(
                    "Erro", str(e), parent=self.win))

        threading.Thread(target=_do, daemon=True).start()

    def _abrir_erp(self, planilha_id: str, casa: str, caminho_arquivo: str):
        """Abre a tela de Lançamento ERP com o arquivo já carregado."""
        self._load()

        if not caminho_arquivo:
            messagebox.showwarning(
                "Arquivo não encontrado",
                "O arquivo não foi encontrado no PocketBase.\n\n"
                "Selecione manualmente na tela de Lançamento ERP.",
                parent=self.win
            )

        try:
            from ui.erp_lancamento_window import ErpLancamentoWindow
            erp = ErpLancamentoWindow(self.win)

            # Pré-seleciona o parceiro/casa
            if hasattr(erp, 'partner_var'):
                from core.partner_rules import PARTNERS
                for p in PARTNERS:
                    if p.get("partner_name", "").upper() == casa.upper():
                        erp.partner_var.set(p["partner_name"])
                        erp._on_partner_selected()
                        break

            # Carrega o arquivo automaticamente
            if caminho_arquivo and hasattr(erp, '_load_file_from_path'):
                erp._load_file_from_path(caminho_arquivo)
            elif caminho_arquivo:
                # Fallback: seta o file_path e carrega
                erp.file_path = caminho_arquivo
                erp.file_label.config(
                    text=caminho_arquivo.split("\\")[-1],
                    fg="#16a34a"
                )
                erp._load_and_validate()

            # Guarda o ID da pendência para atualizar ao concluir
            erp._pendencia_id = planilha_id
            erp._pendencia_casa = casa

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir ERP: {e}", parent=self.win)

    def _marcar_cnab_gerado(self):
        pid, casa, status = self._sel_planilha()
        if not pid:
            return
        if status not in ("lancado",):
            messagebox.showwarning("Pendências",
                f"Status atual: '{status}' — só pode gerar CNAB após ERP lançado.",
                parent=self.win)
            return

        meu_nome = self._get_cfg("meu_nome", "Usuário")
        vals     = self.tree.item(pid, "values")
        valor    = vals[3] if vals else "?"

        if not messagebox.askyesno("Gerar CNAB",
            f"Gerar arquivo CNAB 240 (PIX) para '{casa}'?\n\n"
            f"Valor: {valor}\n\n"
            f"O arquivo será salvo na pasta Downloads.",
            parent=self.win):
            return

        self.lbl_status.config(text="Gerando CNAB...", fg="#2563eb")

        def _do():
            try:
                import tempfile, os
                from pathlib import Path

                # Baixa a planilha do PocketBase
                destino = os.path.join(tempfile.gettempdir(), "magical_pendencias")
                caminho_planilha = self.cloud.download_arquivo(pid, destino)

                if not caminho_planilha:
                    self.win.after(0, lambda: messagebox.showerror(
                        "Erro", "Arquivo não encontrado no PocketBase.", parent=self.win))
                    return

                # Lê a planilha
                import pandas as pd
                try:
                    df = pd.read_excel(caminho_planilha, sheet_name="Despesas",
                                       header=None)
                except Exception:
                    df = pd.read_excel(caminho_planilha, header=None)

                # Detecta header — procura linha com "VALOR"
                header_row = 0
                for i in range(min(10, len(df))):
                    row_vals = [str(v).upper().strip() for v in df.iloc[i].values]
                    if any("VALOR" in v for v in row_vals):
                        header_row = i
                        break

                df.columns = df.iloc[header_row].astype(str).str.strip()
                df = df.iloc[header_row+1:].reset_index(drop=True)
                df = df.dropna(how="all")

                # Normaliza nomes de colunas
                col_map = {}
                for col in df.columns:
                    c = str(col).upper().strip()
                    if "VALOR" in c and col_map.get("VALOR") is None:
                        col_map[col] = "VALOR"
                    elif "FAVORECIDO" in c:
                        col_map[col] = "FAVORECIDO"
                    elif "PIX" in c and "CHAVE" in c:
                        col_map[col] = "PIX_CHAVE"
                    elif "CPF" in c or "CNPJ" in c:
                        col_map[col] = "CPF_CNPJ"
                    elif "DATA" in c and "PAGAMENTO" in c:
                        col_map[col] = "DATA"
                    elif "FORMA" in c and "PGTO" in c:
                        col_map[col] = "FORMA_PGTO"
                df = df.rename(columns=col_map)

                # Monta lista de pagamentos PIX
                from core.cnab_itau import (
                    GeradorCNAB240,
                    PIX_CHAVE_CPF, PIX_CHAVE_CNPJ,
                    PIX_CHAVE_EMAIL, PIX_CHAVE_EVP,
                )
                import re as _re

                pagamentos = []
                for _, row in df.iterrows():
                    # ── Valor ────────────────────────────────────────────────
                    try:
                        valor_raw = row.get("VALOR", 0)
                        v_str = str(valor_raw).strip().replace("R$","").replace(" ","")
                        if "," in v_str:
                            v_str = v_str.replace(".", "").replace(",", ".")
                        valor = abs(float(v_str))
                        if valor <= 0:
                            continue
                    except Exception:
                        continue

                    # ── Forma de pagamento ────────────────────────────────────
                    forma_raw = str(row.get("FORMA_PGTO", "") or "").upper().strip()
                    if forma_raw in ("NAN", ""):
                        forma_raw = "PIX"  # default

                    # Mapeamento forma → tipo interno
                    if "PIX" in forma_raw:
                        forma_cnab = "PIX"
                    elif "TED" in forma_raw:
                        forma_cnab = "TED"
                    elif "DOC" in forma_raw:
                        forma_cnab = "DOC"
                    elif "CC" in forma_raw or "CONTA" in forma_raw or "CREDITO" in forma_raw:
                        forma_cnab = "CC"
                    else:
                        forma_cnab = "PIX"  # default

                    # ── Chave PIX / dados bancários ───────────────────────────
                    pix_chave_raw = row.get("PIX_CHAVE") or row.get("CPF_CNPJ") or ""
                    pix_chave = str(pix_chave_raw).strip()
                    if pix_chave in ("nan", "None", ""):
                        pix_chave = ""

                    cpf_cnpj = _re.sub(r"\D", "", pix_chave)

                    if len(cpf_cnpj) == 11:
                        tipo_chave = PIX_CHAVE_CPF
                    elif len(cpf_cnpj) == 14:
                        tipo_chave = PIX_CHAVE_CNPJ
                    elif "@" in pix_chave:
                        tipo_chave = PIX_CHAVE_EMAIL
                        cpf_cnpj   = pix_chave
                    elif pix_chave:
                        tipo_chave = PIX_CHAVE_EVP
                        cpf_cnpj   = pix_chave
                    else:
                        if forma_cnab == "PIX":
                            continue  # PIX sem chave → pula
                        tipo_chave = PIX_CHAVE_CPF

                    # ── Dados bancários (TED/DOC/CC) ──────────────────────────
                    banco_col = None
                    agencia_col = None
                    conta_col = None
                    for col in df.columns:
                        c = str(col).upper()
                        if "BANCO" in c and banco_col is None:
                            banco_col = col
                        if "AGENCIA" in c or "AGÊNCIA" in c:
                            agencia_col = col
                        if "CONTA" in c and "AGENCIA" not in c.upper():
                            conta_col = col

                    banco   = _re.sub(r"\D", "", str(row.get(banco_col, "341") or "341")) or "341"
                    agencia = _re.sub(r"\D", "", str(row.get(agencia_col, "") or ""))
                    conta   = _re.sub(r"\D", "", str(row.get(conta_col, "") or ""))

                    nome_raw = row.get("FAVORECIDO", "") or ""
                    nome     = str(nome_raw).strip()[:30]
                    data_raw = row.get("DATA", "") or ""
                    data     = str(data_raw).strip()

                    pagamentos.append({
                        "nome":            nome or "FAVORECIDO",
                        "cpf_cnpj":        cpf_cnpj,
                        "pix_chave":       pix_chave,
                        "pix_tipo_chave":  tipo_chave,
                        "banco_favorecido": banco,
                        "agencia":         agencia,
                        "conta":           conta,
                        "dac":             "0",
                        "valor":           valor,
                        "data":            data,
                        "forma_pgto":      forma_cnab,
                    })

                if not pagamentos:
                    self.win.after(0, lambda: messagebox.showwarning(
                        "CNAB", "Nenhum pagamento válido encontrado na planilha.\n"
                                "Verifique se as colunas VALOR e PIX CHAVE estão preenchidas.",
                        parent=self.win))
                    return

                # Gera arquivo CNAB 240
                downloads = str(Path.home() / "Downloads")
                config = {
                    "cnpj":    _re.sub(r"\D", "", self._get_cfg("pb_email", "")),
                    "agencia": "00000",
                    "conta":   "000000000",
                    "dac":     "0",
                    "nome":    "RAYNE TECNOLOGIA LTDA",
                }
                g = GeradorCNAB240(config)
                for p in pagamentos:
                    g.adicionar(p)

                arquivos = g.gerar(output_dir=downloads)
                caminho_rem = arquivos.get("pix")

                if not caminho_rem:
                    self.win.after(0, lambda: messagebox.showerror(
                        "CNAB", "Erro ao gerar arquivo CNAB.", parent=self.win))
                    return

                # Atualiza PocketBase
                todas = self.cloud.listar_todas(limit=200)
                p_rec = next((x for x in todas if x["id"] == pid), {})
                vt    = float(p_rec.get("total_valor", 0))
                self.cloud.confirmar_cnab_gerado(pid, casa, meu_nome, vt)

                # Notifica grupo
                self._notificar_aprovacao(casa, meu_nome, vt, len(pagamentos))

                # Abre a pasta Downloads
                import subprocess
                subprocess.Popen(f'explorer "{downloads}"')

                # Resumo dos arquivos gerados
                arquivos_gerados = []
                if arquivos.get("pix"):
                    qtd_pix = sum(1 for p in pagamentos if p["forma_pgto"] == "PIX")
                    arquivos_gerados.append(f"PIX: {qtd_pix} pagamentos → {Path(arquivos['pix']).name}")
                if arquivos.get("ted_cc"):
                    qtd_outros = sum(1 for p in pagamentos if p["forma_pgto"] != "PIX")
                    arquivos_gerados.append(f"TED/CC: {qtd_outros} pagamentos → {Path(arquivos['ted_cc']).name}")

                resumo = "\n".join(arquivos_gerados) if arquivos_gerados else "Nenhum arquivo gerado"

                # Abre a pasta Downloads
                import subprocess
                subprocess.Popen(f'explorer "{downloads}"')

                self.win.after(0, lambda r=resumo: (
                    self._load(),
                    messagebox.showinfo("CNAB Gerado",
                        f"Arquivos gerados com sucesso!\n\n"
                        f"{r}\n\n"
                        f"Total: {len(pagamentos)} pagamentos\n"
                        f"Salvos em: Downloads\n\n"
                        f"Notificacao enviada ao grupo para aprovacao.",
                        parent=self.win)
                ))

            except Exception as e:
                err_msg = str(e)
                self.win.after(0, lambda m=err_msg: messagebox.showerror(
                    "Erro", f"Erro ao gerar CNAB: {m}", parent=self.win))

        import threading
        threading.Thread(target=_do, daemon=True).start()

    def _confirmar_envio(self):
        pid, casa, status = self._sel_planilha()
        if not pid:
            return
        if status not in ("cnab_gerado",):
            messagebox.showwarning("Pendências",
                f"Status atual: '{status}' — use 'Marcar CNAB gerado' primeiro.",
                parent=self.win)
            return

        meu_nome = self._get_cfg("meu_nome", "Usuário")
        if not messagebox.askyesno("Confirmar envio",
            f"Confirmar que o arquivo CNAB de '{casa}' foi importado no portal Itaú?",
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

    def _notificar_aprovacao(self, casa: str, gerado_por: str,
                              valor: float, qtd: int):
        """Envia mensagem de aprovação para o grupo do Diretor."""
        try:
            evo_url  = self._get_cfg("evo_url")
            evo_key  = self._get_cfg("evo_key")
            instancia= self._get_cfg("evo_instancia", "wanderley")
            grupo    = self._get_cfg("grupo_aprovacao")

            if not evo_url or not grupo:
                return

            from notificador import Notificador
            n = Notificador(evo_url, evo_key, instancia)

            if not n.status_instancia().get("conectado"):
                return

            msg = n.msg_aguardando_aprovacao(casa, valor, gerado_por, qtd)
            n.enviar_grupo(grupo, msg)
        except Exception:
            pass

    def _on_double_click(self, event=None):
        """Mostra detalhes da planilha selecionada."""
        sel = self.tree.selection()
        if not sel:
            return

        pid  = sel[0]
        vals = self.tree.item(pid, "values")
        tags = self.tree.item(pid, "tags")
        status = tags[0] if tags else ""
        label  = self.STATUS_LABEL.get(status, status)

        pop = tk.Toplevel(self.win)
        pop.title("Detalhes da Pendência")
        pop.geometry("420x280")

        info = (
            f"Casa:          {vals[0]}\n"
            f"Planilha:      {vals[1]}\n"
            f"Status:        {label}\n"
            f"Valor Total:   {vals[3]}\n"
            f"Itens:         {vals[4]}\n"
            f"Lançado por:   {vals[5] or '—'}\n"
            f"CNAB por:      {vals[6] or '—'}\n"
            f"Recebido em:   {vals[7]}\n"
        )

        txt = tk.Text(pop, wrap="word", font=("Arial", 10), height=12)
        txt.pack(fill="both", expand=True, padx=12, pady=12)
        txt.insert("1.0", info)
        txt.config(state="disabled")

        ttk.Button(pop, text="Fechar", command=pop.destroy).pack(pady=(0, 10))

    def _on_close(self):
        if self._poll_id:
            self.win.after_cancel(self._poll_id)
        self.win.destroy()