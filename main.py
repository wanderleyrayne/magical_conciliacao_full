from utils.paths import user_data_path
from database.db import DatabaseManager
import tkinter as tk
from ui.splash import SplashScreen
from ui.main_window import MainWindow


def main():
    # Aplica config_inicial.json na primeira execucao (sem precisar de Python instalado)
    try:
        from setup_inicial import aplicar_config_inicial
        aplicar_config_inicial()
    except Exception:
        pass

    db_file = user_data_path("data", "conciliacao.db")
    DatabaseManager(str(db_file))

    # Backup automatico diario
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

    # Verifica atualizacoes silenciosamente 3 segundos apos iniciar
    try:
        from updater import check_for_updates
        root.after(3000, lambda: check_for_updates(root, silent=True))
    except Exception:
        pass

    root.mainloop()


if __name__ == "__main__":
    main()