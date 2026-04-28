from tkinter import messagebox

def erro(msg: str) -> None:
    messagebox.showerror("Erro", msg)

def aviso(msg: str) -> None:
    messagebox.showwarning("Aviso", msg)

def sucesso(msg: str) -> None:
    messagebox.showinfo("Sucesso", msg)
