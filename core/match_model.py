"""
core/match_model.py — Modelo de aprendizado para conciliação manual.

Classifica se um par (lançamento_banco, lançamento_erp) deve ser conciliado.

Técnica: Regressão Logística com gradiente descendente — numpy puro, zero deps extras.

Ciclo de vida:
  1. Usuário faz conciliação manual → salva exemplos positivos + negativos
  2. Modelo retreina automaticamente (segundos)
  3. Próxima conciliação usa predições do modelo

Tabela no banco: match_feedback
  - features JSON (6 features numéricas)
  - label: 1=match confirmado, 0=não é match
  - confianca: score do modelo na época do registro
  - created_at
"""

import json
import re
import math
from datetime import datetime


# =============================================================================
# EXTRAÇÃO DE FEATURES
# =============================================================================

def _clean_doc(v: str) -> str:
    return re.sub(r'\D', '', str(v or ''))


def _tokenize(text: str) -> set:
    return set(re.findall(r'[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ]{3,}', str(text or '').upper()))


def _text_score(a: str, b: str) -> float:
    """
    Score de similaridade entre dois textos usando:
    - Jaccard similarity entre tokens
    - Token containment bidirecional (captura nomes parciais)

    Exemplos:
      "RAFAELA" vs "RAFAELA GONCALVES RAMOS" → 0.90 (containment)
      "PASSAGEM RAFAELA" vs "RAFAELA GONCALVES RAMOS" → 0.45
      "RAFAELA" vs "DENISE BITTENCOURT" → 0.00
    """
    sa, sb = _tokenize(a), _tokenize(b)
    if not sa or not sb:
        return 0.0

    # Jaccard
    jaccard = len(sa & sb) / len(sa | sb)

    # Containment: % dos tokens de A presentes em B (e vice-versa)
    c_a_in_b = len(sa & sb) / len(sa)   # todos os tokens de A estão em B?
    c_b_in_a = len(sa & sb) / len(sb)   # todos os tokens de B estão em A?

    # Score: melhor das três métricas
    # containment ponderado 0.9 para não igualar match exato
    return max(jaccard, c_a_in_b * 0.9, c_b_in_a * 0.9)


def extract_features(
    favor_banco: str,
    desc_banco: str,
    doc_banco: str,
    desc_erp: str,
    favor_erp: str,
    data_banco: str,
    data_erp: str,
    valor_banco: float,
    valor_erp: float,
    cargo_banco: str = "",
    cargo_erp: str = "",
) -> list:
    """
    Extrai 8 features numéricas para o classificador.

    Features:
      0. score_texto_favor_desc  — favorecido banco × descrição ERP
      1. score_texto_favor_favor — favorecido banco × favorecido ERP
      2. score_texto_desc_desc   — descrição banco × descrição ERP
      3. mesmo_cargo             — 1 se cargo_banco == cargo_erp (base entidades)
      4. diff_dias_norm          — diferença de dias / 15 (0=mesmo dia, 1=15 dias)
      5. diff_valor_pct          — |val_banco - val_erp| / max(val_banco, val_erp)
      6. doc_match               — 1 se CPF/CNPJ do banco aparece na descrição ERP
      7. valor_exato             — 1 se valores são iguais (±R$0,02)
    """
    # Scores de texto
    f0 = _text_score(favor_banco, desc_erp)
    f1 = _text_score(favor_banco, favor_erp)
    f2 = _text_score(desc_banco,  desc_erp)

    # Mesmo cargo na base de entidades
    cb = str(cargo_banco or '').strip().upper()
    ce = str(cargo_erp   or '').strip().upper()
    f3 = 1.0 if (cb and ce and cb == ce) else 0.0

    # Diferença de dias normalizada
    try:
        from datetime import datetime as _dt
        db_ = _dt.fromisoformat(str(data_banco)[:10])
        de_ = _dt.fromisoformat(str(data_erp)[:10])
        dias = abs((db_ - de_).days)
        f4 = min(dias / 15.0, 1.0)
    except Exception:
        f4 = 0.5  # desconhecido = neutro

    # Diferença de valor percentual
    vb = abs(float(valor_banco or 0))
    ve = abs(float(valor_erp   or 0))
    denom = max(vb, ve, 0.01)
    f5 = abs(vb - ve) / denom

    # CPF/CNPJ do banco aparece na descrição do ERP
    doc = _clean_doc(doc_banco)
    f6 = 1.0 if (doc and len(doc) >= 8 and doc in _clean_doc(desc_erp)) else 0.0

    # Valor exato
    f7 = 1.0 if abs(vb - ve) < 0.02 else 0.0

    return [f0, f1, f2, f3, f4, f5, f6, f7]


# =============================================================================
# REGRESSÃO LOGÍSTICA (numpy puro)
# =============================================================================

def _sigmoid(z):
    try:
        import numpy as np
        return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))
    except ImportError:
        # Fallback sem numpy
        z = max(-500, min(500, z))
        return 1.0 / (1.0 + math.exp(-z))


class MatchModel:
    """
    Regressão logística binária para classificação de pares banco × ERP.

    Pesos iniciais calibrados para ser conservador sem dados de treino:
    favorece texto e valor exato, penaliza diferença de valor.
    """

    N_FEATURES = 8

    # Pesos iniciais (antes de qualquer treino)
    # [f0_favor_desc, f1_favor_favor, f2_desc_desc, f3_cargo,
    #  f4_dias, f5_val_pct, f6_doc, f7_val_exato]
    DEFAULT_WEIGHTS = [1.8, 2.0, 1.2, 1.0, -0.8, -2.5, 3.0, 2.5]
    DEFAULT_BIAS    = -1.5

    def __init__(self):
        self.weights  = list(self.DEFAULT_WEIGHTS)
        self.bias     = self.DEFAULT_BIAS
        self.n_treino = 0
        self.trained  = False

    def predict_proba(self, features: list) -> float:
        """Retorna probabilidade de match (0.0 a 1.0)."""
        z = self.bias + sum(w * x for w, x in zip(self.weights, features))
        return float(_sigmoid(z))

    def predict(self, features: list, threshold: float = 0.65) -> bool:
        return self.predict_proba(features) >= threshold

    def train(self, X: list, y: list,
              lr: float = 0.1, epochs: int = 200):
        """
        Treina o modelo com gradiente descendente.
        X: lista de listas de features
        y: lista de labels (0 ou 1)
        """
        if not X or not y or len(X) != len(y):
            return

        try:
            import numpy as np
            X_arr = np.array(X, dtype=float)
            y_arr = np.array(y, dtype=float)
            w = np.array(self.weights, dtype=float)
            b = float(self.bias)
            n = len(y_arr)

            for _ in range(epochs):
                z    = X_arr @ w + b
                pred = 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))
                err  = pred - y_arr
                grad_w = (X_arr.T @ err) / n
                grad_b = err.mean()
                # L2 regularização leve — evita overfitting com poucos dados
                grad_w += 0.01 * w
                w -= lr * grad_w
                b -= lr * grad_b

            self.weights  = w.tolist()
            self.bias     = float(b)

        except ImportError:
            # Fallback sem numpy — gradiente descendente Python puro
            w = list(self.weights)
            b = self.bias
            n = len(y)

            for _ in range(epochs):
                total_grad_w = [0.0] * self.N_FEATURES
                total_grad_b = 0.0

                for xi, yi in zip(X, y):
                    z    = b + sum(wi * xi_j for wi, xi_j in zip(w, xi))
                    pred = float(_sigmoid(z))
                    err  = pred - yi
                    for j in range(self.N_FEATURES):
                        total_grad_w[j] += err * xi[j] / n + 0.01 * w[j]
                    total_grad_b += err / n

                w = [wi - lr * gj for wi, gj in zip(w, total_grad_w)]
                b -= lr * total_grad_b

            self.weights = w
            self.bias    = b

        self.n_treino = len(y)
        self.trained  = True

    def to_dict(self) -> dict:
        return {
            "weights":  self.weights,
            "bias":     self.bias,
            "n_treino": self.n_treino,
            "trained":  self.trained,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MatchModel":
        m = cls()
        m.weights  = d.get("weights",  cls.DEFAULT_WEIGHTS)
        m.bias     = d.get("bias",     cls.DEFAULT_BIAS)
        m.n_treino = d.get("n_treino", 0)
        m.trained  = d.get("trained",  False)
        return m


# =============================================================================
# GERENCIADOR DO MODELO (persistência + retreino)
# =============================================================================

class MatchModelManager:
    """
    Gerencia o ciclo de vida do modelo:
      - Carrega do banco (settings key: match_model_weights)
      - Salva após treino
      - Retreina com os exemplos de match_feedback
      - Gera predições para a tela de sugestão
    """

    SETTINGS_KEY = "match_model_weights"
    MIN_EXEMPLOS = 10   # mínimo para retreinar

    def __init__(self, repo):
        self.repo  = repo
        self._model = None

    @property
    def model(self) -> MatchModel:
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> MatchModel:
        try:
            raw = self.repo.get_setting(self.SETTINGS_KEY)
            if raw:
                d = json.loads(raw)
                return MatchModel.from_dict(d)
        except Exception:
            pass
        return MatchModel()  # pesos padrão

    def _save_model(self):
        try:
            self.repo.save_setting(
                self.SETTINGS_KEY,
                json.dumps(self.model.to_dict())
            )
        except Exception:
            pass

    def predict(self, features: list) -> tuple:
        """
        Retorna (probabilidade, confianca_label, trained).
        confianca_label: 'alta', 'media', 'baixa'
        """
        prob = self.model.predict_proba(features)
        if prob >= 0.80:
            label = "alta"
        elif prob >= 0.60:
            label = "média"
        else:
            label = "baixa"
        return prob, label, self.model.trained

    def save_feedback(self,
                      ids_banco: list, rows_banco: list,
                      ids_erp: list, rows_erp: list,
                      label: int,
                      cargo_lookup_fn=None):
        """
        Salva exemplos de feedback no banco.

        label=1: par confirmado como match (conciliação manual confirmada)
        label=0: par negativo (banco com ERP de pessoa diferente)

        Para cada par banco × ERP gera um exemplo.
        Também gera exemplos negativos com os ERP que NÃO foram selecionados.
        """
        if not rows_banco or not rows_erp:
            return

        # Gera exemplos positivos — pares banco × ERP conciliados
        for rid_b, row_b in zip(ids_banco, rows_banco):
            for rid_e, row_e in zip(ids_erp, rows_erp):
                cargo_b = ""
                cargo_e = ""
                if cargo_lookup_fn:
                    try:
                        cargo_b = cargo_lookup_fn(
                            row_b.get("documento_banco"),
                            row_b.get("favorecido_banco")
                        ) or ""
                        cargo_e = cargo_lookup_fn(
                            None,
                            row_e.get("descricao_erp")
                        ) or ""
                    except Exception:
                        pass

                feats = extract_features(
                    favor_banco = str(row_b.get("favorecido_banco") or ""),
                    desc_banco  = str(row_b.get("descricao_banco")  or ""),
                    doc_banco   = str(row_b.get("documento_banco")  or ""),
                    desc_erp    = str(row_e.get("descricao_erp")    or ""),
                    favor_erp   = str(row_e.get("favorecido_erp")   or ""),
                    data_banco  = str(row_b.get("data_banco")       or "")[:10],
                    data_erp    = str(row_e.get("data_erp")         or "")[:10],
                    valor_banco = float(row_b.get("valor_banco")    or 0),
                    valor_erp   = float(row_e.get("valor_erp")      or 0),
                    cargo_banco = cargo_b,
                    cargo_erp   = cargo_e,
                )

                try:
                    self.repo.save_match_feedback(
                        result_id_banco = rid_b,
                        result_id_erp   = rid_e,
                        features_json   = json.dumps(feats),
                        label           = label,
                        confianca       = self.model.predict_proba(feats),
                    )
                except Exception:
                    pass

    def retrain(self) -> dict:
        """
        Retreina o modelo com todos os exemplos de match_feedback.
        Retorna stats do treino.
        """
        try:
            exemplos = self.repo.list_match_feedback()
        except Exception:
            return {"ok": False, "reason": "Erro ao carregar feedback"}

        if len(exemplos) < self.MIN_EXEMPLOS:
            return {
                "ok": False,
                "reason": f"Poucos exemplos ({len(exemplos)}/{self.MIN_EXEMPLOS} mínimo)",
                "n_exemplos": len(exemplos),
            }

        X, y = [], []
        for ex in exemplos:
            try:
                feats = json.loads(ex["features_json"])
                if len(feats) == MatchModel.N_FEATURES:
                    X.append(feats)
                    y.append(int(ex["label"]))
            except Exception:
                continue

        if len(X) < self.MIN_EXEMPLOS:
            return {"ok": False, "reason": "Exemplos inválidos insuficientes"}

        n_pos = sum(y)
        n_neg = len(y) - n_pos

        self.model.train(X, y)
        self._save_model()

        return {
            "ok":       True,
            "n_total":  len(X),
            "n_pos":    n_pos,
            "n_neg":    n_neg,
            "n_treino": self.model.n_treino,
            "trained":  True,
        }