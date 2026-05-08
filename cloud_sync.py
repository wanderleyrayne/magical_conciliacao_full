"""
cloud_sync.py — Sincronizacao com PocketBase
"""

import requests
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("magical_conciliacao")

STATUS_RECEBIDO              = "recebido"
STATUS_EM_LANCAMENTO         = "em_lancamento"
STATUS_AG_APROV_OPERACIONAL  = "ag_aprov_operacional"
STATUS_CNAB_PENDENTE         = "cnab_pendente"
STATUS_CNAB_GERADO           = "cnab_gerado"
STATUS_AG_APROV_FINANCEIRA   = "ag_aprov_financeira"
STATUS_PAGO                  = "pago"
STATUS_REPROVADA             = "reprovado"

# Aliases compatibilidade
STATUS_LANCADO               = STATUS_CNAB_PENDENTE
STATUS_CNAB_ENVIADO          = STATUS_AG_APROV_FINANCEIRA
STATUS_APROVADA              = STATUS_PAGO


class CloudSync:
    def __init__(self, pb_url, pb_email, pb_senha):
        self.pb_url    = pb_url.rstrip("/")
        self.pb_email  = pb_email
        self.pb_senha  = pb_senha
        self._token    = None
        self._token_ts = None

    def _get_token(self):
        if self._token and self._token_ts:
            if (datetime.now() - self._token_ts).seconds < 1800:
                return self._token
        try:
            resp = requests.post(
                f"{self.pb_url}/api/collections/_superusers/auth-with-password",
                json={"identity": self.pb_email, "password": self.pb_senha},
                timeout=10)
            if resp.status_code == 200:
                self._token    = resp.json()["token"]
                self._token_ts = datetime.now()
                return self._token
        except Exception as e:
            log.error(f"[CLOUD] Auth: {e}")
        return None

    def _headers(self):
        token = self._get_token()
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {}

    def _get(self, col, filtro="", limit=50):
        try:
            params = {"perPage": limit, "fields": "@created,@updated,*"}
            if filtro:
                params["filter"] = filtro
            resp = requests.get(
                f"{self.pb_url}/api/collections/{col}/records",
                headers=self._headers(), params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("items", [])
        except Exception as e:
            log.error(f"[CLOUD] GET {col}: {e}")
        return []

    def _post(self, col, data):
        try:
            resp = requests.post(
                f"{self.pb_url}/api/collections/{col}/records",
                headers=self._headers(), json=data, timeout=30)
            if resp.status_code in (200, 201):
                return resp.json()
        except Exception as e:
            log.error(f"[CLOUD] POST {col}: {e}")
        return None

    def _patch(self, col, record_id, data):
        try:
            resp = requests.patch(
                f"{self.pb_url}/api/collections/{col}/records/{record_id}",
                headers=self._headers(), json=data, timeout=30)
            return resp.status_code in (200, 201)
        except Exception as e:
            log.error(f"[CLOUD] PATCH {col}: {e}")
        return False

    def salvar_planilha_recebida(self, casa, nome_arquivo, enviado_por,
                                  total_itens, valor_total, arquivo_path=None):
        rec = self._post("planilhas", {
            "casa": casa, "nome_arquivo": nome_arquivo,
            "enviado_por": enviado_por, "total_itens": total_itens,
            "total_valor": valor_total, "status": STATUS_RECEBIDO,
            "recebido_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        if not rec:
            return None
        pid = rec["id"]
        if arquivo_path:
            self.upload_arquivo(pid, arquivo_path)
        self._registrar_historico(pid, casa, "planilha_recebida", enviado_por,
                                   f"{total_itens} itens", valor_total)
        return pid

    def upload_arquivo(self, planilha_id, arquivo_path):
        try:
            import os
            token = self._get_token()
            if not token:
                return False
            with open(arquivo_path, "rb") as f:
                nome = os.path.basename(arquivo_path)
                resp = requests.patch(
                    f"{self.pb_url}/api/collections/planilhas/records/{planilha_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    files={"arquivo": (nome, f,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                    timeout=30)
            return resp.status_code in (200, 201)
        except Exception as e:
            log.error(f"[CLOUD] Upload: {e}")
            return False

    def download_arquivo(self, planilha_id, destino_dir):
        try:
            import os
            token = self._get_token()
            if not token:
                return None
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(
                f"{self.pb_url}/api/collections/planilhas/records/{planilha_id}",
                headers=headers, timeout=10)
            if resp.status_code != 200:
                return None
            arquivo = resp.json().get("arquivo")
            if not arquivo:
                log.warning(f"[CLOUD] Planilha {planilha_id} sem arquivo")
                return None
            resp2 = requests.get(
                f"{self.pb_url}/api/files/planilhas/{planilha_id}/{arquivo}",
                headers=headers, timeout=30)
            if resp2.status_code != 200:
                return None
            os.makedirs(destino_dir, exist_ok=True)
            caminho = os.path.join(destino_dir, arquivo)
            with open(caminho, "wb") as f:
                f.write(resp2.content)
            return caminho
        except Exception as e:
            log.error(f"[CLOUD] Download: {e}")
            return None

    def iniciar_lancamento(self, planilha_id, usuario):
        """No ERP — em lancamento."""
        ok = self._patch("planilhas", planilha_id, {
            "status": STATUS_EM_LANCAMENTO,
            "lancado_por": usuario,
        })
        if ok:
            self._registrar_historico(planilha_id, "", "lancamento_iniciado", usuario)
        return ok

    def confirmar_lancamento(self, planilha_id, casa, usuario, ok, erros, valor_total):
        """Apos ERP lancado — vai para Ag. Aprov. Operacional."""
        if erros == 0:
            novo_status = STATUS_AG_APROV_OPERACIONAL
            acao = "lancamento_concluido"
        else:
            novo_status = STATUS_RECEBIDO
            acao = "lancamento_erro"
        result = self._patch("planilhas", planilha_id, {
            "status": novo_status,
            "lancado_por": usuario,
            "lancado_em": datetime.now().isoformat(),
        })
        if result:
            self._registrar_historico(planilha_id, casa, acao, usuario,
                                       f"ok={ok} erros={erros}", valor_total)
        return result

    def atualizar_status(self, planilha_id, novo_status, lancado_por="", **kwargs):
        """Atualiza status generico."""
        data = {"status": novo_status}
        if lancado_por:
            data["lancado_por"] = lancado_por
        data.update(kwargs)
        return self._patch("planilhas", planilha_id, data)

    def confirmar_cnab_gerado(self, planilha_id, casa, usuario, valor_total):
        """CNAB gerado — No Itau."""
        result = self._patch("planilhas", planilha_id, {
            "status": STATUS_CNAB_GERADO,
            "cnab_gerado_por": usuario,
            "cnab_gerado_em": datetime.now().isoformat(),
        })
        if result:
            self._registrar_historico(planilha_id, casa, "cnab_gerado",
                                       usuario, "Arquivo .rem gerado", valor_total)
        return result

    def confirmar_cnab_enviado(self, planilha_id, casa, usuario):
        """CNAB importado no Itau — Ag. Aprov. Financeira."""
        result = self._patch("planilhas", planilha_id, {
            "status": STATUS_AG_APROV_FINANCEIRA,
        })
        if result:
            self._registrar_historico(planilha_id, casa, "cnab_enviado_itau", usuario)
        return result

    def registrar_aprovacao(self, planilha_id, casa, aprovado_por, aprovado, motivo=""):
        status = STATUS_PAGO if aprovado else STATUS_REPROVADA
        data = {"status": status, "aprovado_por": aprovado_por,
                "aprovado_em": datetime.now().isoformat()}
        if not aprovado and motivo:
            data["motivo_reprovacao"] = motivo
        result = self._patch("planilhas", planilha_id, data)
        if result:
            acao = "aprovado_financeiro" if aprovado else "reprovado_financeiro"
            self._registrar_historico(planilha_id, casa, acao, aprovado_por, motivo)
        return result

    def listar_todas(self, limit=50):
        return self._get("planilhas", limit=limit)

    def listar_pendencias_lancamento(self):
        return self._get("planilhas", f'status="{STATUS_RECEBIDO}"')

    def listar_pendencias_cnab(self):
        return self._get("planilhas", f'status="{STATUS_CNAB_PENDENTE}"')

    def listar_pendencias_aprovacao(self):
        return self._get("planilhas", f'status="{STATUS_AG_APROV_FINANCEIRA}"')

    def contar_pendencias(self):
        try:
            todas = self.listar_todas(limit=200)
            return {
                "lancamento": sum(1 for p in todas if p.get("status") == STATUS_RECEBIDO),
                "cnab":       sum(1 for p in todas if p.get("status") == STATUS_CNAB_PENDENTE),
                "aprovacao":  sum(1 for p in todas if p.get("status") in (
                                  STATUS_AG_APROV_OPERACIONAL, STATUS_AG_APROV_FINANCEIRA)),
            }
        except Exception:
            return {"lancamento": 0, "cnab": 0, "aprovacao": 0}

    def criar_notificacao(self, tipo, casa, mensagem, planilha_id="", destinatario=""):
        return self._post("notificacoes", {
            "tipo": tipo, "casa": casa, "mensagem": mensagem,
            "planilha_id": planilha_id, "destinatario": destinatario, "lida": False,
        }) is not None

    def listar_notificacoes_nao_lidas(self, destinatario=""):
        filtro = 'lida=false'
        if destinatario:
            filtro += f' && destinatario="{destinatario}"'
        return self._get("notificacoes", filtro, limit=20)

    def marcar_lida(self, notif_id, usuario):
        return self._patch("notificacoes", notif_id, {
            "lida": True, "lida_por": usuario, "lida_em": datetime.now().isoformat()})

    def _registrar_historico(self, planilha_id, casa, acao, usuario, detalhe="", valor=0.0):
        self._post("historico", {
            "planilha_id": planilha_id, "casa": casa, "acao": acao,
            "usuario": usuario, "detalhe": detalhe, "valor_total": valor,
        })

    def get_config(self, chave):
        items = self._get("configuracoes", f'chave="{chave}"', limit=1)
        return items[0].get("valor", "") if items else ""

    def set_config(self, chave, valor):
        items = self._get("configuracoes", f'chave="{chave}"', limit=1)
        if items:
            return self._patch("configuracoes", items[0]["id"], {"valor": valor})
        return self._post("configuracoes", {"chave": chave, "valor": valor}) is not None

    def ping(self):
        try:
            return requests.get(f"{self.pb_url}/api/health", timeout=5).status_code == 200
        except Exception:
            return False