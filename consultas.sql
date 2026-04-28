9. Modelo de dados
9.1 Tabela app_logs

Armazena logs do sistema.
Estrutura
id
level
message
details
created_at

SQL
CREATE TABLE IF NOT EXISTS app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    details TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

9.2 Tabela imported_files
Armazena cada arquivo enviado pelo usuário.

Estrutura
id
file_type
file_name
file_path
total_rows
total_columns
imported_at

SQL
CREATE TABLE IF NOT EXISTS imported_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_type TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    total_rows INTEGER DEFAULT 0,
    total_columns INTEGER DEFAULT 0,
    imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);

9.3 Tabela normalized_records
Armazena os registros após padronização.

Estrutura
id
imported_file_id
source_type
data
descricao
favorecido
documento
forma_pagamento
pago
tipo
valor
categoria
extra_json
created_at

SQL
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
);

9.4 Tabela entities_master
Base persistente de entidades.

Estrutura
id
documento
razao_social
razao_social_short
categoria
nome_busca
nome_resumido
source_file_name
updated_at

SQL
CREATE TABLE IF NOT EXISTS entities_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT,
    razao_social TEXT,
    razao_social_short TEXT,
    categoria TEXT,
    nome_busca TEXT,
    nome_resumido TEXT,
    source_file_name TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

Índice único por documento
CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_master_documento
ON entities_master(documento);

9.5 Tabela reconciliation_runs

Armazena cada execução da conciliação.

Estrutura
id
executed_at
total_records
total_conciliado
total_somente_banco
total_somente_erp
total_despesas
total_receitas

SQL
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    executed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    total_records INTEGER DEFAULT 0,
    total_conciliado INTEGER DEFAULT 0,
    total_somente_banco INTEGER DEFAULT 0,
    total_somente_erp INTEGER DEFAULT 0,
    total_despesas REAL DEFAULT 0,
    total_receitas REAL DEFAULT 0
);
9.6 Tabela reconciliation_results

Armazena o resultado linha a linha de cada conciliação.

Estrutura
id
run_id
tipo_conciliacao
status
diferenca_dias
data_erp
data_banco
descricao_erp
descricao_banco
favorecido_banco
documento_banco
entidade_encontrada
categoria_entidade
valor_erp
valor_banco
created_at

SQL
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
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES reconciliation_runs(id)
);

10. Comandos SQL úteis

10.1 Ver todas as tabelas
SELECT name FROM sqlite_master WHERE type='table'
ORDER BY name;

10.2 Ver estrutura de uma tabela
PRAGMA table_info(entities_master);

10.3 Ver arquivos importados
SELECT * FROM imported_files
ORDER BY id DESC;

10.4 Ver logs
SELECT * FROM app_logs
ORDER BY id DESC;

10.5 Ver base de entidades
SELECT * FROM entities_master
ORDER BY razao_social;

10.6 Contar entidades
SELECT COUNT(*) AS total_entidades
FROM entities_master;

10.7 Ver registros normalizados
SELECT * FROM normalized_records
ORDER BY id DESC LIMIT 100;

10.8 Ver execuções de conciliação
SELECT * FROM reconciliation_runs
ORDER BY id DESC;

10.9 Ver resultados da última conciliação
SELECT * FROM reconciliation_results
WHERE run_id = (SELECT MAX(id) FROM reconciliation_runs)
ORDER BY id;

10.10 Ver apenas conciliados
SELECT * FROM reconciliation_results
WHERE status = 'CONCILIADO'
ORDER BY id DESC;

10.11 Ver somente banco
SELECT * FROM reconciliation_results
WHERE status = 'SOMENTE_BANCO'
ORDER BY id DESC;

10.12 Ver somente ERP
SELECT * FROM reconciliation_results
WHERE status = 'SOMENTE_ERP'
ORDER BY id DESC;

10.13 Somatório de despesas por execução
SELECT run_id, SUM(COALESCE(valor_banco, valor_erp)) AS total_despesas
FROM reconciliation_results
WHERE tipo_conciliacao = 'DESPESA'
GROUP BY run_id
ORDER BY run_id DESC;


10.14 Somatório de receitas por execução
SELECT run_id, SUM(COALESCE(valor_banco, valor_erp)) AS total_receitas
FROM reconciliation_results
WHERE tipo_conciliacao = 'RECEITA'
GROUP BY run_id
ORDER BY run_id DESC;

10.15 Ver conciliações com entidade reconhecida
SELECT * FROM reconciliation_results
WHERE entidade_encontrada IS NOT NULL
  AND entidade_encontrada <> ''
ORDER BY id DESC;


10.16 Ver conciliações sem entidade reconhecida
SELECT * FROM reconciliation_results
WHERE entidade_encontrada IS NULL
   OR entidade_encontrada = ''
ORDER BY id DESC;