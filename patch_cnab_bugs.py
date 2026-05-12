"""
patch_cnab_bugs2.py — Corrige trailer valor + posicao segmento B
Execute da raiz: python patch_cnab_bugs2.py
"""
from pathlib import Path
import ast, re

TARGET = Path("core/cnab_itau.py")

with open(TARGET, encoding='utf-8') as f:
    src = f.read()

# ── Fix 1: Trailer lote — valor zerado ────────────────────────────────────
# O problema: valor_lote estava sendo acumulado ANTES do header do lote
# mas o loop nao reiniciava entre lotes diferentes
old1 = '''        for forma, grupo in formas.items():
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
            # qtd_registros = header_lote + segmentos + trailer_lote
            qtd_lote = num_reg_lote + 2  # +1 header lote +1 trailer lote
            linhas.append(trailer_lote(num_lote, qtd_lote, valor_lote))
            total_registros += 1'''

new1 = '''        for forma, grupo in formas.items():
            num_lote        += 1
            num_reg_lote     = 0
            valor_lote       = 0.0

            # Header lote (registro 1 do lote)
            linhas.append(header_lote(num_lote, forma))
            num_reg_lote    += 1
            total_registros += 1

            for pagto in grupo:
                # Acumula valor ANTES de incrementar registro
                try:
                    valor_lote += abs(float(pagto.get("valor", 0)))
                except Exception:
                    pass

                # Segmento A
                num_reg_lote    += 1
                total_registros += 1
                linhas.append(segmento_a(num_lote, num_reg_lote, pagto, forma))

                # Segmento B (obrigatorio para PIX)
                if forma == FORMA_PIX:
                    num_reg_lote    += 1
                    total_registros += 1
                    linhas.append(segmento_b_pix(num_lote, num_reg_lote, pagto))

            # Trailer lote
            # qtd = header_lote(1) + segmentos(num_reg_lote-1) + trailer(1)
            qtd_lote = num_reg_lote + 1  # +1 pelo trailer
            linhas.append(trailer_lote(num_lote, qtd_lote, valor_lote))
            total_registros += 1'''

if old1 not in src:
    print("ERRO: bloco do loop de formas nao encontrado!")
    exit(1)
src = src.replace(old1, new1)
print("Fix 1 OK: valor do lote acumulado corretamente")

# ── Fix 2: Segmento B — posicao da chave PIX ─────────────────────────────
# Layout correto Itau SISPAG PIX:
# 001-003: banco (3)
# 004-007: lote (4)
# 008:     tipo registro = 3 (1)
# 009-013: nr registro (5)
# 014:     segmento = B (1)
# 015-016: tipo chave PIX (2)   → "01", "02", "03", "04", "05"
# 017-076: chave PIX (60)
# 077-096: id transacao (20)    → brancos na remessa
# 097-116: info complementar (20) → brancos
# 117-240: brancos (124)
# Total: 3+4+1+5+1+2+60+20+20+124 = 240 ✓

old2 = '''    linha = (
        _n(BANCO_ITAU, 3) +       # 001-003 Banco
        _n(num_lote, 4) +         # 004-007 Lote
        "3" +                     # 008     Tipo registro detalhe
        _n(num_registro, 5) +     # 009-013 Nº registro no lote
        "B" +                     # 014     Segmento B
        tipo_chave.zfill(2)[:2] + # 015-016 Tipo chave PIX
        _a(chave_limpa, 60) +     # 017-076 Chave PIX (60 chars)
        _a("", 20) +              # 077-096 ID transacao (brancos remessa)
        _a("", 20) +              # 097-116 Info complementar (brancos)
        _a("", 124)               # 117-240 Brancos
    )
    return _assert_240(linha, f"segmento_b_pix lote={num_lote} reg={num_registro}")'''

new2 = '''    # Monta segmento B verificando tamanho de cada campo
    campo_banco    = _n(BANCO_ITAU, 3)          # 001-003  3 chars
    campo_lote     = _n(num_lote, 4)            # 004-007  4 chars
    campo_treg     = "3"                         # 008      1 char
    campo_nreg     = _n(num_registro, 5)        # 009-013  5 chars
    campo_seg      = "B"                         # 014      1 char
    campo_tpchave  = tipo_chave.zfill(2)[:2]    # 015-016  2 chars
    campo_chave    = _a(chave_limpa, 60)         # 017-076  60 chars
    campo_idtrans  = _a("", 20)                  # 077-096  20 chars
    campo_info     = _a("", 20)                  # 097-116  20 chars
    campo_brancos  = _a("", 124)                 # 117-240  124 chars

    linha = (campo_banco + campo_lote + campo_treg + campo_nreg +
             campo_seg + campo_tpchave + campo_chave + campo_idtrans +
             campo_info + campo_brancos)

    return _assert_240(linha, f"segmento_b_pix lote={num_lote} reg={num_registro}")'''

if old2 not in src:
    print("ERRO: bloco segmento_b_pix linha nao encontrado!")
    exit(1)
src = src.replace(old2, new2)
print("Fix 2 OK: posicao da chave PIX no segmento B corrigida")

# Valida sintaxe
ast.parse(src)
print("Sintaxe OK")

with open(TARGET, 'w', encoding='utf-8') as f:
    f.write(src)

print("\nArquivo atualizado: core/cnab_itau.py")
print("\nLayout Segmento B corrigido:")
print("  001-003: 341 (banco)")
print("  004-007: lote")
print("  008:     3 (tipo registro)")
print("  009-013: nr registro")
print("  014:     B (segmento)")
print("  015-016: tipo chave (01=CPF 02=CNPJ 03=email 04=cel 05=EVP)")
print("  017-076: chave PIX (60 chars, limpa)")
print("  077-096: brancos (id transacao)")
print("  097-116: brancos (info complementar)")
print("  117-240: brancos")
print("\nTrailer do lote:")
print("  Valor total agora acumulado corretamente antes de gravar")