"""
patch_cnab_pix.py — Corrige formatacao das chaves PIX no CNAB 240
Execute da raiz: python patch_cnab_pix.py
"""
from pathlib import Path
import ast

TARGET = Path("core/cnab_itau.py")

with open(TARGET, encoding='utf-8') as f:
    src = f.read()

# Fix 1: limpar chave PIX antes de gravar no segmento B
old = '''def segmento_b_pix(num_lote: int, num_registro: int, pagto: dict) -> str:
    """
    Segmento B — obrigatório para PIX.
    pagto deve ter: pix_chave, pix_tipo_chave, cpf_cnpj
    """
    tipo_inscr = "2" if len(re.sub(r"\\D", "", str(pagto.get("cpf_cnpj", "")))) == 14 else "1"

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
    return _assert_240(linha, f"segmento_b_pix lote={num_lote} reg={num_registro}")'''

new = '''def _normalizar_chave_pix(chave: str, tipo: str) -> str:
    """
    Normaliza chave PIX conforme tipo — remove formatacao.
    Itau SISPAG exige chave sem pontuacao.

    Tipos:
      01 = CPF       -> apenas digitos (11)
      02 = CNPJ      -> apenas digitos (14)
      03 = Email     -> lowercase sem espacos
      04 = Celular   -> +55 + DDD + numero (13 chars)
      05 = EVP/aleat -> UUID sem alteracao
    """
    chave = str(chave or "").strip()
    tipo  = str(tipo or "04")

    if tipo == "01":  # CPF
        return re.sub(r"\\D", "", chave)[:11]

    elif tipo == "02":  # CNPJ
        return re.sub(r"\\D", "", chave)[:14]

    elif tipo == "03":  # Email
        return chave.lower()[:77]

    elif tipo == "04":  # Celular
        digits = re.sub(r"\\D", "", chave)
        # Remove 55 do inicio se ja tiver
        if digits.startswith("55") and len(digits) > 11:
            digits = digits[2:]
        # Garante DDD + 9 digitos
        if len(digits) == 11:
            return f"+55{digits}"
        elif len(digits) == 10:
            return f"+55{digits}"
        else:
            return f"+55{digits}"

    else:  # EVP / chave aleatoria
        return chave[:36]


def segmento_b_pix(num_lote: int, num_registro: int, pagto: dict) -> str:
    """
    Segmento B — obrigatório para PIX.
    pagto deve ter: pix_chave, pix_tipo_chave, cpf_cnpj
    """
    cpf_cnpj_digits = re.sub(r"\\D", "", str(pagto.get("cpf_cnpj", "")))
    tipo_inscr = "2" if len(cpf_cnpj_digits) == 14 else "1"

    tipo_chave  = str(pagto.get("pix_tipo_chave", "04"))
    chave_raw   = str(pagto.get("pix_chave", "") or pagto.get("cpf_cnpj", ""))
    chave_limpa = _normalizar_chave_pix(chave_raw, tipo_chave)

    linha = (
        _n(BANCO_ITAU, 3) +            # 001-003 Banco
        _n(num_lote, 4) +              # 004-007 Lote
        "3" +                          # 008     Tipo registro
        _n(num_registro, 5) +          # 009-013 Mesmo nº do segmento A
        "B" +                          # 014     Segmento B
        _a(tipo_chave, 2) +            # 015-016 Tipo chave PIX
        _a("", 1) +                    # 017     Branco
        tipo_inscr +                   # 018     Tipo inscrição
        _n(cpf_cnpj_digits, 14) +      # 019-032 CPF/CNPJ (so digitos)
        _a("", 30) +                   # 033-062 Endereço (brancos)
        _n(0, 5) +                     # 063-067 Número (zeros)
        _a("", 15) +                   # 068-082 Complemento
        _a("", 15) +                   # 083-097 Bairro
        _a("", 20) +                   # 098-117 Cidade
        _n(0, 8) +                     # 118-125 CEP
        _a("", 2) +                    # 126-127 Estado
        _a(chave_limpa, 100) +         # 128-227 Chave PIX normalizada
        _a("", 3) +                    # 228-230 Brancos
        _a("", 10)                     # 231-240 Ocorrências
    )
    return _assert_240(linha, f"segmento_b_pix lote={num_lote} reg={num_registro}")'''

if old not in src:
    print("ERRO: bloco segmento_b_pix nao encontrado!")
    exit(1)

src = src.replace(old, new)
ast.parse(src)

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print("OK — chaves PIX normalizadas:")
print("  CPF:     so digitos       ex: 16966359777")
print("  CNPJ:    so digitos       ex: 20616052000102")
print("  Celular: +55DDNUMERO      ex: +5521964174203")
print("  Email:   lowercase        ex: fulano@gmail.com")
print("  EVP:     UUID sem alterar")