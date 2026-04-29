"""
updater.py — Auto-updater via GitHub Releases.

Fluxo:
  1. Na inicialização, verifica a versão mais recente no GitHub
  2. Se há versão nova, exibe popup perguntando se quer atualizar
  3. Se confirmar, baixa o novo .exe com barra de progresso
  4. Substitui o executável atual e reinicia o programa
  5. Tudo roda em thread separada para não travar a UI

Configuração:
  - GITHUB_REPO em version.py: "usuario/repositorio"
  - O release no GitHub deve ter um asset chamado "Magical_Conciliacao.exe"
  - Para repositório privado: defina GITHUB_TOKEN abaixo

Publicar um release no GitHub:
  1. git tag v3.2.0
  2. git push origin v3.2.0
  3. No GitHub: Releases → Draft new release → escolhe a tag → 
     faz upload do .exe gerado pelo build.bat → Publish release
"""

import os
import sys
import json
import shutil
import tempfile
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from version import APP_VERSION, APP_NAME, GITHUB_REPO

# Token GitHub para repositório privado
# Cole seu token aqui: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# Gere em: github.com → Settings → Developer settings → Personal access tokens → Tokens (classic)
GITHUB_TOKEN = "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"  # ← coloque seu token aqui

# Nome do asset no release do GitHub
ASSET_NAME = "Magical_Conciliacao.exe"

# URL base da API do GitHub
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _parse_version(v: str) -> tuple:
    """Converte "3.2.1" → (3, 2, 1) para comparação."""
    v = v.lstrip("vV").strip()
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0, 0, 0)


def _get_latest_release() -> dict | None:
    """
    Consulta a API do GitHub e retorna info do release mais recente.
    Retorna None em caso de erro.
    """
    try:
        import requests as _req
        headers = {"Accept": "application/vnd.github+json"}
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        resp = _req.get(GITHUB_API, headers=headers, timeout=8)
        if resp.status_code != 200:
            return None

        data = resp.json()
        tag     = data.get("tag_name", "")
        version = tag.lstrip("vV")
        body    = data.get("body", "")   # notas da versão

        # Busca o asset .exe — usa URL da API (funciona em repos privados)
        asset_url = None
        for asset in data.get("assets", []):
            if asset.get("name") == ASSET_NAME:
                # asset["url"] = API endpoint — suporta autenticação
                # asset["browser_download_url"] = link direto — falha em repos privados
                asset_url = asset.get("url")
                break

        return {
            "version":   version,
            "tag":       tag,
            "notes":     body,
            "asset_url": asset_url,
        }
    except Exception:
        return None


def _is_frozen() -> bool:
    """Retorna True se rodando como .exe (PyInstaller)."""
    return getattr(sys, "frozen", False)


def _current_exe() -> Path:
    """Caminho do executável atual."""
    if _is_frozen():
        return Path(sys.executable)
    return Path(sys.argv[0])


def _download_and_replace(asset_url: str, progress_cb=None) -> bool:
    """
    Baixa o novo .exe e substitui o atual.
    progress_cb(pct: int) — callback de progresso 0-100.
    Retorna True se bem-sucedido.
    """
    try:
        import requests as _req
        headers = {
            "Accept":               "application/octet-stream",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

        resp = _req.get(asset_url, headers=headers,
                        stream=True, timeout=120, allow_redirects=True)
        if resp.status_code not in (200, 302):
            return False

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        # Salva em arquivo temporário
        tmp = tempfile.NamedTemporaryFile(
            suffix=".exe", delete=False,
            dir=_current_exe().parent
        )
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)
                downloaded += len(chunk)
                if total and progress_cb:
                    progress_cb(int(downloaded / total * 100))

        tmp.close()
        tmp_path = Path(tmp.name)

        if progress_cb:
            progress_cb(100)

        current = _current_exe()

        if _is_frozen():
            # Renomeia o atual para .old e coloca o novo no lugar
            old_path = current.with_suffix(".old")
            if old_path.exists():
                old_path.unlink()
            current.rename(old_path)
            shutil.move(str(tmp_path), str(current))
        else:
            # Modo desenvolvimento — apenas copia
            shutil.move(str(tmp_path), str(current.parent / ASSET_NAME))

        return True

    except Exception as exc:
        print(f"[updater] Erro no download: {exc}")
        return False


def _restart():
    """Reinicia o executável atual."""
    exe = str(_current_exe())
    if _is_frozen():
        subprocess.Popen([exe])
    sys.exit(0)


# =============================================================================
# POPUP DE ATUALIZAÇÃO
# =============================================================================

class UpdateDialog:
    """
    Janela de atualização com:
    - Versão atual × nova
    - Notas da versão (changelog)
    - Barra de progresso do download
    - Botões Atualizar agora / Lembrar depois
    """

    def __init__(self, parent, release_info: dict):
        self.release  = release_info
        self.win      = tk.Toplevel(parent)
        self.win.title("Atualização disponível")
        self.win.geometry("520x380")
        self.win.resizable(False, False)
        self.win.grab_set()
        self._build()

    def _build(self):
        win = self.win
        r   = self.release

        # Header
        hdr = tk.Frame(win, bg="#1e293b")
        hdr.pack(fill="x")
        tk.Label(hdr, text="🚀  Nova versão disponível",
                 fg="white", bg="#1e293b",
                 font=("Arial", 11, "bold")).pack(side="left", padx=12, pady=10)

        body = tk.Frame(win, padx=20, pady=12)
        body.pack(fill="both", expand=True)

        # Versões
        ver_f = tk.Frame(body, bg="#f8fafc", padx=12, pady=8)
        ver_f.pack(fill="x", pady=(0, 10))
        tk.Label(ver_f, text=f"Versão atual:  {APP_VERSION}",
                 font=("Arial", 10), bg="#f8fafc",
                 fg="#64748b", anchor="w").pack(fill="x")
        tk.Label(ver_f, text=f"Nova versão:   {r['version']}",
                 font=("Arial", 10, "bold"), bg="#f8fafc",
                 fg="#166534", anchor="w").pack(fill="x")

        # Notas da versão
        if r.get("notes"):
            tk.Label(body, text="O que há de novo:",
                     font=("Arial", 9, "bold"),
                     fg="#475569", anchor="w").pack(fill="x", pady=(0, 4))

            txt_f = tk.Frame(body)
            txt_f.pack(fill="both", expand=True, pady=(0, 10))
            txt = tk.Text(txt_f, height=8, wrap="word",
                          font=("Arial", 9),
                          bg="#f8fafc", relief="flat", bd=0)
            sb = ttk.Scrollbar(txt_f, orient="vertical", command=txt.yview)
            txt.configure(yscrollcommand=sb.set)
            txt.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            txt.insert("1.0", r["notes"])
            txt.config(state="disabled")

        # Progresso (oculto até iniciar download)
        self.progress_f = tk.Frame(body)
        self.progress   = ttk.Progressbar(
            self.progress_f, orient="horizontal",
            length=460, mode="determinate")
        self.progress.pack(fill="x")
        self.progress_lbl = tk.Label(
            self.progress_f, text="Baixando...",
            font=("Arial", 8), fg="#475569", anchor="w")
        self.progress_lbl.pack(fill="x", pady=(2, 0))

        # Botões
        btn_f = tk.Frame(win, padx=20, pady=10)
        btn_f.pack(fill="x")

        self.btn_update = ttk.Button(
            btn_f, text="Atualizar agora →",
            command=self._start_update)
        self.btn_update.pack(side="right", padx=(6, 0))

        ttk.Button(btn_f, text="Lembrar depois",
                   command=win.destroy).pack(side="right")

    def _start_update(self):
        asset_url = self.release.get("asset_url")
        if not asset_url:
            messagebox.showerror(
                "Erro",
                "Arquivo de instalação não encontrado no release.\n"
                "Faça o download manual em github.com/{GITHUB_REPO}.",
                parent=self.win)
            return

        self.btn_update.config(state="disabled")
        self.progress_f.pack(fill="x", pady=(0, 8))
        self.win.update()

        def _do_download():
            # Faz backup do banco ANTES de qualquer atualização
            try:
                from backup import pre_update_backup
                pre_update_backup()
            except Exception:
                pass
            def _prog(pct):
                self.win.after(0, lambda: (
                    self.progress.config(value=pct),
                    self.progress_lbl.config(
                        text=f"Baixando... {pct}%")
                ))

            ok = _download_and_replace(asset_url, progress_cb=_prog)

            def _finish():
                if ok:
                    self.progress_lbl.config(
                        text="Download concluído! Reiniciando...",
                        fg="#166534")
                    self.win.after(1500, _restart)
                else:
                    messagebox.showerror(
                        "Erro no download",
                        "Não foi possível baixar a atualização.\n"
                        f"Faça o download manual em:\n"
                        f"github.com/{GITHUB_REPO}/releases",
                        parent=self.win)
                    self.btn_update.config(state="normal")
                    self.progress_f.pack_forget()

            self.win.after(0, _finish)

        threading.Thread(target=_do_download, daemon=True).start()


# =============================================================================
# PONTO DE ENTRADA — chamado no main.py
# =============================================================================

def check_for_updates(parent_root, silent: bool = True):
    """
    Verifica atualizações em thread separada.

    silent=True  → só mostra popup se tiver atualização (comportamento padrão)
    silent=False → mostra sempre (para botão "Verificar atualizações" manual)
    """
    def _check():
        release = _get_latest_release()

        if release is None:
            if not silent:
                parent_root.after(0, lambda: messagebox.showinfo(
                    "Verificação de atualizações",
                    "Não foi possível conectar ao servidor.\n"
                    "Verifique sua conexão com a internet.",
                    parent=parent_root))
            return

        latest  = _parse_version(release["version"])
        current = _parse_version(APP_VERSION)

        if latest > current:
            parent_root.after(
                0, lambda: UpdateDialog(parent_root, release))
        elif not silent:
            parent_root.after(0, lambda: messagebox.showinfo(
                "Verificação de atualizações",
                f"{APP_NAME} está atualizado!\n\nVersão atual: {APP_VERSION}",
                parent=parent_root))

    threading.Thread(target=_check, daemon=True).start()