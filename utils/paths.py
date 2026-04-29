import sys
import os
from pathlib import Path


def base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def app_path(*parts) -> Path:
    return base_path().joinpath(*parts)


def user_data_path(*parts) -> Path:
    """
    Retorna o caminho para dados do usuario.

    - Quando rodando como .exe (frozen): usa APPDATA/Magical_Conciliacao/
      Garante que o banco nao fica dentro da pasta dist/.

    - Quando rodando como script Python (desenvolvimento): usa a pasta do projeto.
    """
    if getattr(sys, "frozen", False):
        # Executavel — salva em APPDATA/Magical_Conciliacao/
        appdata = Path(os.environ.get("APPDATA", str(Path.home())))
        base = appdata / "Magical_Conciliacao"
    else:
        # Desenvolvimento — salva na pasta do projeto
        base = Path(__file__).resolve().parent.parent

    path = base.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path