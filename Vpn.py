import os
import time
import threading
import requests
from flask import Flask
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ======================
# 🌐 FLASK (ALIVE SERVER)
# ======================
app_flask = Flask(__name__)

# Render URL-i göni setir hökmünde goýduk ýa-da os.getenv içindäki default baha geçirdik
RENDER_URL = os.getenv("RENDER_URL", "https://vpn-bot-z9rj.onrender.com")

@app_flask.route("/")
def home():
    return "Bot is Alive!", 200

def keep_alive():
    time.sleep(15)
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
        except Exception:
            pass
        time.sleep(300)

# ======================
# 🔐 CONFIG (Kompakt sazlamalar)
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y")
KURUCU_ID = int(os.getenv("KURUCU_ID", "7523674506"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")

mongo = MongoClient(MONGO_URI)
db = mongo["vpn_bot"]
admins = db["admins"]
channels = db["channels"]

# ======================
# 👮 ADMIN CHECK
# ======================
def is_admin(user_id):
    if user_id == KURUCU_ID:
        return True
    return admins.find_one({"user_id": user_id}) is not None

# ======================
# 🚀 START
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text("⛔ Size rugsat berilmedi!")
        return

    keyboard = [
        [InlineKeyboardButton("🔗 VPN Paýlaş", callback_data="vpn")],
        [InlineKeyboardButton("➕ Kanal Goş", callback_data="add")]
    ]

    await update.message.reply_text(
        "🤖 VPN BOT PANEL",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================
# 💬 TEXT HANDLER
# ======================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        return

    state = context.user_data.get("state")
    text = update.message.text

    # ➕ KANAL GOŞMAK
    if state == "ADD":
        try:
            cid, link = text.split("|")
            channels.update_one(
                {"channel_id": cid.strip()},
                {"$set": {"link": link.strip()}},
                upsert=True
            )
            await update.message.reply_text("✅ Kanal üstünlikli goşuldy!")
            context.user_data.clear()
        except Exception:
            await update.message.reply_text("❌ Format ýalňyş! Format: ID | link")

    # 🔗 VPN LINK SORAMAK
    elif state == "VPN":
        context.user_data["vpn"] = text
        context.user_data["state"] = "DESC"
        await update.message.reply_text("📝 Indi bolsa düşündirişini (Description) ugradyň:")

    # 📝 DESC VE GÖNI SEND (Hemmesine Awto-Ugratmak)
    elif state == "DESC":
        context.user_data["desc"] = text
        await ugrat_prosesi(update, context)

# ======================
# 🚀 SEND PROCESS (Awtomatiki ugratmak we Hasabat)
# ======================
async def ugrat_prosesi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vpn = context.user_data.get("vpn")
    desc = context.user_data.get("desc")
    
    status_msg = await update.message.reply_text("⏳ VPN kanallara ugradylýar, garaşyň...")

    all_channels = list(channels.find({}))
    if not all_channels:
        await status_msg.edit_text("❌ Binada hiç hili kanal tapylmady. Ilki kanal goşuň!")
        context.user_data.clear()
        return

    ok_channels = []
    fail_channels = []

    for c in all_channels:
        cid = c["channel_id"]
        clink = c.get("link", f"ID: {cid}")
        try:
            # Kanallara ugratmak (Kanal ID int ýa-da string bolup bilýär, şona görä barlap ugradýar)
            chat_target = int(cid) if cid.strip().replace('-', '').isdigit() else cid.strip()
            await context.bot.send_message(
                chat_id=chat_target,
                text=f"{vpn}\n\n{desc}"
            )
            ok_channels.append(f"🟢 {clink}")
        except Exception as e:
            fail_channels.append(f"🔴 {clink} (Rugsat ýok/Bot admin däl)")

    # Hasabat taýýarlamak
    report = "📊 **PAÝLAŞYÝAN NETIJESI:**\n\n"
    
    if ok_channels:
        report += "✅ **Şowluy ugradylan kanallar:**\n" + "\n".join(ok_channels) + "\n\n"
    else:
        report += "✅ **Şowluy ugradylan kanallar:** Hiç birine gitmedi.\n\n"
        
    if fail_channels:
        report += "❌ **Ugradyp bilinmedik kanallar (Rugsat ýok):**\n" + "\n".join(fail_channels)
    else:
        report += "❌ **Ugradyp bilinmedik kanallar:** Ýok, hemmesine gitdi."

    await status_msg.edit_text(report, parse_mode="Markdown")
    context.user_data.clear()

# ======================
# 🔘 CALLBACKS
# ======================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    if not is_admin(uid):
        return

    data = q.data

    # ➕ KANAL GOŞ düwmesi
    if data == "add":
        context.user_data["state"] = "ADD"
        await q.message.reply_text("Kanal maglumatyny ugradyň:\nFormat: `Kanal_ID | Kanal_Linki`", parse_mode="Markdown")
        return

    # 🔗 VPN PAÝLAŞ düwmesi
    if data == "vpn":
        context.user_data["state"] = "VPN"
        await q.message.reply_text("🔗 Göni VPN linkini ugradyň:")
        return

# ======================
# 🤖 RUN BOT
# ======================
def run():
    # Import düzedildi (İmport -> import)
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callback))

    print("Bot işläp dur...")
    app.run_polling()

# ======================
# 🚀 MAIN
# ======================
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=lambda: app_flask.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))), daemon=True).start()
    run()
    
