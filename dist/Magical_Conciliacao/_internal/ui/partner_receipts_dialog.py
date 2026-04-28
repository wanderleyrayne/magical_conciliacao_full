import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from reportlab.pdfbase.pdfmetrics import stringWidth


class PartnerReceiptsDialog:
    STATUS_ORDER = {
        "OK": 1,
        "PARCIAL": 2,
        "EXCEDENTE": 3,
        "SEM_RECEBIMENTO": 4,
    }

    STATUS_BG = {
        "OK": "#dff3e3",
        "PARCIAL": "#fff3cd",
        "EXCEDENTE": "#f8d7da",
        "SEM_RECEBIMENTO": "#e5e7eb",
    }

    def __init__(self, master, summary_rows):
        self.top = tk.Toplevel(master)
        self.top.title("Resumo de Recebimentos dos Parceiros")
        self.top.geometry("1280x620")
        self.top.minsize(1040, 460)

        self.summary_rows = summary_rows or []
        self.df = self._build_dataframe(self.summary_rows)

        self._build_layout()

    # =========================
    # DATAFRAME / ORDENAÇÃO
    # =========================
    def _build_dataframe(self, summary_rows):
        df = pd.DataFrame(summary_rows)

        expected_cols = [
            "reference_month",
            "partner_name",
            "subtotal",
            "marketing_fee",
            "total_expected",
            "total_received",
            "deposit_count",
            "status",
            "observation",
            "partner_cnpj",
            "difference",
            "received_dates",
        ]

        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""

        if df.empty:
            return df

        df["_status_order"] = df["status"].astype(str).str.upper().map(self.STATUS_ORDER).fillna(99)
        df = df.sort_values(
            by=["reference_month", "_status_order", "partner_name"],
            ascending=[False, True, True]
        ).reset_index(drop=True)

        return df

    # =========================
    # UI
    # =========================
    def _build_layout(self):
        header = tk.Frame(self.top, bg="#1e293b", height=48)
        header.pack(fill="x")

        tk.Label(
            header,
            text="Resumo de Recebimentos dos Parceiros",
            fg="white",
            bg="#1e293b",
            font=("Arial", 12, "bold")
        ).pack(side="left", padx=12, pady=10)

        info = tk.Label(
            self.top,
            text="Comparação entre recebimentos identificados no banco e as regras mensais cadastradas.",
            anchor="w",
            justify="left"
        )
        info.pack(fill="x", padx=12, pady=(10, 8))

        frame = tk.Frame(self.top)
        frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        cols = (
            "reference_month",
            "partner_name",
            "subtotal",
            "marketing_fee",
            "total_expected",
            "total_received",
            "deposit_count",
            "status",
            "observation",
        )

        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        self.tree.pack(side="left", fill="both", expand=True)

        scroll_y = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll_y.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll_y.set)

        headings = {
            "reference_month": "Mês",
            "partner_name": "Parceiro",
            "subtotal": "Subtotal",
            "marketing_fee": "Taxa",
            "total_expected": "Total esperado",
            "total_received": "Total recebido",
            "deposit_count": "Depósitos",
            "status": "Status",
            "observation": "Observação",
        }

        widths = {
            "reference_month": 90,
            "partner_name": 180,
            "subtotal": 120,
            "marketing_fee": 120,
            "total_expected": 130,
            "total_received": 130,
            "deposit_count": 90,
            "status": 120,
            "observation": 380,
        }

        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], anchor="center" if col != "observation" else "w")

        self.tree.tag_configure("OK", background="#dff3e3")
        self.tree.tag_configure("PARCIAL", background="#fff3cd")
        self.tree.tag_configure("EXCEDENTE", background="#f8d7da")
        self.tree.tag_configure("SEM_RECEBIMENTO", background="#e5e7eb")

        for _, row in self.df.iterrows():
            status = self._safe_str(row.get("status"))
            self.tree.insert(
                "",
                "end",
                values=(
                    self._safe_str(row.get("reference_month")),
                    self._safe_str(row.get("partner_name")),
                    self._fmt_money(row.get("subtotal")),
                    self._fmt_money(row.get("marketing_fee")),
                    self._fmt_money(row.get("total_expected")),
                    self._fmt_money(row.get("total_received")),
                    self._safe_int(row.get("deposit_count")),
                    status,
                    self._safe_str(row.get("observation")),
                ),
                tags=(status,)
            )

        footer = tk.Frame(self.top)
        footer.pack(fill="x", padx=12, pady=(0, 12))

        ttk.Button(footer, text="Exportar Excel", command=self._export_excel).pack(side="left")
        ttk.Button(footer, text="Exportar PDF", command=self._export_pdf).pack(side="left", padx=8)
        ttk.Button(footer, text="Fechar", command=self.top.destroy).pack(side="right")

    # =========================
    # EXPORTAÇÃO EXCEL
    # =========================
    def _export_excel(self):
        if self.df.empty:
            messagebox.showwarning("Aviso", "Não há dados para exportar.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Salvar Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")]
        )
        if not file_path:
            return

        try:
            df_export = self.df.copy()

            if "_status_order" in df_export.columns:
                df_export = df_export.drop(columns=["_status_order"])

            rename_map = {
                "reference_month": "Mês",
                "partner_name": "Parceiro",
                "partner_cnpj": "CNPJ",
                "subtotal": "Subtotal",
                "marketing_fee": "Taxa",
                "total_expected": "Total esperado",
                "total_received": "Total recebido",
                "deposit_count": "Depósitos",
                "status": "Status",
                "difference": "Diferença",
                "received_dates": "Datas recebidas",
                "observation": "Observação",
            }
            df_export = df_export.rename(columns=rename_map)

            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                df_export.to_excel(writer, sheet_name="Resumo Parceiros", index=False)

                ws = writer.sheets["Resumo Parceiros"]

                # largura simples
                for column_cells in ws.columns:
                    max_length = 0
                    col_letter = column_cells[0].column_letter
                    for cell in column_cells:
                        try:
                            value = str(cell.value) if cell.value is not None else ""
                            if len(value) > max_length:
                                max_length = len(value)
                        except Exception:
                            pass
                    ws.column_dimensions[col_letter].width = min(max(max_length + 2, 12), 40)

                # formatar colunas numéricas como moeda
                money_columns = {"Subtotal", "Taxa", "Total esperado", "Total recebido", "Diferença"}
                header_row = [cell.value for cell in ws[1]]

                for idx, col_name in enumerate(header_row, start=1):
                    if col_name in money_columns:
                        for row in range(2, ws.max_row + 1):
                            ws.cell(row=row, column=idx).number_format = 'R$ #,##0.00'

            messagebox.showinfo("Sucesso", "Arquivo Excel exportado com sucesso.")
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível exportar o Excel.\n\nDetalhes: {exc}")

    # =========================
    # EXPORTAÇÃO PDF
    # =========================
    def _export_pdf(self):
        if self.df.empty:
            messagebox.showwarning("Aviso", "Não há dados para exportar.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Salvar PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if not file_path:
            return

        try:
            doc = SimpleDocTemplate(
                file_path,
                pagesize=landscape(A4),
                leftMargin=10 * mm,
                rightMargin=10 * mm,
                topMargin=10 * mm,
                bottomMargin=10 * mm,
            )

            styles = getSampleStyleSheet()
            style_title = ParagraphStyle(
                "CustomTitle",
                parent=styles["Title"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=18,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#1e293b"),
                spaceAfter=8,
            )
            style_subtitle = ParagraphStyle(
                "CustomSubtitle",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=12,
                alignment=TA_LEFT,
                textColor=colors.HexColor("#475569"),
                spaceAfter=10,
            )
            style_header = ParagraphStyle(
                "HeaderCell",
                parent=styles["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
                textColor=colors.white,
            )
            style_body = ParagraphStyle(
                "BodyCell",
                parent=styles["Normal"],
                fontName="Helvetica",
                fontSize=7,
                leading=9,
                alignment=TA_LEFT,
                textColor=colors.black,
            )
            style_body_center = ParagraphStyle(
                "BodyCellCenter",
                parent=style_body,
                alignment=TA_CENTER,
            )

            elements = []

            elements.append(Paragraph("Resumo de Recebimentos dos Parceiros", style_title))
            elements.append(
                Paragraph(
                    f"Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                    style_subtitle,
                )
            )

            headers = [
                "Mês",
                "Parceiro",
                "Subtotal",
                "Taxa",
                "Total esperado",
                "Total recebido",
                "Depósitos",
                "Status",
                "Observação",
            ]

            table_data = [[Paragraph(h, style_header) for h in headers]]

            for _, row in self.df.iterrows():
                table_data.append([
                    Paragraph(self._safe_str(row.get("reference_month")), style_body_center),
                    Paragraph(self._safe_str(row.get("partner_name")), style_body),
                    Paragraph(self._fmt_money(row.get("subtotal")), style_body_center),
                    Paragraph(self._fmt_money(row.get("marketing_fee")), style_body_center),
                    Paragraph(self._fmt_money(row.get("total_expected")), style_body_center),
                    Paragraph(self._fmt_money(row.get("total_received")), style_body_center),
                    Paragraph(str(self._safe_int(row.get("deposit_count"))), style_body_center),
                    Paragraph(self._safe_str(row.get("status")), style_body_center),
                    Paragraph(self._safe_str(row.get("observation")), style_body),
                ])

            col_widths = [
                22 * mm,   # mês
                40 * mm,   # parceiro
                30 * mm,   # subtotal
                28 * mm,   # taxa
                32 * mm,   # total esperado
                32 * mm,   # total recebido
                22 * mm,   # depósitos
                28 * mm,   # status
                85 * mm,   # observação
            ]

            table = Table(table_data, colWidths=col_widths, repeatRows=1)

            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]

            # aplica cor por status igual ao sistema
            for i, (_, row) in enumerate(self.df.iterrows(), start=1):
                status = self._safe_str(row.get("status")).upper()
                bg = self.STATUS_BG.get(status, "#ffffff")
                style_commands.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(bg)))

            table.setStyle(TableStyle(style_commands))

            elements.append(table)
            elements.append(Spacer(1, 6))

            # resumo rápido
            counts = self.df["status"].astype(str).str.upper().value_counts().to_dict()
            resumo = (
                f"OK: {counts.get('OK', 0)} | "
                f"PARCIAL: {counts.get('PARCIAL', 0)} | "
                f"EXCEDENTE: {counts.get('EXCEDENTE', 0)} | "
                f"SEM_RECEBIMENTO: {counts.get('SEM_RECEBIMENTO', 0)}"
            )
            elements.append(Paragraph(resumo, style_subtitle))

            doc.build(elements)

            messagebox.showinfo("Sucesso", "Arquivo PDF exportado com sucesso.")
        except Exception as exc:
            messagebox.showerror("Erro", f"Não foi possível exportar o PDF.\n\nDetalhes: {exc}")

    # =========================
    # HELPERS
    # =========================
    @staticmethod
    def _safe_str(value):
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""
        return text

    @staticmethod
    def _safe_int(value):
        try:
            if value is None or value == "":
                return 0
            return int(value)
        except Exception:
            return 0

    @staticmethod
    def _fmt_money(value):
        try:
            v = float(value or 0)
        except Exception:
            v = 0.0
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")