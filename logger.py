"""
logger.py — Sistema de log do Magical Conciliação.

Grava em: %APPDATA%\Magical_Conciliacao\logs\magical_YYYY-MM-DD.log
Rotação diária automática, mantém últimos 30 dias.

Uso:
    from logger import log
    log.info("Mensagem")
    log.erro("Erro ao chamar API", exc=e, payload={"campo": "valor"})
    log.api("POST /financials", status=200, payload=p, resposta=r)
    log.lancamento("MAGICAL", "planilha.xlsx", "/path/to/planilha.xlsx", ok=5, erros=0)
    log.conciliacao("run_2", ok=120, erros=3)
    log.atualizacao("3.4.0", "3.5.0")
"""

import os
import sys
import json
import logging
import getpass
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def _log_dir() -> Path:
    if getattr(sys, "frozen", False):
        appdata = Path(os.environ.get("APPDATA", Path.home()))
        base = appdata / "Magical_Conciliacao"
    else:
        base = Path(__file__).resolve().parent
    d = base / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME", "desconhecido")


def _fmt_json(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        return str(obj)


class MagicalLogger:
    """Logger centralizado com métodos semânticos por categoria."""

    def __init__(self):
        self._logger = None
        self._user   = _get_user()

    def _get_logger(self) -> logging.Logger:
        if self._logger is not None:
            return self._logger

        logger = logging.getLogger("magical_conciliacao")
        if logger.handlers:
            self._logger = logger
            return logger

        logger.setLevel(logging.DEBUG)

        # Handler de arquivo com rotação diária
        log_file = _log_dir() / f"magical_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = TimedRotatingFileHandler(
            filename=str(log_file),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))

        # Handler de console (desenvolvimento)
        if not getattr(sys, "frozen", False):
            console = logging.StreamHandler()
            console.setLevel(logging.WARNING)
            console.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
            logger.addHandler(console)

        logger.addHandler(file_handler)
        self._logger = logger
        return logger

    # ── Métodos base ─────────────────────────────────────────────────

    def info(self, msg: str, **extra):
        self._get_logger().info(self._fmt(msg, extra))

    def aviso(self, msg: str, **extra):
        self._get_logger().warning(self._fmt(msg, extra))

    def erro(self, msg: str, exc: Exception = None, **extra):
        if exc:
            extra["excecao"] = str(exc)
        self._get_logger().error(self._fmt(msg, extra))

    def _fmt(self, msg: str, extra: dict) -> str:
        base = f"[{self._user}] {msg}"
        if extra:
            partes = []
            for k, v in extra.items():
                if isinstance(v, (dict, list)):
                    partes.append(f"\n  {k}:\n{_fmt_json(v)}")
                else:
                    partes.append(f" | {k}={v}")
            base += "".join(partes)
        return base

    # ── Métodos semânticos ────────────────────────────────────────────

    def api(self, endpoint: str, status: int, payload: dict = None,
            resposta: dict = None, parceiro: str = ""):
        """Log de chamada à API MeEventos."""
        nivel = logging.INFO if str(status).startswith("2") else logging.ERROR
        partes = [f"[API] {parceiro} | {endpoint} | HTTP {status}"]
        if payload:
            partes.append(f"\n  payload:\n{_fmt_json(payload)}")
        if resposta:
            partes.append(f"\n  resposta:\n{_fmt_json(resposta)}")
        self._get_logger().log(nivel, f"[{self._user}] " + "".join(partes))

    def lancamento(self, parceiro: str, planilha: str, caminho: str,
                   ok: int, erros: int, simulado: bool = False,
                   valor_total: float = 0.0):
        """Log de lançamento no ERP."""
        modo = "SIMULAÇÃO" if simulado else "REAL"
        msg  = (
            f"[ERP] {modo} | parceiro={parceiro}"
            f" | planilha={planilha}"
            f" | caminho={caminho}"
            f" | lançados={ok} | erros={erros}"
            f" | valor=R${valor_total:,.2f}"
        )
        nivel = logging.WARNING if erros > 0 else logging.INFO
        self._get_logger().log(nivel, f"[{self._user}] {msg}")

    def lancamento_item(self, parceiro: str, linha: int, status: str,
                        id_api: str = "", payload: dict = None,
                        mensagem: str = ""):
        """Log de item individual do lançamento."""
        nivel = logging.ERROR if status == "ERRO_API" else logging.INFO
        partes = [
            f"[ERP_ITEM] {parceiro} | linha={linha}"
            f" | status={status} | id_api={id_api or '—'}"
        ]
        if mensagem:
            partes.append(f" | msg={mensagem}")
        if payload and status == "ERRO_API":
            partes.append(f"\n  payload:\n{_fmt_json(payload)}")
        self._get_logger().log(nivel, f"[{self._user}] " + "".join(partes))

    def importacao_planilha(self, caminho: str, parceiro: str,
                             total: int, exc: Exception = None):
        """Log de importação de planilha."""
        if exc:
            self._get_logger().error(
                f"[{self._user}] [PLANILHA] ERRO ao importar"
                f" | parceiro={parceiro} | arquivo={caminho}"
                f" | excecao={exc}"
            )
        else:
            self._get_logger().info(
                f"[{self._user}] [PLANILHA] importada"
                f" | parceiro={parceiro} | arquivo={caminho}"
                f" | linhas={total}"
            )

    def conciliacao(self, nome_run: str, ok: int, erros: int,
                    exc: Exception = None):
        """Log de execução de conciliação."""
        if exc:
            self._get_logger().error(
                f"[{self._user}] [CONCILIACAO] ERRO | run={nome_run}"
                f" | excecao={exc}"
            )
        else:
            nivel = logging.WARNING if erros > 0 else logging.INFO
            self._get_logger().log(
                nivel,
                f"[{self._user}] [CONCILIACAO] run={nome_run}"
                f" | conciliados={ok} | erros={erros}"
            )

    def atualizacao(self, versao_atual: str, versao_nova: str,
                    status: str = "iniciada"):
        """Log de atualização do sistema."""
        self._get_logger().info(
            f"[{self._user}] [ATUALIZACAO] {status}"
            f" | de={versao_atual} para={versao_nova}"
        )

    def backup(self, caminho: str, status: str = "criado",
               exc: Exception = None):
        """Log de backup do banco."""
        if exc:
            self._get_logger().error(
                f"[{self._user}] [BACKUP] ERRO | arquivo={caminho}"
                f" | excecao={exc}"
            )
        else:
            self._get_logger().info(
                f"[{self._user}] [BACKUP] {status} | arquivo={caminho}"
            )

    def log_dir(self) -> Path:
        return _log_dir()


# Instância global — importe e use diretamente
log = MagicalLogger()