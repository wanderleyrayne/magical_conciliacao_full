"""
patch_cnab_globals.py — Corrige uso de variaveis globais no GeradorCNAB240
O problema: EMPRESA_* sao globais, quando dois lotes sao gerados
o segundo sobrescreve o primeiro zerando os valores.
Execute da raiz: python patch_cnab_globals.py
"""
from pathlib import Path
import ast

TARGET = Path("core/cnab_itau.py")

with open(TARGET, encoding='utf-8') as f:
    src = f.read()

# ── Substitui __init__ para usar instancia em vez de globals ──────────────
old = '''    def __init__(self, config: dict = None):
        """
        config: dict com dados da empresa (sobrescreve defaults do módulo)
          - cnpj, agencia, conta, dac, nome
        """
        global EMPRESA_CNPJ, EMPRESA_AGENCIA, EMPRESA_CONTA, EMPRESA_DAC, EMPRESA_NOME
        if config:
            if config.get("cnpj"):    EMPRESA_CNPJ    = re.sub(r"\\D", "", config["cnpj"])
            if config.get("agencia"): EMPRESA_AGENCIA = str(config["agencia"]).zfill(5)
            if config.get("conta"):   EMPRESA_CONTA   = str(config["conta"]).zfill(12)
            if config.get("dac"):     EMPRESA_DAC     = str(config["dac"])
            if config.get("nome"):    EMPRESA_NOME    = str(config["nome"])[:30].upper()

        self._pagamentos_pix  = []   # PIX — arquivo separado
        self._pagamentos_ted  = []   # TED/DOC/CC — arquivo junto'''

new = '''    def __init__(self, config: dict = None):
        """
        config: dict com dados da empresa
          - cnpj, agencia, conta, dac, nome
        """
        # Usa dados da instancia — nao sobrescreve globals
        cfg = config or {}
        self._cnpj    = re.sub(r"\\D", "", str(cfg.get("cnpj", EMPRESA_CNPJ)))
        self._agencia = str(cfg.get("agencia", EMPRESA_AGENCIA)).zfill(5)
        self._conta   = str(cfg.get("conta", EMPRESA_CONTA)).zfill(12)
        self._dac     = str(cfg.get("dac", EMPRESA_DAC))
        self._nome    = str(cfg.get("nome", EMPRESA_NOME))[:30].upper()

        self._pagamentos_pix  = []
        self._pagamentos_ted  = []'''

if old not in src:
    print("ERRO: bloco __init__ nao encontrado!")
    exit(1)
src = src.replace(old, new)
print("Fix 1 OK: __init__ usa variaveis de instancia")

# ── Atualiza _gerar_arquivo para usar self em vez de globals ──────────────
old2 = '''    def _gerar_arquivo(self, pagamentos: list, sufixo: str, output_dir: Path) -> Path:
        """Gera um arquivo CNAB 240 com a lista de pagamentos."""
        linhas = []
        num_lote       = 0
        total_registros = 1  # header arquivo

        # Header arquivo
        linhas.append(header_arquivo())'''

new2 = '''    def _gerar_arquivo(self, pagamentos: list, sufixo: str, output_dir: Path) -> Path:
        """Gera um arquivo CNAB 240 com a lista de pagamentos."""
        # Aplica dados da instancia nas funcoes de registro
        global EMPRESA_CNPJ, EMPRESA_AGENCIA, EMPRESA_CONTA, EMPRESA_DAC, EMPRESA_NOME
        EMPRESA_CNPJ    = self._cnpj
        EMPRESA_AGENCIA = self._agencia
        EMPRESA_CONTA   = self._conta
        EMPRESA_DAC     = self._dac
        EMPRESA_NOME    = self._nome

        linhas = []
        num_lote        = 0
        total_registros = 1  # header arquivo

        # Header arquivo
        linhas.append(header_arquivo())'''

if old2 not in src:
    print("ERRO: bloco _gerar_arquivo nao encontrado!")
    exit(1)
src = src.replace(old2, new2)
print("Fix 2 OK: _gerar_arquivo aplica variaveis da instancia")

ast.parse(src)
print("Sintaxe OK")

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print("\nArquivo atualizado: core/cnab_itau.py")
print("Gere o CNAB novamente pelo Workflow e teste!")