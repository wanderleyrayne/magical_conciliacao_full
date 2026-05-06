"""
listar_grupos.py — Lista grupos do WhatsApp conectado
Execute: python listar_grupos.py
"""

import requests

EVO_URL   = "https://evolution-api-production-cd64.up.railway.app"
API_KEY   = "magical_evo_2026"
INSTANCIA = "wanderley"

headers = {"apikey": API_KEY}

print("Buscando grupos...")
resp = requests.get(
    f"{EVO_URL}/group/fetchAllGroups/{INSTANCIA}",
    headers=headers,
    params={"getParticipants": "false"},
    timeout=30,
)

print(f"Status: {resp.status_code}")

if resp.status_code == 200:
    grupos = resp.json()
    if grupos:
        print(f"\n{len(grupos)} grupo(s) encontrado(s):\n")
        for g in grupos:
            print(f"  Nome: {g.get('subject', '?')}")
            print(f"  ID:   {g.get('id', '?')}")
            print(f"  Participantes: {g.get('size', '?')}")
            print()
    else:
        print("Nenhum grupo encontrado.")
else:
    print(f"Erro: {resp.text[:200]}")