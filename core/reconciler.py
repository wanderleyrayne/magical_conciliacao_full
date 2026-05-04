import pandas as pd
from rapidfuzz import fuzz


# ── Motor de matching de nomes ─────────────────────────────────────────────────
_STOP_NOMES = {
    'DE', 'DA', 'DO', 'DAS', 'DOS', 'E', 'EM', 'COM', 'PIX', 'TED', 'DOC',
    'CNPJ', 'CPF', 'LTDA', 'ME', 'SA', 'EIRELI', 'SERVICOS', 'PRESTACAO',
    'PAGAMENTOS', 'FORNECEDORES', 'ENVIADO', 'RECEBIDO', 'INICIO', 'VT', 'VA',
}

def _gerar_combinacoes_nome(nome: str) -> list:
    """
    Gera todas as combinações possíveis de um nome completo para match robusto.
    Cobre: nome completo, primeiro+último, primeiro+meio, só primeiro nome,
    qualquer par de tokens consecutivos.
    """
    import re as _re
    norm = lambda v: _re.sub(r'\s+', ' ', str(v or '').upper().strip())
    tokens = [t for t in norm(nome).split()
              if len(t) >= 3 and t not in _STOP_NOMES]
    if not tokens:
        return []
    combos = set()
    combos.add(' '.join(tokens))           # nome completo
    primeiro = tokens[0]
    if len(primeiro) >= 4:
        combos.add(primeiro)               # só primeiro nome
        for t in tokens[1:]:
            combos.add(f"{primeiro} {t}") # primeiro + qualquer outro
    if len(tokens) >= 2:
        combos.add(f"{primeiro} {tokens[-1]}")  # primeiro + último
    for i in range(len(tokens)-1):
        combos.add(f"{tokens[i]} {tokens[i+1]}")  # pares consecutivos
    # Ordena do mais específico (longo) ao menos
    return sorted(combos, key=len, reverse=True)



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
    def _identity_score(row_banco, desc_erp: str,
                        df_entidades, entity_index: dict) -> float:
        """
        Score de identidade entre banco e ERP (0.0–1.0).

        Cobre todas as combinações:
          - CPF/CNPJ exato na descrição ERP → 1.0
          - Nome completo, primeiro+último, primeiro+meio, só primeiro,
            pares consecutivos — tanto do favorecido quanto do nome real
            da entidade pelo CPF (alias: HERCELINA conta de MARCIELO)
        """
        import re as _re

        doc        = Reconciler._clean_doc(row_banco.get("documento", ""))
        fav        = Reconciler._normalize_text(row_banco.get("favorecido", ""))
        desc_banco = Reconciler._normalize_text(row_banco.get("descricao", ""))
        desc_erp_n = Reconciler._normalize_text(desc_erp)

        # 1. CPF/CNPJ exato na descrição ERP
        if doc and len(doc) >= 8:
            doc_erp = _re.sub(r'\D', '', desc_erp)
            if doc in doc_erp:
                return 1.0

        # 2. Coleta todos os nomes candidatos
        # Favorecido do banco + nome real da entidade pelo CPF (alias)
        nomes_candidatos = []
        if fav:
            nomes_candidatos.append(fav)

        if doc and len(doc) >= 8:
            ent = entity_index.get(doc) if entity_index else None
            if ent is None and df_entidades is not None and not df_entidades.empty:
                match = df_entidades[
                    df_entidades["documento"].astype(str).apply(
                        Reconciler._clean_doc) == doc
                ]
                ent = match.iloc[0] if not match.empty else None
            if ent is not None:
                for campo in ["razao_social", "razao_social_short", "nome_busca"]:
                    nome = Reconciler._normalize_text(ent.get(campo, ""))
                    if nome and nome not in nomes_candidatos:
                        nomes_candidatos.append(nome)

        # 3. Testa todas as combinações de cada nome candidato
        best_score = 0.0
        for nome in nomes_candidatos:
            for combo in _gerar_combinacoes_nome(nome):
                if combo in desc_erp_n:
                    n_tokens  = len(combo.split())
                    total_tok = max(len(Reconciler._normalize_text(nome).split()), 1)
                    especif   = n_tokens / total_tok
                    s = 0.60 + especif * 0.35
                    if s > best_score:
                        best_score = s
                    break  # achou match para este nome — próximo

        if best_score > 0:
            return best_score

        # 4. Fallback: similaridade de texto conservadora
        sim = max(
            Reconciler._similarity(fav, desc_erp_n),
            Reconciler._similarity(desc_banco, desc_erp_n),
        )
        return sim * 0.4

    @staticmethod
    def _find_best_match_with_identity(candidatos, row_erp, date_tolerance: int,
                                        desc_erp: str, df_entidades, entity_index: dict) -> tuple:
        """
        Escolhe o melhor candidato do banco considerando:
        1. Score de identidade (CPF/nome bate com descrição ERP)
        2. Proximidade de data
        3. Fallback sem identidade (comportamento original) se nenhum candidato tiver score >= 0.3
        """
        if candidatos.empty:
            return None, None

        data_erp = Reconciler._safe_date(row_erp.get("data"))

        scored = []
        for idx, row_banco in candidatos.iterrows():
            diff = Reconciler._days_diff(data_erp, row_banco.get("data"))
            if diff is not None and diff > date_tolerance:
                continue

            id_score = Reconciler._identity_score(
                row_banco, desc_erp, df_entidades, entity_index)

            scored.append((idx, diff, id_score))

        if not scored:
            return None, None

        # Separa candidatos com identidade confirmada (score >= 0.3) dos sem identidade
        with_identity    = [(i, d, s) for i, d, s in scored if s >= 0.3]
        without_identity = [(i, d, s) for i, d, s in scored if s < 0.3]

        if with_identity:
            # Ordena: maior score de identidade primeiro, menor dias por desempate
            with_identity.sort(key=lambda x: (-x[2], x[1] if x[1] is not None else 9999))
            best = with_identity[0]
            return best[0], best[1]
        else:
            # Fallback: sem identidade clara — usa o mais próximo por data (comportamento original)
            # Só aceita se houver apenas 1 candidato (sem ambiguidade)
            if len(without_identity) == 1:
                best = without_identity[0]
                return best[0], best[1]
            # Múltiplos candidatos sem identidade — não arrisca, deixa como SOMENTE_ERP
            return None, None

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
    @staticmethod
    def _conciliar(df_banco, df_erp, df_entidades, tipo_conciliacao, date_tolerance: int):
        """
        Conciliação em 3 fases:
          Fase 1: 1 ERP → 1 Banco (match exato com identidade)
          Fase 2: N ERP → 1 Banco (subset sum: vários ERP somam 1 banco)
          Fase 3: N Banco → 1 ERP (subset sum: vários banco somam 1 ERP)
        """
        results = []

        df_banco = df_banco.copy()
        df_erp   = df_erp.copy()
        df_banco["__matched__"] = False
        df_erp["__matched__"]   = False

        tipo_banco    = "SAIDA" if tipo_conciliacao == "DESPESA" else "ENTRADA"
        df_banco_tipo = df_banco[df_banco["tipo"] == tipo_banco].copy()
        entity_index  = Reconciler._build_entity_index(df_entidades)

        def _make_result(status, tipo, row_erp=None, row_banco=None,
                         diff=None, entidade="", categoria="",
                         v_erp=None, v_banco=None, nota=""):
            return {
                "tipo_conciliacao":    tipo,
                "status":              status,
                "diferenca_dias":      diff,
                "data_erp":            Reconciler._safe_date(row_erp.get("data")) if row_erp is not None else pd.NaT,
                "data_banco":          Reconciler._safe_date(row_banco.get("data")) if row_banco is not None else pd.NaT,
                "descricao_erp":       Reconciler._safe_text(row_erp.get("descricao")) if row_erp is not None else "",
                "descricao_banco":     Reconciler._safe_text(row_banco.get("descricao")) if row_banco is not None else "",
                "favorecido_banco":    Reconciler._safe_text(row_banco.get("favorecido")) if row_banco is not None else "",
                "documento_banco":     Reconciler._safe_text(row_banco.get("documento")) if row_banco is not None else "",
                "entidade_encontrada": entidade,
                "categoria_entidade":  categoria,
                "valor_erp":           v_erp,
                "valor_banco":         v_banco,
                "manual_note":         nota,
            }

        def _subset_sum(itens, target, max_items=8, max_results=3):
            """Backtracking subset sum — retorna combinações que fecham o target."""
            found = []
            def bt(idx, rem, chosen):
                if abs(rem) < 0.02:
                    found.append(list(chosen))
                    return
                if idx >= len(itens) or rem < -0.02 or len(found) >= max_results:
                    return
                if len(chosen) >= max_items:
                    return
                bt(idx+1, round(rem - itens[idx]["valor"], 2), chosen + [itens[idx]])
                bt(idx+1, rem, chosen)
            bt(0, round(target, 2), [])
            return found

        # ── FASE 1: 1 ERP → 1 Banco ──────────────────────────────────────────
        for erp_idx, row_erp in df_erp.iterrows():
            valor_erp = Reconciler._normalize_money(row_erp.get("valor"))
            desc_erp  = Reconciler._normalize_text(row_erp.get("descricao", ""))

            candidatos = df_banco_tipo[
                (~df_banco_tipo["__matched__"]) &
                (df_banco_tipo["valor"].apply(lambda x: Reconciler._same_value(x, valor_erp)))
            ]

            match_idx, diff_days = (
                Reconciler._find_best_match_with_identity(
                    candidatos, row_erp, date_tolerance,
                    desc_erp, df_entidades, entity_index)
                if not candidatos.empty else (None, None)
            )

            if match_idx is not None:
                row_banco = df_banco_tipo.loc[match_idx]
                ent, cat  = Reconciler._classify_entity(row_banco, df_entidades, entity_index)
                results.append(_make_result(
                    "CONCILIADO", tipo_conciliacao,
                    row_erp=row_erp, row_banco=row_banco, diff=diff_days,
                    entidade=ent, categoria=cat,
                    v_erp=valor_erp,
                    v_banco=Reconciler._normalize_money(row_banco.get("valor")),
                ))
                df_erp.at[erp_idx, "__matched__"]         = True
                df_banco_tipo.at[match_idx, "__matched__"] = True
            # Não adiciona SOMENTE_ERP aqui — aguarda fases 2 e 3

        # ── FASE 2: N ERP → 1 Banco (subset sum) ─────────────────────────────
        for banco_idx, row_banco in df_banco_tipo[
            ~df_banco_tipo["__matched__"]
        ].iterrows():
            valor_banco = Reconciler._normalize_money(row_banco.get("valor"))
            if not valor_banco:
                continue

            data_banco = Reconciler._safe_date(row_banco.get("data"))
            ent, cat   = Reconciler._classify_entity(row_banco, df_entidades, entity_index)

            # Candidatos ERP: não conciliados, mesma identidade, dentro da janela
            cands = []
            for erp_idx2, row_erp2 in df_erp[~df_erp["__matched__"]].iterrows():
                diff = Reconciler._days_diff(
                    data_banco, Reconciler._safe_date(row_erp2.get("data")))
                if diff is not None and diff > date_tolerance:
                    continue
                desc_erp2 = Reconciler._normalize_text(row_erp2.get("descricao", ""))
                id_score  = Reconciler._identity_score(
                    row_banco, desc_erp2, df_entidades, entity_index)
                if id_score < 0.3:
                    continue
                v = Reconciler._normalize_money(row_erp2.get("valor"))
                if v and v <= abs(valor_banco) + 0.01:
                    cands.append({
                        "erp_idx": erp_idx2, "row_erp": row_erp2,
                        "valor": v, "diff": diff or 0, "id_score": id_score,
                    })

            if not cands:
                continue

            cands.sort(key=lambda x: (x["diff"], -x["id_score"]))
            combos = _subset_sum(cands, abs(valor_banco))

            if not combos:
                continue

            # Melhor combo: menor diff médio
            combo = min(combos, key=lambda c: sum(d["diff"] for d in c) / len(c))
            max_diff = max(d["diff"] for d in combo)
            desc_erps = " | ".join(
                Reconciler._safe_text(d["row_erp"].get("descricao"))[:30]
                for d in combo)

            # Marca o banco
            df_banco_tipo.at[banco_idx, "__matched__"] = True

            # Cria um resultado CONCILIADO para cada ERP do combo
            for d in combo:
                df_erp.at[d["erp_idx"], "__matched__"] = True
                results.append(_make_result(
                    "CONCILIADO", tipo_conciliacao,
                    row_erp=d["row_erp"], row_banco=row_banco,
                    diff=d["diff"], entidade=ent, categoria=cat,
                    v_erp=d["valor"],
                    v_banco=round(abs(valor_banco) / len(combo), 2),
                    nota=f"Subset N:1 ({len(combo)} ERP → 1 banco) | {desc_erps}",
                ))

        # ── FASE 3: N Banco → 1 ERP (subset sum inverso) ─────────────────────
        for erp_idx3, row_erp3 in df_erp[~df_erp["__matched__"]].iterrows():
            valor_erp3 = Reconciler._normalize_money(row_erp3.get("valor"))
            if not valor_erp3:
                continue

            data_erp3 = Reconciler._safe_date(row_erp3.get("data"))
            desc_erp3 = Reconciler._normalize_text(row_erp3.get("descricao", ""))

            # Candidatos Banco: não conciliados, mesma identidade, dentro da janela
            cands_b = []
            for banco_idx2, row_banco2 in df_banco_tipo[
                ~df_banco_tipo["__matched__"]
            ].iterrows():
                diff = Reconciler._days_diff(
                    data_erp3, Reconciler._safe_date(row_banco2.get("data")))
                if diff is not None and diff > date_tolerance:
                    continue
                id_score = Reconciler._identity_score(
                    row_banco2, desc_erp3, df_entidades, entity_index)
                if id_score < 0.3:
                    continue
                v = Reconciler._normalize_money(row_banco2.get("valor"))
                if v and v <= abs(valor_erp3) + 0.01:
                    cands_b.append({
                        "banco_idx": banco_idx2, "row_banco": row_banco2,
                        "valor": abs(v), "diff": diff or 0, "id_score": id_score,
                    })

            if not cands_b:
                continue

            cands_b.sort(key=lambda x: (x["diff"], -x["id_score"]))
            combos_b = _subset_sum(cands_b, abs(valor_erp3))

            if not combos_b:
                continue

            combo_b  = min(combos_b, key=lambda c: sum(d["diff"] for d in c) / len(c))
            ent_b, cat_b = Reconciler._classify_entity(
                combo_b[0]["row_banco"], df_entidades, entity_index)

            # Marca o ERP
            df_erp.at[erp_idx3, "__matched__"] = True

            # Cria um resultado por banco do combo
            for d in combo_b:
                df_banco_tipo.at[d["banco_idx"], "__matched__"] = True
                results.append(_make_result(
                    "CONCILIADO", tipo_conciliacao,
                    row_erp=row_erp3, row_banco=d["row_banco"],
                    diff=d["diff"], entidade=ent_b, categoria=cat_b,
                    v_erp=round(abs(valor_erp3) / len(combo_b), 2),
                    v_banco=d["valor"],
                    nota=f"Subset 1:N ({len(combo_b)} banco → 1 ERP)",
                ))

        # ── Banco ainda não conciliado → SOMENTE_BANCO ───────────────────────
        for _, row_banco in df_banco_tipo[~df_banco_tipo["__matched__"]].iterrows():
            ent, cat = Reconciler._classify_entity(row_banco, df_entidades, entity_index)
            results.append(_make_result(
                "SOMENTE_BANCO", tipo_conciliacao, row_banco=row_banco,
                entidade=ent, categoria=cat,
                v_banco=Reconciler._normalize_money(row_banco.get("valor")),
            ))

        # ── ERPs não conciliados em nenhuma das 3 fases → SOMENTE_ERP ──────────
        for _, row_erp_r in df_erp[~df_erp["__matched__"]].iterrows():
            v = Reconciler._normalize_money(row_erp_r.get("valor"))
            results.append(_make_result(
                "SOMENTE_ERP", tipo_conciliacao, row_erp=row_erp_r,
                categoria=Reconciler._safe_text(row_erp_r.get("categoria")),
                v_erp=v,
            ))

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