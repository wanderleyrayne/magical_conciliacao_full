from utils.paths import user_data_path
from database.db import DatabaseManager
import tkinter as tk
from ui.splash import SplashScreen
from ui.main_window import MainWindow


def main():
    db_file = user_data_path("data", "conciliacao.db")
    DatabaseManager(str(db_file))

    splash_root = tk.Tk()
    SplashScreen(splash_root)
    splash_root.mainloop()

    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()