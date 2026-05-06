"""
teste_envio_v2.py — Testa envio com timeout maior
Execute: python teste_envio_v2.py
"""

import requests
import json

EVO_URL   = "https://evolution-api-production-cd64.up.railway.app"
API_KEY   = "magical_evo_2026"
INSTANCIA = "wanderley"
NUMERO    = "5521967503863"

headers = {
    "apikey": API_KEY,
    "Content-Type": "application/json",
}

print("Verificando status...")
resp = requests.get(
    f"{EVO_URL}/instance/connectionState/{INSTANCIA}",
    headers=headers,
    timeout=30,
)
print(f"Status: {resp.json()}")

print("\nEnviando mensagem (timeout=60s)...")
try:
    resp2 = requests.post(
        f"{EVO_URL}/message/sendText/{INSTANCIA}",
        headers=headers,
        json={
            "number": NUMERO,
            "text": "Teste Magical Conciliacao - funcionando!",
            "delay": 0,
        },
        timeout=120,  # aumentado para 60s
    )
    print(f"Status HTTP: {resp2.status_code}")
    print(f"Resposta: {resp2.text[:300]}")
except Exception as e:
    print(f"Erro: {e}")