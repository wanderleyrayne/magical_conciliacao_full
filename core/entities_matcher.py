from rapidfuzz import fuzz


class EntitiesMatcher:
    STOPWORDS = {
        "VT", "VA", "VR", "PIX", "PAGO", "PAGAMENTO", "BOLETO",
        "RECEBIMENTO", "RECEBIDO", "TED", "DOC", "REF", "REFERENTE",
        "DIA", "DO", "DA", "DE", "PARA", "COM", "NO", "NA", "E",
    }

    def __init__(self, df_entidades):
        self.df_entidades = df_entidades
        self.by_document = {}
        self.entities = []

        if df_entidades is None or df_entidades.empty:
            return

        for _, row in df_entidades.iterrows():
            entidade = {
                "documento": str(row.get("documento", "") or "").strip(),
                "razao_social": str(row.get("razao_social", "") or "").strip(),
                "razao_social_short": str(row.get("razao_social_short", "") or "").strip(),
                "categoria": str(row.get("categoria", "") or "").strip(),
                "nome_busca": str(row.get("nome_busca", "") or "").strip(),
                "nome_resumido": str(row.get("nome_resumido", "") or "").strip(),
            }

            if entidade["documento"]:
                self.by_document[entidade["documento"]] = entidade

            self.entities.append(entidade)

    def find(self, documento="", nome="", descricao_erp="", descricao_banco="", favorecido_banco=""):
        documento = str(documento or "").strip()
        nome = self._clean_text(nome)
        descricao_erp = self._clean_text(descricao_erp)
        descricao_banco = self._clean_text(descricao_banco)
        favorecido_banco = self._clean_text(favorecido_banco)

        # 1) documento exato
        if documento and documento in self.by_document:
            return self.by_document[documento]

        # 2) prioridade máxima: blocos do ERP separados por |
        if descricao_erp:
            partes_erp = self._split_priority_parts(descricao_erp)
            for parte in partes_erp:
                entidade = self._match_single_text(parte)
                if entidade:
                    return entidade

        # 3) depois favorecido do banco
        if favorecido_banco:
            entidade = self._match_single_text(favorecido_banco)
            if entidade:
                return entidade

        # 4) depois nome informado
        if nome:
            entidade = self._match_single_text(nome)
            if entidade:
                return entidade

        # 5) depois descrição do banco
        if descricao_banco:
            partes_banco = self._split_priority_parts(descricao_banco)
            for parte in partes_banco:
                entidade = self._match_single_text(parte)
                if entidade:
                    return entidade

        return None

    def _match_single_text(self, text):
        text = self._clean_text(text)
        if not text:
            return None

        termos = self._expand_search_terms(text)

        # tenta cada termo em ordem de prioridade
        for termo in termos:
            entidade = self._best_match_for_term(termo)
            if entidade:
                return entidade

        return None

    def _best_match_for_term(self, termo):
        termo = self._clean_text(termo)
        if not termo or len(termo) < 3:
            return None

        # A) exato
        for entidade in self.entities:
            for candidato in self._candidatos_entidade(entidade):
                if termo == candidato:
                    return entidade

        # B) termo contido no candidato ou candidato contido no termo
        best_entidade = None
        best_score = 0

        for entidade in self.entities:
            for candidato in self._candidatos_entidade(entidade):
                if not candidato:
                    continue

                # preferência alta para conter nome da pessoa dentro do cadastro completo
                if len(termo) >= 4 and termo in candidato:
                    score = 97
                elif len(candidato) >= 4 and candidato in termo:
                    score = 95
                else:
                    score = max(
                        fuzz.partial_ratio(termo, candidato),
                        fuzz.token_sort_ratio(termo, candidato),
                        fuzz.token_set_ratio(termo, candidato),
                    )

                if score > best_score:
                    best_score = score
                    best_entidade = entidade

        # limiar
        if best_score >= 86:
            return best_entidade

        return None

    def _split_priority_parts(self, text):
        """
        Mantém a ordem natural dos blocos.
        Ex.: FABIA AZEVEDO | VENDEDOR | LAGO ENFESTA
        -> tenta primeiro FABIA AZEVEDO, depois VENDEDOR, depois LAGO ENFESTA
        """
        text = self._clean_text(text)
        if not text:
            return []

        partes = []

        if "|" in text:
            partes = [self._clean_text(p) for p in text.split("|")]
        elif "/" in text:
            partes = [self._clean_text(p) for p in text.split("/")]
        else:
            partes = [text]

        return [p for p in partes if p]

    def _expand_search_terms(self, text):
        """
        Expande, mas mantém prioridade:
        1. texto inteiro
        2. tokens úteis
        3. combinações de 2 e 3 tokens
        """
        text = self._clean_text(text)
        if not text:
            return []

        termos = []
        seen = set()

        def add(value):
            value = self._clean_text(value)
            if not value:
                return
            if value not in seen:
                seen.add(value)
                termos.append(value)

        # prioridade 1: texto inteiro
        add(text)

        tokens = [
            t for t in text.split()
            if t and t not in self.STOPWORDS and len(t) > 2
        ]

        # prioridade 2: combinações úteis primeiro
        for size in (3, 2):
            if len(tokens) >= size:
                for i in range(len(tokens) - size + 1):
                    add(" ".join(tokens[i:i + size]))

        # prioridade 3: tokens unitários
        for token in tokens:
            add(token)

        return termos

    def _candidatos_entidade(self, entidade):
        candidatos = [
            entidade.get("razao_social", ""),
            entidade.get("razao_social_short", ""),
            entidade.get("nome_busca", ""),
            entidade.get("nome_resumido", ""),
        ]
        candidatos = [self._clean_text(c) for c in candidatos if self._clean_text(c)]
        return list(dict.fromkeys(candidatos))

    @staticmethod
    def _clean_text(text):
        return str(text or "").strip().upper()