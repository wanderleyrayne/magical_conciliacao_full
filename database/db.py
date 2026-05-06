import sqlite3
from pathlib import Path


class DatabaseManager:
    def __init__(self, db_path="data/conciliacao.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with self.connect() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imported_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_type TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    total_rows INTEGER DEFAULT 0,
                    total_columns INTEGER DEFAULT 0,
                    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS normalized_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imported_file_id INTEGER NOT NULL,
                    source_type TEXT NOT NULL,
                    data TEXT,
                    descricao TEXT,
                    favorecido TEXT,
                    documento TEXT,
                    forma_pagamento TEXT,
                    pago TEXT,
                    tipo TEXT,
                    valor REAL,
                    categoria TEXT,
                    extra_json TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (imported_file_id) REFERENCES imported_files(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    documento TEXT,
                    razao_social TEXT,
                    razao_social_short TEXT,
                    categoria TEXT,
                    nome_busca TEXT,
                    nome_resumido TEXT,
                    cargo_ocupacao TEXT,
                    source_file_name TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_master_documento
                ON entities_master(documento)
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS partner_monthly_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reference_month TEXT NOT NULL,
                    partner_name TEXT NOT NULL,
                    partner_cnpj TEXT,
                    subtotal REAL DEFAULT 0,
                    marketing_fee REAL DEFAULT 0,
                    total_expected REAL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_partner_month_rule
                ON partner_monthly_rules(reference_month, partner_name)
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    total_records INTEGER DEFAULT 0,
                    total_conciliado INTEGER DEFAULT 0,
                    total_somente_banco INTEGER DEFAULT 0,
                    total_somente_erp INTEGER DEFAULT 0,
                    total_despesas REAL DEFAULT 0,
                    total_receitas REAL DEFAULT 0,
                    parent_run_id INTEGER,
                    run_group TEXT,
                    run_version INTEGER DEFAULT 1
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    tipo_conciliacao TEXT,
                    status TEXT,
                    diferenca_dias INTEGER,
                    data_erp TEXT,
                    data_banco TEXT,
                    descricao_erp TEXT,
                    descricao_banco TEXT,
                    favorecido_banco TEXT,
                    documento_banco TEXT,
                    entidade_encontrada TEXT,
                    categoria_entidade TEXT,
                    valor_erp REAL,
                    valor_banco REAL,
                    manual_flag INTEGER DEFAULT 0,
                    manual_note TEXT,
                    updated_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES reconciliation_runs(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reconciliation_manual_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_id INTEGER NOT NULL,
                    previous_status TEXT,
                    new_status TEXT,
                    note TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (result_id) REFERENCES reconciliation_results(id)
                )
            """)

            # ── Auditoria de lançamentos ERP ───────────────────────────────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS erp_launch_batches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    partner_name TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    total_rows INTEGER DEFAULT 0,
                    total_enviado INTEGER DEFAULT 0,
                    total_simulado INTEGER DEFAULT 0,
                    total_erro INTEGER DEFAULT 0,
                    dry_run INTEGER DEFAULT 0,
                    executed_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS erp_launch_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    batch_id INTEGER NOT NULL,
                    linha_excel INTEGER,
                    partner_name TEXT,
                    data_pagamento TEXT,
                    descricao TEXT,
                    valor REAL,
                    categoria TEXT,
                    id_categoria INTEGER,
                    modo_pagamento INTEGER,
                    id_evento INTEGER,
                    payload_json TEXT,
                    status TEXT,
                    id_api TEXT,
                    mensagem TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (batch_id) REFERENCES erp_launch_batches(id)
                )
            """)

            # ── Feedback de conciliação manual (treino do match_model) ────
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS match_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_id_banco INTEGER,
                    result_id_erp   INTEGER,
                    features_json   TEXT NOT NULL,
                    label           INTEGER NOT NULL,
                    confianca       REAL DEFAULT 0.0,
                    created_at      TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.commit()

            self._ensure_column(conn, "reconciliation_results", "manual_flag", "INTEGER DEFAULT 0")
            self._ensure_column(conn, "reconciliation_results", "manual_note", "TEXT")
            self._ensure_column(conn, "reconciliation_results", "updated_at", "TEXT")
            # Atribuição manual de aporte a um parceiro específico
            self._ensure_column(conn, "reconciliation_results", "attributed_partner", "TEXT")

            self._ensure_column(conn, "reconciliation_runs", "parent_run_id", "INTEGER")
            self._ensure_column(conn, "reconciliation_runs", "run_group", "TEXT")
            self._ensure_column(conn, "reconciliation_runs", "run_version", "INTEGER DEFAULT 1")
            # Cargo/papel da entidade no grupo (importado da base de entidades)
            self._ensure_column(conn, "entities_master", "cargo_ocupacao", "TEXT")
            self._ensure_column(conn, "erp_launch_batches", "created_at", "TEXT")

    def _ensure_column(self, conn, table_name: str, column_name: str, column_def: str):
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row["name"] for row in cols}
        if column_name not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")
            conn.commit()