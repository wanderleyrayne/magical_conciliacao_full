"""
setup_evolution_v2.py — Cria instancia WhatsApp e gera QR Code
Execute: python setup_evolution_v2.py
"""

import requests
import json

EVO_URL = "https://evolution-api-production-cd64.up.railway.app"
API_KEY = "magical_evo_2026"

headers = {
    "apikey": API_KEY,
    "Content-Type": "application/json",
}

print("=" * 60)
print("  Evolution API - Setup WhatsApp")
print("=" * 60)

# Gera QR Code da instancia wanderley
print("\nGerando QR Code da instancia 'wanderley'...")

resp = requests.get(
    f"{EVO_URL}/instance/connect/wanderley",
    headers=headers,
    timeout=15,
)

print(f"Status: {resp.status_code}")
data = resp.json()

# Tenta pegar o base64 em diferentes formatos
qr_base64 = (
    data.get("base64") or
    data.get("qrcode", {}).get("base64") or
    data.get("code", "")
)

if qr_base64 and qr_base64.startswith("data:image"):
    html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>QR Code WhatsApp - Wanderley</title>
</head>
<body style="text-align:center; font-family:Arial; padding:40px; background:#111; color:#fff;">
  <h2>Escaneie com o WhatsApp - Wanderley</h2>
  <p>Abra WhatsApp > Dispositivos conectados > Conectar dispositivo</p>
  <img src="{qr}" style="width:300px; border:4px solid #25D366; border-radius:12px; margin:20px;">
  <p style="color:#888;">O QR Code expira em ~60 segundos. Se expirar, rode o script novamente.</p>
</body>
</html>""".format(qr=qr_base64)

    with open("qrcode_wanderley.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("\n  OK - QR Code salvo em: qrcode_wanderley.html")
    print("  -> Abra esse arquivo no browser e escaneie com o WhatsApp!")

elif qr_base64:
    print(f"\nCodigo QR (copie e cole em um decoder online):")
    print(qr_base64[:200])
else:
    print(f"\nResposta completa:")
    print(json.dumps(data, indent=2)[:800])

# Lista instancias
print("\nInstancias ativas:")
resp2 = requests.get(f"{EVO_URL}/instance/fetchInstances", headers=headers, timeout=10)
if resp2.status_code == 200:
    for inst in resp2.json():
        nome   = inst.get("instance", {}).get("instanceName", "?")
        status = inst.get("instance", {}).get("status", "?")
        print(f"  - {nome}: {status}")