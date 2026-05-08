"""
verificar_status.py — Verifica e reconfigura webhook + Evolution API
Execute da pasta scripts: python verificar_status.py
"""
import requests
import sqlite3
import os
from pathlib import Path

# Encontra banco automaticamente
POSSIVEIS_DB = [
    Path(__file__).parent.parent / "data" / "conciliacao.db",
    Path(os.environ.get("APPDATA","")) / "Magical_Conciliacao" / "data" / "conciliacao.db",
]
DB_PATH = next((p for p in POSSIVEIS_DB if p.exists()), None)

def get_cfg(chave, default=""):
    if not DB_PATH:
        return default
    try:
        with sqlite3.connect(str(DB_PATH)) as conn:
            row = conn.execute(
                "SELECT valor FROM nuvem_config WHERE chave=? LIMIT 1", (chave,)
            ).fetchone()
            return row[0] if row and row[0] else default
    except Exception:
        return default

EVO_URL     = get_cfg("evo_url", "https://evolution-api-production-cd64.up.railway.app")
API_KEY     = get_cfg("evo_key", "magical_evo_2026")
INSTANCIA   = get_cfg("evo_instancia", "wanderley")
WEBHOOK_URL = "https://magical-webhook-production.up.railway.app/webhook"

headers = {"apikey": API_KEY, "Content-Type": "application/json"}

print(f"EVO_URL:  {EVO_URL}")
print(f"INSTANCIA: {INSTANCIA}")
print()

print("=== 1. Status do WhatsApp ===")
try:
    r = requests.get(
        f"{EVO_URL}/instance/connectionState/{INSTANCIA}",
        headers=headers, timeout=15)
    state = r.json().get("instance", {}).get("state", "?")
    print(f"Estado: {state}")
    if state != "open":
        print("WHATSAPP DESCONECTADO — precisa escanear QR Code!")
        print(f"Acesse: {EVO_URL}/manager")
    else:
        print("OK WhatsApp conectado")
except Exception as e:
    print(f"Erro: {e}")

print("\n=== 2. Status do Webhook ===")
try:
    r2 = requests.get(
        f"{EVO_URL}/webhook/find/{INSTANCIA}",
        headers=headers, timeout=15)
    wh      = r2.json()
    url_wh  = wh.get("url", "")
    enabled = wh.get("enabled", False)
    print(f"URL:    {url_wh}")
    print(f"Ativo:  {enabled}")

    if not enabled or url_wh != WEBHOOK_URL:
        print("Webhook desconfigurado — reconfigurando...")
        r3 = requests.post(
            f"{EVO_URL}/webhook/set/{INSTANCIA}",
            headers=headers,
            json={"webhook": {
                "enabled": True,
                "url": WEBHOOK_URL,
                "webhookByEvents": False,
                "webhookBase64": True,
                "events": ["MESSAGES_UPSERT", "MESSAGES_UPDATE"],
            }},
            timeout=15)
        print(f"Reconfigurado: {r3.status_code}")
    else:
        print("OK Webhook configurado")
except Exception as e:
    print(f"Erro: {e}")

print("\n=== 3. Health do Webhook Server ===")
try:
    r4 = requests.get(
        "https://magical-webhook-production.up.railway.app/health",
        timeout=15)
    print(f"Status: {r4.status_code} — {r4.json()}")
except Exception as e:
    print(f"Erro: {e}")

print("\n=== 4. Grupos mapeados no webhook ===")
try:
    r5 = requests.get(
        "https://magical-webhook-production.up.railway.app/",
        timeout=15)
    data = r5.json()
    print(f"Grupos mapeados: {data.get('grupos_mapeados', 0)}")
    print(f"Casas: {data.get('casas', [])}")
    print(f"Grupo teste: {data.get('grupo_teste', 'nao configurado')}")
except Exception as e:
    print(f"Erro: {e}")

print("\nPronto!")