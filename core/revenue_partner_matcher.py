import pandas as pd
from core.partner_rules import PARTNERS, GROUP_CONTRIBUTORS


class RevenuePartnerMatcher:
    @staticmethod
    def _clean_doc(value):
        if value is None:
            return ""
        return "".join(ch for ch in str(value) if ch.isdigit())

    @staticmethod
    def _safe_text(value):
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() in {"nan", "nat", "none"}:
            return ""
        return text.upper()

    @staticmethod
    def _fmt_money(value) -> str:
        try:
            v = float(value or 0)
        except Exception:
            v = 0.0
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    @classmethod
    def _sorted_partners(cls):
        """
        Ordena parceiros do mais específico para o mais genérico.
        Isso evita que 'LAGO' capture 'CASA DO LAGO' ou 'CHATEAU DO LAGO'.
        """
        partners = [p for p in PARTNERS if not p.get("is_hub")]

        def partner_weight(partner):
            aliases = [cls._safe_text(a) for a in partner.get("aliases", [])]
            legal_name = cls._safe_text(partner.get("legal_name", ""))
            longest_alias = max([len(a) for a in aliases], default=0)
            return max(longest_alias, len(legal_name))

        return sorted(partners, key=partner_weight, reverse=True)

    @classmethod
    def identify_partner(cls, row):
        """
        Identifica o parceiro de uma linha do extrato bancário
        pelos aliases/CNPJ dos parceiros cadastrados em PARTNERS.
        """
        descricao = cls._safe_text(row.get("descricao"))
        favorecido = cls._safe_text(row.get("favorecido"))
        documento = cls._clean_doc(row.get("documento"))

        haystack = f"{descricao} {favorecido}".upper()

        partners_sorted = cls._sorted_partners()

        # 1) CNPJ exato
        for partner in partners_sorted:
            partner_doc = cls._clean_doc(partner.get("cnpj", ""))
            if partner_doc and documento and partner_doc == documento:
                return partner

        # 2) Razão social completa
        for partner in partners_sorted:
            legal_name = cls._safe_text(partner.get("legal_name", ""))
            if legal_name and legal_name in haystack:
                return partner

        # 3) Aliases do mais específico ao mais genérico
        for partner in partners_sorted:
            aliases = [cls._safe_text(a) for a in partner.get("aliases", [])]
            aliases = sorted(aliases, key=len, reverse=True)
            for alias in aliases:
                if alias and alias in haystack:
                    return partner

        return None

    @classmethod
    def identify_group_contributor(cls, row):
        """
        Verifica se uma linha do extrato pertence a um aportador do grupo
        (sócio, holding etc.) cadastrado em GROUP_CONTRIBUTORS.
        Retorna o dict do contribuidor ou None.
        Usado apenas para exibir aviso na UI — a atribuição ao parceiro é sempre manual.
        """
        descricao = cls._safe_text(row.get("descricao"))
        favorecido = cls._safe_text(row.get("favorecido"))
        documento = cls._clean_doc(row.get("documento"))
        haystack = f"{descricao} {favorecido}".upper()

        for contributor in GROUP_CONTRIBUTORS:
            cnpj = cls._clean_doc(contributor.get("cnpj", ""))
            if cnpj and documento and cnpj == documento:
                return contributor

            aliases = [cls._safe_text(a) for a in contributor.get("aliases", [])]
            aliases = sorted(aliases, key=len, reverse=True)
            for alias in aliases:
                if alias and alias in haystack:
                    return contributor

        return None

    @staticmethod
    def _reference_month_from_date(value):
        try:
            dt = pd.to_datetime(value, errors="coerce")
            if pd.isna(dt):
                return ""
            return dt.strftime("%Y-%m")
        except Exception:
            return ""

    @staticmethod
    def _best_received_value(row):
        try:
            return abs(float(row.get("valor", 0) or 0))
        except Exception:
            return 0.0

    @classmethod
    def build_partner_receipts_summary(cls, df_banco: pd.DataFrame, repo):
        """
        Monta o resumo de recebimentos por parceiro/mês.

        Lógica de validação em 3 etapas (ordem de precedência):

        1. Existe depósito com valor EXATO da regra?
           → OK imediato. Depósitos extras do período são classificados
             separadamente como "recebimentos adicionais" (não contaminam o status).

        2. NÃO existe exato → Soma todos os depósitos do período
           → Soma = regra? → OK (múltiplos depósitos que juntos fecham)
           → Soma < regra? → PARCIAL
           → Soma > regra? → Tenta encontrar subconjunto que fecha exato
             (subset sum). Se encontrar → OK, excedente é adicional.
             Se não encontrar → EXCEDENTE real.

        3. Depósitos "adicionais" (fora da fatura) são anotados na observação
           mas NÃO alteram o status.
        """
        if df_banco is None or df_banco.empty:
            return []

        rules = repo.list_partner_month_rules()
        if not rules:
            return []

        df = df_banco.copy()

        if "tipo" not in df.columns or "data" not in df.columns:
            return []

        df_entradas = df[df["tipo"] == "ENTRADA"].copy()
        if df_entradas.empty:
            return cls._build_empty_results_from_rules(rules)

        grouped = {}

        # ── 1) Depósitos identificados automaticamente ──────────────────────
        for _, row in df_entradas.iterrows():
            attributed = cls._safe_text(row.get("attributed_partner", ""))
            if attributed:
                continue

            partner = cls.identify_partner(row)
            if not partner:
                continue

            ref_month = cls._reference_month_from_date(row.get("data"))
            if not ref_month:
                continue

            key = (ref_month, partner["partner_name"])
            if key not in grouped:
                grouped[key] = {"deposits": [], "has_attributed": False}

            value = cls._best_received_value(row)
            try:
                dt = pd.to_datetime(row.get("data"), errors="coerce")
                date_str = dt.strftime("%d/%m/%Y") if pd.notna(dt) else ""
            except Exception:
                date_str = ""

            grouped[key]["deposits"].append({
                "value":    value,
                "date":     date_str,
                "manual":   False,
            })

        # ── 2) Depósitos com atribuição manual (aportadores do grupo) ────────
        for _, row in df_entradas.iterrows():
            attributed = cls._safe_text(row.get("attributed_partner", ""))
            if not attributed:
                continue

            ref_month = cls._reference_month_from_date(row.get("data"))
            if not ref_month:
                continue

            key = (ref_month, attributed)
            if key not in grouped:
                grouped[key] = {"deposits": [], "has_attributed": False}

            value = cls._best_received_value(row)
            try:
                dt = pd.to_datetime(row.get("data"), errors="coerce")
                date_str = dt.strftime("%d/%m/%Y") if pd.notna(dt) else ""
            except Exception:
                date_str = ""

            grouped[key]["deposits"].append({
                "value":  value,
                "date":   date_str,
                "manual": True,
            })
            grouped[key]["has_attributed"] = True

        # ── 3) Monta resultado por regra com validação inteligente ────────────
        results = []

        for rule in rules:
            ref_month    = rule["reference_month"]
            partner_name = rule["partner_name"]
            key          = (ref_month, partner_name)

            subtotal       = float(rule.get("subtotal") or 0)
            fee            = float(rule.get("marketing_fee") or 0)
            total_expected = float(rule.get("total_expected") or 0)

            received_data  = grouped.get(key, {})
            deposits       = received_data.get("deposits", [])
            has_attributed = received_data.get("has_attributed", False)

            deposit_count  = len(deposits)
            total_received = round(sum(d["value"] for d in deposits), 2)
            all_dates      = [d["date"] for d in deposits if d["date"]]

            # ── Validação inteligente ─────────────────────────────────────
            status      = "SEM_RECEBIMENTO"
            observation = ""
            fatura_deposits   = []   # depósitos que compõem a fatura
            adicional_deposits = []  # depósitos extras fora da fatura

            if deposit_count == 0:
                status = "SEM_RECEBIMENTO"
                observation = "Nenhum recebimento identificado para o parceiro no período."

            elif total_expected <= 0:
                # Regra zerada — apenas informa o recebido
                status = "OK"
                observation = f"Regra sem valor esperado. Recebido: {cls._fmt_money(total_received)}."
                fatura_deposits = deposits

            else:
                # ETAPA 1 — Existe depósito com valor EXATO?
                exact = [d for d in deposits if abs(d["value"] - total_expected) < 0.02]

                if exact:
                    # Encontrou depósito exato — esse é a fatura
                    fatura_deposits    = exact[:1]
                    adicional_deposits = [d for d in deposits if d not in fatura_deposits]
                    status = "OK"
                    if adicional_deposits:
                        extra_total = sum(d["value"] for d in adicional_deposits)
                        observation = (
                            f"Fatura recebida exatamente (R$ {total_expected:,.2f}). "
                            f"{len(adicional_deposits)} recebimento(s) adicional(is) "
                            f"de {cls._fmt_money(extra_total)} no período "
                            f"(não fazem parte da fatura)."
                        ).replace(",", "X").replace(".", ",").replace("X", ".")
                    else:
                        observation = "Recebimento em conformidade com o total esperado."

                else:
                    # ETAPA 2 — Soma total fecha?
                    diff_total = round(total_received - total_expected, 2)

                    if abs(diff_total) < 0.02:
                        # Soma exata — múltiplos depósitos que fecham juntos
                        fatura_deposits = deposits
                        status = "OK"
                        observation = (
                            f"Recebimento em conformidade. "
                            f"{deposit_count} depósito(s) que somam "
                            f"{cls._fmt_money(total_received)}."
                        )
                        if has_attributed:
                            observation += " Inclui aporte atribuído manualmente."

                    elif diff_total > 0:
                        # Soma maior — ETAPA 3: tenta subset sum
                        subset = cls._find_subset_sum(deposits, total_expected)

                        if subset is not None:
                            # Subconjunto que fecha exatamente
                            fatura_deposits    = subset
                            adicional_deposits = [d for d in deposits if d not in subset]
                            extra_total        = sum(d["value"] for d in adicional_deposits)
                            status = "OK"
                            observation = (
                                f"Fatura fechada por {len(subset)} depósito(s) "
                                f"({cls._fmt_money(total_expected)}). "
                                f"{len(adicional_deposits)} recebimento(s) adicional(is) "
                                f"de {cls._fmt_money(extra_total)} no período "
                                f"(não fazem parte da fatura)."
                            ).replace(",", "X").replace(".", ",").replace("X", ".")
                        else:
                            # Excedente real — não existe combinação que fecha
                            fatura_deposits = deposits
                            excedente = round(total_received - total_expected, 2)
                            status = "EXCEDENTE"
                            observation = (
                                f"Recebimento acima do esperado. "
                                f"Excedente real de {cls._fmt_money(excedente)}."
                            )

                    else:
                        # Soma menor — PARCIAL
                        fatura_deposits = deposits
                        faltando = round(total_expected - total_received, 2)
                        status = "PARCIAL"
                        observation = (
                            f"Recebimento parcial. "
                            f"Faltando {cls._fmt_money(faltando)}."
                        )
                        if has_attributed:
                            observation += " Inclui aporte atribuído manualmente."

            # Datas dos depósitos da fatura
            fatura_dates = [d["date"] for d in fatura_deposits if d["date"]]

            results.append({
                "reference_month":     ref_month,
                "partner_name":        partner_name,
                "partner_cnpj":        rule.get("partner_cnpj", ""),
                "subtotal":            subtotal,
                "marketing_fee":       fee,
                "total_expected":      total_expected,
                "total_received":      round(sum(d["value"] for d in fatura_deposits), 2),
                "total_received_all":  total_received,
                "deposit_count":       len(fatura_deposits),
                "deposit_count_all":   deposit_count,
                "received_dates":      ", ".join(fatura_dates),
                "difference":          round(
                    sum(d["value"] for d in fatura_deposits) - total_expected, 2
                ),
                "status":              status,
                "observation":         observation,
                "adicional_deposits":  len(adicional_deposits),
                "adicional_total":     round(
                    sum(d["value"] for d in adicional_deposits), 2
                ),
            })

        return results

    @staticmethod
    def _find_subset_sum(deposits, target, tolerance=0.02):
        """
        Encontra subconjunto de depósitos que soma exatamente o target.
        Usa backtracking com poda por valor — eficiente para N pequeno (< 20).
        Retorna a lista de depósitos que formam o subconjunto, ou None.
        """
        target = round(target, 2)
        n      = len(deposits)

        # Ordena decrescente para podar mais rápido
        sorted_deps = sorted(deposits, key=lambda d: d["value"], reverse=True)

        result = []

        def backtrack(idx, remaining, chosen):
            if abs(remaining) <= tolerance:
                result.extend(chosen)
                return True
            if idx >= n or remaining < 0:
                return False
            d = sorted_deps[idx]
            # Inclui este depósito
            if backtrack(idx + 1, round(remaining - d["value"], 2), chosen + [d]):
                return True
            # Não inclui
            return backtrack(idx + 1, remaining, chosen)

        found = backtrack(0, target, [])
        return result if found else None

    @classmethod
    def _build_empty_results_from_rules(cls, rules):
        results = []
        for rule in rules:
            subtotal = float(rule.get("subtotal") or 0)
            fee = float(rule.get("marketing_fee") or 0)
            total_expected = float(rule.get("total_expected") or 0)

            results.append({
                "reference_month": rule["reference_month"],
                "partner_name": rule["partner_name"],
                "partner_cnpj": rule.get("partner_cnpj", ""),
                "subtotal": subtotal,
                "marketing_fee": fee,
                "total_expected": total_expected,
                "total_received": 0.0,
                "deposit_count": 0,
                "received_dates": "",
                "difference": round(0.0 - total_expected, 2),
                "status": "SEM_RECEBIMENTO",
                "observation": "Nenhum recebimento identificado para o parceiro no período.",
            })
        return results