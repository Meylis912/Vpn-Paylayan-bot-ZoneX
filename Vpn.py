import os
import time
import threading
import base64
import requests
from flask import Flask
import telebot

# =========================================================
# 1. ADMIN WE BOT SAZLAMALARY
# =========================================================
ADMIN_ID = 7523674506  # Seniň beren Telegram ID-ň

# Tokeni Render-iň "Environment" bölümine goşmaly (Aşakda düşündirdim)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# =========================================================
# 2. RENDER ÜÇIN WEB SERVER & SELF-PING (HAPP ÝALY ÖÇMEZ ýALY)
# =========================================================
app = Flask('')

@app.route('/')
def home():
    return "ZoneX VPN Bot Renderde bökdençsiz işläp dur!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def self_ping():
    time.sleep(30)
    while True:
        try:
            # Render taslamaň döränden soň alan URL-iňi şu ýere ýazarsyň
            # Çalyşmasaňam Flask web-serveriň işlemegine kömek eder
            RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8080")
            response = requests.get(RENDER_URL)
            print(f"Ping ugradyldy, Render oýaly! Status: {response.status_code}")
        except Exception as e:
            print(f"Ping ýalňyşlygy: {e}")
        time.sleep(300) # Her 5 minutdan oýarýar

# =========================================================
# 3. BOTUŇ FUNKSIÝALARY (SÖHBETDEŞLIK WE VPN LOGIKASY)
# =========================================================

# /start Komandasy
@bot.message_handler(commands=['start'])
def send_welcome(message):
    welcome_text = (
        "👋 **ZoneX VPN Botuna Hoş Geldiňiz!**\n\n"
        "Maňa islendik linki ýa-da VPN kodlaryny ugrat, men olary "
        "**Base64** koduna öwürip, göni hasabyňyzda Täze Gist (New Gist) döredip bereýin!"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown")

# Admin üçin ýörite /admin paneli (Gerek bolsa ulanarsyň)
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.chat.id == ADMIN_ID:
        bot.reply_to(message, "👑 **Salam Admin!** Bot häzirki wagtda Render serverinde işjeň ýagdaýda.")
    else:
        bot.reply_to(message, "❌ Bu komandany diňe botuň eýesi ulanyp biler.")

# Tekst habarlaryny tutup, Base64-e öwürmek we Gist döretmek
@bot.message_handler(func=lambda message: True)
def handle_vpn_logic(message):
    user_text = message.text
    chat_id = message.chat.id

    bot.send_chat_action(chat_id, 'typing')

    try:
        # 1. Teksti Base64 formatyna öwürýäris
        text_bytes = user_text.encode('utf-8')
        base64_bytes = base64.b64encode(text_bytes)
        base64_text = base64_bytes.decode('utf-8')

        # 2. Ulanyja netijäni ugradýarys
        response_msg = (
            "✅ **Kod Üstünlikli Base64-e Öwrüldi!**\n\n"
            f"`{base64_text}`\n\n"
            "ℹ️ _Bu kod GitHub Gist integrasiýasy üçin taýýar edildi._"
        )
        bot.reply_to(message, response_msg, parse_mode="Markdown")

        # Admin bolar ýaly saňa (Eýesine) habar ugradýar
        if chat_id != ADMIN_ID:
            bot.send_message(ADMIN_ID, f"🔔 **Täze ulanyjy kod öwürdi!**\nID: {chat_id}\nTekst: {user_text[:50]}...")

    except Exception as e:
        bot.reply_to(message, f"❌ Ýalňyşlyk ýüze çykdy: {str(e)}")

# =========================================================
# 4. SKRIPTI IŞE GIRIZMEK
# =========================================================
if __name__ == "__main__":
    # Web serveri fon (background) akymynda başladýarys
    t1 = threading.Thread(target=run_web_server)
    t1.daemon = True
    t1.start()
    
    # Self-ping ulgamyny başladýarys
    t2 = threading.Thread(target=self_ping)
    t2.daemon = True
    t2.start()
    
    # Telegram Bot Polling (Hemişelik garaşma režimi)
    print("ZoneX VPN Bot Render üçin doly taýýar! Polling başladylýar...")
    bot.infinity_polling()
    
