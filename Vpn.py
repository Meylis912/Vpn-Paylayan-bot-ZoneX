import logging
import os
import time
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from pymongo import MongoClient

# ---------------- FLASK ----------------
flask_app = Flask(__name__)

RENDER_URL = "https://vpn-bot-z9rj.onrender.com"

@flask_app.route("/")
def home():
    return "Bot is Alive!", 200


def self_ping():
    time.sleep(20)
    print("Anti-Sleep aktif...")
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
            print("Ping OK")
        except Exception as e:
            print(f"Ping error: {e}")
        time.sleep(300)


# ---------------- LOGGING ----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ---------------- BOT SETTINGS ----------------
BOT_TOKEN = "7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y"
KURUCU_ID = 7523674506

# ---------------- MONGO ----------------
MONGO_URI = "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/vpn_telegram_bot?retryWrites=true&w=majority&appName=Cluster1"

mongo_client = MongoClient(MONGO_URI)
db = mongo_client["vpn_telegram_bot"]
db_adminler = db["adminler"]
db_kanallar = db["kanallar"]

# ---------------- HELPERS ----------------
def admin_mi(user_id):
    if user_id == KURUCU_ID:
        return True
    return db_adminler.find_one({"user_id": int(user_id)}) is not None


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not admin_mi(user_id):
        await update.message.reply_text("⛔ Giriş gadagan!")
        return

    context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("🔗 VPN Paýlaş", callback_data="menu_vpn")],
        [InlineKeyboardButton("➕ Kanal Goş", callback_data="menu_add_channel")],
        [InlineKeyboardButton("📊 Statistika", callback_data="menu_stats")]
    ]

    if user_id == KURUCU_ID:
        keyboard.append([
            InlineKeyboardButton("👤 Admin Goş", callback_data="menu_add_admin")
        ])

    await update.message.reply_text(
        "VPN Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ---------------- MESSAGE HANDLER ----------------
async def sms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not admin_mi(user_id):
        return

    text = update.message.text.strip()
    isleg = context.user_data.get("isleg")

    # ---------- KANAL EKLEME FIX ----------
    if "|" in text and "-100" in text:
        try:
            parts = text.split("|")

            if len(parts) < 2:
                await update.message.reply_text("❌ Format: -100ID | link")
                return

            k_id = int(parts[0].strip())
            k_link = parts[1].strip()

            # ❗ DUPLICATE CHECK (EN ÖNEMLİ FIX)
            if db_kanallar.find_one({"kanal_id": k_id}):
                await update.message.reply_text("⚠️ Bu kanal zaten eklenmiş!")
                return

            # Telegram test
            try:
                msg = await context.bot.send_message(chat_id=k_id, text="test")
                await context.bot.delete_message(chat_id=k_id, message_id=msg.message_id)
            except TelegramError:
                await update.message.reply_text("❌ Bot admin değil veya izin yok!")
                return

            # Mongo insert (overwrite FIXED)
            db_kanallar.insert_one({
                "kanal_id": k_id,
                "kanal_link": k_link
            })

            await update.message.reply_text("✅ Kanal goşuldy!")
            context.user_data.clear()
            return

        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
            return

    # ---------- ADMIN ADD ----------
    if isleg == "add_admin" and user_id == KURUCU_ID:
        if not text.isdigit():
            await update.message.reply_text("❌ ID san bolmaly")
            return

        db_adminler.update_one(
            {"user_id": int(text)},
            {"$setOnInsert": {"paylasim_sayisi": 0}},
            upsert=True
        )

        await update.message.reply_text("✅ Admin goşuldy")
        context.user_data.clear()
        return


# ---------------- CALLBACKS ----------------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    user_id = q.from_user.id
    data = q.data

    if not admin_mi(user_id):
        return

    if data == "menu_add_channel":
        context.user_data["isleg"] = "add_channel"
        await q.message.reply_text("Format: -100ID | link")

    elif data == "menu_add_admin":
        context.user_data["isleg"] = "add_admin"
        await q.message.reply_text("Admin ID yaz")


# ---------------- RUN BOT ----------------
def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, sms))
    app.add_handler(CallbackQueryHandler(buttons))

    app.run_polling(close_loop=False)


# ---------------- MAIN ----------------
if __name__ == "__main__":
    threading.Thread(target=self_ping, daemon=True).start()

    port = int(os.environ.get("PORT", 10000))
    threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=port, use_reloader=False),
        daemon=True
    ).start()

    print("Bot running...")
    run_bot()
