# test_bot.py
import os
import telegram

print("--- Iniciando Prueba de Conexión de Telegram ---")

# 1. Cargar las variables de entorno
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not BOT_TOKEN:
    print("❌ ERROR: No se encontró la variable TELEGRAM_BOT_TOKEN.")
    exit(1)

if not CHAT_ID:
    print("❌ ERROR: No se encontró la variable TELEGRAM_CHAT_ID.")
    exit(1)

print(f"Token encontrado: ...{BOT_TOKEN[-6:]}") # Muestra solo los últimos 6
print(f"Chat ID encontrado: {CHAT_ID}")

bot = telegram.Bot(token=BOT_TOKEN)

# --- Prueba 1: Validar el Token ---
try:
    print("\nPrueba 1/2: Verificando el Token con bot.get_me()...")
    me = bot.get_me()
    print(f"✅ Éxito. El token pertenece al bot: {me.first_name} (@{me.username})")
except Exception as e:
    print("\n❌ FALLO EN PRUEBA 1: El Token es INVÁLIDO.")
    print(f"Error: {e}")
    print("--- Prueba fallida ---")
    exit(1)

# --- Prueba 2: Validar el Chat ID y Permisos ---
try:
    print("\nPrueba 2/2: Enviando mensaje de prueba al Chat ID...")
    bot.send_message(chat_id=CHAT_ID, text="Este es un mensaje de prueba de conexión. ¡Funciona! ✅")
    print(f"✅ Éxito. Mensaje enviado al Chat ID {CHAT_ID}.")
except Exception as e:
    print(f"\n❌ FALLO EN PRUEBA 2: El Chat ID es INVÁLIDO o el bot no está en el chat.")
    print(f"Error: {e}")
    print("--- Prueba fallida ---")
    exit(1)

print("\n--- ¡Prueba completada con éxito! ---")
