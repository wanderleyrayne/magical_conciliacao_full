import json
from database.repository import SystemRepository


DEFAULT_VISIBLE_COLUMNS = [
    "tipo_conciliacao",
    "status",
    "data_erp",
    "data_banco",
    "descricao_erp",
    "descricao_banco",
    "favorecido_banco",
    "documento_banco",
    "entidade_encontrada",
    "categoria_entidade",
    "valor_erp",
    "valor_banco",
    "manual_note",
]

# Tolerância padrão de dias para match de data na conciliação
DEFAULT_DATE_TOLERANCE = 3


class SettingsManager:
    KEY_VISIBLE_COLUMNS  = "visible_columns_v2"
    KEY_DATE_TOLERANCE   = "reconciler_date_tolerance_days"

    def __init__(self, db_path="data/conciliacao.db"):
        self.repo = SystemRepository(db_path)

    # ── Colunas visíveis ─────────────────────────────────────────────────────
    def get_visible_columns(self):
        raw = self.repo.get_setting(self.KEY_VISIBLE_COLUMNS)
        if not raw:
            return DEFAULT_VISIBLE_COLUMNS.copy()
        try:
            value = json.loads(raw)
            if isinstance(value, list) and value:
                return value
        except Exception:
            pass
        return DEFAULT_VISIBLE_COLUMNS.copy()

    def save_visible_columns(self, columns):
        self.repo.save_setting(self.KEY_VISIBLE_COLUMNS, json.dumps(columns, ensure_ascii=False))

    def restore_default_columns(self):
        self.save_visible_columns(DEFAULT_VISIBLE_COLUMNS.copy())
        return DEFAULT_VISIBLE_COLUMNS.copy()

    # ── Tolerância de data ───────────────────────────────────────────────────
    def get_date_tolerance(self) -> int:
        raw = self.repo.get_setting(self.KEY_DATE_TOLERANCE)
        try:
            v = int(raw)
            return max(0, min(v, 30))   # limita entre 0 e 30 dias
        except (TypeError, ValueError):
            return DEFAULT_DATE_TOLERANCE

    def save_date_tolerance(self, days: int):
        self.repo.save_setting(self.KEY_DATE_TOLERANCE, str(int(days)))