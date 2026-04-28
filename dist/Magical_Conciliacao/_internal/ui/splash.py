import tkinter as tk
from tkinter import ttk
from version import APP_NAME, APP_VERSION, APP_AUTHOR
from datetime import datetime
from pathlib import Path
from utils.paths import app_path

class SplashScreen:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("520x320")
        self.root.overrideredirect(True)
        self.root.configure(bg="#0f172a")

        frame = tk.Frame(root, bg="#0f172a")
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        logo_path = app_path("assets", "logo.png")
        self.logo_img = None
        if logo_path.exists() and logo_path.stat().st_size > 0:
            try:
                self.logo_img = tk.PhotoImage(file=str(logo_path))
                tk.Label(frame, image=self.logo_img, bg="#0f172a").pack(pady=(0, 10))
            except Exception:
                pass

        tk.Label(frame, text=APP_NAME, fg="white", bg="#0f172a", font=("Arial", 18, "bold")).pack(pady=10)
        tk.Label(frame, text=f"Versão {APP_VERSION}", fg="white", bg="#0f172a").pack()
        tk.Label(frame, text=f"Desenvolvido por {APP_AUTHOR}", fg="white", bg="#0f172a").pack()
        tk.Label(frame, text=datetime.now().strftime("%d/%m/%Y %H:%M:%S"), fg="white", bg="#0f172a").pack(pady=10)

        self.progress = ttk.Progressbar(frame, orient="horizontal", length=320, mode="determinate")
        self.progress.pack(pady=20)

        self.status = tk.Label(frame, text="Inicializando...", fg="#cbd5e1", bg="#0f172a")
        self.status.pack()

        self.current = 0
        self.load()

    def load(self):
        if self.current <= 100:
            self.progress["value"] = self.current
            if self.current < 30:
                self.status.config(text="Carregando interface...")
            elif self.current < 60:
                self.status.config(text="Validando componentes...")
            elif self.current < 90:
                self.status.config(text="Preparando módulos...")
            else:
                self.status.config(text="Concluindo...")
            self.current += 5
            self.root.after(40, self.load)
        else:
            self.root.destroy()
