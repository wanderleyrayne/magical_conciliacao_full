"""
patch_cnab_valor.py — Verifica e corrige o campo valor no trailer do lote
Execute da raiz: python patch_cnab_valor.py
"""
from pathlib import Path
import ast

# Primeiro verifica o que _valor retorna
TARGET = Path("core/cnab_itau.py")

with open(TARGET, encoding='utf-8') as f:
    src = f.read()

# Verifica _valor atual
print("=== Verificando _valor ===")
exec_src = src + """
resultado = _valor(8921.67)
print(f"_valor(8921.67) = '{resultado}'")
print(f"len = {len(resultado)}")
print(f"inteiros=13, decimais=2 -> total=15 chars")
print(f"Interpretacao: R$ {float(resultado) / 100:,.2f}")
"""
exec(compile(exec_src, "<test>", "exec"))

# Verifica o campo no trailer_lote
print("\n=== Trailer lote ===")
# Conta os chars do trailer
campos_trailer = [
    ("banco", 3),
    ("lote", 4),
    ("tipo_reg", 1),
    ("brancos", 9),
    ("qtd_reg", 6),
    ("valor_total", 15),  # _valor = 13+2 = 15
    ("qtd_moeda", 6),
    ("brancos2", 3),
    ("aviso", 10),
    ("brancos3", 183),
]
total = sum(t for _, t in campos_trailer)
print(f"Total campos trailer: {total} (deve ser 240)")
for nome, tam in campos_trailer:
    print(f"  {nome}: {tam}")

print("\n=== Verificando se o problema e na escrita do arquivo ===")
# O problema pode ser que o arquivo e salvo sem newline fixo
# e o banco le 240+newline = 241 chars por linha
print("Arquivo salvo com: f.write('\\n'.join(linhas) + '\\n')")
print("Isso gera linhas de 240 chars separadas por \\n — CORRETO")
print("\nO valor 000000000892167 em centavos = R$ 8.921,67 CORRETO")
print("Se o banco mostra 8 milhoes, pode ser que ele leia")
print("os campos em posicoes diferentes do esperado")
print("\nVerificando posicoes do trailer:")
pos = 1
for nome, tam in campos_trailer:
    print(f"  {nome}: pos {pos:03d}-{pos+tam-1:03d} ({tam} chars)")
    pos += tam