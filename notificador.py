"""
notificador.py — Envio de notificacoes via WhatsApp (Evolution API)
"""

import requests
import logging
import re

log = logging.getLogger("magical_conciliacao")


class Notificador:
    def __init__(self, evo_url: str, api_key: str, instancia: str = "wanderley"):
        self.evo_url   = evo_url.rstrip("/")
        self.api_key   = api_key
        self.instancia = instancia
        self.headers   = {
            "apikey":       api_key,
            "Content-Type": "application/json",
        }

    def _post(self, endpoint: str, payload: dict) -> dict:
        try:
            resp = requests.post(
                f"{self.evo_url}/{endpoint}",
                headers=self.headers,
                json=payload,
                timeout=15,
            )
            if resp.status_code in (200, 201):
                return {"ok": True, "data": resp.json()}
            log.error(f"[WHATSAPP] Erro {resp.status_code}: {resp.text[:200]}")
            return {"ok": False, "erro": resp.text[:200]}
        except Exception as e:
            log.error(f"[WHATSAPP] Excecao: {e}")
            return {"ok": False, "erro": str(e)}

    def enviar_contato(self, numero: str, mensagem: str) -> dict:
        num_limpo = re.sub(r"\D", "", numero)
        jid = f"{num_limpo}@s.whatsapp.net"
        return self._post(
            f"message/sendText/{self.instancia}",
            {"number": jid, "text": mensagem},
        )

    def enviar_grupo(self, grupo_id: str, mensagem: str) -> dict:
        if not grupo_id.endswith("@g.us"):
            grupo_id = f"{grupo_id}@g.us"
        return self._post(
            f"message/sendText/{self.instancia}",
            {"number": grupo_id, "text": mensagem},
        )

    def listar_grupos(self) -> list:
        try:
            resp = requests.get(
                f"{self.evo_url}/group/fetchAllGroups/{self.instancia}",
                headers=self.headers,
                params={"getParticipants": "false"},
                timeout=15,
            )
            if resp.status_code == 200:
                return [
                    {"id": g.get("id",""), "nome": g.get("subject",""), "size": g.get("size",0)}
                    for g in resp.json()
                ]
        except Exception as e:
            log.error(f"[WHATSAPP] Erro ao listar grupos: {e}")
        return []

    def status_instancia(self) -> dict:
        try:
            resp = requests.get(
                f"{self.evo_url}/instance/connectionState/{self.instancia}",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                state = resp.json().get("instance", {}).get("state", "unknown")
                return {"conectado": state == "open", "state": state}
        except Exception as e:
            log.error(f"[WHATSAPP] Erro status: {e}")
        return {"conectado": False, "state": "error"}

    @staticmethod
    def _brl(valor: float) -> str:
        try:
            return (f"R$ {float(valor):,.2f}"
                    .replace(",","X").replace(".",",").replace("X","."))
        except Exception:
            return "R$ 0,00"

    # Mensagens pre-formatadas

    def msg_planilha_recebida(self, casa: str, total_itens: int,
                               valor_total: float, enviado_por: str) -> str:
        return (
            f"*Magical \u2014 Nova Planilha Recebida*\n\n"
            f"Casa: {casa}\n"
            f"Enviado por: {enviado_por}\n"
            f"Itens: {total_itens} despesas\n"
            f"Total: {self._brl(valor_total)}\n\n"
            f"Acesse o sistema para lan\u00e7ar no ERP."
        )

    def msg_erp_lancado(self, casa: str, planilha: str,
                         valor_total: float, lancado_por: str,
                         ok: int, erros: int) -> str:
        status = "com sucesso" if erros == 0 else f"com {erros} erro(s)"
        return (
            f"*Magical \u2014 Despesas Lan\u00e7adas no MeEventos*\n\n"
            f"Casa: {casa}\n"
            f"Planilha: {planilha}\n"
            f"Lan\u00e7ado por: {lancado_por}\n"
            f"Total: {self._brl(valor_total)}\n"
            f"Resultado: {ok} lan\u00e7ados {status}\n\n"
            f"CNAB dispon\u00edvel para gera\u00e7\u00e3o."
        )

    def msg_aguardando_aprovacao(self, casa: str, valor_total: float,
                                  gerado_por: str, qtd: int) -> str:
        return (
            f"*Magical \u2014 Lote Pagamento Gerado*\n\n"
            f"Casa: {casa}\n"
            f"Gerado por: {gerado_por}\n"
            f"Total: {self._brl(valor_total)}\n"
            f"Pagamentos: {qtd}\n"
            f"Arquivo importado no Ita\u00fa.\n\n"
            f"Para aprovar responda:\n"
            f"APROVAR {casa.upper()}\n\n"
            f"Para reprovar responda:\n"
            f"REPROVAR {casa.upper()} [motivo]"
        )

    def msg_aprovado(self, casa: str, aprovado_por: str,
                      valor_total: float) -> str:
        return (
            f"*Magical \u2014 Pagamento Aprovado*\n\n"
            f"Casa: {casa}\n"
            f"Aprovado por: {aprovado_por}\n"
            f"Total: {self._brl(valor_total)}\n\n"
            f"Pagamentos liberados para processamento."
        )

    def msg_reprovado(self, casa: str, reprovado_por: str,
                       motivo: str) -> str:
        return (
            f"*Magical \u2014 Pagamento Reprovado*\n\n"
            f"Casa: {casa}\n"
            f"Reprovado por: {reprovado_por}\n"
            f"Motivo: {motivo or 'n\u00e3o informado'}\n\n"
            f"Entre em contato para corre\u00e7\u00f5es."
        )