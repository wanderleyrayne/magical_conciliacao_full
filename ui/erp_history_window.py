"""
ui/erp_history_window.py — Historico de lancamentos enviados ao ERP via API.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path


class ErpHistoryWindow:
    def __init__(self, master, repo):
        self.repo = repo
        self.win  = tk.Toplevel(master)
        self.win.title("Historico de Lancamentos no ERP")
        self.win.geometry("1100x620")
        self.win.resizable(True, True)
        self._build()

    def _build(self):
        hdr = tk.Frame(self.win, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text="Historico de Lancamentos — ERP MeEventos",
                 fg="white", bg="#1e293b",
                 font=("Arial", 11, "bold")).pack(side="left", padx=12, pady=10)

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

        self.mostrar_simulacao = tk.BooleanVar(value=False)
        ttk.Checkbutton(fil, text="Mostrar simulacoes",
                        variable=self.mostrar_simulacao,
                        command=self._load_batches).pack(side="left", padx=(16,0))

        ttk.Button(fil, text="Atualizar",
                   command=self._load_batches).pack(side="left", padx=8)

        self.lbl_total = tk.Label(fil, text="", font=("Arial", 9, "bold"))
        self.lbl_total.pack(side="right")

        pane = tk.PanedWindow(self.win, orient="vertical", sashrelief="flat")
        pane.pack(fill="both", expand=True, padx=10, pady=8)

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

        bot_f = tk.LabelFrame(pane, text="Itens do lote selecionado")
        pane.add(bot_f, minsize=150)

        item_cols = ("linha","parceiro","status","id_api","id_evento",
                     "categoria","valor","descricao","mensagem")
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
            ("descricao", "Descricao", 220),
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

        # Footer com botao PDF
        ft = tk.Frame(self.win, padx=10, pady=8)
        ft.pack(fill="x")
        tk.Label(ft, text="Duplo-clique em um item para ver o payload JSON completo.",
                 fg="#64748b", font=("Arial", 8)).pack(side="left")
        ttk.Button(ft, text="Fechar",
                   command=self.win.destroy).pack(side="right")
        ttk.Button(ft, text="📄 Gerar PDF",
                   command=self._gerar_pdf_lote).pack(side="right", padx=6)

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

        parceiros = sorted({b.get("partner_name","") for b in batches
                            if b.get("partner_name")})
        self.cb_parceiro["values"] = ["TODOS"] + parceiros

        filtro = self.parceiro_var.get()
        if filtro != "TODOS":
            batches = [b for b in batches
                       if b.get("partner_name","").upper() == filtro.upper()]

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

        if not self.mostrar_simulacao.get():
            batches = [b for b in batches if not b.get("dry_run")]

        total_valor = 0.0

        for b in batches:
            bid      = b.get("id", "")
            created  = str(b.get("created_at") or "")[:16].replace("T"," ")
            parceiro = b.get("partner_name", "")
            planilha = b.get("file_name", "")
            total    = b.get("total_rows", 0)
            dry      = "Simulacao" if b.get("dry_run") else "Real"

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
                enviados  = b.get("total_enviado", 0)
                simulados = b.get("total_simulado", 0)
                erros     = b.get("total_erro", 0)
                val       = 0.0

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
                cat_nome = str(it.get("categoria") or "")
                cat_id   = str(it.get("id_categoria") or payload.get("idcategoria") or "")
                categoria_display = (
                    f"{cat_nome} [{cat_id}]" if cat_nome and cat_id else
                    cat_nome or cat_id or "—"
                )
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
            payload     = json.loads(it.get("payload_json") or "{}")
            txt_content = json.dumps(payload, indent=2, ensure_ascii=False)
        except Exception:
            txt_content = str(it.get("payload_json",""))

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

    # =========================================================================
    # GERAR PDF
    # =========================================================================

    def _gerar_pdf_lote(self):
        """Gera PDF com os itens do lote selecionado ou todos do dia."""
        sel = self.batch_tree.selection()
        if not sel:
            messagebox.showwarning("PDF", "Selecione um lote primeiro.",
                                   parent=self.win)
            return

        try:
            batch_id = int(sel[0])
            vals     = self.batch_tree.item(sel[0], "values")
            parceiro = vals[2] if len(vals) > 2 else ""
            data_str = vals[1] if len(vals) > 1 else ""

            # Pergunta: este lote ou todos do dia?
            import tkinter as _tk2
            from tkinter import simpledialog as _sd

            popup = _tk2.Toplevel(self.win)
            popup.title("Gerar PDF")
            popup.geometry("380x160")
            popup.resizable(False, False)
            popup.grab_set()
            popup.focus_set()

            escolha = _tk2.StringVar(value="")

            _tk2.Label(popup,
                text="Qual período deseja incluir no PDF?",
                font=("Arial", 10, "bold"), pady=12).pack()

            bf = _tk2.Frame(popup)
            bf.pack(pady=8)

            def _escolher(v):
                escolha.set(v)
                popup.destroy()

            from tkinter import ttk as _ttk2
            _ttk2.Button(bf, text="📄  Este lote apenas",
                command=lambda: _escolher("lote")).pack(side="left", padx=8, ipadx=6)
            _ttk2.Button(bf, text="📋  Todos os lançamentos de hoje",
                command=lambda: _escolher("hoje")).pack(side="left", padx=8, ipadx=6)
            _ttk2.Button(bf, text="Cancelar",
                command=lambda: _escolher("")).pack(side="left", padx=8)

            popup.wait_window()

            if not escolha.get():
                return

            if escolha.get() == "hoje":
                # Busca todos os itens do parceiro lançados hoje
                from datetime import date as _date_hoje2
                hoje_str = _date_hoje2.today().strftime("%Y-%m-%d")
                try:
                    import sqlite3 as _sq3
                    db_path = str(self.repo.db.db_path)
                    with _sq3.connect(db_path) as conn:
                        rows = conn.execute("""
                            SELECT i.* FROM erp_launch_items i
                            JOIN erp_launch_batches b ON i.batch_id = b.id
                            WHERE b.partner_name = ?
                              AND date(b.created_at) = ?
                              AND i.status IN ('LANCADO','SIMULADO')
                            ORDER BY i.id ASC
                        """, (parceiro, hoje_str)).fetchall()
                        cols = [d[0] for d in conn.execute(
                            "SELECT * FROM erp_launch_items LIMIT 0").description]
                    items = [dict(zip(cols, r)) for r in rows]
                except Exception as e:
                    messagebox.showerror("Erro",
                        f"Erro ao buscar itens do dia:\n{e}", parent=self.win)
                    return

                if not items:
                    messagebox.showwarning("PDF",
                        f"Nenhum lançamento encontrado hoje para {parceiro}.",
                        parent=self.win)
                    return

                data_str = f"{_date_hoje2.today().strftime('%Y-%m-%d')} 00:00"

            else:
                items = self.repo.get_erp_launch_items(batch_id)
                if not items:
                    messagebox.showwarning("PDF",
                        "Nenhum item encontrado neste lote.", parent=self.win)
                    return

            self._gerar_pdf_pagamentos(parceiro, data_str, items)

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao gerar PDF:\n{e}",
                                 parent=self.win)

    def _gerar_pdf_pagamentos(self, parceiro, data_str, itens):
        """Gera PDF de pagamentos e abre dialogo para salvar."""
        import re
        from tkinter import filedialog
        from datetime import datetime

        # Instala reportlab se necessario
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import (SimpleDocTemplate, Table,
                                             TableStyle, Paragraph, Spacer)
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        except ImportError:
            import subprocess, sys
            messagebox.showinfo("Instalando",
                "Instalando reportlab, aguarde...", parent=self.win)
            subprocess.run([sys.executable, "-m", "pip", "install",
                           "reportlab", "--break-system-packages"],
                          capture_output=True)
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import (SimpleDocTemplate, Table,
                                             TableStyle, Paragraph, Spacer)
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

        # Calcula total apenas dos lancados/simulados
        total = 0.0
        for item in itens:
            try:
                payload = json.loads(item.get("payload_json") or "{}")
                if item.get("status") in ("LANCADO", "SIMULADO"):
                    total += abs(float(payload.get("valor", 0)))
            except Exception:
                pass

        total_fmt = self._brl(total)

        # Formata data
        try:
            raw = data_str[:16].replace("T"," ")
            dt  = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        except Exception:
            try:
                dt = datetime.strptime(data_str[:10], "%d/%m/%Y")
            except Exception:
                dt = datetime.now()

        data_fmt    = dt.strftime("%d.%m")
        data_extenso = dt.strftime("%d/%m/%Y")

        # Nome do arquivo: PAGAMENTOS CONTEMPORANEO 11.05 - R$ 82.023,31.pdf
        total_nome = total_fmt.replace("/","").replace("\\","")
        nome_base  = f"PAGAMENTOS {parceiro.upper()} {data_fmt} - {total_fmt}.pdf"
        nome_base  = re.sub(r'[<>:"|?*]', '', nome_base)

        destino = filedialog.asksaveasfilename(
            title="Salvar PDF de pagamentos",
            initialfile=nome_base,
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")],
            parent=self.win,
        )
        if not destino:
            return

        # Monta PDF
        doc = SimpleDocTemplate(
            destino, pagesize=A4,
            rightMargin=1.5*cm, leftMargin=1.5*cm,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
        )
        styles = getSampleStyleSheet()

        s_titulo = ParagraphStyle("titulo", parent=styles["Heading1"],
                                   fontSize=13, textColor=colors.HexColor("#0f172a"),
                                   spaceAfter=2)
        s_sub    = ParagraphStyle("sub", parent=styles["Normal"],
                                   fontSize=9, textColor=colors.HexColor("#475569"),
                                   spaceAfter=10)
        s_rod    = ParagraphStyle("rod", parent=styles["Normal"],
                                   fontSize=7, textColor=colors.HexColor("#94a3b8"),
                                   alignment=TA_CENTER)

        story = []
        story.append(Paragraph("Relatorio de Pagamentos", s_titulo))
        story.append(Paragraph(
            f"Casa: {parceiro}   |   Data: {data_extenso}   |   Total: {total_fmt}",
            s_sub))

        # Tabela de itens
        col_w = [9.5*cm, 4.5*cm, 1.8*cm, 2.0*cm, 1.8*cm]
        header = ["Descricao / Favorecido", "Categoria", "ID Evento", "Valor", "Status"]
        rows   = [header]

        for item in itens:
            try:
                payload   = json.loads(item.get("payload_json") or "{}")
                desc      = str(item.get("descricao") or
                                payload.get("descricao",""))[:55]
                cat       = str(item.get("categoria",""))[:22]
                id_evento = str(payload.get("idevento","") or "—")
                valor     = self._brl(item.get("valor") or payload.get("valor",0))
                status    = str(item.get("status",""))
                rows.append([desc, cat, id_evento, valor, status])
            except Exception:
                pass

        # Linha de total
        rows.append(["", "TOTAL GERAL", "", total_fmt, ""])

        AZUL     = colors.HexColor("#0f172a")
        CINZA    = colors.HexColor("#f8fafc")
        VERDE    = colors.HexColor("#dff3e3")
        AZUL_L   = colors.HexColor("#dbeafe")
        BORDA    = colors.HexColor("#e2e8f0")

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, 0), AZUL),
            ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
            ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",     (0, 0), (-1, 0), 9),
            ("ALIGN",        (0, 0), (-1, 0), "CENTER"),
            ("TOPPADDING",   (0, 0), (-1, 0), 7),
            ("BOTTOMPADDING",(0, 0), (-1, 0), 7),
            ("FONTSIZE",     (0, 1), (-1,-2), 8),
            ("ROWBACKGROUNDS",(0,1), (-1,-2), [colors.white, CINZA]),
            ("GRID",         (0, 0), (-1,-1), 0.4, BORDA),
            ("VALIGN",       (0, 0), (-1,-1), "MIDDLE"),
            ("TOPPADDING",   (0, 1), (-1,-2), 4),
            ("BOTTOMPADDING",(0, 1), (-1,-2), 4),
            ("ALIGN",        (3, 1), (3,-1), "RIGHT"),
            ("ALIGN",        (2, 0), (2, 0), "CENTER"),
            ("BACKGROUND",   (0,-1), (-1,-1), AZUL_L),
            ("FONTNAME",     (0,-1), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",     (0,-1), (-1,-1), 9),
            ("ALIGN",        (1,-1), (3,-1), "RIGHT"),
            ("TOPPADDING",   (0,-1), (-1,-1), 6),
            ("BOTTOMPADDING",(0,-1), (-1,-1), 6),
        ]))

        story.append(tbl)
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} | Magical Conciliacao",
            s_rod))

        doc.build(story)

        messagebox.showinfo("PDF Gerado",
            f"PDF salvo com sucesso!\n\n{Path(destino).name}",
            parent=self.win)

        import os
        if os.name == "nt":
            os.startfile(destino)