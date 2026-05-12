"""
cnab_itau.py — Gerador CNAB 240 SISPAG Itau (versao 086)
Layout baseado no manual Itau CNAB 240 SISPAG PIX.
"""

from datetime import datetime, date
from pathlib import Path
import re

EMPRESA_CNPJ    = "00000000000000"
EMPRESA_AGENCIA = "00000"
EMPRESA_CONTA   = "000000000000"
EMPRESA_DAC     = "0"
EMPRESA_NOME    = "RAYNE TECNOLOGIA LTDA"
BANCO_ITAU      = "341"
BANCO_NOME      = "BANCO ITAU SA"

FORMA_PIX       = "45"
FORMA_TED_OUTRO = "41"
FORMA_TED_MESMO = "43"
FORMA_CC_ITAU   = "01"
FORMA_CC_MESMO  = "06"
FORMA_DOC_C     = "03"

TIPO_PAGTO_FORNEC   = "20"
TIPO_PAGTO_DIVERSOS = "98"

PIX_CHAVE_CPF     = "01"
PIX_CHAVE_CNPJ    = "02"
PIX_CHAVE_EMAIL   = "03"
PIX_CHAVE_CELULAR = "04"
PIX_CHAVE_EVP     = "05"


def _n(valor, tam):
    s = re.sub(r"\D", "", str(valor or ""))
    return s.zfill(tam)[:tam]

def _a(valor, tam):
    s = str(valor or "").upper().strip()
    return s.ljust(tam)[:tam]

def _cents(v, tam=18):
    try:
        c = round(abs(float(v)) * 100)
        return str(int(c)).zfill(tam)[:tam]
    except Exception:
        return "0" * tam

def _data(d):
    if isinstance(d, (datetime, date)):
        return d.strftime("%d%m%Y")
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(d).strip(), fmt).strftime("%d%m%Y")
        except Exception:
            pass
    return datetime.today().strftime("%d%m%Y")

def _assert_240(linha, campo=""):
    if len(linha) != 240:
        raise ValueError(f"Tamanho {len(linha)} != 240 [{campo}]\n{linha!r}")
    return linha


def _normalizar_chave_pix(chave, tipo):
    chave = str(chave or "").strip()
    tipo  = str(tipo or "04")
    if tipo == "01":
        return re.sub(r"\D", "", chave)[:11]
    elif tipo == "02":
        return re.sub(r"\D", "", chave)[:14]
    elif tipo == "03":
        return chave.lower()[:77]
    elif tipo == "04":
        digits = re.sub(r"\D", "", chave)
        if digits.startswith("55") and len(digits) > 11:
            digits = digits[2:]
        return f"+55{digits}"
    else:
        return chave[:36]


# ── Header Arquivo ────────────────────────────────────────────────────────────
def header_arquivo(seq=1):
    now = datetime.now()
    # 3+4+1+6+3+1+14+20+5+1+12+1+1+30+30+10+1+8+6+9+5+69 = 240
    l = (
        _n(BANCO_ITAU, 3)   +  # 001-003
        _n(0, 4)             +  # 004-007 lote=0000
        "0"                  +  # 008
        _a("", 6)            +  # 009-014
        _n(80, 3)            +  # 015-017 versao
        "2"                  +  # 018 CNPJ
        _n(EMPRESA_CNPJ, 14) +  # 019-032
        _a("", 20)           +  # 033-052
        _n(EMPRESA_AGENCIA,5)+  # 053-057
        " "                  +  # 058
        _n(EMPRESA_CONTA,12) +  # 059-070
        " "                  +  # 071
        _n(EMPRESA_DAC, 1)   +  # 072
        _a(EMPRESA_NOME, 30) +  # 073-102
        _a(BANCO_NOME, 30)   +  # 103-132
        _a("", 10)           +  # 133-142
        "1"                  +  # 143
        now.strftime("%d%m%Y") + # 144-151
        now.strftime("%H%M%S") + # 152-157
        _n(seq, 9)           +  # 158-166
        _n(0, 5)             +  # 167-171
        _a("", 69)              # 172-240
    )
    return _assert_240(l, "header_arquivo")


# ── Header Lote ───────────────────────────────────────────────────────────────
def header_lote(num_lote, forma_pagto, tipo_pagto=TIPO_PAGTO_FORNEC):
    # 3+4+1+1+2+2+3+1+1+14+4+16+5+1+12+1+1+30+30+10+30+5+15+20+8+2+8+10 = 240
    l = (
        _n(BANCO_ITAU, 3)    +  # 001-003
        _n(num_lote, 4)      +  # 004-007
        "1"                  +  # 008
        "C"                  +  # 009
        _n(tipo_pagto, 2)    +  # 010-011
        _n(forma_pagto, 2)   +  # 012-013
        _n(40, 3)            +  # 014-016 versao lote
        " "                  +  # 017
        "2"                  +  # 018
        _n(EMPRESA_CNPJ, 14) +  # 019-032
        _a("", 4)            +  # 033-036
        _a("", 16)           +  # 037-052
        _n(EMPRESA_AGENCIA,5)+  # 053-057
        " "                  +  # 058
        _n(EMPRESA_CONTA,12) +  # 059-070
        " "                  +  # 071
        _n(EMPRESA_DAC, 1)   +  # 072
        _a(EMPRESA_NOME, 30) +  # 073-102
        _a("", 30)           +  # 103-132
        _a("", 10)           +  # 133-142
        _a("", 30)           +  # 143-172
        _n(0, 5)             +  # 173-177
        _a("", 15)           +  # 178-192
        _a("", 20)           +  # 193-212
        _n(0, 8)             +  # 213-220
        _a("", 2)            +  # 221-222
        _a("", 8)            +  # 223-230
        _a("", 10)              # 231-240
    )
    return _assert_240(l, "header_lote")


# ── Segmento A ────────────────────────────────────────────────────────────────
def segmento_a(num_lote, num_reg, pagto, forma_pagto):
    banco_fav = str(pagto.get("banco_favorecido", "341")).strip().zfill(3)
    eh_pix    = forma_pagto == FORMA_PIX
    eh_itau   = banco_fav in ("341", "409")

    # Camara de compensacao (pos 018-020)
    if forma_pagto == FORMA_PIX:
        camara = "009"
    elif forma_pagto in (FORMA_TED_OUTRO, FORMA_TED_MESMO):
        camara = "018"
    elif forma_pagto == FORMA_DOC_C:
        camara = "700"
    else:
        camara = "000"

    # Agencia/conta favorecido (20 chars, pos 024-043)
    if eh_pix:
        ag_conta = _n(0, 20)
    elif eh_itau:
        ag_conta = ("0" + _n(pagto.get("agencia",""),4) + " " +
                    _n(0,6) + _n(pagto.get("conta",""),6) + " " +
                    _n(pagto.get("dac","0"),1))
    else:
        ag_conta = (_n(pagto.get("agencia",""),5) + " " +
                    _n(pagto.get("conta",""),12) + " " +
                    _n(pagto.get("dac","0"),1))

    tipo_chave = str(pagto.get("pix_tipo_chave","04")) if eh_pix else "  "

    # 3+4+1+5+1+3+3+3+20+30+20+8+3+8+2+5+15+15+5+8+15+20+6+14+2+5+5+1+10 = 240
    l = (
        _n(BANCO_ITAU, 3)                   +  # 001-003
        _n(num_lote, 4)                      +  # 004-007
        "3"                                  +  # 008
        _n(num_reg, 5)                       +  # 009-013
        "A"                                  +  # 014
        _n(0, 3)                             +  # 015-017 tipo movimento
        camara                               +  # 018-020 camara (3)
        _n(banco_fav, 3)                     +  # 021-023 banco fav
        ag_conta                             +  # 024-043 ag/conta (20)
        _a(pagto.get("nome",""), 30)         +  # 044-073 nome (30)
        _a(pagto.get("seu_numero",""), 20)   +  # 074-093 seu numero (20)
        _data(pagto.get("data",""))          +  # 094-101 data pgto (8)
        "REA"                                +  # 102-104 moeda (3)
        _n(0, 8)                             +  # 105-112 ISPB (8)
        tipo_chave[:2].ljust(2)              +  # 113-114 tipo chave (2)
        _n(0, 5)                             +  # 115-119 zeros (5)
        _cents(pagto.get("valor",0), 15)     +  # 120-134 valor (15)
        _a("", 15)                           +  # 135-149 nosso num (15)
        _a("", 5)                            +  # 150-154 brancos (5)
        _n(0, 8)                             +  # 155-162 data efetiva (8)
        _cents(0, 15)                        +  # 163-177 valor efetivo (15)
        _a(pagto.get("finalidade",""), 20)   +  # 178-197 finalidade (20)
        _n(0, 6)                             +  # 198-203 nr documento (6)
        _n(pagto.get("cpf_cnpj",""), 14)    +  # 204-217 cpf/cnpj (14)
        _a("", 2)                            +  # 218-219 finalidade doc (2)
        _a("", 5)                            +  # 220-224 finalidade ted (5)
        _a("", 5)                            +  # 225-229 brancos (5)
        "0"                                  +  # 230 aviso (1)
        _a("", 10)                              # 231-240 ocorrencias (10)
    )
    return _assert_240(l, f"segmento_a lote={num_lote} reg={num_reg}")


# ── Segmento B PIX ────────────────────────────────────────────────────────────
def segmento_b_pix(num_lote, num_reg, pagto):
    tipo_chave  = str(pagto.get("pix_tipo_chave","04"))
    chave_raw   = str(pagto.get("pix_chave","") or pagto.get("cpf_cnpj",""))
    chave_limpa = _normalizar_chave_pix(chave_raw, tipo_chave)

    # 3+4+1+5+1+2+60+20+20+124 = 240
    l = (
        _n(BANCO_ITAU, 3)           +  # 001-003
        _n(num_lote, 4)             +  # 004-007
        "3"                         +  # 008
        _n(num_reg, 5)              +  # 009-013
        "B"                         +  # 014
        tipo_chave.zfill(2)[:2]     +  # 015-016 tipo chave (2)
        _a(chave_limpa, 60)         +  # 017-076 chave PIX (60)
        _a("", 20)                  +  # 077-096 id transacao (20)
        _a("", 20)                  +  # 097-116 info complementar (20)
        _a("", 124)                    # 117-240 brancos (124)
    )
    return _assert_240(l, f"segmento_b lote={num_lote} reg={num_reg}")


# ── Trailer Lote ──────────────────────────────────────────────────────────────
def trailer_lote(num_lote, qtd_registros, valor_total):
    # Manual Itau SISPAG v086:
    # 001-003 banco (3)
    # 004-007 lote (4)
    # 008     tipo=5 (1)
    # 009-017 brancos (9)
    # 018-023 qtd registros (6)
    # 024-041 valor total em centavos (18)
    # 042-047 qtd moeda (6)
    # 048-057 nro aviso debito (10)
    # 058-240 brancos (183)
    # Total: 3+4+1+9+6+18+6+10+183 = 240
    cents = round(abs(float(valor_total)) * 100)
    valor_str = str(int(cents)).zfill(18)[:18]

    l = (
        _n(BANCO_ITAU, 3)      +  # 001-003 (3)
        _n(num_lote, 4)        +  # 004-007 (4)
        "5"                    +  # 008     (1)
        _a("", 9)              +  # 009-017 (9)
        _n(qtd_registros, 6)   +  # 018-023 (6)
        valor_str              +  # 024-041 (18)
        _n(0, 6)               +  # 042-047 (6)
        _n(0, 10)              +  # 048-057 (10)
        _a("", 183)               # 058-240 (183)
    )
    return _assert_240(l, f"trailer_lote {num_lote}")


# ── Trailer Arquivo ───────────────────────────────────────────────────────────
def trailer_arquivo(qtd_lotes, qtd_registros):
    # 3+4+1+9+6+6+6+205 = 240
    l = (
        _n(BANCO_ITAU, 3)      +  # 001-003
        _n(9999, 4)            +  # 004-007
        "9"                    +  # 008
        _a("", 9)              +  # 009-017
        _n(qtd_lotes, 6)       +  # 018-023
        _n(qtd_registros, 6)   +  # 024-029
        _n(0, 6)               +  # 030-035
        _a("", 205)               # 036-240
    )
    return _assert_240(l, "trailer_arquivo")


# ── Gerador Principal ─────────────────────────────────────────────────────────
class GeradorCNAB240:
    def __init__(self, config=None):
        cfg = config or {}
        self._cnpj    = re.sub(r"\D", "", str(cfg.get("cnpj", EMPRESA_CNPJ)))
        self._agencia = str(cfg.get("agencia", EMPRESA_AGENCIA)).zfill(5)
        self._conta   = str(cfg.get("conta", EMPRESA_CONTA)).zfill(12)
        self._dac     = str(cfg.get("dac", EMPRESA_DAC))
        self._nome    = str(cfg.get("nome", EMPRESA_NOME))[:30].upper()
        self._pagamentos_pix = []
        self._pagamentos_ted = []

    def adicionar(self, pagto):
        forma = str(pagto.get("forma_pgto","PIX")).upper().strip()
        p = dict(pagto)
        if forma == "PIX":
            p["_forma"] = FORMA_PIX
            self._pagamentos_pix.append(p)
        elif forma in ("TED","TED_OUTRO"):
            p["_forma"] = FORMA_TED_OUTRO
            self._pagamentos_ted.append(p)
        elif forma == "TED_MESMO":
            p["_forma"] = FORMA_TED_MESMO
            self._pagamentos_ted.append(p)
        elif forma == "DOC":
            p["_forma"] = FORMA_DOC_C
            self._pagamentos_ted.append(p)
        elif forma == "CC_MESMO":
            p["_forma"] = FORMA_CC_MESMO
            self._pagamentos_ted.append(p)
        else:
            p["_forma"] = FORMA_CC_ITAU
            self._pagamentos_ted.append(p)

    def _gerar_arquivo(self, pagamentos, sufixo, output_dir):
        global EMPRESA_CNPJ, EMPRESA_AGENCIA, EMPRESA_CONTA, EMPRESA_DAC, EMPRESA_NOME
        EMPRESA_CNPJ    = self._cnpj
        EMPRESA_AGENCIA = self._agencia
        EMPRESA_CONTA   = self._conta
        EMPRESA_DAC     = self._dac
        EMPRESA_NOME    = self._nome

        linhas = []
        num_lote        = 0
        total_registros = 1

        linhas.append(header_arquivo())

        formas = {}
        for p in pagamentos:
            formas.setdefault(p["_forma"], []).append(p)

        for forma, grupo in formas.items():
            num_lote        += 1
            num_reg_lote     = 0
            valor_lote       = 0.0

            linhas.append(header_lote(num_lote, forma))
            num_reg_lote    += 1
            total_registros += 1

            for pagto in grupo:
                try:
                    valor_lote += abs(float(pagto.get("valor", 0)))
                except Exception:
                    pass

                num_reg_lote    += 1
                total_registros += 1
                linhas.append(segmento_a(num_lote, num_reg_lote, pagto, forma))

                if forma == FORMA_PIX:
                    num_reg_lote    += 1
                    total_registros += 1
                    linhas.append(segmento_b_pix(num_lote, num_reg_lote, pagto))

            qtd_lote = num_reg_lote + 1
            linhas.append(trailer_lote(num_lote, qtd_lote, valor_lote))
            total_registros += 1

        total_registros += 1
        linhas.append(trailer_arquivo(num_lote, total_registros))

        now      = datetime.now()
        filename = now.strftime("IT%d%m%S") + ".rem"
        path     = output_dir / filename
        if path.exists():
            filename = now.strftime("IT%d%m") + sufixo[0] + "S.rem"
            path     = output_dir / filename

        with open(path, "w", encoding="ascii", errors="replace") as f:
            f.write("\n".join(linhas) + "\n")

        return path

    def gerar(self, output_dir=None):
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


def planilha_para_pagamentos(df, col_map=None):
    if col_map is None:
        col_map = {
            "favorecido": "FAVORECIDO", "banco": "BANCO",
            "agencia": "AGÊNCIA", "conta": "CONTA",
            "cpf_cnpj": "PIX CHAVE", "valor": "VALOR",
            "data": "DATA PAGAMENTO", "forma_pgto": "FORMA\nPGTO",
            "pix_chave": "PIX CHAVE",
        }
    pagamentos = []
    for _, row in df.iterrows():
        def get(k, d=""):
            return str(row.get(col_map.get(k,k)) or d).strip()
        cpf_cnpj_raw = get("cpf_cnpj")
        cpf_cnpj     = re.sub(r"\D", "", cpf_cnpj_raw)
        pix_chave    = get("pix_chave") or cpf_cnpj_raw
        if re.match(r"^\d{11}$", cpf_cnpj):
            tipo = PIX_CHAVE_CPF
        elif re.match(r"^\d{14}$", cpf_cnpj):
            tipo = PIX_CHAVE_CNPJ
        elif "@" in pix_chave:
            tipo = PIX_CHAVE_EMAIL
        elif re.match(r"^\+?\d{10,13}$", re.sub(r"\D","",pix_chave)):
            tipo = PIX_CHAVE_CELULAR
        else:
            tipo = PIX_CHAVE_EVP
        try:
            v = get("valor","0").replace(",",".").replace("R$","").strip()
            valor = abs(float(v))
        except Exception:
            valor = 0.0
        pagamentos.append({
            "nome": get("favorecido")[:30],
            "banco_favorecido": re.sub(r"\D","",get("banco")) or "000",
            "agencia": re.sub(r"\D","",get("agencia")),
            "conta": re.sub(r"\D","",get("conta")),
            "dac": "0", "cpf_cnpj": cpf_cnpj,
            "pix_chave": pix_chave, "pix_tipo_chave": tipo,
            "valor": valor, "data": get("data"),
            "forma_pgto": get("forma_pgto","PIX"),
            "finalidade": "", "seu_numero": "",
        })
    return pagamentos