import os
import time
import asyncio
import threading
import requests
from datetime import datetime
from flask import Flask
from pymongo import MongoClient
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ======================
# 🌐 FLASK (ALIVE SERVER)
# ======================
app_flask = Flask(__name__)
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
# 🔐 CONFIG
# ======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "7846603711:AAHvjcqfwEe7VG2EVnD1krqQsa6v8D6Zy3Y")
KURUCU_ID = int(os.getenv("KURUCU_ID", "7523674506"))
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://mergenowlyagulyyew41_db_user:ZvZhOKOAF6ZMRbHX@cluster1.l8z8gll.mongodb.net/?appName=Cluster1")

mongo = MongoClient(MONGO_URI)
db = mongo["vpn_bot"]
admins = db["admins"]
channels = db["channels"]
settings = db["settings"]  # Iň soňky paýlaşyk wagtyny saklamak üçin

# ======================
# 👮 ADMIN CHECK & COUNTER
# ======================
def is_admin(user_id):
    if user_id == KURUCU_ID:
        return True
    return admins.find_one({"user_id": int(user_id)}) is not None

def increment_admin_counter(user_id):
    if user_id == KURUCU_ID:
        admins.update_one(
            {"user_id": KURUCU_ID},
            {"$inc": {"sent_count": 1}, "$set": {"is_kurucu": True}},
            upsert=True
        )
    else:
        admins.update_one(
            {"user_id": int(user_id)},
            {"$inc": {"sent_count": 1}},
            upsert=True
        )

# ======================
# ⏳ WAGT HASAPLAMAK (HUMAN READABLE)
# ======================
def get_last_share_text():
    data = settings.find_one({"key": "last_share"})
    if not data:
        return "ℹ️ Entek hiç hili VPN paýlaşylmady."
    
    sender = data.get("sender_id")
    share_time_ts = data.get("timestamp")
    
    diff_seconds = int(time.time() - share_time_ts)
    
    if diff_seconds < 60:
        wagt_text = "ýaňyja"
    elif diff_seconds < 3600:
        wagt_text = f"{diff_seconds // 60} minut öň"
    elif diff_seconds < 86400:
        wagt_text = f"{diff_seconds // 3600} sagat öň"
    else:
        wagt_text = f"{diff_seconds // 86400} gün öň"
        
    return f"👤 **Iň soňky paýlaşan:** `{sender}`\n⏱️ **Wagty:** {wagt_text}"

# ======================
# 🚀 START PANEL
# ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text("⛔ Size rugsat berilmedi!")
        return

    keyboard = [
        [InlineKeyboardButton("🔗 VPN Paýlaş", callback_data="vpn")],
        [InlineKeyboardButton("➕ Kanal Goş", callback_data="add")],
        [InlineKeyboardButton("🗑️ Kanallary Dolandyr", callback_data="manage_channels")],
        [InlineKeyboardButton("👮 Adminleri Dolandyr", callback_data="manage_admins")],
        [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
    ]

    last_share_info = get_last_share_text()

    await update.message.reply_text(
        f"🤖 **VPN BOT PANELI**\n\n{last_share_info}\n\nLütfen amaly saýlaň:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
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

    # ➕ KANAL GOŞMAK (Düzedildi!)
    if state == "ADD":
        try:
            cid, link = text.split("|")
            channel_id_str = cid.strip()
            
            # MongoDB-de her kanaly aýratyn ID bilen goşýarys, şonda biri-biriniň üstüne ýazmaz!
            channels.update_one(
                {"channel_id": channel_id_str},
                {"$set": {"_id": channel_id_str, "link": link.strip()}},
                upsert=True
            )
            await update.message.reply_text("✅ Kanal üstünlikli goşuldy!")
            context.user_data.clear()
        except Exception:
            await update.message.reply_text("❌ Format ýalňyş! Format: `Kanal_ID | link`", parse_mode="Markdown")

    # 👮 ADMIN GOŞMAK
    elif state == "ADD_ADMIN":
        text_clean = text.strip()
        if not text_clean.isdigit():
            await update.message.reply_text("❌ Ýalňyş ID! Diňe san ugradyň:")
            return
        
        target_id = int(text_clean)
        admins.update_one(
            {"user_id": target_id},
            {"$setOnInsert": {"sent_count": 0}},
            upsert=True
        )
        await update.message.reply_text(f"✅ ID: `{target_id}` bolan admin üstünlikli goşuldy!", parse_mode="Markdown")
        context.user_data.clear()

    # 🔗 VPN LINK PROCESS
    elif state == "VPN":
        context.user_data["vpn"] = text
        context.user_data["state"] = "DESC"
        await update.message.reply_text("📝 Indi bolsa düşündirişini (Description) ugradyň:")

    # 📝 DESC VE AUTOMATIC SEND
    elif state == "DESC":
        context.user_data["desc"] = text
        # Arka planda async ugratmak (Bökmezligi üçin asyncio task ulanýarys)
        asyncio.create_task(awto_goyber_prosesi(update, context, uid))

# ======================
# 🚀 BACKGROUND AUTOMATIC SEND & REPORT
# ======================
async def awto_goyber_prosesi(update: Update, context: ContextTypes.DEFAULT_TYPE, sender_id: int):
    vpn = context.user_data.get("vpn")
    desc = context.user_data.get("desc")
    context.user_data.clear() # Sessiýany arassalaýarys
    
    status_msg = await update.message.reply_text("⏳ VPN ähli kanallara ugradylýar, garaşyň...")

    all_channels = list(channels.find({}))
    if not all_channels:
        await status_msg.edit_text("❌ Binada hiç hili kanal tapymaldy!")
        return

    # Iň soňky paýlaşan adamy we wagty ýazýarys
    settings.update_one(
        {"key": "last_share"},
        {"$set": {"sender_id": sender_id, "timestamp": time.time()}},
        upsert=True
    )

    ok_channels = []
    fail_channels = []

    for c in all_channels:
        cid = c["channel_id"]
        clink = c.get("link", f"ID: {cid}")
        try:
            chat_target = int(cid) if cid.strip().replace('-', '').isdigit() else cid.strip()
            await context.bot.send_message(
                chat_id=chat_target,
                text=f"{vpn}\n\n{desc}"
            )
            ok_channels.append(f"🟢 {clink}")
        except Exception:
            fail_channels.append(f"🔴 {clink}")

    increment_admin_counter(sender_id)

    # Hasabaty ekrana anyk çykarýas
    report = "📊 **GÖYBERLEN KANALLARYŇ NETIJESI:**\n\n"
    if ok_channels:
        report += "✅ **Şowluy ugradylan kanallar:**\n" + "\n".join(ok_channels) + "\n\n"
    else:
        report += "✅ **Şowluy ugradylan kanallar:** Ýok.\n\n"
        
    if fail_channels:
        report += "❌ **Göyberip bilinmedik kanallar (Bot admin däl):**\n" + "\n".join(fail_channels)
    else:
        report += "❌ **Göyberip bilinmedik kanallar:** Ýok, hemmesine üstünlikli gitdi."

    await status_msg.edit_text(report, parse_mode="Markdown")

# ======================
# 🗑️ KANAL POZMAK PANELI
# ======================
async def kanal_pozmak_paneli(message, is_callback=False):
    all_channels = list(channels.find({}))
    keyboard = []

    if not all_channels:
        text = "📭 Binada hiç hili kanal ýok."
    else:
        text = "🗑️ **Pozmak isleýän kanalyňyzyň ýanyndaky ❌ düwmesine basyň:**"
        for c in all_channels:
            cid = str(c["channel_id"])
            clink = c.get("link", f"ID: {cid}")
            keyboard.append([
                InlineKeyboardButton(f"{clink}", callback_data="none"),
                InlineKeyboardButton("❌ Poz", callback_data=f"del_{cid}")
            ])
            
    keyboard.append([InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")])

    if is_callback:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ======================
# 👮 ADMIN DOLANDYRMAK PANELI
# ======================
async def admin_dolandyr_paneli(message, is_callback=False):
    all_admins = list(admins.find({"is_kurucu": {"$ne": True}}))
    keyboard = [
        [InlineKeyboardButton("➕ Täze Admin Goş (Diňe ID)", callback_data="add_admin_btn")]
    ]
    
    text = f"👮 **Adminleri Dolandyryş Paneli:**\n\n👑 **Esasy Kurucu:** `{KURUCU_ID}` (Goragly)\n\n"
    
    if all_admins:
        text += "Aşakdaky adminleri öçürmek üçin ❌ düwmesine basyň:\n"
        for a in all_admins:
            aid = str(a["user_id"])
            keyboard.append([
                InlineKeyboardButton(f"👤 ID: {aid}", callback_data="none"),
                InlineKeyboardButton("❌ Poz", callback_data=f"del_adm_{aid}")
            ])
    else:
        text += "ℹ️ Goşmaça admin ýok."

    keyboard.append([InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")])

    if is_callback:
        await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ======================
# 📊 STATISTIKA PANELI
# ======================
async def statistika_paneli(message):
    total_channels = channels.count_documents({})
    total_admins = admins.count_documents({"is_kurucu": {"$ne": True}})
    
    kurucu_data = admins.find_one({"user_id": KURUCU_ID})
    kurucu_count = kurucu_data.get("sent_count", 0) if kurucu_data else 0

    text = "📊 **BOTUŇ UMUMY STATISTIKASY**\n\n"
    text += f"📢 **Jemi Goşulan Kanallar:** `{total_channels}` sany\n"
    text += f"👮 **Jemi Goşmaça Adminler:** `{total_admins}` sany\n"
    text += "----------------------------------------\n"
    text += "📈 **Adminleriň VPN Paýlaşyş Sanawy:**\n\n"
    text += f"👑 Kurucu (`{KURUCU_ID}`): **{kurucu_count} gezek** ugratdy.\n"

    all_registered = admins.find({"is_kurucu": {"$ne": True}})
    for adm in all_registered:
        aid = adm["user_id"]
        count = adm.get("sent_count", 0)
        text += f"👤 Admin (`{aid}`): **{count} gezek** ugratdy.\n"

    keyboard = [[InlineKeyboardButton("⬅️ Baş Menýu", callback_data="back_main")]]
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ======================
# 🔘 CALLBACK HANDLER
# ======================
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id
    if not is_admin(uid):
        return

    data = q.data

    if data == "add":
        context.user_data["state"] = "ADD"
        await q.message.reply_text("Kanal maglumatyny ugradyň:\nFormat: `Kanal_ID | Kanal_Linki`", parse_mode="Markdown")
        return

    if data == "vpn":
        context.user_data["state"] = "VPN"
        await q.message.reply_text("🔗 Göni VPN linkini ugradyň:")
        return

    if data == "manage_channels":
        await kanal_pozmak_paneli(q.message, is_callback=True)
        return

    if data.startswith("del_") and not data.startswith("del_adm_"):
        target_cid = data.replace("del_", "")
        channels.delete_one({"channel_id": target_cid})
        await kanal_pozmak_paneli(q.message, is_callback=True)
        return

    if data == "manage_admins":
        await admin_dolandyr_paneli(q.message, is_callback=True)
        return

    if data == "add_admin_btn":
        context.user_data["state"] = "ADD_ADMIN"
        await q.message.reply_text("Täze adminiň diňe **Telegram ID**-sini ugradyň:", parse_mode="Markdown")
        return

    if data.startswith("del_adm_"):
        target_aid = int(data.replace("del_adm_", ""))
        admins.delete_one({"user_id": target_aid})
        await admin_dolandyr_paneli(q.message, is_callback=True)
        return

    if data == "stats":
        await statistika_paneli(q.message)
        return

    if data == "back_main":
        keyboard = [
            [InlineKeyboardButton("🔗 VPN Paýlaş", callback_data="vpn")],
            [InlineKeyboardButton("➕ Kanal Goş", callback_data="add")],
            [InlineKeyboardButton("🗑️ Kanallary Dolandyr", callback_data="manage_channels")],
            [InlineKeyboardButton("👮 Adminleri Dolandyr", callback_data="manage_admins")],
            [InlineKeyboardButton("📊 Statistika", callback_data="stats")]
        ]
        last_share_info = get_last_share_text()
        await q.message.edit_text(
            f"🤖 **VPN BOT PANELI**\n\n{last_share_info}\n\nLütfen amaly saýlaň:", 
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return

# ======================
# 🤖 RUN BOT
# ======================
def run():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callback))
    print("Bot işläp dur...")
    app.run_polling()

if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    threading.Thread(target=lambda: app_flask.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000))), daemon=True).start()
    run()
    
