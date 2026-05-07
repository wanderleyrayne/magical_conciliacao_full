"""
setup_inicial.py — Aplica config_inicial.json no banco local na primeira execucao.
Chamado automaticamente pelo main.py antes de qualquer outra coisa.
"""

import sqlite3
import json
import sys
import os
from pathlib import Path


def _get_config_path() -> Path:
    """Localiza o config_inicial.json — funciona no .exe e em desenvolvimento."""
    # PyInstaller: arquivos ficam em sys._MEIPASS
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).parent

    return base / "config_inicial.json"


def _get_db_path() -> Path:
    """Retorna o caminho do banco de producao."""
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "Magical_Conciliacao" / "data" / "conciliacao.db"
    return Path("data") / "conciliacao.db"


def aplicar_config_inicial() -> bool:
    """
    Aplica as configuracoes do config_inicial.json no banco local.
    So executa se o banco ainda nao tiver as configs de nuvem.
    Retorna True se aplicou, False se ja estava configurado ou erro.
    """
    config_path = _get_config_path()
    if not config_path.exists():
        return False

    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Verifica se ja tem configs
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS nuvem_config "
                "(chave TEXT PRIMARY KEY, valor TEXT)"
            )
            row = conn.execute(
                "SELECT valor FROM nuvem_config WHERE chave='pb_url' LIMIT 1"
            ).fetchone()

            if row and row[0]:
                return False  # ja configurado

            # Carrega e aplica o JSON
            with open(config_path, encoding="utf-8") as f:
                configs = json.load(f)

            for chave, valor in configs.items():
                conn.execute(
                    "INSERT INTO nuvem_config(chave, valor) VALUES(?,?) "
                    "ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                    (chave, str(valor))
                )
            conn.commit()

        return True

    except Exception as e:
        print(f"[SETUP] Erro ao aplicar config_inicial: {e}")
        return False