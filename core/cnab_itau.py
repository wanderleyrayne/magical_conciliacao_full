"""
cnab_itau.py — Gerador de arquivo CNAB 240 SISPAG Itaú (versão 086)

Gera arquivo .rem para upload no portal Itaú SISPAG.
Suporta: PIX (arquivo separado), TED/DOC (outro banco), Crédito em Conta Corrente Itaú.

Estrutura do arquivo:
  Header de Arquivo      (1 registro)
  Para cada lote:
    Header de Lote       (1 registro)
    Segmento A           (1 por pagamento)
    Segmento B           (1 por pagamento PIX — obrigatório)
    Trailer de Lote      (1 registro)
  Trailer de Arquivo     (1 registro)

Cada registro = 240 bytes + '\n'
"""

from datetime import datetime, date
from pathlib import Path
import re


# ── Configuração da empresa debitada ─────────────────────────────────────────
# Preencher com os dados reais da conta Itaú
EMPRESA_CNPJ        = "00000000000000"   # CNPJ sem pontuação (14 dígitos)
EMPRESA_AGENCIA     = "00000"            # Agência sem dígito (5 dígitos)
EMPRESA_CONTA       = "000000000000"     # Conta sem dígito (12 dígitos)
EMPRESA_DAC         = "0"               # Dígito agência/conta (1 dígito)
EMPRESA_NOME        = "RAYNE TECNOLOGIA LTDA"  # Nome da empresa (max 30)
BANCO_ITAU          = "341"
BANCO_NOME          = "BANCO ITAU SA"


# ── Forma de pagamento ────────────────────────────────────────────────────────
FORMA_PIX           = "45"  # PIX Transferência
FORMA_TED_OUTRO     = "41"  # TED — Outro Titular
FORMA_TED_MESMO     = "43"  # TED — Mesmo Titular
FORMA_CC_ITAU       = "01"  # Crédito em conta corrente Itaú
FORMA_CC_MESMO      = "06"  # Crédito em conta corrente mesma titularidade
FORMA_DOC_C         = "03"  # DOC "C" — Outro Titular

TIPO_PAGTO_FORNEC   = "20"  # Fornecedores
TIPO_PAGTO_DIVERSOS = "98"  # Diversos


# ── Tipo de chave PIX (Nota 37) ───────────────────────────────────────────────
PIX_CHAVE_CPF       = "01"
PIX_CHAVE_CNPJ      = "02"
PIX_CHAVE_EMAIL     = "03"
PIX_CHAVE_CELULAR   = "04"
PIX_CHAVE_EVP       = "05"  # Chave aleatória


def _n(valor, tam, fill="0"):
    """Campo numérico: remove não-dígitos, preenche com zeros à esquerda."""
    s = re.sub(r"\D", "", str(valor or ""))
    return s.zfill(tam)[:tam]


def _a(valor, tam, fill=" "):
    """Campo alfanumérico: uppercase, preenche com espaços à direita."""
    s = str(valor or "").upper().strip()
    return s.ljust(tam, fill)[:tam]


def _valor(v, inteiros=13, decimais=2):
    """Valor monetário: sem vírgula/ponto — centavos em inteiros."""
    try:
        cents = round(abs(float(v)) * (10 ** decimais))
        return str(int(cents)).zfill(inteiros + decimais)[:inteiros + decimais]
    except Exception:
        return "0" * (inteiros + decimais)


def _data(d):
    """Data no formato DDMMAAAA."""
    if isinstance(d, (datetime, date)):
        return d.strftime("%d%m%Y")
    try:
        dt = datetime.strptime(str(d).strip(), "%Y-%m-%d")
        return dt.strftime("%d%m%Y")
    except Exception:
        pass
    try:
        dt = datetime.strptime(str(d).strip(), "%d/%m/%Y")
        return dt.strftime("%d%m%Y")
    except Exception:
        return datetime.today().strftime("%d%m%Y")


def _assert_240(linha: str, campo: str = ""):
    """Garante que a linha tem exatamente 240 caracteres."""
    if len(linha) != 240:
        raise ValueError(
            f"Registro com tamanho incorreto: {len(linha)} chars "
            f"(esperado 240) [{campo}]\n{linha!r}")
    return linha


# ── Registros ────────────────────────────────────────────────────────────────

def header_arquivo(num_sequencial: int = 1) -> str:
    """Registro Header de Arquivo (posições 1-240)."""
    now = datetime.now()
    linha = (
        _n(BANCO_ITAU, 3) +           # 001-003 Código banco
        _n(0, 4) +                     # 004-007 Código lote (0000)
        "0" +                          # 008     Tipo registro
        _a("", 6) +                    # 009-014 Brancos
        _n(80, 3) +                    # 015-017 Versão layout arquivo
        "2" +                          # 018     Tipo inscrição (2=CNPJ)
        _n(EMPRESA_CNPJ, 14) +         # 019-032 CNPJ empresa
        _a("", 20) +                   # 033-052 Brancos
        _n(EMPRESA_AGENCIA, 5) +       # 053-057 Agência
        _a("", 1) +                    # 058     Branco
        _n(EMPRESA_CONTA, 12) +        # 059-070 Conta
        _a("", 1) +                    # 071     Branco
        _n(EMPRESA_DAC, 1) +           # 072     DAC
        _a(EMPRESA_NOME, 30) +         # 073-102 Nome empresa
        _a(BANCO_NOME, 30) +           # 103-132 Nome banco
        _a("", 10) +                   # 133-142 Brancos
        "1" +                          # 143     Código remessa
        now.strftime("%d%m%Y") +       # 144-151 Data geração
        now.strftime("%H%M%S") +       # 152-157 Hora geração
        _n(num_sequencial, 9) +        # 158-166 Sequencial
        _n(0, 5) +                     # 167-171 Densidade (zeros)
        _a("", 69)                     # 172-240 Brancos
    )
    return _assert_240(linha, "header_arquivo")


def header_lote(num_lote: int, forma_pagto: str,
                tipo_pagto: str = TIPO_PAGTO_FORNEC) -> str:
    """Registro Header de Lote (posições 1-240)."""
    linha = (
        _n(BANCO_ITAU, 3) +            # 001-003 Banco
        _n(num_lote, 4) +              # 004-007 Lote
        "1" +                          # 008     Tipo registro header lote
        "C" +                          # 009     Tipo operação (crédito)
        _n(tipo_pagto, 2) +            # 010-011 Tipo pagamento
        _n(forma_pagto, 2) +           # 012-013 Forma pagamento
        _n(40, 3) +                    # 014-016 Versão layout lote
        _a("", 1) +                    # 017     Branco
        "2" +                          # 018     Tipo inscrição empresa
        _n(EMPRESA_CNPJ, 14) +         # 019-032 CNPJ
        _a("", 4) +                    # 033-036 ID lançamento
        _a("", 16) +                   # 037-052 Brancos
        _n(EMPRESA_AGENCIA, 5) +       # 053-057 Agência
        _a("", 1) +                    # 058     Branco
        _n(EMPRESA_CONTA, 12) +        # 059-070 Conta
        _a("", 1) +                    # 071     Branco
        _n(EMPRESA_DAC, 1) +           # 072     DAC
        _a(EMPRESA_NOME, 30) +         # 073-102 Nome empresa
        _a("", 30) +                   # 103-132 Finalidade lote
        _a("", 10) +                   # 133-142 Histórico C/C
        _a("", 30) +                   # 143-172 Endereço
        _n(0, 5) +                     # 173-177 Número
        _a("", 15) +                   # 178-192 Complemento
        _a("", 20) +                   # 193-212 Cidade
        _n(0, 8) +                     # 213-220 CEP
        _a("", 2) +                    # 221-222 Estado
        _a("", 8) +                    # 223-230 Brancos
        _a("", 10)                     # 231-240 Ocorrências (retorno)
    )
    return _assert_240(linha, "header_lote")


def segmento_a(num_lote: int, num_registro: int, pagto: dict,
               forma_pagto: str) -> str:
    """
    Segmento A — obrigatório para todos os pagamentos.
    pagto deve ter: banco_favorecido, agencia, conta, dac, nome, data, valor,
                    cpf_cnpj, finalidade (opcional)
    """
    banco_fav = str(pagto.get("banco_favorecido", "341")).strip().zfill(3)
    eh_itau   = banco_fav in ("341", "409")
    eh_pix    = forma_pagto == FORMA_PIX

    # Campo agência/conta favorecido (pos 024-043 = 20 chars) — Nota 11
    if eh_pix:
        # PIX: preenche com zeros se usar chave
        ag_conta = _n(0, 20)
    elif eh_itau:
        # Itaú: 0 + agência(4) + branco + 0(6) + conta(6) + branco + dac(1)
        ag_conta = (
            "0" +
            _n(pagto.get("agencia", ""), 4) +
            " " +
            _n(0, 6) +
            _n(pagto.get("conta", ""), 6) +
            " " +
            _n(pagto.get("dac", "0"), 1)
        )
    else:
        # Outro banco: agência(5) + branco + conta(12) + branco + dac(1)
        ag_conta = (
            _n(pagto.get("agencia", ""), 5) +
            " " +
            _n(pagto.get("conta", ""), 12) +
            " " +
            _n(pagto.get("dac", "0"), 1)
        )

    # Câmara + ISPB (pos 018-020 / 105-112)
    camara = "000"
    ispb   = _n(0, 8)

    # Complemento para PIX (pos 113-114)
    if eh_pix:
        tipo_chave = pagto.get("pix_tipo_chave", "04")  # 04 = chave
        id_transf  = str(tipo_chave).zfill(2)[:2]
    else:
        id_transf = "  "

    linha = (
        _n(BANCO_ITAU, 3) +            # 001-003 Banco
        _n(num_lote, 4) +              # 004-007 Lote
        "3" +                          # 008     Tipo registro detalhe
        _n(num_registro, 5) +          # 009-013 Nº registro no lote
        "A" +                          # 014     Segmento
        _n(0, 3) +                     # 015-017 Tipo movimento (000=inclusão)
        camara +                       # 018-020 Câmara
        _n(banco_fav, 3) +             # 021-023 Banco favorecido
        ag_conta +                     # 024-043 Agência/conta favorecido (20)
        _a(pagto.get("nome", ""), 30) +# 044-073 Nome favorecido
        _a(pagto.get("seu_numero", ""), 20) +  # 074-093 Seu número
        _data(pagto.get("data")) +     # 094-101 Data pagamento
        "REA" +                        # 102-104 Moeda
        ispb +                         # 105-112 ISPB (zeros)
        id_transf +                    # 113-114 Tipo transf / PIX tipo chave
        _n(0, 5) +                     # 115-119 Zeros
        _valor(pagto.get("valor", 0)) +# 120-134 Valor (13+2)
        _a("", 15) +                   # 135-149 Nosso número (brancos remessa)
        _a("", 5) +                    # 150-154 Brancos
        _n(0, 8) +                     # 155-162 Data efetiva (zeros remessa)
        _valor(0) +                    # 163-177 Valor efetivo (zeros remessa)
        _a(pagto.get("finalidade", ""), 20) +  # 178-197 Finalidade detalhe
        _n(0, 6) +                     # 198-203 Nº documento (zeros remessa)
        _n(pagto.get("cpf_cnpj", ""), 14) +    # 204-217 CPF/CNPJ favorecido
        _a("", 2) +                    # 218-219 Finalidade DOC/status
        _a("", 5) +                    # 220-224 Finalidade TED
        _a("", 5) +                    # 225-229 Brancos
        "0" +                          # 230     Aviso ao favorecido (0=sem)
        _a("", 10)                     # 231-240 Ocorrências (brancos remessa)
    )
    return _assert_240(linha, f"segmento_a lote={num_lote} reg={num_registro}")


def segmento_b_pix(num_lote: int, num_registro: int, pagto: dict) -> str:
    """
    Segmento B — obrigatório para PIX.
    pagto deve ter: pix_chave, pix_tipo_chave, cpf_cnpj
    """
    tipo_inscr = "2" if len(re.sub(r"\D", "", str(pagto.get("cpf_cnpj", "")))) == 14 else "1"

    linha = (
        _n(BANCO_ITAU, 3) +            # 001-003 Banco
        _n(num_lote, 4) +              # 004-007 Lote
        "3" +                          # 008     Tipo registro
        _n(num_registro, 5) +          # 009-013 Mesmo nº do segmento A
        "B" +                          # 014     Segmento B
        _a(pagto.get("pix_tipo_chave", "04"), 2) +  # 015-016 Tipo chave PIX
        _a("", 1) +                    # 017     Branco
        tipo_inscr +                   # 018     Tipo inscrição
        _n(pagto.get("cpf_cnpj", ""), 14) +  # 019-032 CPF/CNPJ
        _a("", 30) +                   # 033-062 Endereço (brancos)
        _n(0, 5) +                     # 063-067 Número (zeros)
        _a("", 15) +                   # 068-082 Complemento
        _a("", 15) +                   # 083-097 Bairro
        _a("", 20) +                   # 098-117 Cidade
        _n(0, 8) +                     # 118-125 CEP
        _a("", 2) +                    # 126-127 Estado
        _a(pagto.get("pix_chave", ""), 100) +  # 128-227 Chave PIX
        _a("", 3) +                    # 228-230 Brancos
        _a("", 10)                     # 231-240 Ocorrências
    )
    return _assert_240(linha, f"segmento_b_pix lote={num_lote} reg={num_registro}")


def trailer_lote(num_lote: int, qtd_registros: int, valor_total: float) -> str:
    """Trailer de Lote."""
    linha = (
        _n(BANCO_ITAU, 3) +            # 001-003 Banco
        _n(num_lote, 4) +              # 004-007 Lote
        "5" +                          # 008     Tipo registro trailer lote
        _a("", 9) +                    # 009-017 Brancos
        _n(qtd_registros, 6) +         # 018-023 Qtd registros no lote
        _valor(valor_total) +          # 024-038 Valor total (13+2)
        _n(0, 6) +                     # 039-044 Qtd moeda (zeros)
        _a("", 3) +                    # 045-047 Brancos
        _n(0, 10) +                    # 048-057 Aviso (zeros)
        _a("", 183)                    # 058-240 Brancos
    )
    return _assert_240(linha, f"trailer_lote {num_lote}")


def trailer_arquivo(qtd_lotes: int, qtd_registros: int) -> str:
    """Trailer de Arquivo."""
    linha = (
        _n(BANCO_ITAU, 3) +            # 001-003 Banco
        _n(9999, 4) +                  # 004-007 Lote (9999 no trailer)
        "9" +                          # 008     Tipo registro trailer arquivo
        _a("", 9) +                    # 009-017 Brancos
        _n(qtd_lotes, 6) +             # 018-023 Qtd lotes
        _n(qtd_registros, 6) +         # 024-029 Qtd registros totais
        _n(0, 6) +                     # 030-035 Qtd contas (zeros)
        _a("", 205)                    # 036-240 Brancos
    )
    return _assert_240(linha, "trailer_arquivo")


# ── Gerador principal ─────────────────────────────────────────────────────────

class GeradorCNAB240:
    """
    Gera arquivo(s) CNAB 240 a partir de lista de pagamentos.

    PIX é separado dos demais conforme exigência do Itaú.

    Uso:
        g = GeradorCNAB240(config)
        g.adicionar_pagamentos(lista)
        arquivos = g.gerar()
        # arquivos = {"pix": Path(...), "ted_cc": Path(...)}
    """

    def __init__(self, config: dict = None):
        """
        config: dict com dados da empresa (sobrescreve defaults do módulo)
          - cnpj, agencia, conta, dac, nome
        """
        global EMPRESA_CNPJ, EMPRESA_AGENCIA, EMPRESA_CONTA, EMPRESA_DAC, EMPRESA_NOME
        if config:
            if config.get("cnpj"):    EMPRESA_CNPJ    = re.sub(r"\D", "", config["cnpj"])
            if config.get("agencia"): EMPRESA_AGENCIA = str(config["agencia"]).zfill(5)
            if config.get("conta"):   EMPRESA_CONTA   = str(config["conta"]).zfill(12)
            if config.get("dac"):     EMPRESA_DAC     = str(config["dac"])
            if config.get("nome"):    EMPRESA_NOME    = str(config["nome"])[:30].upper()

        self._pagamentos_pix  = []   # PIX — arquivo separado
        self._pagamentos_ted  = []   # TED/DOC/CC — arquivo junto

    def adicionar(self, pagto: dict):
        """
        Adiciona um pagamento. O campo 'forma_pagto' determina o arquivo:
          'PIX'  → arquivo PIX (separado)
          'TED'  → TED outro titular
          'DOC'  → DOC C
          'CC'   → Crédito em conta Itaú
          'CC_MESMO' → Crédito mesma titularidade
        """
        forma_raw = str(pagto.get("forma_pgto", "PIX")).upper().strip()

        if forma_raw == "PIX":
            p = dict(pagto)
            p["_forma"] = FORMA_PIX
            self._pagamentos_pix.append(p)
        elif forma_raw in ("TED", "TED_OUTRO"):
            p = dict(pagto)
            p["_forma"] = FORMA_TED_OUTRO
            self._pagamentos_ted.append(p)
        elif forma_raw == "TED_MESMO":
            p = dict(pagto)
            p["_forma"] = FORMA_TED_MESMO
            self._pagamentos_ted.append(p)
        elif forma_raw == "DOC":
            p = dict(pagto)
            p["_forma"] = FORMA_DOC_C
            self._pagamentos_ted.append(p)
        elif forma_raw == "CC_MESMO":
            p = dict(pagto)
            p["_forma"] = FORMA_CC_MESMO
            self._pagamentos_ted.append(p)
        else:  # CC / default
            p = dict(pagto)
            p["_forma"] = FORMA_CC_ITAU
            self._pagamentos_ted.append(p)

    def _gerar_arquivo(self, pagamentos: list, sufixo: str, output_dir: Path) -> Path:
        """Gera um arquivo CNAB 240 com a lista de pagamentos."""
        linhas = []
        num_lote       = 0
        total_registros = 1  # header arquivo

        # Header arquivo
        linhas.append(header_arquivo())

        # Agrupa por forma de pagamento (cada forma = 1 lote)
        formas = {}
        for p in pagamentos:
            f = p["_forma"]
            formas.setdefault(f, []).append(p)

        for forma, grupo in formas.items():
            num_lote       += 1
            num_reg_lote    = 0
            valor_lote      = 0.0

            # Header lote
            linhas.append(header_lote(num_lote, forma))
            num_reg_lote   += 1
            total_registros += 1

            for pagto in grupo:
                num_reg_lote   += 1
                total_registros += 1
                valor_lote     += abs(float(pagto.get("valor", 0)))

                # Segmento A
                linhas.append(segmento_a(num_lote, num_reg_lote, pagto, forma))

                # Segmento B (obrigatório para PIX)
                if forma == FORMA_PIX:
                    num_reg_lote   += 1
                    total_registros += 1
                    linhas.append(segmento_b_pix(num_lote, num_reg_lote, pagto))

            # Trailer lote
            # qtd_registros = header + segmentos + trailer
            qtd_lote = num_reg_lote + 1  # +1 pelo trailer
            linhas.append(trailer_lote(num_lote, qtd_lote + 1, valor_lote))
            total_registros += 1

        # Trailer arquivo
        total_registros += 1
        linhas.append(trailer_arquivo(num_lote, total_registros))

        # Salva
        now      = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CNAB240_{sufixo}_{now}.rem"
        path     = output_dir / filename

        with open(path, "w", encoding="ascii", errors="replace") as f:
            f.write("\n".join(linhas) + "\n")

        return path

    def gerar(self, output_dir: Path | str = None) -> dict:
        """
        Gera os arquivos CNAB 240.
        Retorna dict: {"pix": Path|None, "ted_cc": Path|None}
        """
        if output_dir is None:
            output_dir = Path.home() / "Downloads"
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        resultado = {"pix": None, "ted_cc": None}

        if self._pagamentos_pix:
            resultado["pix"] = self._gerar_arquivo(
                self._pagamentos_pix, "PIX", output_dir)

        if self._pagamentos_ted:
            resultado["ted_cc"] = self._gerar_arquivo(
                self._pagamentos_ted, "TED_CC", output_dir)

        return resultado


# ── Mapeamento da planilha de despesas → pagamento CNAB ───────────────────────

def planilha_para_pagamentos(df, col_map: dict = None) -> list:
    """
    Converte DataFrame da planilha de despesas em lista de pagamentos CNAB.

    col_map: mapeamento de colunas (opcional)
      {
        "favorecido": "FAVORECIDO",
        "banco":      "BANCO",
        "agencia":    "AGÊNCIA",
        "conta":      "CONTA",
        "cpf_cnpj":   "PIX CHAVE",
        "valor":      "VALOR",
        "data":       "DATA PAGAMENTO",
        "forma_pgto": "FORMA PGTO",
        "pix_chave":  "PIX CHAVE",
      }
    """
    if col_map is None:
        col_map = {
            "favorecido": "FAVORECIDO",
            "banco":      "BANCO",
            "agencia":    "AGÊNCIA",
            "conta":      "CONTA",
            "cpf_cnpj":   "PIX CHAVE",
            "valor":      "VALOR",
            "data":       "DATA PAGAMENTO",
            "forma_pgto": "FORMA\nPGTO",
            "pix_chave":  "PIX CHAVE",
        }

    pagamentos = []
    for _, row in df.iterrows():
        def get(col_key, default=""):
            col = col_map.get(col_key, col_key)
            return str(row.get(col) or default).strip()

        cpf_cnpj_raw = get("cpf_cnpj")
        cpf_cnpj     = re.sub(r"\D", "", cpf_cnpj_raw)
        pix_chave    = get("pix_chave") or cpf_cnpj_raw

        # Detecta tipo de chave PIX
        if re.match(r"^\d{11}$", cpf_cnpj):
            tipo_chave = PIX_CHAVE_CPF
        elif re.match(r"^\d{14}$", cpf_cnpj):
            tipo_chave = PIX_CHAVE_CNPJ
        elif "@" in pix_chave:
            tipo_chave = PIX_CHAVE_EMAIL
        elif re.match(r"^\+?\d{10,13}$", re.sub(r"\D", "", pix_chave)):
            tipo_chave = PIX_CHAVE_CELULAR
        else:
            tipo_chave = PIX_CHAVE_EVP

        try:
            valor = abs(float(str(get("valor")).replace(",", ".").replace(".", "", 1 if "," in get("valor") else 0)))
        except Exception:
            valor = 0.0

        pagamento = {
            "nome":          get("favorecido")[:30],
            "banco_favorecido": re.sub(r"\D", "", get("banco")) or "000",
            "agencia":       re.sub(r"\D", "", get("agencia")),
            "conta":         re.sub(r"\D", "", get("conta")),
            "dac":           "0",
            "cpf_cnpj":      cpf_cnpj,
            "pix_chave":     pix_chave,
            "pix_tipo_chave": tipo_chave,
            "valor":         valor,
            "data":          get("data"),
            "forma_pgto":    get("forma_pgto", "PIX"),
            "finalidade":    "",
            "seu_numero":    "",
        }
        pagamentos.append(pagamento)

    return pagamentos