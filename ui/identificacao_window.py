"""
identificacao_window.py — Tela de identificação na primeira abertura.
Usa queue para comunicação thread-safe entre busca PocketBase e UI Tkinter.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import re
import threading
import queue


class IdentificacaoWindow:
    def __init__(self, master, db_path: str, on_success=None):
        self.db_path    = db_path
        self.on_success = on_success
        self.resultado  = None
        self._queue     = queue.Queue()

        self.win = tk.Toplevel(master)
        self.win.title("Magical Conciliação — Identificação")
        self.win.geometry("420x320")
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.protocol("WM_DELETE_WINDOW", self._on_fechar)

        self.win.update_idletasks()
        x = (master.winfo_screenwidth()  - 420) // 2
        y = (master.winfo_screenheight() - 320) // 2
        self.win.geometry(f"420x320+{x}+{y}")

        self._build_ui()
        self._poll_queue()

    def _poll_queue(self):
        try:
            while True:
                msg = self._queue.get_nowait()
                if msg[0] == "ok":
                    _, num, nome, perfil = msg
                    self._aplicar_perfil(num, nome, perfil)
                elif msg[0] == "erro":
                    _, texto = msg
                    self._erro(texto)
        except queue.Empty:
            pass
        if self.win.winfo_exists():
            self.win.after(100, self._poll_queue)

    def _build_ui(self):
        hdr = tk.Frame(self.win, bg="#1e293b", pady=16)
        hdr.pack(fill="x")
        tk.Label(hdr, text="Magical Conciliação",
                 bg="#1e293b", fg="white",
                 font=("Arial", 14, "bold")).pack()
        tk.Label(hdr, text="Identificação do usuário",
                 bg="#1e293b", fg="#94a3b8",
                 font=("Arial", 9)).pack()

        body = tk.Frame(self.win, pady=20, padx=30)
        body.pack(fill="both", expand=True)

        tk.Label(body,
                 text="Para continuar, informe seu número de WhatsApp.\nIsso será feito apenas uma vez.",
                 justify="center", fg="#475569", wraplength=340).pack(pady=(0, 16))

        tk.Label(body, text="Número WhatsApp:", anchor="w").pack(fill="x")

        num_frame = tk.Frame(body)
        num_frame.pack(fill="x", pady=(4, 0))
        tk.Label(num_frame, text="+55", fg="#64748b").pack(side="left")

        self.num_var = tk.StringVar()
        self.num_entry = ttk.Entry(num_frame, textvariable=self.num_var,
                                   width=25, font=("Arial", 12))
        self.num_entry.pack(side="left", padx=6)
        self.num_entry.focus()
        self.num_entry.bind("<Return>", lambda e: self._confirmar())

        tk.Label(body, text="Aceita: 967503863 / 21967503863 / 5521967503863",
                 fg="#94a3b8", font=("Arial", 8)).pack(anchor="w", pady=(2, 0))

        self.lbl_status = tk.Label(body, text="", fg="#dc2626", font=("Arial", 9))
        self.lbl_status.pack(pady=(8, 0))

        self.btn = ttk.Button(body, text="Confirmar →", command=self._confirmar)
        self.btn.pack(pady=(12, 0))

    def _confirmar(self):
        raw = self.num_var.get().strip()
        num = re.sub(r"\D", "", raw)

        # Normaliza para 13 dígitos (55 + DDD + 9 dígitos)
        if len(num) == 9:
            num = "5521" + num  # assume DDD 21
        elif len(num) == 10 or len(num) == 11:
            num = "55" + num
        elif num.startswith("55"):
            pass  # já tem DDI
        else:
            num = "55" + num

        if len(num) < 12:
            self.lbl_status.config(
                text="Número inválido. Digite DDD + número (ex: 21967503863)")
            return

        self.lbl_status.config(text="Buscando perfil...", fg="#2563eb")
        self.btn.config(state="disabled")

        def _buscar():
            try:
                perfil, nome = self._buscar_pocketbase(num)
                self._queue.put(("ok", num, nome, perfil))
            except Exception as e:
                self._queue.put(("erro", str(e)))

        threading.Thread(target=_buscar, daemon=True).start()

    def _buscar_pocketbase(self, numero: str):
        import requests

        pb_url   = self._get_cfg("pb_url")
        pb_email = self._get_cfg("pb_email")
        pb_senha = self._get_cfg("pb_senha")

        if not pb_url:
            raise Exception("PocketBase não configurado.\nEntre em contato com o administrador.")

        resp = requests.post(
            f"{pb_url}/api/collections/_superusers/auth-with-password",
            json={"identity": pb_email, "password": pb_senha},
            timeout=30,
        )
        if resp.status_code != 200:
            raise Exception("Erro ao conectar com o servidor.")

        token   = resp.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp2 = requests.get(
            f"{pb_url}/api/collections/usuarios/records",
            headers=headers,
            params={"perPage": 50},
            timeout=30,
        )
        usuarios = resp2.json().get("items", [])

        # Compara pelos últimos 9 dígitos
        sufixo = re.sub(r"\D", "", numero)[-9:]

        for u in usuarios:
            wpp = re.sub(r"\D", "", str(u.get("whatsapp", "")))
            if wpp and wpp[-9:] == sufixo:
                return u.get("perfil", "operacional_erp"), u.get("nome", "")

        raise Exception("Número não encontrado.\nEntre em contato com o administrador.")

    def _aplicar_perfil(self, numero: str, nome: str, perfil: str):
        self._save_cfg("meu_nome",   nome)
        self._save_cfg("meu_perfil", perfil)
        self._save_cfg("meu_numero", numero)

        self.resultado = {"nome": nome, "perfil": perfil, "numero": numero}

        messagebox.showinfo(
            "Bem-vindo!",
            f"Olá, {nome}!\n\nPerfil: {perfil}\n\nSua identificação foi salva.\nEsta tela não aparecerá novamente.",
            parent=self.win,
        )

        if self.on_success:
            self.on_success(self.resultado)

        self.win.destroy()

    def _erro(self, msg: str):
        self.lbl_status.config(text=msg, fg="#dc2626")
        self.btn.config(state="normal")

    def _on_fechar(self):
        if not self.resultado:
            if not messagebox.askyesno("Sair",
                "Você precisa se identificar para usar o sistema.\n\nDeseja sair?",
                parent=self.win):
                return
        self.win.destroy()

    def _get_cfg(self, chave: str, default: str = "") -> str:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS nuvem_config (chave TEXT PRIMARY KEY, valor TEXT)")
                row = conn.execute(
                    "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
                ).fetchone()
                return row[0] if row and row[0] else default
        except Exception:
            return default

    def _save_cfg(self, chave: str, valor: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS nuvem_config (chave TEXT PRIMARY KEY, valor TEXT)")
                conn.execute(
                    "INSERT INTO nuvem_config(chave,valor) VALUES(?,?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                    (chave, valor)
                )
                conn.commit()
        except Exception:
            pass


def verificar_identificacao(root, db_path: str) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS nuvem_config (chave TEXT PRIMARY KEY, valor TEXT)")
            row = conn.execute(
                "SELECT valor FROM nuvem_config WHERE chave='meu_numero' LIMIT 1"
            ).fetchone()
            if row and row[0]:
                return True
    except Exception:
        pass

    resultado = [None]

    def on_success(r):
        resultado[0] = r

    win = IdentificacaoWindow(root, db_path, on_success=on_success)
    root.wait_window(win.win)

    return resultado[0] is not None