import json
import uuid
import pandas as pd
from database.db import DatabaseManager


class SystemRepository:
    def __init__(self, db_path="data/conciliacao.db"):
        self.db = DatabaseManager(db_path=db_path)

    # =========================
    # LOGS / SETTINGS
    # =========================
    def log(self, level: str, message: str, details: str = ""):
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_logs (level, message, details)
                VALUES (?, ?, ?)
                """,
                (level, message, details)
            )
            conn.commit()

    def save_setting(self, key: str, value: str):
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value)
            )
            conn.commit()

    def get_setting(self, key: str, default=None):
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,)
            ).fetchone()
            return row["value"] if row else default

    # =========================
    # IMPORTAÇÃO / NORMALIZAÇÃO
    # =========================
    def save_imported_file(self, file_type: str, file_name: str, file_path: str, total_rows: int, total_columns: int) -> int:
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO imported_files (file_type, file_name, file_path, total_rows, total_columns)
                VALUES (?, ?, ?, ?, ?)
                """,
                (file_type, file_name, file_path, total_rows, total_columns)
            )
            conn.commit()
            return cursor.lastrowid

    def save_normalized_dataframe(self, imported_file_id: int, source_type: str, df: pd.DataFrame):
        if df is None or df.empty:
            return

        rows = []
        for _, row in df.iterrows():
            extra = {}
            for col in df.columns:
                if col not in {
                    "data", "descricao", "favorecido", "documento",
                    "forma_pagamento", "pago", "tipo", "valor", "categoria"
                }:
                    value = row.get(col)
                    if pd.notna(value):
                        extra[col] = str(value)

            data_value = row.get("data")
            if pd.notna(data_value):
                try:
                    data_value = pd.to_datetime(data_value).strftime("%Y-%m-%d")
                except Exception:
                    data_value = str(data_value)
            else:
                data_value = None

            valor = row.get("valor")
            try:
                valor = float(valor) if pd.notna(valor) else None
            except Exception:
                valor = None

            rows.append((
                imported_file_id,
                source_type,
                data_value,
                self._safe(row.get("descricao")),
                self._safe(row.get("favorecido")),
                self._safe(row.get("documento")),
                self._safe(row.get("forma_pagamento")),
                self._safe(row.get("pago")),
                self._safe(row.get("tipo")),
                valor,
                self._safe(row.get("categoria")),
                json.dumps(extra, ensure_ascii=False)
            ))

        with self.db.connect() as conn:
            conn.executemany(
                """
                INSERT INTO normalized_records (
                    imported_file_id, source_type, data, descricao, favorecido,
                    documento, forma_pagamento, pago, tipo, valor, categoria, extra_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
            conn.commit()

    # =========================
    # BASE DE ENTIDADES
    # =========================
    def upsert_entities_master(self, df: pd.DataFrame, source_file_name: str = ""):
        if df is None or df.empty:
            return 0

        total = 0
        with self.db.connect() as conn:
            for _, row in df.iterrows():
                documento          = self._safe(row.get("documento"))
                razao_social       = self._safe(row.get("razao_social"))
                razao_social_short = self._safe(row.get("razao_social_short"))
                categoria          = self._safe(row.get("categoria"))
                nome_busca         = self._safe(row.get("nome_busca"))
                nome_resumido      = self._safe(row.get("nome_resumido"))
                cargo_ocupacao     = self._safe(row.get("cargo_ocupacao"))

                if not documento and not razao_social:
                    continue

                if documento:
                    existing = conn.execute(
                        "SELECT id FROM entities_master WHERE documento = ?",
                        (documento,)
                    ).fetchone()

                    if existing:
                        conn.execute(
                            """
                            UPDATE entities_master
                            SET razao_social = ?,
                                razao_social_short = ?,
                                categoria = ?,
                                nome_busca = ?,
                                nome_resumido = ?,
                                cargo_ocupacao = ?,
                                source_file_name = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE documento = ?
                            """,
                            (razao_social, razao_social_short, categoria,
                             nome_busca, nome_resumido, cargo_ocupacao,
                             source_file_name, documento)
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO entities_master (
                                documento, razao_social, razao_social_short,
                                categoria, nome_busca, nome_resumido,
                                cargo_ocupacao, source_file_name
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (documento, razao_social, razao_social_short,
                             categoria, nome_busca, nome_resumido,
                             cargo_ocupacao, source_file_name)
                        )
                else:
                    existing = conn.execute(
                        "SELECT id FROM entities_master WHERE razao_social = ?",
                        (razao_social,)
                    ).fetchone()

                    if existing:
                        conn.execute(
                            """
                            UPDATE entities_master
                            SET razao_social_short = ?,
                                categoria = ?,
                                nome_busca = ?,
                                nome_resumido = ?,
                                cargo_ocupacao = ?,
                                source_file_name = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE razao_social = ?
                            """,
                            (razao_social_short, categoria, nome_busca,
                             nome_resumido, cargo_ocupacao,
                             source_file_name, razao_social)
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO entities_master (
                                documento, razao_social, razao_social_short,
                                categoria, nome_busca, nome_resumido,
                                cargo_ocupacao, source_file_name
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (documento, razao_social, razao_social_short,
                             categoria, nome_busca, nome_resumido,
                             cargo_ocupacao, source_file_name)
                        )
                total += 1

            conn.commit()
        return total

    def import_base_entidades(self, file_path: str) -> tuple:
        """
        Importa a planilha base_entidades.xlsx para entities_master.

        Colunas esperadas:
          CPF CNPJ           → documento
          RAZÃO SOCIAL       → razao_social
          RAZÃO SOCIAL SHORT → razao_social_short
          CARGO OCUPAÇÃO     → cargo_ocupacao
                             → categoria (derivada do cargo)

        Retorna (total_inserido, total_atualizado, erros).
        """
        import pandas as pd
        import os
        import re

        def clean_doc(v):
            return re.sub(r'\D', '', str(v or ''))

        try:
            df = pd.read_excel(file_path, dtype=str)
        except Exception as exc:
            return 0, 0, [str(exc)]

        # Normaliza nomes de colunas
        df.columns = [c.strip().upper() for c in df.columns]

        col_map = {
            "CPF CNPJ":           "documento",
            "RAZÃO SOCIAL":       "razao_social",
            "RAZAO SOCIAL":       "razao_social",
            "RAZÃO SOCIAL SHORT": "razao_social_short",
            "RAZAO SOCIAL SHORT": "razao_social_short",
            "CARGO OCUPAÇÃO":     "cargo_ocupacao",
            "CARGO OCUPACAO":     "cargo_ocupacao",
        }
        df = df.rename(columns={c: col_map[c] for c in df.columns if c in col_map})

        required = ["razao_social"]
        for req in required:
            if req not in df.columns:
                return 0, 0, [f"Coluna obrigatória não encontrada: {req}"]

        # Preenche campos derivados
        if "documento" not in df.columns:
            df["documento"] = ""
        if "razao_social_short" not in df.columns:
            df["razao_social_short"] = df["razao_social"]
        if "cargo_ocupacao" not in df.columns:
            df["cargo_ocupacao"] = ""

        # Limpa documentos — remove formatação
        df["documento"] = df["documento"].apply(
            lambda x: clean_doc(x) if x and str(x).strip() not in ("nan","") else "")

        # Deriva categoria do cargo_ocupacao para manter compatibilidade
        # com o reconciler (que usa categoria para classificar)
        def cargo_to_categoria(cargo):
            cargo = str(cargo or "").strip().upper()
            if not cargo or cargo == "NAN":
                return ""
            if "PARCEIRO CASA" in cargo:
                return "PARCEIRO"
            if "MAGICAL DIRETOR" in cargo:
                return "SOCIO_DIRETOR"
            if "MAGICAL ADM" in cargo:
                return "COLABORADOR_FINANCEIRO"
            if "MAGICAL RH" in cargo:
                return "COLABORADOR_RH"
            if "MAGICAL MARKETING" in cargo:
                return "COLABORADOR_MARKETING"
            if "MAGICAL GERENTE" in cargo:
                return "COLABORADOR_GERENTE"
            if "REPASSE VENDEDOR" in cargo:
                return "REPASSE_VENDEDOR"
            if "REPASSE PLANEJADOR" in cargo:
                return "REPASSE_PLANEJADOR"
            if "REPASSE GERENTE" in cargo:
                return "REPASSE_GERENTE"
            if "REPASSE SDR" in cargo:
                return "REPASSE_SDR"
            if "REPASSE COORDENADOR" in cargo:
                return "REPASSE_COORDENADOR"
            if "CLIENTE RECEITA" in cargo:
                return "CLIENTE"
            if "DEGUSTAÇÃO" in cargo or "DEGUSTACAO" in cargo:
                return "PROSPECT"
            if "MARKETING" in cargo:
                return "FORNECEDOR_MARKETING"
            if "ADMINISTRATIVO" in cargo:
                return "FORNECEDOR_ADMIN"
            if "IMPOSTO" in cargo or "FGTS" in cargo:
                return "IMPOSTO"
            if "BUFFET" in cargo:
                return "FORNECEDOR_BUFFET"
            if "SOCIO RECEITA" in cargo or "SÓCIO RECEITA" in cargo:
                return "SOCIO_RECEITA"
            if "ADVOCACIA" in cargo:
                return "FORNECEDOR_JURIDICO"
            return cargo.split()[0] if cargo else ""

        df["categoria"] = df["cargo_ocupacao"].apply(cargo_to_categoria)
        df["nome_busca"] = df["razao_social_short"].fillna(df["razao_social"])
        df["nome_resumido"] = df["razao_social_short"].fillna(df["razao_social"])

        # Remove linhas completamente vazias
        df = df[
            df["razao_social"].notna() &
            (df["razao_social"].str.strip() != "") &
            (df["razao_social"].str.lower() != "nan")
        ].copy()

        fname = os.path.basename(file_path)
        total = self.upsert_entities_master(df, source_file_name=fname)
        return total, 0, []

    def load_entities_master_df(self) -> pd.DataFrame:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT documento, razao_social, razao_social_short,
                       categoria, nome_busca, nome_resumido
                FROM entities_master
                ORDER BY razao_social
                """
            ).fetchall()

        if not rows:
            return pd.DataFrame(columns=[
                "documento", "razao_social", "razao_social_short",
                "categoria", "nome_busca", "nome_resumido"
            ])

        return pd.DataFrame([dict(r) for r in rows])

    def count_entities_master(self) -> int:
        with self.db.connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS total FROM entities_master").fetchone()
            return int(row["total"])

    def get_entities_master_info(self):
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total, MAX(updated_at) AS ultima_atualizacao
                FROM entities_master
                """
            ).fetchone()

        return {
            "total": int(row["total"]) if row and row["total"] is not None else 0,
            "ultima_atualizacao": row["ultima_atualizacao"] if row else None,
        }

    # =========================
    # REGRAS MENSAIS DOS PARCEIROS
    # =========================
    def save_partner_month_rule(
        self,
        reference_month: str,
        partner_name: str,
        partner_cnpj: str,
        subtotal: float,
        marketing_fee: float,
        total_expected: float,
        notes: str = ""
    ):
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO partner_monthly_rules (
                    reference_month, partner_name, partner_cnpj,
                    subtotal, marketing_fee, total_expected, notes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(reference_month, partner_name)
                DO UPDATE SET
                    partner_cnpj = excluded.partner_cnpj,
                    subtotal = excluded.subtotal,
                    marketing_fee = excluded.marketing_fee,
                    total_expected = excluded.total_expected,
                    notes = excluded.notes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    reference_month,
                    partner_name,
                    partner_cnpj,
                    float(subtotal or 0),
                    float(marketing_fee or 0),
                    float(total_expected or 0),
                    notes or ""
                )
            )
            conn.commit()

    def list_partner_month_rules(self, reference_month: str = None):
        with self.db.connect() as conn:
            if reference_month:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM partner_monthly_rules
                    WHERE reference_month = ?
                    ORDER BY partner_name
                    """,
                    (reference_month,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT *
                    FROM partner_monthly_rules
                    ORDER BY reference_month DESC, partner_name
                    """
                ).fetchall()

        return [dict(r) for r in rows]

    def get_partner_month_rule(self, reference_month: str, partner_name: str):
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM partner_monthly_rules
                WHERE reference_month = ? AND partner_name = ?
                """,
                (reference_month, partner_name)
            ).fetchone()

        return dict(row) if row else None

    def delete_partner_month_rule(self, reference_month: str, partner_name: str):
        with self.db.connect() as conn:
            conn.execute(
                """
                DELETE FROM partner_monthly_rules
                WHERE reference_month = ? AND partner_name = ?
                """,
                (reference_month, partner_name)
            )
            conn.commit()

    # =========================
    # CONCILIAÇÕES / VERSIONAMENTO
    # =========================
    def get_reconciliation_run(self, run_id: int):
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM reconciliation_runs
                WHERE id = ?
                """,
                (run_id,)
            ).fetchone()

        return dict(row) if row else None

    def get_next_run_version_info(self, base_run_id: int):
        base = self.get_reconciliation_run(base_run_id)
        if not base:
            return None

        run_group = base.get("run_group")
        if not run_group:
            run_group = f"RUN-GROUP-{base_run_id}"

            with self.db.connect() as conn:
                conn.execute(
                    """
                    UPDATE reconciliation_runs
                    SET run_group = ?
                    WHERE id = ?
                    """,
                    (run_group, base_run_id)
                )
                conn.commit()

        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT MAX(run_version) AS max_version
                FROM reconciliation_runs
                WHERE run_group = ?
                """,
                (run_group,)
            ).fetchone()

        max_version = int(row["max_version"]) if row and row["max_version"] is not None else 1

        return {
            "parent_run_id": base_run_id,
            "run_group": run_group,
            "next_version": max_version + 1
        }

    def save_reconciliation_run_versioned(
        self,
        df_resultado: pd.DataFrame,
        parent_run_id: int = None,
        run_group: str = None,
        run_version: int = 1
    ) -> int:
        if df_resultado is None:
            df_resultado = pd.DataFrame()

        total_records = len(df_resultado)
        total_conciliado = int((df_resultado["status"] == "CONCILIADO").sum()) if "status" in df_resultado.columns else 0
        total_somente_banco = int((df_resultado["status"] == "SOMENTE_BANCO").sum()) if "status" in df_resultado.columns else 0
        total_somente_erp = int((df_resultado["status"] == "SOMENTE_ERP").sum()) if "status" in df_resultado.columns else 0

        total_despesas = 0.0
        total_receitas = 0.0

        if not df_resultado.empty:
            for _, row in df_resultado.iterrows():
                tipo = str(row.get("tipo_conciliacao", "") or "").upper()
                valor = row.get("valor_banco")
                if valor is None or pd.isna(valor):
                    valor = row.get("valor_erp")
                try:
                    valor = abs(float(valor))
                except Exception:
                    valor = 0.0

                if tipo == "DESPESA":
                    total_despesas += valor
                elif tipo == "RECEITA":
                    total_receitas += valor

        if not run_group:
            run_group = f"RUN-GROUP-{uuid.uuid4().hex[:10].upper()}"

        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reconciliation_runs (
                    total_records, total_conciliado, total_somente_banco,
                    total_somente_erp, total_despesas, total_receitas,
                    parent_run_id, run_group, run_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    total_records,
                    total_conciliado,
                    total_somente_banco,
                    total_somente_erp,
                    total_despesas,
                    total_receitas,
                    parent_run_id,
                    run_group,
                    run_version
                )
            )
            conn.commit()
            return cursor.lastrowid

    def save_reconciliation_run(self, df_resultado: pd.DataFrame) -> int:
        return self.save_reconciliation_run_versioned(df_resultado)

    def save_reconciliation_results(self, run_id: int, df_resultado: pd.DataFrame):
        if df_resultado is None or df_resultado.empty:
            return

        rows = []
        for _, row in df_resultado.iterrows():
            rows.append((
                run_id,
                self._safe(row.get("tipo_conciliacao")),
                self._safe(row.get("status")),
                self._int_or_none(row.get("diferenca_dias")),
                self._date_or_none(row.get("data_erp")),
                self._date_or_none(row.get("data_banco")),
                self._safe(row.get("descricao_erp")),
                self._safe(row.get("descricao_banco")),
                self._safe(row.get("favorecido_banco")),
                self._safe(row.get("documento_banco")),
                self._safe(row.get("entidade_encontrada")),
                self._safe(row.get("categoria_entidade")),
                self._float_or_none(row.get("valor_erp")),
                self._float_or_none(row.get("valor_banco")),
            ))

        with self.db.connect() as conn:
            conn.executemany(
                """
                INSERT INTO reconciliation_results (
                    run_id, tipo_conciliacao, status, diferenca_dias,
                    data_erp, data_banco, descricao_erp, descricao_banco,
                    favorecido_banco, documento_banco, entidade_encontrada,
                    categoria_entidade, valor_erp, valor_banco
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows
            )
            conn.commit()

    def list_reconciliation_runs(self, limit: int = 100):
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM reconciliation_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_reconciliation_results_df(self, run_id: int) -> pd.DataFrame:
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM reconciliation_results
                WHERE run_id = ?
                ORDER BY id
                """,
                (run_id,)
            ).fetchall()

        if not rows:
            return pd.DataFrame()

        return pd.DataFrame([dict(r) for r in rows])

    # =========================
    # AJUSTES MANUAIS
    # =========================
    def update_reconciliation_result_status(self, result_id: int, new_status: str, note: str = ""):
        with self.db.connect() as conn:
            current = conn.execute(
                "SELECT status FROM reconciliation_results WHERE id = ?",
                (result_id,)
            ).fetchone()

            if not current:
                return False

            previous_status = current["status"]

            conn.execute(
                """
                UPDATE reconciliation_results
                SET status = ?,
                    manual_flag = 1,
                    manual_note = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_status, note, result_id)
            )

            conn.execute(
                """
                INSERT INTO reconciliation_manual_actions (
                    result_id, previous_status, new_status, note
                )
                VALUES (?, ?, ?, ?)
                """,
                (result_id, previous_status, new_status, note)
            )

            conn.commit()
            return True

    def bulk_update_reconciliation_results(self, result_ids, new_status: str, note: str = ""):
        if not result_ids:
            return 0

        updated = 0
        with self.db.connect() as conn:
            for result_id in result_ids:
                current = conn.execute(
                    "SELECT status FROM reconciliation_results WHERE id = ?",
                    (result_id,)
                ).fetchone()

                if not current:
                    continue

                previous_status = current["status"]

                conn.execute(
                    """
                    UPDATE reconciliation_results
                    SET status = ?,
                        manual_flag = 1,
                        manual_note = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (new_status, note, result_id)
                )

                conn.execute(
                    """
                    INSERT INTO reconciliation_manual_actions (
                        result_id, previous_status, new_status, note
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (result_id, previous_status, new_status, note)
                )
                updated += 1

            conn.commit()
        return updated

    def bulk_conciliar_manual(self, ids_banco: list, ids_erp: list,
                               nota: str = "", partner_name: str = "") -> int:
        """
        Conciliação manual que além de marcar CONCILIADO, preenche os valores
        cruzados e salva feedback para o match_model retreinar.
        """
        all_ids = list(ids_banco) + list(ids_erp)
        if not all_ids:
            return 0

        updated = 0
        nota_final = nota or "Conciliação manual via Magical Conciliação"

        with self.db.connect() as conn:
            rows = {}
            for result_id in all_ids:
                try:
                    row = conn.execute(
                        """SELECT id, status, valor_banco, valor_erp,
                                  tipo_conciliacao, descricao_banco, descricao_erp,
                                  favorecido_banco, documento_banco, data_banco, data_erp
                           FROM reconciliation_results WHERE id = ?""",
                        (result_id,)
                    ).fetchone()
                    if row:
                        rows[result_id] = dict(row)
                except Exception:
                    pass

            soma_erp   = sum(abs(self._safe_float(rows[r].get("valor_erp")))
                             for r in ids_erp if r in rows)
            soma_banco = sum(abs(self._safe_float(rows[r].get("valor_banco")))
                             for r in ids_banco if r in rows)

            for result_id in all_ids:
                if result_id not in rows:
                    continue

                row        = rows[result_id]
                prev_st    = row["status"]
                val_banco  = row.get("valor_banco")
                val_erp    = row.get("valor_erp")
                is_erp     = result_id in ids_erp
                is_banco   = result_id in ids_banco

                if is_erp:
                    val_erp_num = abs(self._safe_float(val_erp))
                    conn.execute(
                        """UPDATE reconciliation_results
                           SET status='CONCILIADO', manual_flag=1, manual_note=?,
                               attributed_partner=?,
                               valor_banco=?, updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (nota_final, partner_name or None,
                         val_erp_num if val_erp_num > 0 else val_banco,
                         result_id)
                    )
                elif is_banco:
                    val_banco_num = abs(self._safe_float(val_banco))
                    conn.execute(
                        """UPDATE reconciliation_results
                           SET status='CONCILIADO', manual_flag=1, manual_note=?,
                               attributed_partner=?,
                               valor_erp=?, updated_at=CURRENT_TIMESTAMP
                           WHERE id=?""",
                        (nota_final, partner_name or None,
                         soma_erp if soma_erp > 0 else val_banco_num,
                         result_id)
                    )

                conn.execute(
                    """INSERT INTO reconciliation_manual_actions
                       (result_id, previous_status, new_status, note)
                       VALUES (?, ?, 'CONCILIADO', ?)""",
                    (result_id, prev_st, nota_final)
                )
                updated += 1

            conn.commit()

        # ── Salva feedback positivo e retreina o modelo ───────────────────
        try:
            from core.match_model import MatchModelManager, extract_features
            import json as _json

            mgr = MatchModelManager(self)

            # Gera exemplos positivos: todos os pares banco × ERP conciliados
            for rid_b in ids_banco:
                if rid_b not in rows:
                    continue
                rb = rows[rid_b]
                for rid_e in ids_erp:
                    if rid_e not in rows:
                        continue
                    re_ = rows[rid_e]

                    feats = extract_features(
                        favor_banco = str(rb.get("favorecido_banco") or ""),
                        desc_banco  = str(rb.get("descricao_banco")  or ""),
                        doc_banco   = str(rb.get("documento_banco")  or ""),
                        desc_erp    = str(re_.get("descricao_erp")   or ""),
                        favor_erp   = "",
                        data_banco  = str(rb.get("data_banco")       or "")[:10],
                        data_erp    = str(re_.get("data_erp")        or "")[:10],
                        valor_banco = self._safe_float(rb.get("valor_banco")),
                        valor_erp   = self._safe_float(re_.get("valor_erp")),
                    )
                    self.save_match_feedback(
                        result_id_banco = rid_b,
                        result_id_erp   = rid_e,
                        features_json   = _json.dumps(feats),
                        label           = 1,
                        confianca       = mgr.model.predict_proba(feats),
                    )

            # Retreina se tiver exemplos suficientes
            stats = mgr.retrain()
            if stats.get("ok"):
                self.log("INFO", "MatchModel retreinado",
                         f"n={stats['n_total']} pos={stats['n_pos']} neg={stats['n_neg']}")
        except Exception:
            pass  # ML nunca interrompe a conciliação

        return updated

    # =========================
    # AUDITORIA DE LANÇAMENTOS ERP
    # =========================

    def save_erp_launch_batch(
        self,
        partner_name: str,
        file_name: str,
        file_path: str,
        total_rows: int,
        total_enviado: int,
        total_simulado: int,
        total_erro: int,
        dry_run: bool,
    ) -> int:
        """Registra um lote de lançamento ERP e retorna o batch_id."""
        from datetime import datetime
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.db.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO erp_launch_batches (
                    partner_name, file_name, file_path,
                    total_rows, total_enviado, total_simulado, total_erro,
                    dry_run, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (partner_name, file_name, file_path,
                 total_rows, total_enviado, total_simulado, total_erro,
                 1 if dry_run else 0, created_at)
            )
            conn.commit()
            return cursor.lastrowid

    def check_already_launched(self, partner_name: str, file_name: str,
                                linha: int, descricao: str, valor: float,
                                dry_run: bool = False) -> dict | None:
        """
        Verifica se um item já foi lançado anteriormente com sucesso.
        Retorna dict com info do lançamento anterior ou None se não foi lançado.
        Ignora lançamentos em modo simulação.
        """
        with self.db.connect() as conn:
            row = conn.execute(
                """
                SELECT i.id, i.status, i.id_api, b.created_at, b.id as batch_id
                FROM erp_launch_items i
                JOIN erp_launch_batches b ON i.batch_id = b.id
                WHERE b.partner_name = ?
                  AND b.file_name    = ?
                  AND i.linha_excel  = ?
                  AND i.status       = 'LANCADO'
                  AND b.dry_run      = 0
                ORDER BY b.created_at DESC
                LIMIT 1
                """,
                (partner_name, file_name, linha)
            ).fetchone()
        if row:
            return dict(row)
        return None

    def save_erp_launch_item(
        self,
        batch_id: int,
        linha_excel: int,
        partner_name: str,
        payload: dict,
        status: str,
        id_api: str = "",
        mensagem: str = "",
        categoria: str = "",
    ):
        """Registra o resultado de um item individual do lançamento ERP."""
        import json as _json
        with self.db.connect() as conn:
            conn.execute(
                """
                INSERT INTO erp_launch_items (
                    batch_id, linha_excel, partner_name,
                    data_pagamento, descricao, valor,
                    categoria, id_categoria, modo_pagamento, id_evento,
                    payload_json, status, id_api, mensagem
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    batch_id,
                    linha_excel,
                    partner_name,
                    payload.get("datapagamento", ""),
                    payload.get("descricao", "")[:200],
                    payload.get("valor"),
                    categoria,
                    payload.get("idcategoria"),
                    payload.get("mododepagamento"),
                    payload.get("idevento"),
                    _json.dumps(payload, ensure_ascii=False),
                    status,
                    id_api or "",
                    mensagem[:300] if mensagem else "",
                )
            )
            conn.commit()

    def list_erp_launch_batches(self, limit: int = 100):
        """Lista os últimos lotes de lançamento ERP."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM erp_launch_batches
                ORDER BY id DESC LIMIT ?
                """,
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_erp_launch_items(self, batch_id: int):
        """Retorna todos os itens de um lote de lançamento."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM erp_launch_items
                WHERE batch_id = ? ORDER BY id
                """,
                (batch_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def load_manual_memory(self, partner_name: str = "") -> list:
        """
        Carrega registros conciliados manualmente em execuções anteriores.
        Se partner_name for informado, filtra pelo attributed_partner da casa.
        Retorna lista de dicts com chaves de identificação.
        """
        with self.db.connect() as conn:
            if partner_name:
                rows = conn.execute(
                    """
                    SELECT DISTINCT
                        rr.data_banco, rr.valor_banco, rr.documento_banco,
                        rr.descricao_banco, rr.data_erp, rr.valor_erp,
                        rr.descricao_erp, rr.manual_note, rr.tipo_conciliacao,
                        rr.favorecido_banco
                    FROM reconciliation_results rr
                    WHERE rr.manual_flag = 1
                      AND rr.status = 'CONCILIADO'
                      AND (
                          rr.attributed_partner = ?
                          OR rr.attributed_partner IS NULL
                          OR rr.attributed_partner = ''
                      )
                    ORDER BY rr.updated_at DESC
                    """,
                    (partner_name,)
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT DISTINCT
                        rr.data_banco, rr.valor_banco, rr.documento_banco,
                        rr.descricao_banco, rr.data_erp, rr.valor_erp,
                        rr.descricao_erp, rr.manual_note, rr.tipo_conciliacao,
                        rr.favorecido_banco
                    FROM reconciliation_results rr
                    WHERE rr.manual_flag = 1
                      AND rr.status = 'CONCILIADO'
                    ORDER BY rr.updated_at DESC
                    """
                ).fetchall()
        return [dict(r) for r in rows]

    def count_manual_memory(self) -> int:
        """Retorna quantos registros manuais estão salvos na memória."""
        with self.db.connect() as conn:
            return conn.execute(
                "SELECT COUNT(DISTINCT id) FROM reconciliation_results WHERE manual_flag=1 AND status='CONCILIADO'"
            ).fetchone()[0]

    def save_match_feedback(self, result_id_banco: int, result_id_erp: int,
                             features_json: str, label: int,
                             confianca: float = 0.0):
        """Salva um exemplo de feedback para treino do match_model."""
        with self.db.connect() as conn:
            conn.execute(
                """INSERT INTO match_feedback
                   (result_id_banco, result_id_erp, features_json, label, confianca)
                   VALUES (?, ?, ?, ?, ?)""",
                (result_id_banco, result_id_erp,
                 features_json, int(label), float(confianca))
            )
            conn.commit()

    def list_match_feedback(self, limit: int = 2000) -> list:
        """Retorna todos os exemplos de feedback para retreino."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT * FROM match_feedback
                   ORDER BY id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def count_match_feedback(self) -> dict:
        """Retorna contagem de exemplos por label."""
        with self.db.connect() as conn:
            rows = conn.execute(
                """SELECT label, COUNT(*) as n
                   FROM match_feedback GROUP BY label"""
            ).fetchall()
        return {int(r["label"]): r["n"] for r in rows}

    def attribute_contribution(self, result_id: int, partner_name: str, note: str = "") -> bool:
        """
        Atribui manualmente um depósito (geralmente de aportador do grupo) a um parceiro.
        Salva o partner_name em attributed_partner e marca manual_flag=1.
        O Resumo de Parceiros soma esses registros ao total do parceiro atribuído.
        """
        with self.db.connect() as conn:
            current = conn.execute(
                "SELECT status FROM reconciliation_results WHERE id = ?",
                (result_id,)
            ).fetchone()

            if not current:
                return False

            previous_status = current["status"]
            auto_note = note or f"Aporte atribuído ao parceiro: {partner_name}"

            conn.execute(
                """
                UPDATE reconciliation_results
                SET attributed_partner = ?,
                    manual_flag = 1,
                    manual_note = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (partner_name, auto_note, result_id)
            )

            conn.execute(
                """
                INSERT INTO reconciliation_manual_actions (
                    result_id, previous_status, new_status, note
                )
                VALUES (?, ?, ?, ?)
                """,
                (result_id, previous_status, previous_status,
                 f"Atribuição de aporte ao parceiro '{partner_name}'. {auto_note}")
            )

            conn.commit()
            return True

    @staticmethod
    def _safe_float(value, default=0.0):
        """Converts any value to float safely."""
        try:
            if value is None or str(value).strip() in ("nan", "NaN", "", "None"):
                return default
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe(value):
        if value is None:
            return ""
        if pd.isna(value):
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""
        return text

    @staticmethod
    def _float_or_none(value):
        try:
            if value is None or pd.isna(value):
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _int_or_none(value):
        try:
            if value is None or pd.isna(value):
                return None
            return int(value)
        except Exception:
            return None

    @staticmethod
    def _date_or_none(value):
        try:
            if value is None or pd.isna(value):
                return None
            return pd.to_datetime(value).strftime("%Y-%m-%d")
        except Exception:
            return None