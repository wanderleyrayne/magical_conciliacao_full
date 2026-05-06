"""
reset_evolution.py — Deleta e recria instancia com configuracoes corretas
Execute: python reset_evolution.py
"""

import requests
import json
import time

EVO_URL = "https://evolution-api-production-cd64.up.railway.app"
API_KEY = "magical_evo_2026"

headers = {
    "apikey": API_KEY,
    "Content-Type": "application/json",
}

print("1. Deletando instancia antiga...")
resp = requests.delete(
    f"{EVO_URL}/instance/delete/wanderley",
    headers=headers,
    timeout=15,
)
print(f"   Status: {resp.status_code} — {resp.text[:100]}")

time.sleep(3)

print("\n2. Criando nova instancia...")
payload = {
    "instanceName": "wanderley",
    "integration": "WHATSAPP-BAILEYS",
    "qrcode": True,
    "browser": ["Chrome", "Chrome", "120.0"],
    "syncFullHistory": False,
}

resp = requests.post(
    f"{EVO_URL}/instance/create",
    headers=headers,
    json=payload,
    timeout=15,
)
print(f"   Status: {resp.status_code}")
data = resp.json()
print(f"   Resposta: {json.dumps(data, indent=2)[:400]}")

time.sleep(2)

print("\n3. Conectando e gerando QR Code...")
resp2 = requests.get(
    f"{EVO_URL}/instance/connect/wanderley",
    headers=headers,
    timeout=15,
)
data2 = resp2.json()

qr = (
    data2.get("base64") or
    data2.get("qrcode", {}).get("base64") or
    ""
)

if qr and "data:image" in qr:
    html = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>QR Code WhatsApp</title></head>
<body style="text-align:center;font-family:Arial;padding:40px;background:#111;color:#fff;">
  <h2>Escaneie com WhatsApp</h2>
  <p>WhatsApp > Menu > Dispositivos conectados > Conectar dispositivo</p>
  <img src="{qr}" style="width:320px;border:4px solid #25D366;border-radius:12px;margin:20px">
  <p style="color:#aaa;font-size:13px">Expira em 60s — rode o script novamente se expirar</p>
  <p style="color:#aaa;font-size:12px">Se der erro no WhatsApp: desconecte todos os dispositivos e tente novamente</p>
</body>
</html>""".format(qr=qr)

    with open("qrcode_wanderley.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("   OK - qrcode_wanderley.html gerado!")
    print("   -> Abra no browser e escaneie")
else:
    print(f"   Resposta: {json.dumps(data2, indent=2)[:500]}")