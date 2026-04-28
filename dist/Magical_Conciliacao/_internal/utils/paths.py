import sys
from pathlib import Path


def base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def app_path(*parts) -> Path:
    return base_path().joinpath(*parts)


def user_data_path(*parts) -> Path:
    base = Path.cwd()
    path = base.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path