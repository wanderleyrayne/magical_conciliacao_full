"""
debug_cnab.py — Testa geracao CNAB e mostra posicoes exatas
Execute da raiz: python debug_cnab.py
"""
import sys
sys.path.insert(0, '.')
from core.cnab_itau import (
    segmento_b_pix, trailer_lote, GeradorCNAB240,
    FORMA_PIX, PIX_CHAVE_CPF, PIX_CHAVE_CNPJ,
    _normalizar_chave_pix
)

print("=== Teste Segmento B ===")
pagto = {
    "pix_tipo_chave": PIX_CHAVE_CPF,
    "pix_chave": "169.663.597-77",
    "cpf_cnpj":  "16966359777",
    "valor": 200.0,
}
seg = segmento_b_pix(1, 3, pagto)
print(f"Tamanho: {len(seg)} (deve ser 240)")
print(f"001-003: '{seg[0:3]}'   (deve ser 341)")
print(f"004-007: '{seg[3:7]}'   (deve ser 0001)")
print(f"008:     '{seg[7]}'     (deve ser 3)")
print(f"009-013: '{seg[8:13]}'  (deve ser 00003)")
print(f"014:     '{seg[13]}'    (deve ser B)")
print(f"015-016: '{seg[14:16]}' (deve ser 01 = CPF)")
print(f"017-076: '{seg[16:76]}' (chave PIX 60 chars)")
print(f"077-096: '{seg[76:96]}' (id transacao - brancos)")
print()

print("=== Teste Trailer Lote ===")
trl = trailer_lote(1, 19, 8921.67)
print(f"Tamanho: {len(trl)} (deve ser 240)")
print(f"018-023: '{trl[17:23]}' (qtd registros)")
print(f"024-038: '{trl[23:38]}' (valor total - deve ser 000000000892167)")
print()

print("=== Geracao completa ===")
config = {
    "cnpj":    "57344283000106",
    "agencia": "02971",
    "conta":   "000000098707",
    "dac":     "4",
    "nome":    "CONTEMPORANEO",
}
g = GeradorCNAB240(config)
pagamentos = [
    {"nome": "LUIZ HENRIQUE", "valor": 200.0, "data": "2026-05-12",
     "forma_pgto": "PIX", "pix_chave": "16966359777",
     "pix_tipo_chave": "01", "cpf_cnpj": "16966359777",
     "banco_favorecido": "341", "agencia": "", "conta": "", "dac": "0"},
    {"nome": "ANA PAULA", "valor": 1000.0, "data": "2026-05-12",
     "forma_pgto": "PIX", "pix_chave": "21964174203",
     "pix_tipo_chave": "04", "cpf_cnpj": "21964174203",
     "banco_favorecido": "341", "agencia": "", "conta": "", "dac": "0"},
]
for p in pagamentos:
    g.adicionar(p)

import tempfile, os
tmp = tempfile.mkdtemp()
arqs = g.gerar(output_dir=tmp)

if arqs.get("pix"):
    with open(arqs["pix"], encoding="ascii", errors="replace") as f:
        linhas = f.readlines()
    print(f"Linhas geradas: {len(linhas)}")
    for i, l in enumerate(linhas, 1):
        l = l.rstrip('\n')
        print(f"Linha {i:02d}: {l[:50]}...")
        if i == 1:
            print(f"  Header arquivo OK")
        elif l[7] == "5":
            print(f"  Trailer lote - valor: '{l[23:38]}'")
        elif l[13] == "B":
            print(f"  Seg B - tipo: '{l[14:16]}' chave: '{l[16:76].strip()}'")
else:
    print("ERRO: arquivo nao gerado!")