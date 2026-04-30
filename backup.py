"""
backup.py — Backup automático do banco de dados.

Estratégias:
  1. Backup antes de atualização (chamado pelo updater)
  2. Backup periódico (chamado na inicialização — máximo 1x por dia)
  3. Backup manual (botão nas Configurações)

Política de retenção: mantém os últimos N backups, remove os mais antigos.
Local padrão: mesma pasta do banco → data/backups/
"""

import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from utils.paths import user_data_path

# Configurações
MAX_BACKUPS     = 10     # quantos backups manter
BACKUP_INTERVAL = 1      # dias entre backups automáticos
DB_RELATIVE     = ("data", "conciliacao.db")
BACKUP_DIR_REL  = ("data", "backups")


def _db_path() -> Path:
    return user_data_path(*DB_RELATIVE)


def _backup_dir() -> Path:
    d = user_data_path(*BACKUP_DIR_REL)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _backup_filename(label: str = "") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""
    return f"conciliacao_backup_{ts}{suffix}.db"


def _list_backups() -> list:
    """Retorna lista de backups existentes ordenados do mais novo ao mais antigo."""
    d = _backup_dir()
    backups = sorted(
        d.glob("conciliacao_backup_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    return backups


def _rotate(max_keep: int = MAX_BACKUPS):
    """Remove backups antigos além do limite."""
    backups = _list_backups()
    for old in backups[max_keep:]:
        try:
            old.unlink()
        except Exception:
            pass


def make_backup(label: str = "") -> Path | None:
    """
    Cria um backup do banco de dados.
    Usa hot backup via SQLite VACUUM INTO (seguro mesmo com banco aberto).
    Retorna o Path do backup criado, ou None em caso de erro.
    """
    db = _db_path()
    if not db.exists():
        return None

    dest = _backup_dir() / _backup_filename(label)

    try:
        # VACUUM INTO — cópia limpa e consistente mesmo com conexões abertas
        conn = sqlite3.connect(str(db))
        conn.execute(f"VACUUM INTO '{dest}'")
        conn.close()
    except Exception:
        # Fallback: cópia simples se VACUUM INTO não disponível (SQLite < 3.27)
        try:
            shutil.copy2(str(db), str(dest))
        except Exception:
            return None

    _rotate()

    try:
        from logger import log as _log
        _log.backup(str(dest), status=f"criado ({label or 'auto'})")
    except Exception:
        pass

    return dest


def should_backup_today() -> bool:
    """
    Verifica se já foi feito backup hoje (ou no intervalo configurado).
    Usa o backup mais recente como referência.
    """
    backups = _list_backups()
    if not backups:
        return True

    newest = backups[0]
    age = datetime.now() - datetime.fromtimestamp(newest.stat().st_mtime)
    return age > timedelta(days=BACKUP_INTERVAL)


def auto_backup(label: str = "auto") -> Path | None:
    """
    Faz backup automático apenas se necessário (intervalo configurado).
    Retorna o Path do backup ou None se não era necessário / erro.
    """
    if not should_backup_today():
        return None
    return make_backup(label=label)


def pre_update_backup() -> Path | None:
    """
    Backup forçado antes de atualização.
    Sempre executa independente do intervalo.
    """
    return make_backup(label="pre_update")


def list_backups_info() -> list:
    """
    Retorna lista de dicts com info dos backups para exibição na UI.
    """
    result = []
    for p in _list_backups():
        try:
            size_kb = p.stat().st_size / 1024
            mtime   = datetime.fromtimestamp(p.stat().st_mtime)
            result.append({
                "path":     p,
                "name":     p.name,
                "size_kb":  round(size_kb, 1),
                "datetime": mtime.strftime("%d/%m/%Y %H:%M"),
                "label":    _extract_label(p.name),
            })
        except Exception:
            pass
    return result


def _extract_label(filename: str) -> str:
    """Extrai o label do nome do arquivo de backup."""
    # conciliacao_backup_20260427_143022_pre_update.db
    parts = filename.replace("conciliacao_backup_", "").replace(".db", "").split("_")
    if len(parts) > 2:
        return " ".join(parts[2:]).replace("_", " ")
    return "automático"


def restore_backup(backup_path: Path) -> bool:
    """
    Restaura um backup (substitui o banco atual).
    ATENÇÃO: fecha todas as conexões antes de chamar.
    """
    db = _db_path()
    try:
        # Faz backup do estado atual antes de restaurar
        make_backup(label="pre_restore")
        shutil.copy2(str(backup_path), str(db))
        return True
    except Exception:
        return False