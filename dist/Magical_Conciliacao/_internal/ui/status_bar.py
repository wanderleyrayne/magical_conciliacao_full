import tkinter as tk
from datetime import datetime

class StatusBar(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg="#e2e8f0")
        self.label = tk.Label(self, text="", bg="#e2e8f0", anchor="w")
        self.label.pack(side="left", padx=10, fill="x", expand=True)
        self.update_clock()

    def set_text(self, text: str) -> None:
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.label.config(text=f"{text} | Data/Hora: {now}")

    def update_clock(self) -> None:
        current = self.label.cget("text")
        if "Data/Hora:" in current:
            prefix = current.split("| Data/Hora:")[0].strip()
        else:
            prefix = "Sistema pronto"
        self.set_text(prefix)
        self.after(1000, self.update_clock)
