from notificador import Notificador

n = Notificador(
    evo_url  = "https://evolution-api-production-cd64.up.railway.app",
    api_key  = "magical_evo_2026",
    instancia = "wanderley"
)

# Verifica status
status = n.status_instancia()
print(f"Status: {status}")

# Envia mensagem para você mesmo (teste)
resultado = n.enviar_contato("+5521967503863", "Teste Magical Conciliacao - WhatsApp funcionando!")
print(f"Resultado: {resultado}")