"""
updater.py — Verificador e instalador de atualizacoes do Magical Conciliacao.

Melhorias v2:
- SSL tolerante (proxy corporativo, antivirus)
- Timeout configuravel
- Download com barra de progresso
- Cancelamento de download
- Sem travar UI (thread separada)
- Mensagem clara em caso de erro com alternativas
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import logging

log = logging.getLogger("magical_conciliacao")

GITHUB_REPO    = "wanderleyrayne/magical_conciliacao_full"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
TIMEOUT_CHECK  = 15
TIMEOUT_DOWN   = 300  # 5 minutos para arquivos grandes

# Token GitHub opcional — necessario se o repositorio for privado
# Gere em: https://github.com/settings/tokens (scope: repo)
# Salve nas configuracoes do sistema ou defina aqui diretamente
GITHUB_TOKEN   = ""  # ex: "ghp_xxxxxxxxxxxxxxxxxxxx"


def _get_github_token() -> str:
    """Tenta buscar token do banco local, senao usa a constante acima."""
    if GITHUB_TOKEN:
        return GITHUB_TOKEN
    try:
        import sqlite3
        from pathlib import Path
        import os
        candidatos = [
            Path("data/conciliacao.db"),
            Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
        ]
        for db in candidatos:
            if db.exists():
                with sqlite3.connect(str(db)) as conn:
                    row = conn.execute(
                        "SELECT valor FROM app_settings WHERE key='github_token' LIMIT 1"
                    ).fetchone()
                    if row and row[0]:
                        return row[0]
    except Exception:
        pass
    return ""


def _versao_tuple(v: str) -> tuple:
    try:
        return tuple(int(x) for x in str(v).lstrip("vV").split(".")[:3])
    except Exception:
        return (0, 0, 0)


def verificar_atualizacao(versao_atual: str) -> dict:
    import urllib.request, urllib.error, json, ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE

    token = _get_github_token()
    headers = {
        "User-Agent": "MagicalConciliacao-Updater/2.0",
        "Accept":     "application/vnd.github.v3+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req  = urllib.request.Request(GITHUB_API_URL, headers=headers)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT_CHECK, context=ctx)
        data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        # Repositorio privado ou sem conexao — ignora silenciosamente
        log.debug(f"[UPDATER] Verificacao ignorada: {e}")
        return None

    versao_nova = data.get("tag_name", "").lstrip("vV")
    if not versao_nova:
        return None

    if _versao_tuple(versao_nova) <= _versao_tuple(versao_atual):
        return None

    for asset in data.get("assets", []):
        if asset.get("name", "").lower().endswith(".exe"):
            return {
                "versao": versao_nova,
                "url":    asset["browser_download_url"],
                "nome":   asset["name"],
                "notas":  data.get("body", "")[:500],
            }
    return None


def baixar_atualizacao(url, nome, progress_cb=None, cancel_event=None):
    import urllib.request, ssl

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE

    destino = Path.home() / "Downloads" / nome

    try:
        dl_headers = {"User-Agent": "MagicalConciliacao-Updater/2.0"}
        token = _get_github_token()
        if token:
            dl_headers["Authorization"] = f"Bearer {token}"
        req  = urllib.request.Request(url, headers=dl_headers)
        resp = urllib.request.urlopen(req, timeout=TIMEOUT_DOWN, context=ctx)
        total   = int(resp.headers.get("Content-Length", 0))
        baixado = 0

        with open(destino, "wb") as f:
            while True:
                if cancel_event and cancel_event.is_set():
                    destino.unlink(missing_ok=True)
                    return None
                bloco = resp.read(65536)
                if not bloco:
                    break
                f.write(bloco)
                baixado += len(bloco)
                if total > 0 and progress_cb:
                    progress_cb(int(baixado * 100 / total))

        if progress_cb:
            progress_cb(100)
        return destino

    except Exception as e:
        log.error(f"[UPDATER] Erro no download: {e}")
        if destino.exists():
            destino.unlink(missing_ok=True)
        return None


class UpdaterDialog:
    def __init__(self, master, versao_atual, info, on_close=None):
        self.master       = master
        self.versao_atual = versao_atual
        self.info         = info
        self.on_close     = on_close
        self._cancel      = threading.Event()

        self.win = tk.Toplevel(master)
        self.win.title("Atualizacao disponivel")
        self.win.geometry("480x340")
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._fechar)
        self._build()

    def _build(self):
        hdr = tk.Frame(self.win, bg="#1e293b", pady=14)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Nova versao disponivel!",
                 bg="#1e293b", fg="white",
                 font=("Arial", 13, "bold")).pack()
        tk.Label(hdr, text=f"v{self.versao_atual}  ->  v{self.info['versao']}",
                 bg="#1e293b", fg="#94a3b8", font=("Arial", 10)).pack(pady=(2,0))

        body = tk.Frame(self.win, padx=20, pady=12)
        body.pack(fill="both", expand=True)

        if self.info.get("notas"):
            tk.Label(body, text="O que ha de novo:", font=("Arial", 9, "bold"), anchor="w").pack(fill="x")
            txt = tk.Text(body, height=7, wrap="word", font=("Arial", 9),
                          relief="flat", bg="#f8fafc", fg="#334155")
            txt.pack(fill="both", expand=True, pady=(4, 10))
            txt.insert("1.0", self.info["notas"])
            txt.config(state="disabled")

        self.lbl = tk.Label(body, text="Pronto para baixar.", fg="#475569", font=("Arial", 9))
        self.lbl.pack(anchor="w")
        self.bar = ttk.Progressbar(body, length=440, mode="determinate")
        self.bar.pack(fill="x", pady=(4, 0))

        bf = tk.Frame(self.win, pady=12)
        bf.pack()
        self.btn = ttk.Button(bf, text="Baixar e instalar", command=self._baixar)
        self.btn.pack(side="left", padx=8)
        ttk.Button(bf, text="Agora nao", command=self._fechar).pack(side="left", padx=8)

    def _baixar(self):
        self.btn.config(state="disabled")
        self.lbl.config(text="Conectando...", fg="#2563eb")
        self.bar.config(mode="indeterminate")
        self.bar.start(10)
        self._cancel.clear()

        def _run():
            def _prog(p):
                try:
                    def _upd(pct=p):
                        self.bar.stop()
                        self.bar.config(mode="determinate", value=pct)
                        mb_total = 56  # aprox
                        mb_baixado = pct * mb_total / 100
                        self.lbl.config(
                            text=f"Baixando... {pct}%  ({mb_baixado:.0f}/{mb_total} MB)",
                            fg="#2563eb"
                        )
                    self.win.after(0, _upd)
                except Exception:
                    pass

            path = baixar_atualizacao(
                self.info["url"], self.info["nome"],
                progress_cb=_prog, cancel_event=self._cancel)

            if path:
                self.win.after(0, lambda p=path: self._ok(p))
            else:
                self.win.after(0, self._erro)

        threading.Thread(target=_run, daemon=True).start()

    def _ok(self, path):
        self.lbl.config(text=f"Salvo em: {path.parent}", fg="#166534")
        self.bar.config(value=100)
        if messagebox.askyesno("Download concluido",
            f"Salvo em:\n{path}\n\nAbrir pasta Downloads?\n\n"
            "Feche o sistema e execute o novo .exe para atualizar.",
            parent=self.win):
            import subprocess
            subprocess.Popen(f'explorer "{path.parent}"')
        self._fechar()

    def _erro(self):
        self.lbl.config(text="Erro no download.", fg="#dc2626")
        self.btn.config(state="normal")
        messagebox.showerror("Erro no download",
            "Nao foi possivel baixar automaticamente.\n\n"
            "Alternativas:\n"
            f"1. github.com/{GITHUB_REPO}/releases\n"
            "2. Baixe o .exe manualmente\n"
            "3. Verifique antivirus ou proxy da empresa",
            parent=self.win)

    def _fechar(self):
        self._cancel.set()
        if self.on_close:
            self.on_close()
        self.win.destroy()


def verificar_em_background(master, versao_atual, silencioso=True):
    """Verifica atualizacao em background sem travar a UI."""
    def _run():
        info = verificar_atualizacao(versao_atual)
        def _ui():
            if info:
                UpdaterDialog(master, versao_atual, info)
            elif not silencioso:
                messagebox.showinfo("Sem atualizacoes",
                    f"Voce ja esta na versao mais recente ({versao_atual}).",
                    parent=master)
        try:
            master.after(0, _ui)
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()