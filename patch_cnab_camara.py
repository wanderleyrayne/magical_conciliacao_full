"""
patch_cnab_camara.py — Corrige camara de compensacao no Segmento A para PIX
Execute da raiz: python patch_cnab_camara.py
"""
from pathlib import Path
import ast

TARGET = Path("core/cnab_itau.py")

with open(TARGET, encoding='utf-8') as f:
    src = f.read()

# Fix: camara deve ser 009 para PIX, 018 para TED, 700 para DOC
old = '''    # Câmara + ISPB (pos 018-020 / 105-112)
    camara = "000"
    ispb   = _n(0, 8)'''

new = '''    # Câmara de compensacao (pos 018-020)
    # 009 = PIX, 018 = TED (STR), 700 = DOC (CIP), 000 = CC mesmo banco
    if forma_pagto == FORMA_PIX:
        camara = "009"
    elif forma_pagto in (FORMA_TED_OUTRO, FORMA_TED_MESMO):
        camara = "018"
    elif forma_pagto == FORMA_DOC_C:
        camara = "700"
    else:
        camara = "000"
    ispb = _n(0, 8)'''

if old not in src:
    print("ERRO: bloco camara nao encontrado!")
    exit(1)

src = src.replace(old, new)

import ast as _ast
_ast.parse(src)
print("Fix OK: camara PIX=009, TED=018, DOC=700, CC=000")

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print(f"\nArquivo atualizado: {TARGET}")
print("\nAgora o Segmento A fica:")
print("  PIX: ...3A000 009 341...")
print("              ↑↑↑")
print("           camara=009 (PIX Itau)")