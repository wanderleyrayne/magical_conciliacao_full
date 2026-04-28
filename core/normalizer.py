import re
import unicodedata
import pandas as pd


class Normalizer:
    EXTRATO_DESCRICOES_IGNORAR = [
        "SALDO ANTERIOR",
        "SALDO TOTAL DISPONIVEL DIA",
        "SALDO MOVIMENTACAO CONTA",
        "SALDO APLIC. AUT.",
        "SALDO APLIC AUT",
        "SDO APLIC AUT MAIS AP",
        "APL APLIC AUT MAIS",
        "APL APLIC AUT MAIS AP",
        "RES APLIC AUT MAIS",
        "RENDIMENTOS REND PAGO APLIC AUT MAIS",
    ]

    @staticmethod
    def mapear_colunas(df: pd.DataFrame):
        mapa = {}
        for col in df.columns:
            chave = Normalizer._normalize_header(col)
            mapa[chave] = col
        return mapa

    @staticmethod
    def obter_coluna(mapa, candidatos, obrigatoria=True, contexto="Arquivo"):
        candidatos_norm = [Normalizer._normalize_header(c) for c in candidatos]

        for candidato in candidatos_norm:
            if candidato in mapa:
                return mapa[candidato]

        # tentativa parcial
        for candidato in candidatos_norm:
            for col_norm, col_real in mapa.items():
                if candidato == col_norm:
                    return col_real
                if candidato in col_norm:
                    return col_real
                if col_norm in candidato:
                    return col_real

        if obrigatoria:
            raise ValueError(
                f"Coluna obrigatória não encontrada em {contexto}: "
                + " / ".join(candidatos)
            )
        return None

    @staticmethod
    def _normalize_header(text):
        text = str(text or "").strip()
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = text.upper()
        text = re.sub(r"[\n\r\t]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def limpar_texto(value):
        if value is None:
            return ""
        if pd.isna(value):
            return ""

        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""

        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = text.upper()
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def limpar_documento(value):
        if value is None or pd.isna(value):
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""
        return re.sub(r"\D+", "", text)

    @staticmethod
    def converter_data(value):
        if value is None or pd.isna(value):
            return pd.NaT

        try:
            dt = pd.to_datetime(value, errors="coerce", dayfirst=True)
            return dt
        except Exception:
            return pd.NaT

    @staticmethod
    def converter_valor(value):
        if value is None or pd.isna(value):
            return 0.0

        if isinstance(value, (int, float)):
            try:
                return float(value)
            except Exception:
                return 0.0

        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none", ""}:
            return 0.0

        # remove moeda e espaços
        text = text.replace("R$", "").replace("RS", "").replace(" ", "")

        # formato BR com ponto milhar e vírgula decimal
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")

        # remove caracteres indevidos, preservando sinal e ponto
        text = re.sub(r"[^0-9\.\-]", "", text)

        try:
            return float(text)
        except Exception:
            return 0.0

    @staticmethod
    def deve_ignorar_lancamento_extrato(descricao):
        descricao = Normalizer.limpar_texto(descricao)

        if not descricao:
            return True

        for termo in Normalizer.EXTRATO_DESCRICOES_IGNORAR:
            if termo in descricao:
                return True

        return False

    @staticmethod
    def _categoria_extrato(descricao):
        descricao = Normalizer.limpar_texto(descricao)

        palavras_tarifa = [
            "TARIFA",
            "CESTA",
            "PACOTE",
            "MANUTENCAO",
            "SERVICO BANCARIO",
            "IOF",
            "JUROS",
            "ENCARGOS",
        ]

        for palavra in palavras_tarifa:
            if palavra in descricao:
                return "TARIFA_BANCARIA"

        return ""

    @staticmethod
    def normalizar_extrato(df):
        df = df.copy()
        mapa = Normalizer.mapear_colunas(df)

        col_data = Normalizer.obter_coluna(
            mapa,
            ["DATA"],
            contexto="Extrato bancário"
        )

        col_desc = Normalizer.obter_coluna(
            mapa,
            ["LANCAMENTO", "HISTORICO", "DESCRICAO", "DESCRIÇÃO"],
            contexto="Extrato bancário"
        )

        col_razao = Normalizer.obter_coluna(
            mapa,
            ["RAZAO SOCIAL", "FAVORECIDO", "NOME"],
            obrigatoria=False,
            contexto="Extrato bancário"
        )

        col_doc = Normalizer.obter_coluna(
            mapa,
            ["CPF/CNPJ", "CPF CNPJ", "DOCUMENTO"],
            obrigatoria=False,
            contexto="Extrato bancário"
        )

        col_valor = Normalizer.obter_coluna(
            mapa,
            ["VALOR (R$)", "VALOR (RS)", "VALOR", "VALOR R$"],
            contexto="Extrato bancário"
        )

        df_normalizado = pd.DataFrame()
        df_normalizado["data"] = df[col_data].apply(Normalizer.converter_data)
        df_normalizado["descricao"] = df[col_desc].apply(Normalizer.limpar_texto)
        df_normalizado["favorecido"] = df[col_razao].apply(Normalizer.limpar_texto) if col_razao else ""
        df_normalizado["documento"] = df[col_doc].apply(Normalizer.limpar_documento) if col_doc else ""
        df_normalizado["valor"] = df[col_valor].apply(Normalizer.converter_valor)
        df_normalizado["forma_pagamento"] = ""
        df_normalizado["pago"] = ""
        df_normalizado["categoria"] = df_normalizado["descricao"].apply(Normalizer._categoria_extrato)

        df_normalizado = df_normalizado[df_normalizado["descricao"] != ""]
        df_normalizado = df_normalizado[df_normalizado["data"].notna()]
        df_normalizado = df_normalizado[
            ~df_normalizado["descricao"].apply(Normalizer.deve_ignorar_lancamento_extrato)
        ]
        df_normalizado = df_normalizado[df_normalizado["valor"] != 0]

        df_normalizado["tipo"] = df_normalizado["valor"].apply(
            lambda x: "ENTRADA" if x > 0 else "SAIDA"
        )

        df_normalizado = df_normalizado.reset_index(drop=True)
        return df_normalizado

    @staticmethod
    def normalizar_erp_despesas(df):
        df = df.copy()
        mapa = Normalizer.mapear_colunas(df)

        col_data = Normalizer.obter_coluna(
            mapa,
            ["DATA PAGAMENTO", "DATA", "DATA BAIXA"],
            contexto="ERP despesas"
        )
        col_desc = Normalizer.obter_coluna(
            mapa,
            ["DESCRICAO", "DESCRIÇÃO", "HISTORICO", "HISTÓRICO"],
            contexto="ERP despesas"
        )
        col_valor = Normalizer.obter_coluna(
            mapa,
            ["VALOR", "VALOR FINAL", "VALOR TOTAL"],
            contexto="ERP despesas"
        )
        col_forma = Normalizer.obter_coluna(
            mapa,
            ["FORMA PAGAMENTO", "FORMA DE PAGAMENTO"],
            obrigatoria=False,
            contexto="ERP despesas"
        )
        col_pago = Normalizer.obter_coluna(
            mapa,
            ["PAGO", "STATUS"],
            obrigatoria=False,
            contexto="ERP despesas"
        )

        out = pd.DataFrame()
        out["data"] = df[col_data].apply(Normalizer.converter_data)
        out["descricao"] = df[col_desc].apply(Normalizer.limpar_texto)
        out["valor"] = df[col_valor].apply(Normalizer.converter_valor).abs()
        out["forma_pagamento"] = df[col_forma].apply(Normalizer.limpar_texto) if col_forma else ""
        out["pago"] = df[col_pago].apply(Normalizer.limpar_texto) if col_pago else ""
        out["favorecido"] = ""
        out["documento"] = ""
        out["categoria"] = ""
        out["tipo"] = "SAIDA"

        out = out[out["data"].notna()]
        out = out[out["descricao"] != ""]
        out = out[out["valor"] != 0]
        out = out.reset_index(drop=True)

        return out

    @staticmethod
    def normalizar_erp_receitas(df):
        df = df.copy()
        mapa = Normalizer.mapear_colunas(df)

        col_data = Normalizer.obter_coluna(
            mapa,
            ["DATA PAGAMENTO", "DATA", "DATA BAIXA", "DATA RECEBIMENTO"],
            contexto="ERP receitas"
        )
        col_desc = Normalizer.obter_coluna(
            mapa,
            ["DESCRICAO", "DESCRIÇÃO", "HISTORICO", "HISTÓRICO"],
            contexto="ERP receitas"
        )
        col_valor = Normalizer.obter_coluna(
            mapa,
            ["VALOR", "VALOR FINAL", "VALOR TOTAL"],
            contexto="ERP receitas"
        )
        col_forma = Normalizer.obter_coluna(
            mapa,
            ["FORMA PAGAMENTO", "FORMA DE PAGAMENTO"],
            obrigatoria=False,
            contexto="ERP receitas"
        )
        col_pago = Normalizer.obter_coluna(
            mapa,
            ["PAGO", "STATUS"],
            obrigatoria=False,
            contexto="ERP receitas"
        )

        out = pd.DataFrame()
        out["data"] = df[col_data].apply(Normalizer.converter_data)
        out["descricao"] = df[col_desc].apply(Normalizer.limpar_texto)
        out["valor"] = df[col_valor].apply(Normalizer.converter_valor).abs()
        out["forma_pagamento"] = df[col_forma].apply(Normalizer.limpar_texto) if col_forma else ""
        out["pago"] = df[col_pago].apply(Normalizer.limpar_texto) if col_pago else ""
        out["favorecido"] = ""
        out["documento"] = ""
        out["categoria"] = ""
        out["tipo"] = "ENTRADA"

        out = out[out["data"].notna()]
        out = out[out["descricao"] != ""]
        out = out[out["valor"] != 0]
        out = out.reset_index(drop=True)

        return out

    @staticmethod
    def normalizar_erp_consolidado(df):
        df = df.copy()
        mapa = Normalizer.mapear_colunas(df)

        col_data = Normalizer.obter_coluna(
            mapa,
            ["DATA PAGAMENTO", "DATA", "DATA BAIXA", "DATA MOVIMENTO"],
            contexto="ERP consolidado"
        )

        col_desc = Normalizer.obter_coluna(
            mapa,
            ["DESCRICAO", "DESCRIÇÃO", "HISTORICO", "HISTÓRICO"],
            obrigatoria=False,
            contexto="ERP consolidado"
        )

        col_razao = Normalizer.obter_coluna(
            mapa,
            ["RAZAO SOCIAL", "RAZÃO SOCIAL", "CLIENTE", "FORNECEDOR", "PARCEIRO", "NOME"],
            obrigatoria=False,
            contexto="ERP consolidado"
        )

        col_categoria = Normalizer.obter_coluna(
            mapa,
            ["CATEGORIA", "CLASSIFICACAO", "CLASSIFICAÇÃO"],
            obrigatoria=False,
            contexto="ERP consolidado"
        )

        col_valor = Normalizer.obter_coluna(
            mapa,
            ["VALOR", "VALOR FINAL", "VALOR TOTAL"],
            contexto="ERP consolidado"
        )

        col_tipo = Normalizer.obter_coluna(
            mapa,
            ["TIPO", "TIPO MOVIMENTO", "NATUREZA", "ENTRADA/SAIDA", "ENTRADA-SAIDA"],
            obrigatoria=False,
            contexto="ERP consolidado"
        )

        col_forma = Normalizer.obter_coluna(
            mapa,
            ["FORMA PAGAMENTO", "FORMA DE PAGAMENTO", "FORMA DE PG.", "FORMA PG"],
            obrigatoria=False,
            contexto="ERP consolidado"
        )

        col_pago = Normalizer.obter_coluna(
            mapa,
            ["PAGO", "STATUS"],
            obrigatoria=False,
            contexto="ERP consolidado"
        )

        df_normalizado = pd.DataFrame()
        df_normalizado["data"] = df[col_data].apply(Normalizer.converter_data)
        df_normalizado["valor"] = df[col_valor].apply(Normalizer.converter_valor)
        df_normalizado["forma_pagamento"] = df[col_forma].apply(Normalizer.limpar_texto) if col_forma else ""
        df_normalizado["pago"] = df[col_pago].apply(Normalizer.limpar_texto) if col_pago else ""
        df_normalizado["categoria"] = df[col_categoria].apply(Normalizer.limpar_texto) if col_categoria else ""

        # Favorecido / parceiro / cliente
        df_normalizado["favorecido"] = df[col_razao].apply(Normalizer.limpar_texto) if col_razao else ""

        # Descrição principal
        if col_desc:
            df_normalizado["descricao"] = df[col_desc].apply(Normalizer.limpar_texto)
        else:
            df_normalizado["descricao"] = ""

        # Se descrição vier vazia, usa o favorecido
        df_normalizado.loc[
            df_normalizado["descricao"] == "",
            "descricao"
        ] = df_normalizado["favorecido"]

        # Se ainda estiver vazia, usa categoria
        df_normalizado.loc[
            (df_normalizado["descricao"] == "") & (df_normalizado["categoria"] != ""),
            "descricao"
        ] = df_normalizado["categoria"]

        # Se houver favorecido e categoria, monta uma descrição mais rica
        mask_compose = (
            (df_normalizado["favorecido"] != "") &
            (df_normalizado["categoria"] != "")
        )

        df_normalizado.loc[mask_compose, "descricao"] = (
            df_normalizado.loc[mask_compose, "favorecido"] + " " +
            df_normalizado.loc[mask_compose, "categoria"]
        )

        # Documento não costuma vir forte nesse arquivo
        df_normalizado["documento"] = ""

        if col_tipo:
            def inferir_tipo_por_coluna(v):
                txt = Normalizer.limpar_texto(v)
                if txt in {"ENTRADA", "RECEITA", "CREDITO", "CRÉDITO"}:
                    return "ENTRADA"
                if txt in {"SAIDA", "SAÍDA", "DESPESA", "DEBITO", "DÉBITO"}:
                    return "SAIDA"
                return None

            df_normalizado["tipo"] = df[col_tipo].apply(inferir_tipo_por_coluna)
        else:
            df_normalizado["tipo"] = None

        # fallback pelo sinal do valor
        df_normalizado.loc[
            df_normalizado["tipo"].isna() & (df_normalizado["valor"] > 0),
            "tipo"
        ] = "ENTRADA"

        df_normalizado.loc[
            df_normalizado["tipo"].isna() & (df_normalizado["valor"] < 0),
            "tipo"
        ] = "SAIDA"

        # fallback pela descrição
        def inferir_tipo_por_descricao(desc):
            desc = Normalizer.limpar_texto(desc)

            palavras_entrada = [
                "RECEBIMENTO", "RECEITA", "ENTRADA", "CREDITO", "CRÉDITO"
            ]
            palavras_saida = [
                "PAGAMENTO", "DESPESA", "SAIDA", "SAÍDA", "PIX ENVIADO", "BOLETO"
            ]

            for p in palavras_entrada:
                if p in desc:
                    return "ENTRADA"

            for p in palavras_saida:
                if p in desc:
                    return "SAIDA"

            return ""

        df_normalizado.loc[
            df_normalizado["tipo"].isna(),
            "tipo"
        ] = df_normalizado.loc[
            df_normalizado["tipo"].isna(),
            "descricao"
        ].apply(inferir_tipo_por_descricao)

        df_normalizado = df_normalizado[df_normalizado["data"].notna()]
        df_normalizado = df_normalizado[df_normalizado["descricao"] != ""]
        df_normalizado = df_normalizado[df_normalizado["valor"] != 0]
        df_normalizado = df_normalizado[df_normalizado["tipo"].isin(["ENTRADA", "SAIDA"])]

        # No ERP trabalhamos com valor positivo e tipo separado
        df_normalizado["valor"] = df_normalizado["valor"].abs()

        df_normalizado = df_normalizado.reset_index(drop=True)
        return df_normalizado

    @staticmethod
    def normalizar_base_entidades(df):
        df = df.copy()
        mapa = Normalizer.mapear_colunas(df)

        col_doc = Normalizer.obter_coluna(
            mapa,
            ["CPF CNPJ", "CPF/CNPJ", "DOCUMENTO"],
            contexto="Base de entidades"
        )
        col_razao = Normalizer.obter_coluna(
            mapa,
            ["RAZAO SOCIAL", "RAZÃO SOCIAL", "NOME", "FAVORECIDO"],
            contexto="Base de entidades"
        )
        col_short = Normalizer.obter_coluna(
            mapa,
            ["RAZAO SOCIAL SHORT", "RAZÃO SOCIAL SHORT", "NOME FANTASIA", "SHORT", "APELIDO"],
            obrigatoria=False,
            contexto="Base de entidades"
        )
        col_cargo = Normalizer.obter_coluna(
            mapa,
            ["CARGO OCUPACAO", "CARGO/OCUPACAO", "CARGO OCUPAÇÃO", "TIPO", "CATEGORIA"],
            obrigatoria=False,
            contexto="Base de entidades"
        )

        out = pd.DataFrame()
        out["documento"] = df[col_doc].apply(Normalizer.limpar_documento)
        out["razao_social"] = df[col_razao].apply(Normalizer.limpar_texto)
        out["razao_social_short"] = df[col_short].apply(Normalizer.limpar_texto) if col_short else ""
        out["categoria"] = df[col_cargo].apply(Normalizer.limpar_texto) if col_cargo else ""

        out["nome_busca"] = out["razao_social_short"]
        out.loc[out["nome_busca"] == "", "nome_busca"] = out["razao_social"]

        out["nome_resumido"] = out["razao_social"].apply(
            lambda x: " ".join(str(x).split()[:3]) if str(x).strip() else ""
        )

        out = out[(out["documento"] != "") | (out["razao_social"] != "")]
        out = out.drop_duplicates().reset_index(drop=True)

        return out