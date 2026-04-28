PARTNERS = [
    {
        "partner_name": "CONTEMPORANEO",
        "cnpj": "57344283000106",
        "legal_name": "CONTEMPORANEO EVENTOS LTDA",
        "aliases": ["CONTEMPORANEO EVENTOS LTDA", "CONTEMPORANEO", "IF ESPACO CONTEMPORANEO", "if espaço contemporâneo"],
        "is_hub": 0,
    },
    {
        "partner_name": "ESPACO SER",
        "cnpj": "54016131000196",
        "legal_name": "MAGIC SER EVENTOS LTDA",
        "aliases": ["MAGIC SER EVENTOS LTDA", "ESPACO SER", "ESPAÇO SER", "MAGIC SER"],
        "is_hub": 0,
    },
    {
        "partner_name": "EVORA",
        "cnpj": "23883120000180",
        "legal_name": "EVORA FESTAS & EVENTOS LTDA",
        "aliases": ["EVORA FESTAS & EVENTOS LTDA", "EVORA FESTAS", "EVORA"],
        "is_hub": 0,
    },
    {
        "partner_name": "LAGO",
        "cnpj": "46851740000132",
        "legal_name": "LAGO ENFESTA LTDA",
        "aliases": ["LAGO ENFESTA LTDA", "LAGO ENFESTA", "LAGO"],
        "is_hub": 0,
    },
    {
        "partner_name": "CHALE",
        "cnpj": "41486103000190",
        "legal_name": "ENFESTA PRODUCOES LTDA",
        "aliases": ["ENFESTA PRODUCOES LTDA", "ENFESTA PRODUÇÕES LTDA", "CHALE", "CHALÉ", "ENFESTA PRODUCOES", "ENFESTA PRODUÇÕES"],
        "is_hub": 0,
    },
    {
        "partner_name": "CHATEAU",
        "cnpj": "62975315000101",
        "legal_name": "CHATEAU DO LAGO ENFESTA LTDA",
        "aliases": ["CHATEAU DO LAGO ENFESTA LTDA", "CHATEAU DO LAGO", "CHATEAU"],
        "is_hub": 0,
    },
    {
        "partner_name": "CASA DO LAGO",
        "cnpj": "60180505000107",
        "legal_name": "CASA DO LAGO ENFESTA LTDA",
        "aliases": ["CASA DO LAGO ENFESTA LTDA", "CASA DO LAGO"],
        "is_hub": 0,
    },
    {
        "partner_name": "VILLA FONTANA",
        "cnpj": "46395450000121",
        "legal_name": "VILLA FONTANA",
        "aliases": ["VILLA FONTANA"],
        "is_hub": 0,
    },
    {
        "partner_name": "OLEGARIO",
        "cnpj": "64114261000115",
        "legal_name": "ESPACO OLEGARIO ENFESTA LTDA",
        "aliases": ["ESPACO OLEGARIO ENFESTA LTDA", "ESPACO OLEGARIO", "ESPACO OLEGÁRIO", "OLEGARIO", "OLEGÁRIO"],
        "is_hub": 0,
    },
    {
        "partner_name": "MAGICAL",
        "cnpj": "46395450000121",
        "legal_name": "MAGICAL",
        "aliases": ["MAGICAL"],
        "is_hub": 1,
    },
]

# =============================================================================
# APORTADORES DO GRUPO
# Entidades conhecidas (sócios, holdings, empresas do grupo) que podem fazer
# aportes/empréstimos para qualquer parceiro em qualquer mês.
# Esses depósitos chegam no extrato bancário sem identificação de parceiro,
# e precisam ser atribuídos manualmente pelo usuário na tela de detalhe.
# O sistema usa esta lista apenas para EXIBIR o aviso "Aportador do grupo"
# na tela — a atribuição em si é sempre manual.
# =============================================================================
GROUP_CONTRIBUTORS = [
    {
        "label": "RICK ROCK DONUTS (sócio)",
        "cnpj": "48351731000108",
        "aliases": ["RICK ROCK DONUTS", "RICK DONUTS", "RICK RO"],
    },
    # Para adicionar outros aportadores no futuro, basta incluir aqui:
    # {
    #     "label": "HOLDING XYZ",
    #     "cnpj": "00000000000000",
    #     "aliases": ["HOLDING XYZ", "XYZ PARTICIPACOES"],
    # },
]