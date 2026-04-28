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
                documento = self._safe(row.get("documento"))
                razao_social = self._safe(row.get("razao_social"))
                razao_social_short = self._safe(row.get("razao_social_short"))
                categoria = self._safe(row.get("categoria"))
                nome_busca = self._safe(row.get("nome_busca"))
                nome_resumido = self._safe(row.get("nome_resumido"))

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
                                source_file_name = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE documento = ?
                            """,
                            (
                                razao_social,
                                razao_social_short,
                                categoria,
                                nome_busca,
                                nome_resumido,
                                source_file_name,
                                documento
                            )
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO entities_master (
                                documento, razao_social, razao_social_short,
                                categoria, nome_busca, nome_resumido, source_file_name
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                documento,
                                razao_social,
                                razao_social_short,
                                categoria,
                                nome_busca,
                                nome_resumido,
                                source_file_name
                            )
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
                                source_file_name = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE razao_social = ?
                            """,
                            (
                                razao_social_short,
                                categoria,
                                nome_busca,
                                nome_resumido,
                                source_file_name,
                                razao_social
                            )
                        )
                    else:
                        conn.execute(
                            """
                            INSERT INTO entities_master (
                                documento, razao_social, razao_social_short,
                                categoria, nome_busca, nome_resumido, source_file_name
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                documento,
                                razao_social,
                                razao_social_short,
                                categoria,
                                nome_busca,
                                nome_resumido,
                                source_file_name
                            )
                        )
                total += 1

            conn.commit()
        return total

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