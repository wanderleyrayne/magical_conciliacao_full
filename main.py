from utils.paths import user_data_path
from database.db import DatabaseManager
import tkinter as tk
from ui.splash import SplashScreen
from ui.main_window import MainWindow


def main():
    db_file = user_data_path("data", "conciliacao.db")
    DatabaseManager(str(db_file))

    # Backup automático diário — antes de qualquer outra operação
    try:
        from backup import auto_backup
        auto_backup(label="auto")
    except Exception:
        pass

    splash_root = tk.Tk()
    SplashScreen(splash_root)
    splash_root.mainloop()

    root = tk.Tk()
    MainWindow(root)

    # Verifica atualizações silenciosamente 3 segundos após iniciar
    # (silent=True → só mostra popup se tiver versão nova)
    try:
        from updater import check_for_updates
        root.after(3000, lambda: check_for_updates(root, silent=True))
    except Exception:
        pass  # updater indisponível não impede o sistema de funcionar

    root.mainloop()


if __name__ == "__main__":
    main()