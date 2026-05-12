"""
patch_cnab_filename.py — Corrige nome do arquivo CNAB para max 8 caracteres
Execute da raiz: python patch_cnab_filename.py
"""
from pathlib import Path
import ast

TARGET = Path("core/cnab_itau.py")

with open(TARGET, encoding='utf-8') as f:
    src = f.read()

old = '''        # Salva
        now      = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CNAB240_{sufixo}_{now}.rem"
        path     = output_dir / filename'''

new = '''        # Salva — nome maximo 8 chars sem extensao (exigencia Itau SISPAG)
        # Formato: IT + dia(2) + mes(2) + seg(2) = 8 chars  ex: IT120526.rem
        now      = datetime.now()
        filename = now.strftime("IT%d%m%S") + ".rem"
        path     = output_dir / filename
        if path.exists():
            filename = now.strftime("IT%d%m") + sufixo[0] + "S.rem"
            path     = output_dir / filename'''

if old not in src:
    print("ERRO: bloco nao encontrado em core/cnab_itau.py")
    print("Verifique se o arquivo nao foi modificado manualmente.")
    exit(1)

src = src.replace(old, new)
ast.parse(src)

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print("OK — nome do arquivo CNAB corrigido para 8 caracteres")
print("Exemplo: IT120526.rem")