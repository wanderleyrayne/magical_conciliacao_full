# Magical Conciliação

**Versão:** 1.0.0  
**Desenvolvido por:** Rayne Tecnologia  

---

## 📌 Visão Geral

O **Magical Conciliação** é um sistema desktop desenvolvido em Python para realizar conciliação financeira automatizada entre:

- Extrato bancário
- ERP de despesas
- ERP de receitas
- Base de entidades (clientes, fornecedores, parceiros)

O sistema identifica automaticamente divergências e correspondências financeiras, reduzindo esforço manual.

---

## 🎯 Objetivo

- Automatizar conciliação financeira
- Identificar inconsistências
- Cruzar dados com base de entidades
- Manter histórico local em banco SQLite


### Estrutura de pastas
magical_conciliacao_full/
├── assets/
├── core/
├── data/
├── database/
├── logs/
├── ui/
├── utils/
├── main.py

## 🧱 Arquitetura do Sistema

## ⚙️ Tecnologias

- Python 3.x
- Tkinter (interface)
- Pandas (dados)
- SQLite3 (persistência)
- RapidFuzz (similaridade)
- PyInstaller (executável)

---

## 🔄 Fluxo do Sistema

### 1. Inicialização
- Cria banco SQLite automaticamente
- Carrega interface

### 2. Upload de arquivos
- Extrato bancário
- ERP despesas
- ERP receitas
- Base de entidades (opcional)

### 3. Normalização
Padroniza dados:

- data
- valor
- descrição
- documento
- tipo (entrada/saída)

### 4. Persistência
Dados salvos em:
- arquivos importados
- registros normalizados
- base de entidades

### 5. Conciliação
Comparação baseada em:

- valor
- data
- descrição
- entidade

### 6. Resultado
Classificação:

- CONCILIADO
- SOMENTE_BANCO
- SOMENTE_ERP

---

## 📊 Banco de Dados (SQLite)

Arquivo: data/conciliacao.db

## 🗄️ Estrutura das Tabelas

### 🔹 app_logs
```sql
CREATE TABLE app_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT,
    message TEXT,
    details TEXT,
    created_at TEXT
);

🔹 imported_files

CREATE TABLE imported_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_type TEXT,
    file_name TEXT,
    file_path TEXT,
    total_rows INTEGER,
    total_columns INTEGER,
    imported_at TEXT
);

🔹 normalized_records

CREATE TABLE normalized_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imported_file_id INTEGER,
    source_type TEXT,
    data TEXT,
    descricao TEXT,
    favorecido TEXT,
    documento TEXT,
    forma_pagamento TEXT,
    pago TEXT,
    tipo TEXT,
    valor REAL,
    categoria TEXT,
    extra_json TEXT
);

🔹 entities_master

CREATE TABLE entities_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    documento TEXT,
    razao_social TEXT,
    razao_social_short TEXT,
    categoria TEXT,
    nome_busca TEXT,
    nome_resumido TEXT,
    source_file_name TEXT,
    updated_at TEXT
);

Índice:
CREATE UNIQUE INDEX idx_entities_master_documento
ON entities_master(documento);

🔹 reconciliation_runs
CREATE TABLE reconciliation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    executed_at TEXT,
    total_records INTEGER,
    total_conciliado INTEGER,
    total_somente_banco INTEGER,
    total_somente_erp INTEGER,
    total_despesas REAL,
    total_receitas REAL
);

🔹 reconciliation_results

CREATE TABLE reconciliation_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER,
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
    valor_banco REAL
);


🔎 Consultas SQL úteis

Ver entidades
SELECT * FROM entities_master;

Ver conciliações
SELECT * FROM reconciliation_runs;

Última conciliação
SELECT * FROM reconciliation_results
WHERE run_id = (SELECT MAX(id) FROM reconciliation_runs);

Logs
SELECT * FROM app_logs ORDER BY id DESC;


🧠 Regras de Negócio
Classificação
Valor positivo → RECEITA
Valor negativo → DESPESA
Linhas ignoradas
SALDO
IOF
APLICAÇÃO AUTOMÁTICA
Conciliação
valor igual
data compatível
tipo compatível
👥 Base de Entidades
Persistida no banco
Não obrigatória para execução
Atualizada via upload
Regra de atualização
se documento existir → atualiza
se não → insere
🎨 Interface
Tela principal
upload de arquivos
validação
execução
Tela de resultado
tabela de conciliação
cores:
verde → conciliado
amarelo → ERP
vermelho → banco
💾 Persistência

O sistema salva automaticamente:

arquivos importados
dados normalizados
base de entidades
resultados de conciliação
logs
🚀 Execução
Rodar projeto

⚠️ Limitações atuais
sem tela de configurações
sem exportação Excel
sem histórico visual
sem edição manual de entidades
🔮 Roadmap 2.0.0
tela de configurações
exportação Excel/PDF
histórico visual
edição de entidades
backup automático
regras customizadas

📌 Resumo

O sistema já permite:

leitura de planilhas
normalização de dados
conciliação automatizada
identificação por entidades
persistência em banco
execução como aplicativo desktop