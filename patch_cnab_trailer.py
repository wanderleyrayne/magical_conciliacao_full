"""
patch_cnab_trailer.py — Corrige tamanho do campo valor no trailer do lote
O manual Itau SISPAG define valor total como 18 digitos (pos 024-041)
Execute da raiz: python patch_cnab_trailer.py
"""
from pathlib import Path
import ast

TARGET = Path("core/cnab_itau.py")

with open(TARGET, encoding='utf-8') as f:
    src = f.read()

# Layout correto do trailer de lote conforme manual Itau SISPAG v086:
# 001-003  Banco (3)
# 004-007  Lote (4)
# 008      Tipo registro = 5 (1)
# 009-017  Brancos (9)
# 018-023  Qtd registros (6)
# 024-041  Valor total em centavos (18) ← campo de 18 chars!
# 042-047  Qtd moeda (6)
# 048-057  Nro aviso debito (10)
# 058-240  Brancos (183)
# Total: 3+4+1+9+6+18+6+10+183 = 240 ✓

old = '''def trailer_lote(num_lote: int, qtd_registros: int, valor_total: float) -> str:
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
    return _assert_240(linha, f"trailer_lote {num_lote}")'''

new = '''def trailer_lote(num_lote: int, qtd_registros: int, valor_total: float) -> str:
    """Trailer de Lote — Manual Itau SISPAG CNAB 240 v086."""
    # Valor em centavos com 18 digitos (pos 024-041)
    cents = round(abs(float(valor_total)) * 100)
    valor_str = str(int(cents)).zfill(18)[:18]

    linha = (
        _n(BANCO_ITAU, 3) +            # 001-003 Banco (3)
        _n(num_lote, 4) +              # 004-007 Lote (4)
        "5" +                          # 008     Tipo registro (1)
        _a("", 9) +                    # 009-017 Brancos (9)
        _n(qtd_registros, 6) +         # 018-023 Qtd registros (6)
        valor_str +                    # 024-041 Valor total centavos (18)
        _n(0, 6) +                     # 042-047 Qtd moeda (6)
        _n(0, 10) +                    # 048-057 Nro aviso debito (10)
        _a("", 183)                    # 058-240 Brancos (183)
    )
    return _assert_240(linha, f"trailer_lote {num_lote}")'''

if old not in src:
    print("ERRO: bloco trailer_lote nao encontrado!")
    exit(1)

src = src.replace(old, new)
ast.parse(src)

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

# Verifica resultado
cents = round(abs(8921.67) * 100)
valor_str = str(int(cents)).zfill(18)[:18]
print(f"Valor R$ 8.921,67 -> '{valor_str}' ({len(valor_str)} chars)")
print(f"Posicoes 024-041: correto conforme manual Itau SISPAG")
print(f"\nArquivo atualizado: {TARGET}")