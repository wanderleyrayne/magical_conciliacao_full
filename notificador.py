"""
notificador.py — Envio de notificações via WhatsApp (Evolution API)

Uso:
    from notificador import Notificador
    n = Notificador(evo_url, api_key, instancia)
    n.enviar_contato("+5521999999999", "Mensagem aqui")
    n.enviar_grupo("ID_DO_GRUPO@g.us", "Mensagem aqui")
"""

import requests
import logging
from typing import Optional

log = logging.getLogger("magical_conciliacao")


class Notificador:
    """Cliente para envio de mensagens via Evolution API."""

    def __init__(self, evo_url: str, api_key: str, instancia: str = "wanderley"):
        self.evo_url  = evo_url.rstrip("/")
        self.api_key  = api_key
        self.instancia = instancia
        self.headers  = {
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
            else:
                log.error(f"[WHATSAPP] Erro {resp.status_code}: {resp.text[:200]}")
                return {"ok": False, "erro": resp.text[:200]}
        except Exception as e:
            log.error(f"[WHATSAPP] Exceção: {e}")
            return {"ok": False, "erro": str(e)}

    def enviar_contato(self, numero: str, mensagem: str) -> dict:
        """
        Envia mensagem para um contato.
        numero: formato +5521999999999
        """
        # Remove tudo que não for dígito e adiciona @s.whatsapp.net
        import re
        num_limpo = re.sub(r"\D", "", numero)
        jid = f"{num_limpo}@s.whatsapp.net"

        return self._post(
            f"message/sendText/{self.instancia}",
            {"number": jid, "text": mensagem},
        )

    def enviar_grupo(self, grupo_id: str, mensagem: str) -> dict:
        """
        Envia mensagem para um grupo.
        grupo_id: formato 120363xxxxxx@g.us
        """
        if not grupo_id.endswith("@g.us"):
            grupo_id = f"{grupo_id}@g.us"

        return self._post(
            f"message/sendText/{self.instancia}",
            {"number": grupo_id, "text": mensagem},
        )

    def listar_grupos(self) -> list:
        """Lista todos os grupos que o número participa."""
        try:
            resp = requests.get(
                f"{self.evo_url}/group/fetchAllGroups/{self.instancia}",
                headers=self.headers,
                params={"getParticipants": "false"},
                timeout=15,
            )
            if resp.status_code == 200:
                grupos = resp.json()
                return [
                    {
                        "id":   g.get("id", ""),
                        "nome": g.get("subject", ""),
                        "size": g.get("size", 0),
                    }
                    for g in grupos
                ]
        except Exception as e:
            log.error(f"[WHATSAPP] Erro ao listar grupos: {e}")
        return []

    def status_instancia(self) -> dict:
        """Verifica se a instância está conectada."""
        try:
            resp = requests.get(
                f"{self.evo_url}/instance/connectionState/{self.instancia}",
                headers=self.headers,
                timeout=10,
            )
            if resp.status_code == 200:
                data  = resp.json()
                state = data.get("instance", {}).get("state", "unknown")
                return {"conectado": state == "open", "state": state}
        except Exception as e:
            log.error(f"[WHATSAPP] Erro ao verificar status: {e}")
        return {"conectado": False, "state": "error"}

    # ── Mensagens pré-formatadas do fluxo ────────────────────────────────────

    def msg_planilha_recebida(self, casa: str, total_itens: int,
                               valor_total: float, enviado_por: str) -> str:
        return (
            f"*Magical Conciliacao — Nova Planilha*\n\n"
            f"Casa: {casa}\n"
            f"Enviado por: {enviado_por}\n"
            f"Itens: {total_itens} despesas\n"
            f"Total: R$ {valor_total:,.2f}\n\n"
            f"Acesse o sistema para lancar no ERP."
        ).replace(",", "X").replace(".", ",").replace("X", ".")

    def msg_erp_lancado(self, casa: str, valor_total: float,
                         lancado_por: str, ok: int, erros: int) -> str:
        status = "com sucesso" if erros == 0 else f"com {erros} erro(s)"
        return (
            f"*Magical Conciliacao — ERP Lancado*\n\n"
            f"Casa: {casa}\n"
            f"Lancado por: {lancado_por}\n"
            f"Total: R$ {valor_total:,.2f}\n"
            f"Resultado: {ok} lancados {status}\n\n"
            f"CNAB disponivel para geracao."
        ).replace(",", "X").replace(".", ",").replace("X", ".")

    def msg_aguardando_aprovacao(self, casa: str, valor_total: float,
                                  gerado_por: str, qtd: int) -> str:
        return (
            f"*Magical Conciliacao — CNAB Gerado*\n\n"
            f"Casa: {casa}\n"
            f"Gerado por: {gerado_por}\n"
            f"Total: R$ {valor_total:,.2f}\n"
            f"Pagamentos: {qtd}\n\n"
            f"Arquivo importado no Itau.\n\n"
            f"Para aprovar responda:\n"
            f"*APROVAR {casa.upper()}*\n\n"
            f"Para reprovar responda:\n"
            f"*REPROVAR {casa.upper()} [motivo]*"
        ).replace(",", "X").replace(".", ",").replace("X", ".")

    def msg_aprovado(self, casa: str, aprovado_por: str,
                      valor_total: float) -> str:
        return (
            f"*Magical Conciliacao — Aprovado*\n\n"
            f"Casa: {casa}\n"
            f"Aprovado por: {aprovado_por}\n"
            f"Total: R$ {valor_total:,.2f}\n\n"
            f"Pagamentos liberados para processamento."
        ).replace(",", "X").replace(".", ",").replace("X", ".")

    def msg_reprovado(self, casa: str, reprovado_por: str,
                       motivo: str) -> str:
        return (
            f"*Magical Conciliacao — Reprovado*\n\n"
            f"Casa: {casa}\n"
            f"Reprovado por: {reprovado_por}\n"
            f"Motivo: {motivo}\n\n"
            f"Entre em contato para correcoes."
        )