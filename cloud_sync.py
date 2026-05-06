"""
cloud_sync.py — Sincronização com PocketBase (banco central compartilhado)

Responsabilidades:
  - Salvar pendências após lançamento ERP
  - Consultar pendências (polling)
  - Atualizar status do fluxo
  - Registrar histórico de ações

Uso:
    from cloud_sync import CloudSync
    cs = CloudSync(pb_url, pb_email, pb_senha)
    cs.salvar_pendencia_erp(casa, planilha, itens, valor_total)
    pendencias = cs.listar_pendencias_cnab()
"""

import requests
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("magical_conciliacao")

# Status do fluxo
STATUS_RECEBIDO          = "recebido"
STATUS_EM_LANCAMENTO     = "em_lancamento"
STATUS_LANCADO           = "lancado"
STATUS_CNAB_GERADO       = "cnab_gerado"
STATUS_CNAB_ENVIADO      = "cnab_enviado"
STATUS_APROVADA          = "aprovado"
STATUS_REPROVADA         = "reprovado"


class CloudSync:
    """Cliente PocketBase para sincronização entre instâncias."""

    def __init__(self, pb_url: str, pb_email: str, pb_senha: str):
        self.pb_url   = pb_url.rstrip("/")
        self.pb_email = pb_email
        self.pb_senha = pb_senha
        self._token   = None
        self._token_ts = None

    # ── Autenticação ──────────────────────────────────────────────────────────

    def _get_token(self) -> Optional[str]:
        """Obtém token de autenticação (renova se necessário)."""
        # Renova a cada 30 minutos
        if self._token and self._token_ts:
            elapsed = (datetime.now() - self._token_ts).seconds
            if elapsed < 1800:
                return self._token

        try:
            resp = requests.post(
                f"{self.pb_url}/api/collections/_superusers/auth-with-password",
                json={"identity": self.pb_email, "password": self.pb_senha},
                timeout=10,
            )
            if resp.status_code == 200:
                self._token    = resp.json()["token"]
                self._token_ts = datetime.now()
                return self._token
            else:
                log.error(f"[CLOUD] Auth erro: {resp.status_code}")
        except Exception as e:
            log.error(f"[CLOUD] Auth exceção: {e}")
        return None

    def _headers(self) -> dict:
        token = self._get_token()
        if not token:
            return {}
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        }

    def _get(self, col: str, filtro: str = "", limit: int = 50) -> list:
        try:
            params = {"perPage": limit}
            if filtro:
                params["filter"] = filtro
            # Solicita campos de sistema do PocketBase
            params["fields"] = "@created,@updated,*"
            hdrs = self._headers()
            resp = requests.get(
                f"{self.pb_url}/api/collections/{col}/records",
                headers=hdrs,
                params=params,
                timeout=30,
            )
            if resp.status_code == 200:
                return resp.json().get("items", [])
            else:
                log.error(f"[CLOUD] GET {col}: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            log.error(f"[CLOUD] GET {col}: {e}")
        return []

    def _post(self, col: str, data: dict) -> Optional[dict]:
        try:
            resp = requests.post(
                f"{self.pb_url}/api/collections/{col}/records",
                headers=self._headers(),
                json=data,
                timeout=30,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            else:
                log.error(f"[CLOUD] POST {col}: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            log.error(f"[CLOUD] POST {col}: {e}")
        return None

    def _patch(self, col: str, record_id: str, data: dict) -> bool:
        try:
            resp = requests.patch(
                f"{self.pb_url}/api/collections/{col}/records/{record_id}",
                headers=self._headers(),
                json=data,
                timeout=30,
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            log.error(f"[CLOUD] PATCH {col}: {e}")
        return False

    # ── Planilhas ─────────────────────────────────────────────────────────────

    def salvar_planilha_recebida(self, casa: str, nome_arquivo: str,
                                  enviado_por: str, total_itens: int,
                                  valor_total: float,
                                  arquivo_path: str = None) -> Optional[str]:
        """
        Registra nova planilha recebida.
        Se arquivo_path fornecido, faz upload do arquivo para o PocketBase.
        Retorna o ID criado.
        """
        # Cria o registro primeiro
        rec = self._post("planilhas", {
            "casa":         casa,
            "nome_arquivo": nome_arquivo,
            "enviado_por":  enviado_por,
            "total_itens":  total_itens,
            "total_valor":  valor_total,
            "status":       STATUS_RECEBIDO,
            "recebido_em":  datetime.now().strftime("%d/%m/%Y %H:%M"),
        })
        if not rec:
            return None

        pid = rec["id"]

        # Faz upload do arquivo se fornecido
        if arquivo_path:
            self.upload_arquivo(pid, arquivo_path)

        self._registrar_historico(pid, casa, "planilha_recebida",
                                   enviado_por, f"{total_itens} itens", valor_total)
        return pid

    def upload_arquivo(self, planilha_id: str, arquivo_path: str) -> bool:
        """Faz upload do arquivo Excel para o PocketBase."""
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
                    timeout=30,
                )
            ok = resp.status_code in (200, 201)
            if ok:
                log.info(f"[CLOUD] Upload OK: {nome} → {planilha_id}")
            else:
                log.error(f"[CLOUD] Upload erro: {resp.status_code} {resp.text[:100]}")
            return ok
        except Exception as e:
            log.error(f"[CLOUD] Upload exceção: {e}")
            return False

    def download_arquivo(self, planilha_id: str, destino_dir: str) -> Optional[str]:
        """
        Baixa o arquivo Excel do PocketBase para o diretório destino.
        Retorna o caminho do arquivo baixado ou None.
        """
        try:
            import os
            token = self._get_token()
            if not token:
                return None

            headers = {"Authorization": f"Bearer {token}"}

            # Busca o registro para obter o nome do arquivo
            resp = requests.get(
                f"{self.pb_url}/api/collections/planilhas/records/{planilha_id}",
                headers=headers,
                timeout=10,
            )
            if resp.status_code != 200:
                return None

            rec       = resp.json()
            arquivo   = rec.get("arquivo")
            if not arquivo:
                return None

            # URL de download do PocketBase
            url = f"{self.pb_url}/api/files/planilhas/{planilha_id}/{arquivo}"
            resp2 = requests.get(url, headers=headers, timeout=30)
            if resp2.status_code != 200:
                return None

            # Salva o arquivo localmente
            os.makedirs(destino_dir, exist_ok=True)
            caminho = os.path.join(destino_dir, arquivo)
            with open(caminho, "wb") as f:
                f.write(resp2.content)

            log.info(f"[CLOUD] Download OK: {arquivo} → {caminho}")
            return caminho

        except Exception as e:
            log.error(f"[CLOUD] Download exceção: {e}")
            return None

    def iniciar_lancamento(self, planilha_id: str, usuario: str) -> bool:
        """Marca planilha como em lançamento (trava para outros)."""
        ok = self._patch("planilhas", planilha_id, {
            "status":      STATUS_EM_LANCAMENTO,
            "lancado_por": usuario,
        })
        if ok:
            self._registrar_historico(planilha_id, "", "lancamento_iniciado", usuario)
        return ok

    def confirmar_lancamento(self, planilha_id: str, casa: str,
                              usuario: str, ok: int, erros: int,
                              valor_total: float) -> bool:
        """Confirma lançamento no ERP."""
        status  = STATUS_LANCADO if erros == 0 else STATUS_RECEBIDO
        result  = self._patch("planilhas", planilha_id, {
            "status":     status,
            "lancado_por": usuario,
            "lancado_em": datetime.now().isoformat(),
        })
        if result:
            acao = "lancamento_concluido" if erros == 0 else "lancamento_erro"
            self._registrar_historico(
                planilha_id, casa, acao, usuario,
                f"ok={ok} erros={erros}", valor_total)
        return result

    def confirmar_cnab_gerado(self, planilha_id: str, casa: str,
                               usuario: str, valor_total: float) -> bool:
        """Marca CNAB como gerado."""
        result = self._patch("planilhas", planilha_id, {
            "status":          STATUS_CNAB_GERADO,
            "cnab_gerado_por": usuario,
            "cnab_gerado_em":  datetime.now().isoformat(),
        })
        if result:
            self._registrar_historico(planilha_id, casa, "cnab_gerado",
                                       usuario, "Arquivo .rem gerado", valor_total)
        return result

    def confirmar_cnab_enviado(self, planilha_id: str, casa: str,
                                usuario: str) -> bool:
        """Marca CNAB como enviado ao Itaú."""
        result = self._patch("planilhas", planilha_id, {
            "status": STATUS_CNAB_ENVIADO,
        })
        if result:
            self._registrar_historico(planilha_id, casa, "cnab_enviado_itau", usuario)
        return result

    def registrar_aprovacao(self, planilha_id: str, casa: str,
                             aprovado_por: str, aprovado: bool,
                             motivo: str = "") -> bool:
        """Registra aprovação ou reprovação do Diretor."""
        status = STATUS_APROVADA if aprovado else STATUS_REPROVADA
        data   = {
            "status":      status,
            "aprovado_por": aprovado_por,
            "aprovado_em": datetime.now().isoformat(),
        }
        if not aprovado and motivo:
            data["motivo_reprovacao"] = motivo

        result = self._patch("planilhas", planilha_id, data)
        if result:
            acao = "aprovado" if aprovado else "reprovado"
            self._registrar_historico(planilha_id, casa, acao,
                                       aprovado_por, motivo)
        return result

    # ── Consultas ─────────────────────────────────────────────────────────────

    def listar_pendencias_lancamento(self) -> list:
        """Planilhas recebidas aguardando lançamento no ERP."""
        return self._get("planilhas", f'status="{STATUS_RECEBIDO}"')

    def listar_pendencias_cnab(self) -> list:
        """Planilhas com ERP lançado aguardando geração de CNAB."""
        return self._get("planilhas", f'status="{STATUS_LANCADO}"')

    def listar_pendencias_aprovacao(self) -> list:
        """Planilhas com CNAB enviado aguardando aprovação."""
        return self._get("planilhas",
            f'status="{STATUS_CNAB_ENVIADO}" || status="{STATUS_CNAB_GERADO}"')

    def listar_todas(self, limit: int = 50) -> list:
        """Lista todas as planilhas recentes."""
        return self._get("planilhas", limit=limit)

    def contar_pendencias(self) -> dict:
        """Retorna contagem por status para badge na tela."""
        try:
            todas = self.listar_todas(limit=200)
            return {
                "lancamento": sum(1 for p in todas if p.get("status") == STATUS_RECEBIDO),
                "cnab":       sum(1 for p in todas if p.get("status") == STATUS_LANCADO),
                "aprovacao":  sum(1 for p in todas
                                  if p.get("status") in (STATUS_CNAB_GERADO, STATUS_CNAB_ENVIADO)),
            }
        except Exception:
            return {"lancamento": 0, "cnab": 0, "aprovacao": 0}

    # ── Notificações ──────────────────────────────────────────────────────────

    def criar_notificacao(self, tipo: str, casa: str, mensagem: str,
                           planilha_id: str = "", destinatario: str = "") -> bool:
        rec = self._post("notificacoes", {
            "tipo":        tipo,
            "casa":        casa,
            "mensagem":    mensagem,
            "planilha_id": planilha_id,
            "destinatario": destinatario,
            "lida":        False,
        })
        return rec is not None

    def listar_notificacoes_nao_lidas(self, destinatario: str = "") -> list:
        filtro = 'lida=false'
        if destinatario:
            filtro += f' && destinatario="{destinatario}"'
        return self._get("notificacoes", filtro, limit=20)

    def marcar_lida(self, notif_id: str, usuario: str) -> bool:
        return self._patch("notificacoes", notif_id, {
            "lida":    True,
            "lida_por": usuario,
            "lida_em": datetime.now().isoformat(),
        })

    # ── Histórico ─────────────────────────────────────────────────────────────

    def _registrar_historico(self, planilha_id: str, casa: str,
                              acao: str, usuario: str,
                              detalhe: str = "", valor: float = 0.0):
        self._post("historico", {
            "planilha_id": planilha_id,
            "casa":        casa,
            "acao":        acao,
            "usuario":     usuario,
            "detalhe":     detalhe,
            "valor_total": valor,
        })

    # ── Configurações ─────────────────────────────────────────────────────────

    def get_config(self, chave: str) -> str:
        """Busca configuração salva no PocketBase."""
        items = self._get("configuracoes", f'chave="{chave}"', limit=1)
        if items:
            return items[0].get("valor", "")
        return ""

    def set_config(self, chave: str, valor: str) -> bool:
        """Atualiza configuração no PocketBase."""
        items = self._get("configuracoes", f'chave="{chave}"', limit=1)
        if items:
            return self._patch("configuracoes", items[0]["id"], {"valor": valor})
        else:
            rec = self._post("configuracoes", {"chave": chave, "valor": valor})
            return rec is not None

    def ping(self) -> bool:
        """Verifica se o PocketBase está acessível."""
        try:
            resp = requests.get(f"{self.pb_url}/api/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False