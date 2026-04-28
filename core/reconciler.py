import pandas as pd
from rapidfuzz import fuzz


class Reconciler:
    # Valor padrão usado quando a tolerância não é injetada externamente.
    # Em produção, main_window.py lê do banco via SettingsManager e passa
    # date_tolerance_days para conciliar_despesas / conciliar_receitas.
    DATE_TOLERANCE_DAYS = 3
    TEXT_SIMILARITY_THRESHOLD = 0.25

    # =============================
    # HELPERS
    # =============================

    @staticmethod
    def _safe_text(value):
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""
        return text.upper()

    @staticmethod
    def _safe_date(value):
        try:
            dt = pd.to_datetime(value, errors="coerce")
            return dt if pd.notna(dt) else pd.NaT
        except Exception:
            return pd.NaT

    @staticmethod
    def _safe_float(value):
        try:
            if value is None or pd.isna(value):
                return 0.0
            return float(value)
        except Exception:
            return 0.0

    @staticmethod
    def _normalize_money(value):
        return round(abs(Reconciler._safe_float(value)), 2)

    @staticmethod
    def _days_diff(d1, d2):
        d1 = Reconciler._safe_date(d1)
        d2 = Reconciler._safe_date(d2)
        if pd.isna(d1) or pd.isna(d2):
            return None
        return abs((d1.date() - d2.date()).days)

    @staticmethod
    def _same_value(v1, v2, tolerance=0.01):
        return abs(Reconciler._normalize_money(v1) - Reconciler._normalize_money(v2)) <= tolerance

    @staticmethod
    def _similarity(a, b):
        a = Reconciler._safe_text(a)
        b = Reconciler._safe_text(b)
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        if a in b or b in a:
            return 0.92
        return fuzz.ratio(a, b) / 100.0

    @staticmethod
    def _build_text(row):
        parts = [
            Reconciler._safe_text(row.get("descricao")),
            Reconciler._safe_text(row.get("favorecido")),
            Reconciler._safe_text(row.get("categoria")),
        ]
        return " ".join([p for p in parts if p])

    @staticmethod
    def _clean_doc(value):
        return "".join(ch for ch in str(value or "") if ch.isdigit())

    @staticmethod
    def _normalize_text(value):
        return " ".join(Reconciler._safe_text(value).split())

    # =============================
    # FIND BEST MATCH
    # =============================

    @staticmethod
    def _find_best_match(candidatos: pd.DataFrame, row_erp, date_tolerance: int) -> tuple:
        """
        Dentre os candidatos com mesmo valor, escolhe o com menor diferença
        de dias em relação à data do ERP, respeitando date_tolerance como limite.
        Retorna (index, diff_days) ou (None, None).
        """
        if candidatos.empty:
            return None, None

        data_erp = Reconciler._safe_date(row_erp.get("data"))

        best_idx  = None
        best_days = None

        for idx, row_banco in candidatos.iterrows():
            diff = Reconciler._days_diff(data_erp, row_banco.get("data"))

            if diff is None:
                if best_idx is None:
                    best_idx  = idx
                    best_days = None
                continue

            if diff > date_tolerance:
                continue

            if best_days is None or diff < best_days:
                best_idx  = idx
                best_days = diff

        return best_idx, best_days

    # =============================
    # CLASSIFICAÇÃO DE ENTIDADE  (agora com índice CNPJ → O(1) no caso comum)
    # =============================

    @staticmethod
    def _build_entity_index(df_entidades: pd.DataFrame) -> dict:
        """
        Pré-compila um dicionário {cnpj_limpo: row} para match exato por documento
        em O(1). Chamado uma única vez por execução de conciliação.
        """
        if df_entidades is None or df_entidades.empty:
            return {}
        index = {}
        for _, ent in df_entidades.iterrows():
            doc = Reconciler._clean_doc(ent.get("documento", ""))
            if doc and doc not in index:
                index[doc] = ent
        return index

    @staticmethod
    def _classify_entity(row_banco, df_entidades, entity_index: dict = None):
        if df_entidades is None or df_entidades.empty:
            return "", ""

        documento_banco  = Reconciler._clean_doc(row_banco.get("documento"))
        descricao_banco  = Reconciler._normalize_text(row_banco.get("descricao"))
        favorecido_banco = Reconciler._normalize_text(row_banco.get("favorecido"))
        banco_text       = " ".join([t for t in [descricao_banco, favorecido_banco] if t]).strip()

        def _build_result(ent):
            """Monta (entidade, categoria) enriquecido com cargo_ocupacao se disponível."""
            nome = Reconciler._safe_text(ent.get("razao_social"))
            cat  = Reconciler._safe_text(ent.get("categoria"))
            cargo = Reconciler._safe_text(ent.get("cargo_ocupacao"))
            # Retorna categoria enriquecida: "COLABORADOR_FINANCEIRO (MAGICAL ADM FINANCEIRO)"
            if cargo and cargo.upper() not in cat.upper():
                cat_enrich = f"{cat} | {cargo}" if cat else cargo
            else:
                cat_enrich = cat
            return nome, cat_enrich

        # 1) MATCH EXATO POR DOCUMENTO — O(1) com índice, O(n) sem
        if documento_banco:
            if entity_index is not None:
                ent = entity_index.get(documento_banco)
            else:
                match = df_entidades[
                    df_entidades["documento"].astype(str).apply(Reconciler._clean_doc) == documento_banco
                ]
                ent = match.iloc[0] if not match.empty else None

            if ent is not None:
                return _build_result(ent)

        # 2) MATCH EXATO POR NOME / NOME_BUSCA
        for _, ent in df_entidades.iterrows():
            razao         = Reconciler._normalize_text(ent.get("razao_social"))
            nome_busca    = Reconciler._normalize_text(ent.get("nome_busca"))
            nome_short    = Reconciler._normalize_text(ent.get("razao_social_short"))
            nome_resumido = Reconciler._normalize_text(ent.get("nome_resumido"))

            for candidate in [razao, nome_busca, nome_short]:
                if not candidate:
                    continue
                if candidate == banco_text:
                    return _build_result(ent)
                if candidate in descricao_banco or candidate in favorecido_banco:
                    if len(candidate) >= 8:
                        return _build_result(ent)

            if nome_resumido and len(nome_resumido) >= 10:
                if nome_resumido in descricao_banco or nome_resumido in favorecido_banco:
                    return _build_result(ent)

        # 3) SIMILARIDADE FORTE
        best_ent      = None
        best_score    = 0.0

        for _, ent in df_entidades.iterrows():
            candidates = [
                Reconciler._normalize_text(ent.get("razao_social")),
                Reconciler._normalize_text(ent.get("razao_social_short")),
                Reconciler._normalize_text(ent.get("nome_busca")),
                Reconciler._normalize_text(ent.get("nome_resumido")),
            ]
            candidates = sorted([c for c in candidates if c], key=len, reverse=True)

            local_best = 0.0
            for candidate in candidates:
                if len(candidate) < 8:
                    continue
                score = max(
                    Reconciler._similarity(descricao_banco, candidate),
                    Reconciler._similarity(favorecido_banco, candidate),
                    Reconciler._similarity(banco_text, candidate),
                )
                if score > local_best:
                    local_best = score

            if local_best > best_score:
                best_score = local_best
                best_ent   = ent

        if best_score >= 0.82 and best_ent is not None:
            return _build_result(best_ent)

        return "", ""

    # =============================
    # CONCILIAÇÃO
    # =============================

    @staticmethod
    def _conciliar(df_banco, df_erp, df_entidades, tipo_conciliacao, date_tolerance: int):
        results = []

        df_banco = df_banco.copy()
        df_erp   = df_erp.copy()

        df_banco["__matched__"] = False
        df_erp["__matched__"]   = False

        tipo_banco    = "SAIDA" if tipo_conciliacao == "DESPESA" else "ENTRADA"
        df_banco_tipo = df_banco[df_banco["tipo"] == tipo_banco].copy()

        # Pré-compila índice de entidades uma única vez para toda a execução
        entity_index = Reconciler._build_entity_index(df_entidades)

        for erp_idx, row_erp in df_erp.iterrows():
            valor_erp = Reconciler._normalize_money(row_erp.get("valor"))

            candidatos = df_banco_tipo[
                (~df_banco_tipo["__matched__"]) &
                (df_banco_tipo["valor"].apply(lambda x: Reconciler._same_value(x, valor_erp)))
            ]

            match_idx, diff_days = Reconciler._find_best_match(candidatos, row_erp, date_tolerance)

            if match_idx is not None:
                row_banco = df_banco_tipo.loc[match_idx]
                entidade, categoria = Reconciler._classify_entity(row_banco, df_entidades, entity_index)

                results.append({
                    "tipo_conciliacao": tipo_conciliacao,
                    "status":           "CONCILIADO",
                    "diferenca_dias":   diff_days,
                    "data_erp":         Reconciler._safe_date(row_erp.get("data")),
                    "data_banco":       Reconciler._safe_date(row_banco.get("data")),
                    "descricao_erp":    Reconciler._safe_text(row_erp.get("descricao")),
                    "descricao_banco":  Reconciler._safe_text(row_banco.get("descricao")),
                    "favorecido_banco": Reconciler._safe_text(row_banco.get("favorecido")),
                    "documento_banco":  Reconciler._safe_text(row_banco.get("documento")),
                    "entidade_encontrada": entidade,
                    "categoria_entidade":  categoria,
                    "valor_erp":   valor_erp,
                    "valor_banco": Reconciler._normalize_money(row_banco.get("valor")),
                    "manual_note": "",
                })

                df_erp.at[erp_idx, "__matched__"]         = True
                df_banco_tipo.at[match_idx, "__matched__"] = True

            else:
                results.append({
                    "tipo_conciliacao": tipo_conciliacao,
                    "status":           "SOMENTE_ERP",
                    "diferenca_dias":   None,
                    "data_erp":         Reconciler._safe_date(row_erp.get("data")),
                    "data_banco":       pd.NaT,
                    "descricao_erp":    Reconciler._safe_text(row_erp.get("descricao")),
                    "descricao_banco":  "",
                    "favorecido_banco": "",
                    "documento_banco":  "",
                    "entidade_encontrada": "",
                    "categoria_entidade":  Reconciler._safe_text(row_erp.get("categoria")),
                    "valor_erp":   valor_erp,
                    "valor_banco": None,
                    "manual_note": "",
                })

        # Registros do banco sem par no ERP
        for _, row_banco in df_banco_tipo[df_banco_tipo["__matched__"] == False].iterrows():
            entidade, categoria = Reconciler._classify_entity(row_banco, df_entidades, entity_index)

            results.append({
                "tipo_conciliacao": tipo_conciliacao,
                "status":           "SOMENTE_BANCO",
                "diferenca_dias":   None,
                "data_erp":         pd.NaT,
                "data_banco":       Reconciler._safe_date(row_banco.get("data")),
                "descricao_erp":    "",
                "descricao_banco":  Reconciler._safe_text(row_banco.get("descricao")),
                "favorecido_banco": Reconciler._safe_text(row_banco.get("favorecido")),
                "documento_banco":  Reconciler._safe_text(row_banco.get("documento")),
                "entidade_encontrada": entidade,
                "categoria_entidade":  categoria,
                "valor_erp":   None,
                "valor_banco": Reconciler._normalize_money(row_banco.get("valor")),
                "manual_note": "",
            })

        return pd.DataFrame(results)

    # =============================
    # PÚBLICO — recebem date_tolerance opcional
    # =============================

    @staticmethod
    def conciliar_despesas(df_banco, df_erp, df_entidades=None, date_tolerance: int = None):
        tol = date_tolerance if date_tolerance is not None else Reconciler.DATE_TOLERANCE_DAYS
        return Reconciler._conciliar(df_banco, df_erp, df_entidades, "DESPESA", tol)

    @staticmethod
    def conciliar_receitas(df_banco, df_erp, df_entidades=None, date_tolerance: int = None):
        tol = date_tolerance if date_tolerance is not None else Reconciler.DATE_TOLERANCE_DAYS
        return Reconciler._conciliar(df_banco, df_erp, df_entidades, "RECEITA", tol)

    @staticmethod
    def consolidar_resultados(df_desp, df_rec):
        frames = []
        if df_desp is not None and not df_desp.empty:
            frames.append(df_desp)
        if df_rec is not None and not df_rec.empty:
            frames.append(df_rec)
        if not frames:
            return pd.DataFrame()

        return pd.concat(frames, ignore_index=True).sort_values(
            by=["data_banco", "data_erp"],
            ascending=True,
            na_position="last"
        ).reset_index(drop=True)