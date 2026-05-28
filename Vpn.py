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

RENDER_URL = os.getenv("https://vpn-bot-z9rj.onrender.com")

@app_flask.route("/")
def home():
    return "Bot is Alive!", 200

def keep_alive():
    time.sleep(15)
    while True:
        try:
            requests.get(RENDER_URL, timeout=10)
        except:
            pass
        time.sleep(300)

# ======================
# 🔐 CONFIG (ONLY ONCE!)
# ======================
BOT_TOKEN = os.getenv("7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y")
KURUCU_ID = int(os.getenv("7523674506"))

MONGO_URI = os.getenv("mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")

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
        await update.message.reply_text("⛔ You are not allowed!")
        return

    keyboard = [
        [InlineKeyboardButton("🔗 VPN Share", callback_data="vpn")],
        [InlineKeyboardButton("➕ Add Channel", callback_data="add")]
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

    # ➕ ADD CHANNEL
    if state == "ADD":
        try:
            cid, link = text.split("|")

            channels.update_one(
                {"channel_id": cid.strip()},
                {"$set": {"link": link.strip()}},
                upsert=True
            )

            await update.message.reply_text("✅ Channel added!")
            context.user_data.clear()
        except:
            await update.message.reply_text("❌ Format: ID | link")

    # 🔗 VPN LINK
    elif state == "VPN":
        context.user_data["vpn"] = text
        context.user_data["state"] = "DESC"
        await update.message.reply_text("📝 Send description")

    # 📝 DESC
    elif state == "DESC":
        context.user_data["desc"] = text
        context.user_data["selected"] = set()
        await vpn_panel(update, context)

# ======================
# 📡 VPN PANEL
# ======================
async def vpn_panel(update, context):
    data = list(channels.find({}))
    selected = context.user_data.get("selected", set())

    keyboard = [
        [
            InlineKeyboardButton("🚀 SEND", callback_data="send"),
            InlineKeyboardButton("✅ ALL", callback_data="all")
        ]
    ]

    for c in data:
        cid = str(c["channel_id"])
        mark = "🟢" if cid in selected else "🔴"

        keyboard.append([
            InlineKeyboardButton(
                f"{mark} {c['link']}",
                callback_data=f"t_{cid}"
            )
        ])

    text = f"🔗 {context.user_data.get('vpn')}\n📝 {context.user_data.get('desc')}"

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

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
    selected = context.user_data.get("selected", set())

    # ➕ ADD CHANNEL
    if data == "add":
        context.user_data["state"] = "ADD"
        await q.message.reply_text("Send: ID | link")
        return

    # 🔗 VPN
    if data == "vpn":
        context.user_data["state"] = "VPN"
        await q.message.reply_text("Send VPN link")
        return

    # 🔘 TOGGLE
    if data.startswith("t_"):
        cid = data.replace("t_", "")

        if cid in selected:
            selected.remove(cid)
        else:
            selected.add(cid)

        context.user_data["selected"] = selected
        await vpn_panel(update, context)
        return

    # 🚀 SEND
    if data == "send":
        vpn = context.user_data.get("vpn")
        desc = context.user_data.get("desc")

        ok, fail = 0, 0

        for cid in selected:
            try:
                await context.bot.send_message(
                    chat_id=cid,
                    text=f"{vpn}\n\n{desc}"
                )
                ok += 1
            except:
                fail += 1

        await q.message.edit_text(f"Done!\nOK: {ok}\nFAIL: {fail}")
        context.user_data.clear()

    # ✅ ALL
    if data == "all":
        all_channels = list(channels.find({}))
        all_ids = {str(c["channel_id"]) for c in all_channels}

        if selected == all_ids:
            context.user_data["selected"] = set()
        else:
            context.user_data["selected"] = all_ids

        await vpn_panel(update, context)

# ======================
# 🤖 RUN BOT
# ======================
def run():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callback))

    print("Bot running...")
    app.run_polling()

# ======================
# 🚀 MAIN
# ======================
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=lambda: app_flask.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))), daemon=True).start()
    run()
